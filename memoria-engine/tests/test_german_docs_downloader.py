from __future__ import annotations

import json
import re
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.german_docs_downloader import (  # noqa: E402
    download_german_docs_opis_delos,
    download_german_docs_pages,
    write_manifest,
)
from caduti_fonti_report.document_analysis.german_docs_manifest import (  # noqa: E402
    render_german_docs_manifest_markdown,
)


@contextmanager
def workspace_temp_dir():
    base_dir = Path(__file__).resolve().parents[1] / ".tmp-tests"
    base_dir.mkdir(exist_ok=True)
    tmp_dir = base_dir / f"test-{uuid.uuid4().hex}"
    tmp_dir.mkdir()
    try:
        yield tmp_dir
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


class FakeResponse:
    def __init__(self, *, status: int = 200, body: bytes = b"\xff\xd8\xfffake-jpeg\xff\xd9") -> None:
        self.status = status
        self.ok = 200 <= status < 300
        self._body = body

    def body(self) -> bytes:
        return self._body


class FakeRequest:
    def __init__(self, responses: dict[str, bytes] | None = None) -> None:
        self.urls: list[str] = []
        self.responses = responses or {}

    def get(self, url: str, *, timeout: int) -> FakeResponse:
        self.urls.append(url)
        if url in self.responses:
            return FakeResponse(body=self.responses[url])
        return FakeResponse(body=f"image:{url}".encode("utf-8"))


class FakeLocator:
    def __init__(self, *, text: str = "", visible: bool = False) -> None:
        self.first = self
        self.text = text
        self.visible = visible
        self.clicked = False

    def count(self) -> int:
        return 1

    def is_visible(self, *, timeout: int) -> bool:
        return self.visible

    def click(self) -> None:
        self.clicked = True

    def text_content(self, *, timeout: int) -> str:
        return self.text


class FakePage:
    def __init__(self, html: str) -> None:
        self.html = html
        self.goto_calls: list[str] = []
        self.agreement = FakeLocator(visible=True)
        self.heading = FakeLocator(text="Delo 30 sample title")

    def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        self.goto_calls.append(url)

    def wait_for_load_state(self, state: str, *, timeout: int) -> None:
        return None

    def wait_for_timeout(self, timeout: int) -> None:
        return None

    def content(self) -> str:
        return self.html

    def locator(self, selector: str) -> FakeLocator:
        if selector == ".user_agreements__button--yes":
            return self.agreement
        if selector == "h1":
            return self.heading
        return FakeLocator()


class FakeContext:
    def __init__(self, page: FakePage, request: FakeRequest) -> None:
        self.page = page
        self.request = request
        self.closed = False

    def new_page(self) -> FakePage:
        return self.page

    def close(self) -> None:
        self.closed = True


class FakeBrowser:
    def __init__(self, context: FakeContext) -> None:
        self.context = context
        self.closed = False
        self.context_kwargs: dict[str, object] = {}

    def new_context(self, **kwargs) -> FakeContext:
        self.context_kwargs = dict(kwargs)
        return self.context

    def close(self) -> None:
        self.closed = True


class FakeChromium:
    def __init__(self, browser: FakeBrowser) -> None:
        self.browser = browser
        self.launch_kwargs: dict[str, object] = {}

    def launch(self, **kwargs) -> FakeBrowser:
        self.launch_kwargs = dict(kwargs)
        return self.browser


class FakePlaywright:
    def __init__(self, chromium: FakeChromium) -> None:
        self.chromium = chromium


class FakePlaywrightFactory:
    def __init__(self, html: str, responses: dict[str, bytes] | None = None) -> None:
        self.request = FakeRequest(responses=responses)
        self.page = FakePage(html)
        self.context = FakeContext(self.page, self.request)
        self.browser = FakeBrowser(self.context)
        self.chromium = FakeChromium(self.browser)
        self.playwright = FakePlaywright(self.chromium)

    def __call__(self) -> "FakePlaywrightFactory":
        return self

    def __enter__(self) -> FakePlaywright:
        return self.playwright

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class UrlAwareFakePage(FakePage):
    def __init__(self, html_by_url: dict[str, str]) -> None:
        first_html = next(iter(html_by_url.values()))
        super().__init__(first_html)
        self.html_by_url = html_by_url

    def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        super().goto(url, wait_until=wait_until, timeout=timeout)
        self.html = self.html_by_url[url]

    def locator(self, selector: str) -> FakeLocator:
        if selector == "h1":
            match = re.search(r"<h1[^>]*>(.*?)</h1>", self.html, flags=re.IGNORECASE | re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", match.group(1)).strip() if match else ""
            return FakeLocator(text=text)
        return super().locator(selector)


class UrlAwareFakePlaywrightFactory(FakePlaywrightFactory):
    def __init__(self, html_by_url: dict[str, str], responses: dict[str, bytes] | None = None) -> None:
        self.request = FakeRequest(responses=responses)
        self.page = UrlAwareFakePage(html_by_url)
        self.context = FakeContext(self.page, self.request)
        self.browser = FakeBrowser(self.context)
        self.chromium = FakeChromium(self.browser)
        self.playwright = FakePlaywright(self.chromium)


class GermanDocsDownloaderTests(unittest.TestCase):
    def test_manifest_markdown_helper_renders_context_and_delo_nodes(self) -> None:
        long_description = "x" * 260
        manifest = {
            "source_id": "german_docs_in_russia_wwii",
            "opis_url": "https://example.test/opis",
            "opis_title": "Opis 12475",
            "archival_reference": "Fond 500, Opis 12475",
            "output_dir": "out",
            "archival_context": {
                "hierarchy": [
                    {
                        "level": "fond",
                        "title": "Fond 500",
                        "url": "https://example.test/fond",
                        "metadata": {"Description": long_description},
                    }
                ]
            },
            "delo_nodes": [
                {"title": "Delo 30", "page_count_detected": 2, "output_dir": "out/Fond_500/Delo_30"},
            ],
            "documents": [
                {"status": "downloaded", "page_number": 1, "page_id": 101, "file": "out/page.jpg"},
            ],
        }

        markdown = render_german_docs_manifest_markdown(manifest)

        self.assertIn("# German Docs in Russia download manifest", markdown)
        self.assertIn("Node: https://example.test/opis", markdown)
        self.assertIn("Title: Opis 12475", markdown)
        self.assertIn("## Archival Context", markdown)
        self.assertIn("Fond 500", markdown)
        self.assertIn("xxx...", markdown)
        self.assertIn("## Delo Nodes", markdown)
        self.assertIn("Delo 30 - detected pages: 2", markdown)
        self.assertIn("page_id `101`", markdown)

    def test_adds_archival_hierarchy_metadata_to_manifest_and_sidecar(self) -> None:
        html = """
        <div class="crumbs">
          <a href="/ru/nodes/28468-top">Top</a>
          <a href="/ru/nodes/1-fond-500">Fond 500</a>
          <a href="/ru/nodes/9329-opis-12475-tankovye-korpusa">Opis 12475 - Tank units</a>
          <span>Delo 30</span>
        </div>
        <h1>Delo 30</h1>
        <div class="metadata__table">
          <div class="table__strike record_of_type_8">
            <div class="table__column first">Code</div>
            <div class="table__column">Fond 500 Opis 12475 Delo 30</div>
          </div>
          <div class="table__strike record_of_type_17">
            <div class="table__column first">Description</div>
            <div class="table__column">Delo-level description</div>
          </div>
        </div>
        <script>pages: [{"id": 1242640, "downloadUrl": null}]</script>
        """
        fond_html = """
        <h1>Fond 500</h1>
        <div class="metadata__table">
          <div class="table__strike record_of_type_17">
            <div class="table__column first">Description</div>
            <div class="table__column">Fond-level description</div>
          </div>
        </div>
        """.encode("utf-8")
        opis_html = """
        <h1>Opis 12475 - Tank units</h1>
        <div class="metadata__table">
          <div class="table__strike record_of_type_17">
            <div class="table__column first">Description</div>
            <div class="table__column">Opis-level description</div>
          </div>
        </div>
        """.encode("utf-8")
        factory = FakePlaywrightFactory(
            html,
            responses={
                "https://wwii.germandocsinrussia.org/ru/nodes/1-fond-500": fond_html,
                "https://wwii.germandocsinrussia.org/ru/nodes/9329-opis-12475-tankovye-korpusa": opis_html,
            },
        )
        with workspace_temp_dir() as tmp_dir:
            output_dir = tmp_dir / "downloads"
            manifest = download_german_docs_pages(
                node_url="https://wwii.germandocsinrussia.org/ru/nodes/21261-delo-30",
                output_dir=output_dir,
                archival_reference="Fond 500, Opis 12475, Delo 30",
                max_pages=1,
                delay_seconds=0,
                playwright_factory=factory,
            )
            sidecar_path = next(output_dir.glob("*.jpg.document.yaml"))
            sidecar = yaml.safe_load(sidecar_path.read_text(encoding="utf-8"))

        hierarchy = manifest["archival_context"]["hierarchy"]
        sidecar_hierarchy = sidecar["metadata"]["german_docs_archival_context"]["hierarchy"]
        self.assertEqual([item["level"] for item in hierarchy], ["fond", "opis", "delo"])
        self.assertEqual(hierarchy[0]["metadata"]["Description"], "Fond-level description")
        self.assertEqual(hierarchy[1]["metadata"]["Description"], "Opis-level description")
        self.assertEqual(hierarchy[2]["metadata"]["Description"], "Delo-level description")
        self.assertEqual(sidecar_hierarchy[0]["metadata"]["Description"], "Fond-level description")

    def test_repairs_mojibake_node_title_in_manifest(self) -> None:
        html = '<script>pages: [{"id": 1, "downloadUrl": null}]</script>'
        factory = FakePlaywrightFactory(html)
        factory.page.heading.text = "Ð”ÐµÐ»Ð¾ 30"
        with workspace_temp_dir() as tmp_dir:
            manifest = download_german_docs_pages(
                node_url="https://wwii.germandocsinrussia.org/ru/nodes/sample",
                output_dir=tmp_dir / "downloads",
                archival_reference="Fond 500, Opis 12475, Delo 30",
                max_pages=1,
                delay_seconds=0,
                playwright_factory=factory,
            )

        self.assertEqual(manifest["node_title"], "Дело 30")

    def test_downloads_limited_pages_and_writes_sidecars(self) -> None:
        html = """
        <html><head><title>Fallback title</title></head><body>
        <script>
        pages: [
          {"id": 1242640, "downloadUrl": null},
          {"id": 1242641, "downloadUrl": null},
          {"id": 1242642, "downloadUrl": null}
        ]
        </script>
        </body></html>
        """
        factory = FakePlaywrightFactory(html)
        with workspace_temp_dir() as tmp_dir:
            output_dir = tmp_dir / "downloads"
            manifest = download_german_docs_pages(
                node_url="https://wwii.germandocsinrussia.org/ru/nodes/21261-delo-30",
                output_dir=output_dir,
                archival_reference="Fond 500, Opis 12475, Delo 30",
                title_prefix="Fond 500 Opis 12475 Delo 30",
                start_page=2,
                max_pages=2,
                zoom=7,
                delay_seconds=0,
                playwright_factory=factory,
            )
            files = sorted(output_dir.glob("*.jpg"))
            sidecars = sorted(output_dir.glob("*.jpg.document.yaml"))
            first_sidecar = yaml.safe_load(sidecars[0].read_text(encoding="utf-8"))

        self.assertTrue(factory.page.agreement.clicked)
        self.assertEqual(manifest["summary"], {"total": 2, "downloaded": 2})
        self.assertEqual(manifest["page_count_detected"], 3)
        self.assertEqual(manifest["page_ids_selected"], [1242641, 1242642])
        self.assertEqual(len(files), 2)
        self.assertEqual(len(sidecars), 2)
        self.assertEqual(first_sidecar["source_id"], "german_docs_in_russia_wwii")
        self.assertEqual(first_sidecar["metadata"]["review_status"], "unreviewed")
        self.assertEqual(first_sidecar["metadata"]["extraction_status"], "manual_ocr_required")
        self.assertIn("Fond 500, Opis 12475, Delo 30, page 2, page_id 1242641", first_sidecar["metadata"]["archival_reference"])
        self.assertIn("/pages/1242641/zooms/7", first_sidecar["url"])
        self.assertEqual(factory.request.urls[0], "https://wwii.germandocsinrussia.org/pages/1242641/zooms/7")
        self.assertTrue(factory.browser.context_kwargs["ignore_https_errors"])

    def test_skips_existing_file_and_sidecar_without_overwrite(self) -> None:
        html = '<script>pages: [{"id": 1, "downloadUrl": null}]</script>'
        factory = FakePlaywrightFactory(html)
        with workspace_temp_dir() as tmp_dir:
            output_dir = tmp_dir / "downloads"
            first = download_german_docs_pages(
                node_url="https://wwii.germandocsinrussia.org/ru/nodes/sample",
                output_dir=output_dir,
                archival_reference="Fond 500, Opis 12475, Delo 30",
                title_prefix="Sample",
                max_pages=1,
                delay_seconds=0,
                playwright_factory=factory,
            )
            second_factory = FakePlaywrightFactory(html)
            second = download_german_docs_pages(
                node_url="https://wwii.germandocsinrussia.org/ru/nodes/sample",
                output_dir=output_dir,
                archival_reference="Fond 500, Opis 12475, Delo 30",
                title_prefix="Sample",
                max_pages=1,
                delay_seconds=0,
                playwright_factory=second_factory,
            )

        self.assertEqual(first["summary"]["downloaded"], 1)
        self.assertEqual(second["summary"], {"total": 1, "skipped_existing": 1})
        self.assertEqual(second_factory.request.urls, [])

    def test_opis_download_discovers_delo_nodes_and_uses_hierarchical_dirs(self) -> None:
        opis_url = "https://wwii.germandocsinrussia.org/ru/nodes/9329-opis-12475"
        delo_30_url = "https://wwii.germandocsinrussia.org/ru/nodes/21261-delo-30"
        delo_31_url = "https://wwii.germandocsinrussia.org/ru/nodes/21262-delo-31"
        fond_url = "https://wwii.germandocsinrussia.org/ru/nodes/1-fond-500"
        opis_html = f"""
        <div class="crumbs">
          <a href="/ru/nodes/28468-top">Top</a>
          <a href="/ru/nodes/1-fond-500">Fond 500</a>
          <span>Opis 12475</span>
        </div>
        <h1>Opis 12475</h1>
        <a href="{delo_30_url}">Delo 30</a>
        <a href="{delo_31_url}">Delo 31</a>
        <a href="/ru/nodes/9000-opis-ignored">Opis ignored</a>
        """
        delo_30_html = """
        <div class="crumbs">
          <a href="/ru/nodes/28468-top">Top</a>
          <a href="/ru/nodes/1-fond-500">Fond 500</a>
          <a href="/ru/nodes/9329-opis-12475">Opis 12475</a>
          <span>Delo 30</span>
        </div>
        <h1>Delo 30</h1>
        <script>pages: [{"id": 101}, {"id": 102}]</script>
        """
        delo_31_html = """
        <div class="crumbs">
          <a href="/ru/nodes/28468-top">Top</a>
          <a href="/ru/nodes/1-fond-500">Fond 500</a>
          <a href="/ru/nodes/9329-opis-12475">Opis 12475</a>
          <span>Delo 31</span>
        </div>
        <h1>Delo 31</h1>
        <script>pages: [{"id": 201}]</script>
        """
        factory = UrlAwareFakePlaywrightFactory(
            {
                opis_url: opis_html,
                delo_30_url: delo_30_html,
                delo_31_url: delo_31_html,
            },
            responses={
                fond_url: b"<h1>Fond 500</h1>",
                opis_url: b"<h1>Opis 12475</h1>",
            },
        )
        with workspace_temp_dir() as tmp_dir:
            manifest = download_german_docs_opis_delos(
                opis_url=opis_url,
                output_dir=tmp_dir / "downloads",
                archival_reference="Fond 500, Opis 12475",
                max_delos=0,
                max_total_pages=10,
                delay_seconds=0,
                playwright_factory=factory,
            )
            files = sorted((tmp_dir / "downloads").glob("**/*.jpg"))
            sidecars = sorted((tmp_dir / "downloads").glob("**/*.jpg.document.yaml"))
            first_sidecar = yaml.safe_load(sidecars[0].read_text(encoding="utf-8"))

        self.assertEqual(manifest["@type"], "GermanDocsInRussiaOpisDownloadManifest")
        self.assertEqual(manifest["delo_count_detected"], 2)
        self.assertEqual(manifest["summary"], {"total": 3, "downloaded": 3})
        self.assertEqual([item["title"] for item in manifest["delo_nodes"]], ["Delo 30", "Delo 31"])
        self.assertEqual(len(files), 3)
        self.assertEqual(len(sidecars), 3)
        self.assertIn("Fond_500", str(files[0]))
        self.assertIn("Opis_12475", str(files[0]))
        self.assertIn("Delo_", str(files[0]))
        self.assertEqual(
            first_sidecar["metadata"]["german_docs_archival_context"]["hierarchy"][-1]["level"],
            "delo",
        )

    def test_opis_download_respects_delo_and_total_limits(self) -> None:
        opis_url = "https://wwii.germandocsinrussia.org/ru/nodes/9329-opis-12475"
        delo_30_url = "https://wwii.germandocsinrussia.org/ru/nodes/21261-delo-30"
        delo_31_url = "https://wwii.germandocsinrussia.org/ru/nodes/21262-delo-31"
        factory = UrlAwareFakePlaywrightFactory(
            {
                opis_url: f'<h1>Opis 12475</h1><a href="{delo_30_url}">Delo 30</a><a href="{delo_31_url}">Delo 31</a>',
                delo_30_url: '<h1>Delo 30</h1><script>pages: [{"id": 101}, {"id": 102}]</script>',
                delo_31_url: '<h1>Delo 31</h1><script>pages: [{"id": 201}]</script>',
            }
        )
        with workspace_temp_dir() as tmp_dir:
            manifest = download_german_docs_opis_delos(
                opis_url=opis_url,
                output_dir=tmp_dir / "downloads",
                archival_reference="Fond 500, Opis 12475",
                max_delos=1,
                max_pages_per_delo=1,
                max_total_pages=10,
                delay_seconds=0,
                playwright_factory=factory,
            )

        self.assertEqual(manifest["delo_count_detected"], 2)
        self.assertEqual(manifest["delo_count_selected"], 1)
        self.assertEqual(manifest["summary"], {"total": 1, "downloaded": 1})
        self.assertEqual(factory.page.goto_calls, [opis_url, delo_30_url])

    def test_write_manifest_outputs_json_and_markdown(self) -> None:
        manifest = {
            "source_id": "german_docs_in_russia_wwii",
            "node_url": "https://example.test/node",
            "node_title": "Delo 30",
            "archival_reference": "Fond 500",
            "output_dir": "out",
            "page_count_detected": 1,
            "archival_context": {
                "hierarchy": [
                    {
                        "level": "fond",
                        "title": "Fond 500",
                        "url": "https://example.test/fond",
                        "metadata": {"Description": "Fond description"},
                    }
                ]
            },
            "documents": [{"status": "downloaded", "page_number": 1, "page_id": 10, "file": "out/page.jpg"}],
        }
        with workspace_temp_dir() as tmp_dir:
            output_json = tmp_dir / "manifest.json"
            output_md = tmp_dir / "manifest.md"
            write_manifest(manifest=manifest, output_json=output_json, output_md=output_md)
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(payload["node_title"], "Delo 30")
        self.assertIn("German Docs in Russia download manifest", markdown)
        self.assertIn("Archival Context", markdown)
        self.assertIn("Fond description", markdown)
        self.assertIn("page_id `10`", markdown)


if __name__ == "__main__":
    unittest.main()
