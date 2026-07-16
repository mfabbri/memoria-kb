from __future__ import annotations

import html
import http.cookiejar
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

from ..http_utils import NoRedirectHandler, extract_hidden_inputs, fetch_text_with_opener, post_form_with_opener
from ..models import Caduto, SearchHit, Source, SourceResult


ITALIAN_TO_ENGLISH_PHRASES = {
    "u.r.s.s.": "soviet union",
    "urss": "soviet union",
    "partigiano sovietico": "soviet partisan",
    "partigiana sovietica": "soviet partisan",
    "partigiano austriaco": "austrian partisan",
    "partigiano straniero": "foreign partisan",
    "partigiano cecoslovacco": "czechoslovak partisan",
    "ufficiale medico": "medical officer",
    "servizio sanitario": "medical service",
    "infermiere partigiano": "partisan nurse",
    "infermiera partigiana": "partisan nurse",
    "ufficiale dei bersaglieri": "bersaglieri officer",
    "capo di stato maggiore": "chief of staff",
    "vice commissario politico": "political commissar",
    "comandante di compagnia": "company commander",
    "caposquadra": "squad leader",
    "ispettore di compagnia": "company inspector",
    "medico laureato": "doctor",
    "disertore": "deserter",
    "passato ai partigiani": "joined partisans",
    "brigata garibaldi": "garibaldi brigade",
    "36a brigata": "36th brigade",
    "bianconcini": "bianconcini",
    "austria": "austria",
    "cecoslovacchia": "czechoslovakia",
    "bologna": "bologna",
    "imola": "imola",
    "bracciante": "farm labourer",
    "contadino": "farmer",
    "operaio": "worker",
    "carabiniere": "carabinieri",
    "studente in medicina": "medical student",
}

TNA_STOPWORDS = {
    "della",
    "delle",
    "degli",
    "dei",
    "del",
    "di",
    "a",
    "da",
    "in",
    "con",
    "per",
    "su",
    "the",
    "and",
    "or",
    "non",
    "reperito",
    "secondo",
    "memoria",
    "locale",
    "fonti",
    "battaglia",
}


def _clean_name_token(token: str) -> str:
    token = _normalize_text(token)
    token = re.sub(r"[^a-z0-9]+", " ", token)
    return " ".join(token.split())


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return normalized.lower()


def _translate_italian_context(*values: str) -> str:
    text = " ".join(value for value in values if value).strip()
    lowered = _normalize_text(text)
    for italian, english in sorted(ITALIAN_TO_ENGLISH_PHRASES.items(), key=lambda item: len(item[0]), reverse=True):
        lowered = lowered.replace(italian, english)
    lowered = re.sub(r"[^a-z0-9\s-]+", " ", lowered)
    return " ".join(lowered.split())


def _extract_years(*values: str) -> list[int]:
    years: set[int] = set()
    for value in values:
        for match in re.findall(r"\b(19[0-9]{2}|20[0-9]{2}|18[0-9]{2})\b", value or ""):
            years.add(int(match))
    return sorted(years)


def _extract_name_parts(name: str) -> list[str]:
    parts: list[str] = []
    for raw_part in re.split(r"\s+", name.strip()):
        cleaned = _clean_name_token(raw_part)
        if not cleaned:
            continue
        if cleaned in {"il", "lo", "la", "memo"}:
            continue
        if cleaned not in parts:
            parts.append(cleaned)
    return parts


def _build_context_keywords(caduto: Caduto) -> list[str]:
    translated_context = _translate_italian_context(
        caduto.origine_sulla_lapide,
        caduto.ruolo_affiliazione,
        caduto.profilo_biografico,
        caduto.episodio_documentato,
    )
    candidate_keywords: list[str] = []
    for token in translated_context.split():
        if token in TNA_STOPWORDS or len(token) < 3:
            continue
        if token not in candidate_keywords:
            candidate_keywords.append(token)
    return candidate_keywords


def _build_tna_search_attempts(source: Source, caduto: Caduto) -> list[dict[str, object]]:
    candidate_keywords = _build_context_keywords(caduto)
    name_parts = _extract_name_parts(caduto.nome)
    full_name = caduto.nome.strip() or " ".join(part.capitalize() for part in name_parts)
    normalized_original_name = " ".join(part.capitalize() for part in name_parts) if name_parts else full_name
    years = _extract_years(caduto.nascita, caduto.morte, caduto.profilo_biografico, caduto.episodio_documentato)
    from_year = ""
    to_year = ""
    if years:
        preferred_years = [year for year in years if 1939 <= year <= 1947]
        if preferred_years:
            from_year = str(min(preferred_years))
            to_year = str(max(preferred_years))
        else:
            from_year = str(min(years))
            to_year = str(max(years))

    reference_code = source.auth.get("reference_code", "").strip()
    attempt_specs: list[dict[str, object]] = []

    def add_attempt(
        label: str,
        *,
        exact_phrase: str = "",
        all_words: str = "",
        any_words: list[str] | None = None,
        without_words: list[str] | None = None,
    ) -> None:
        any_words = any_words or []
        without_words = without_words or []
        query_description_parts = [label, f'ref="{reference_code}"']
        if exact_phrase:
            query_description_parts.append(f'exact="{exact_phrase}"')
        if all_words:
            query_description_parts.append(f'all_words="{all_words}"')
        if any_words:
            query_description_parts.append(f'any_words="{", ".join(any_words)}"')
        if without_words:
            query_description_parts.append(f'without="{", ".join(without_words)}"')
        if from_year or to_year:
            query_description_parts.append(f"years={from_year or '?'}-{to_year or '?'}")
        attempt_specs.append(
            {
                "label": label,
                "exact_phrase": exact_phrase,
                "all_words": all_words,
                "any_words": any_words[:3],
                "without_words": without_words[:3],
                "from_year": from_year,
                "to_year": to_year,
                "reference_code": reference_code,
                "query_description": "; ".join(query_description_parts),
            }
        )

    context_primary = candidate_keywords[:2]
    context_secondary = candidate_keywords[2:5]
    broad_context = candidate_keywords[:3]

    if len(name_parts) >= 2:
        reversed_name = " ".join(part.capitalize() for part in reversed(name_parts))
        original_all_words = " ".join(name_parts[:2])
        reversed_all_words = " ".join(reversed(name_parts[:2]))
        add_attempt(
            "exact-original-context",
            exact_phrase=full_name,
            all_words=" ".join(context_primary),
            any_words=context_secondary,
        )
        add_attempt(
            "exact-original-years",
            exact_phrase=full_name,
        )
        add_attempt(
            "all-words-original-context",
            all_words=original_all_words,
            any_words=broad_context,
        )
        add_attempt(
            "all-words-reversed-context",
            all_words=reversed_all_words,
            any_words=broad_context,
        )
        if reversed_name != normalized_original_name and reversed_name != full_name:
            add_attempt(
                "exact-reversed-context",
                exact_phrase=reversed_name,
                all_words=" ".join(context_primary),
                any_words=context_secondary,
            )
            add_attempt(
                "exact-reversed-years",
                exact_phrase=reversed_name,
            )
        for pivot_index, pivot_label in ((0, "first-token"), (-1, "last-token")):
            pivot = name_parts[pivot_index].capitalize()
            companions = [part for index, part in enumerate(name_parts) if index != (pivot_index % len(name_parts))]
            add_attempt(
                f"{pivot_label}-exact-context",
                exact_phrase=pivot,
                all_words=" ".join(companions[:2]),
                any_words=broad_context,
            )
    else:
        mononym = full_name or caduto.nome.strip()
        add_attempt(
            "mononym-context",
            exact_phrase=mononym,
            all_words=" ".join(context_primary),
            any_words=context_secondary,
        )
        add_attempt(
            "mononym-broad",
            all_words=mononym,
            any_words=broad_context,
        )

    if candidate_keywords:
        add_attempt(
            "name-broad-context",
            all_words=full_name,
            any_words=broad_context,
        )

    deduped_attempts: list[dict[str, object]] = []
    seen_signatures: set[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = set()
    for attempt in attempt_specs:
        signature = (
            str(attempt["exact_phrase"]),
            str(attempt["all_words"]),
            tuple(attempt["any_words"]),
            tuple(attempt["without_words"]),
        )
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        deduped_attempts.append(attempt)
    return deduped_attempts


def _execute_tna_advanced_search(page, advanced_search_url: str, search_plan: dict[str, object]) -> tuple[str, str]:
    page.goto(advanced_search_url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_load_state("networkidle", timeout=60000)
    page.fill('input[name="_ep"]', "")
    page.fill('input[name="_aq"]', "")
    for field_name in ("_or1", "_or2", "_or3", "_nq1", "_nq2", "_nq3", "_sd", "_ed"):
        page.fill(f'input[name="{field_name}"]', "")

    if search_plan["exact_phrase"]:
        page.fill('input[name="_ep"]', str(search_plan["exact_phrase"]))
    if search_plan["all_words"]:
        page.fill('input[name="_aq"]', str(search_plan["all_words"]))

    any_words = list(search_plan["any_words"])
    for index, value in enumerate(any_words[:3], start=1):
        page.fill(f'input[name="_or{index}"]', value)

    without_words = list(search_plan["without_words"])
    for index, value in enumerate(without_words[:3], start=1):
        page.fill(f'input[name="_nq{index}"]', value)

    reference_inputs = page.locator('input[name="_cr"]')
    reference_inputs.nth(0).fill(str(search_plan["reference_code"]))
    if search_plan["from_year"] and search_plan["to_year"]:
        page.check("#search-date-range")
        page.fill('input[name="_sd"]', str(search_plan["from_year"]))
        page.fill('input[name="_ed"]', str(search_plan["to_year"]))
    page.check("#search-tna-as-repository")
    page.get_by_role("button", name="Search").first.click()
    page.wait_for_load_state("networkidle", timeout=60000)
    return page.url, page.locator("#page_wrap").inner_text()


def _login_tna_via_playwright(source: Source) -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "Playwright non installato nell'ambiente Python corrente."

    email = source.credentials.get("email", "").strip()
    password = source.credentials.get("password", "").strip()
    login_page_url = source.auth.get("login_page_url", "https://discovery.nationalarchives.gov.uk/sign-in").strip()
    success_url = source.auth.get("success_url", "https://discovery.nationalarchives.gov.uk/Home").strip()
    username_field = source.auth.get("username_field", "UserName").strip()
    password_field = source.auth.get("password_field", "Password").strip()
    signed_in_marker = source.auth.get("signed_in_marker", "Sign out").strip()
    post_login_link_text = source.auth.get("post_login_link_text", "").strip()
    post_login_expected_url = source.auth.get("post_login_expected_url", "").strip()
    browser_channel = source.auth.get("browser_channel", "").strip() or None
    browser_user_agent = source.auth.get(
        "browser_user_agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    ).strip()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            channel=browser_channel,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=browser_user_agent,
            locale="en-GB",
            viewport={"width": 1366, "height": 900},
        )
        page = context.new_page()
        try:
            page.goto(login_page_url, wait_until="domcontentloaded", timeout=source.timeout * 1000)
            if "restricted" in page.title().lower():
                current_url = page.url
                context.close()
                browser.close()
                return False, f"Playwright bloccato da TNA con pagina `{page.title()}` su {current_url}."
            page.locator(f'input[name="{username_field}"]').fill(email)
            page.locator(f'input[name="{password_field}"]').fill(password)
            page.get_by_role("button", name="Sign in").click()
            page.wait_for_load_state("networkidle", timeout=source.timeout * 1000)
            current_url = page.url
            page_text = page.content()
            login_confirmed = current_url.startswith(success_url) or (
                signed_in_marker and signed_in_marker.lower() in page_text.lower()
            )
            if login_confirmed and post_login_link_text:
                page.get_by_role("link", name=post_login_link_text, exact=True).click()
                page.wait_for_load_state("networkidle", timeout=source.timeout * 1000)
                current_url = page.url
                if post_login_expected_url and post_login_expected_url in current_url:
                    context.close()
                    browser.close()
                    return True, f"Login riuscito e navigazione TNA completata via Playwright. URL finale: {current_url}"
                context.close()
                browser.close()
                return False, f"Login riuscito ma navigazione post-login TNA non confermata. URL finale: {current_url}"
            if login_confirmed:
                context.close()
                browser.close()
                return True, f"Login riuscito su TNA Discovery via Playwright. URL finale: {current_url}"
            if "/redirection/notfound" in current_url:
                context.close()
                browser.close()
                return False, f"Login TNA respinto con redirect a `{current_url}`."
            if "restricted" in page.title().lower():
                context.close()
                browser.close()
                return False, f"Playwright bloccato da TNA con pagina `{page.title()}` su {current_url}."
            context.close()
            browser.close()
            return False, f"Login TNA non confermato via Playwright. URL finale: {current_url}"
        except Exception as exc:  # noqa: BLE001
            context.close()
            browser.close()
            return False, f"Errore Playwright durante il login TNA: {type(exc).__name__}: {exc}"


def _login_tna_via_urllib(source: Source) -> tuple[bool, str]:
    email = source.credentials.get("email", "").strip()
    password = source.credentials.get("password", "").strip()
    if not email or not password:
        missing = [key for key in ("email", "password") if not source.credentials.get(key, "").strip()]
        return False, f"Credenziali mancanti nel file YAML: {', '.join(missing)}."

    login_page_url = source.auth.get("login_page_url", "https://secure.nationalarchives.gov.uk/Login/sign-in?wa=wsignin1.0").strip()
    success_url = source.auth.get("success_url", "https://secure.nationalarchives.gov.uk/Login/youraccount").strip()
    signed_in_marker = source.auth.get("signed_in_marker", "Sign out").strip()
    failure_marker = source.auth.get("failure_marker", 'data-valmsg-for="wrong_pwd"').strip()
    username_field = source.auth.get("username_field", "UserName").strip()
    password_field = source.auth.get("password_field", "Password").strip()

    try:
        cookie_jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

        login_page_html = fetch_text_with_opener(opener, login_page_url, timeout=source.timeout)
        form_action_match = re.search(r'<form action="([^"]+)" method="post">', login_page_html, flags=re.I)
        if not form_action_match:
            return False, "Form di login TNA non trovato nella pagina di accesso."

        post_url = urllib.parse.urljoin(login_page_url, html.unescape(form_action_match.group(1)))
        form_data = extract_hidden_inputs(login_page_html)
        form_data[username_field] = email
        form_data[password_field] = password
        form_data.setdefault("PostBack", "True")

        post_opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cookie_jar),
            NoRedirectHandler(),
        )
        final_url, post_response_html = post_form_with_opener(post_opener, post_url, form_data, timeout=source.timeout)
        success_page_html = fetch_text_with_opener(opener, success_url, timeout=source.timeout)

        if signed_in_marker and signed_in_marker in success_page_html:
            return True, f"Login riuscito su TNA Discovery. URL finale: {final_url}"

        if failure_marker and failure_marker in post_response_html and "wrong username or password" in post_response_html.lower():
            return False, "Login fallito su TNA Discovery: username o password non validi."

        if "sign out" in success_page_html.lower() or "signed-in" in success_page_html.lower():
            return True, f"Login riuscito su TNA Discovery. URL finale: {final_url}"

        return False, f"Login TNA non confermato. URL finale: {final_url}"
    except urllib.error.HTTPError as exc:
        location = exc.headers.get("Location", "")
        if location:
            return False, f"Login TNA respinto con redirect a `{location}` (HTTP {exc.code})."
        return False, f"Errore HTTP durante il login TNA: {exc.code}."
    except Exception as exc:  # noqa: BLE001
        return False, f"Errore tecnico durante il login TNA: {type(exc).__name__}: {exc}"


def login_tna_discovery(source: Source) -> tuple[bool, str]:
    engine = source.auth.get("engine", "playwright").strip().lower()
    if engine == "playwright":
        authenticated, note = _login_tna_via_playwright(source)
        if authenticated:
            return authenticated, note
        if "Playwright non installato" not in note:
            return authenticated, note
    return _login_tna_via_urllib(source)


def run_tna_advanced_search(source: Source, caduto: Caduto) -> SourceResult:
    search_attempts = _build_tna_search_attempts(source, caduto)
    query = " | ".join(str(search_plan["query_description"]) for search_plan in search_attempts)
    search_url = source.search_url_builder(caduto.nome)

    missing = [key for key, value in source.credentials.items() if not str(value).strip()]
    if missing:
        return SourceResult(
            source_id=source.source_id,
            source_name=source.source_name,
            status="needs_credentials",
            note=f"{source.note} Credenziali mancanti nel file YAML: {', '.join(missing)}.",
            query=query,
            search_url=search_url,
        )

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return SourceResult(
            source_id=source.source_id,
            source_name=source.source_name,
            status="error",
            note=f"{source.note} Playwright non installato nell'ambiente Python corrente.",
            query=query,
            search_url=search_url,
        )

    email = source.credentials.get("email", "").strip()
    password = source.credentials.get("password", "").strip()
    login_page_url = source.auth.get("login_page_url", "https://secure.nationalarchives.gov.uk/Login/sign-in?wa=wsignin1.0").strip()
    success_url = source.auth.get("success_url", "https://secure.nationalarchives.gov.uk/Login/youraccount").strip()
    username_field = source.auth.get("username_field", "UserName").strip()
    password_field = source.auth.get("password_field", "Password").strip()
    signed_in_marker = source.auth.get("signed_in_marker", "Sign out").strip()
    post_login_link_text = source.auth.get("post_login_link_text", "").strip()
    post_login_expected_url = source.auth.get("post_login_expected_url", "").strip()
    advanced_search_url = source.auth.get("advanced_search_url", "https://discovery.nationalarchives.gov.uk/advanced-search").strip()
    reference_code = str(search_attempts[0]["reference_code"]) if search_attempts else ""
    browser_channel = source.auth.get("browser_channel", "").strip() or None
    browser_user_agent = source.auth.get(
        "browser_user_agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    ).strip()

    if not reference_code:
        return SourceResult(
            source_id=source.source_id,
            source_name=source.source_name,
            status="error",
            note=f"{source.note} `reference_code` mancante nella configurazione auth della fonte.",
            query=query,
            search_url=search_url,
        )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            channel=browser_channel,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=browser_user_agent,
            locale="en-GB",
            viewport={"width": 1440, "height": 1200},
        )
        page = context.new_page()
        try:
            page.goto(login_page_url, wait_until="domcontentloaded", timeout=60000)
            page.locator(f'input[name="{username_field}"]').fill(email)
            page.locator(f'input[name="{password_field}"]').fill(password)
            page.get_by_role("button", name="Sign in").click()
            page.wait_for_load_state("networkidle", timeout=60000)

            current_url = page.url
            page_text = page.content()
            login_confirmed = current_url.startswith(success_url) or (
                signed_in_marker and signed_in_marker.lower() in page_text.lower()
            )
            if not login_confirmed:
                context.close()
                browser.close()
                return SourceResult(
                    source_id=source.source_id,
                    source_name=source.source_name,
                    status="error",
                    note=f"{source.note} Login TNA non confermato via Playwright. URL finale: {current_url}",
                    query=query,
                    search_url=search_url,
                )

            if post_login_link_text:
                page.get_by_role("link", name=post_login_link_text, exact=True).click()
                page.wait_for_load_state("networkidle", timeout=60000)
                current_url = page.url
                if post_login_expected_url and post_login_expected_url not in current_url:
                    context.close()
                    browser.close()
                    return SourceResult(
                        source_id=source.source_id,
                        source_name=source.source_name,
                        status="error",
                        note=f"{source.note} Login riuscito ma navigazione post-login TNA non confermata. URL finale: {current_url}",
                        query=query,
                        search_url=search_url,
                    )

            attempts_summary: list[str] = []
            last_results_url = search_url
            for search_plan in search_attempts:
                results_url, results_text = _execute_tna_advanced_search(page, advanced_search_url, search_plan)
                last_results_url = results_url
                attempts_summary.append(str(search_plan["query_description"]))
                if "We did not find any results for your search" in results_text:
                    continue

                hits: list[SearchHit] = []
                seen_urls: set[str] = set()
                result_links = page.locator('a[href*="/details/r/"]')
                for index in range(min(result_links.count(), 5)):
                    link = result_links.nth(index)
                    title = link.inner_text().strip()
                    href = link.get_attribute("href") or ""
                    absolute_url = urllib.parse.urljoin(results_url, href)
                    if not title or absolute_url in seen_urls:
                        continue
                    seen_urls.add(absolute_url)
                    snippet = ""
                    parent_text = link.locator("xpath=ancestor::li[1]").inner_text()
                    if parent_text:
                        snippet = " ".join(parent_text.split())
                    hits.append(SearchHit(title=title, url=absolute_url, snippet=snippet[:280]))

                if hits:
                    context.close()
                    browser.close()
                    return SourceResult(
                        source_id=source.source_id,
                        source_name=source.source_name,
                        status="ok",
                        note=(
                            f"{source.note} Advanced search TNA eseguita nel catalogo autenticato con riferimento "
                            f"{reference_code}. Query riuscita: {search_plan['query_description']}."
                        ),
                        query=" | ".join(attempts_summary),
                        search_url=results_url,
                        hits=hits,
                    )

            context.close()
            browser.close()
            return SourceResult(
                source_id=source.source_id,
                source_name=source.source_name,
                status="no_results",
                note=(
                    f"{source.note} Advanced search TNA completata senza risultati utili per il riferimento "
                    f"{reference_code}. Tentativi: {' | '.join(attempts_summary)}."
                ),
                query=query,
                search_url=last_results_url,
            )
        except Exception as exc:  # noqa: BLE001
            context.close()
            browser.close()
            return SourceResult(
                source_id=source.source_id,
                source_name=source.source_name,
                status="error",
                note=f"{source.note} Errore Playwright durante la advanced search TNA: {type(exc).__name__}: {exc}",
                query=query,
                search_url=search_url,
            )
