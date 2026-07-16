from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from .profile_html_forms import profile_search_form_html
from .source_profiles import SourceSearchProfile, write_source_search_profile


def build_profile_from_html(
    *,
    source_id: str,
    engine: str,
    html: str,
    discovery: dict[str, str] | None = None,
) -> SourceSearchProfile:
    return profile_search_form_html(
        html=html,
        source_id=source_id,
        engine=engine,
        discovery=discovery or {},
    )


def profile_source_form_from_html_file(
    *,
    source_id: str,
    engine: str,
    html_path: Path | str,
    output_path: Path | str,
    save_html_path: Path | str | None = None,
) -> SourceSearchProfile:
    source_path = Path(html_path)
    html = source_path.read_text(encoding="utf-8")
    if save_html_path is not None:
        _write_html_snapshot(save_html_path, html)
    profile = build_profile_from_html(
        source_id=source_id,
        engine=engine,
        html=html,
        discovery={
            "method": "html_file",
            "path": str(source_path),
            "profiled_at": _utc_now_iso(),
        },
    )
    write_source_search_profile(output_path, profile)
    return profile


def profile_source_form_from_url(
    *,
    source_id: str,
    engine: str,
    url: str,
    output_path: Path | str,
    use_playwright: bool,
    wait_selector: str = "",
    timeout_seconds: float = 30.0,
    save_html_path: Path | str | None = None,
) -> SourceSearchProfile:
    if not use_playwright:
        raise ValueError("La profilazione da URL richiede --use-playwright.")

    html = _read_page_html_with_playwright(
        url=url,
        wait_selector=wait_selector,
        timeout_seconds=timeout_seconds,
    )
    if save_html_path is not None:
        _write_html_snapshot(save_html_path, html)
    profile = build_profile_from_html(
        source_id=source_id,
        engine=engine,
        html=html,
        discovery={
            "method": "playwright",
            "url": url,
            "wait_selector": wait_selector,
            "profiled_at": _utc_now_iso(),
        },
    )
    write_source_search_profile(output_path, profile)
    return profile


def format_profile_summary(*, output_path: Path | str, profile: SourceSearchProfile) -> str:
    lines = [
        f"Profilo fonte scritto in {output_path}",
        f"Fonte: {profile.source_id}",
        f"Campi trovati: {len(profile.fields)}",
    ]
    for field in profile.fields:
        suffix = f" opzioni={len(field.options)}" if field.options else ""
        lines.append(f"- {field.field_id} [{field.field_type}]{suffix}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.html:
            profile = profile_source_form_from_html_file(
                source_id=args.source,
                engine=args.engine,
                html_path=args.html,
                output_path=args.output,
                save_html_path=args.save_html,
            )
        else:
            profile = profile_source_form_from_url(
                source_id=args.source,
                engine=args.engine,
                url=args.url,
                output_path=args.output,
                use_playwright=args.use_playwright,
                wait_selector=args.wait_selector or "",
                timeout_seconds=args.timeout,
                save_html_path=args.save_html,
            )
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(status=2, message=f"Errore: {exc}\n")

    print(format_profile_summary(output_path=args.output, profile=profile))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Genera un SourceSearchProfile YAML da una fixture HTML o da una singola pagina Playwright.",
    )
    parser.add_argument("--source", required=True, help="Identificativo fonte, per esempio cwgc.")
    parser.add_argument("--engine", required=True, help="Identificativo motore o form profilato.")
    parser.add_argument("--output", required=True, help="Percorso YAML da scrivere.")
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--html", help="Percorso a una fixture HTML locale.")
    input_group.add_argument("--url", help="URL della pagina da profilare con Playwright.")
    parser.add_argument(
        "--use-playwright",
        action="store_true",
        help="Abilita la profilazione live della singola pagina indicata da --url.",
    )
    parser.add_argument(
        "--wait-selector",
        default="",
        help="Se indicato, attende questo selettore prima di leggere l'HTML.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Timeout Playwright in secondi.",
    )
    parser.add_argument(
        "--save-html",
        default=None,
        help="Percorso opzionale dove salvare l'HTML letto prima della profilazione.",
    )
    return parser


def _read_page_html_with_playwright(*, url: str, wait_selector: str, timeout_seconds: float) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright non e' disponibile. Installa le dipendenze opzionali e i browser prima di usare --use-playwright."
        ) from exc

    timeout_ms = max(timeout_seconds, 0.1) * 1000
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if wait_selector:
                page.wait_for_selector(wait_selector, timeout=timeout_ms)
            return page.content()
        finally:
            browser.close()


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _write_html_snapshot(path: Path | str, html: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
