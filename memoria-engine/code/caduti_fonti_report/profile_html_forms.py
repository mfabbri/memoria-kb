from __future__ import annotations

from html.parser import HTMLParser

from .source_profiles import SourceSearchField, SourceSearchOption, SourceSearchProfile


class _FormFieldParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.fields: list[dict[str, object]] = []
        self.labels_by_for: dict[str, str] = {}
        self._current_label_for = ""
        self._current_label_text: list[str] = []
        self._current_select: dict[str, object] | None = None
        self._current_option: dict[str, str] | None = None
        self._current_option_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}
        if tag == "label":
            self._current_label_for = attributes.get("for", "")
            self._current_label_text = []
        elif tag == "input":
            field_id = attributes.get("name") or attributes.get("id")
            if not field_id:
                return
            self.fields.append(
                {
                    "id": field_id,
                    "label": "",
                    "type": attributes.get("type", "text") or "text",
                    "required": "required" in attributes,
                    "default": attributes.get("value", ""),
                    "html_id": attributes.get("id", ""),
                    "options": [],
                }
            )
        elif tag == "select":
            field_id = attributes.get("name") or attributes.get("id")
            if not field_id:
                return
            self._current_select = {
                "id": field_id,
                "label": "",
                "type": "select",
                "required": "required" in attributes,
                "default": "",
                "html_id": attributes.get("id", ""),
                "options": [],
            }
        elif tag == "option" and self._current_select is not None:
            self._current_option = {
                "value": attributes.get("value", ""),
                "label": "",
                "selected": "selected" if "selected" in attributes else "",
            }
            self._current_option_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "label" and self._current_label_for:
            self.labels_by_for[self._current_label_for] = _clean_text(" ".join(self._current_label_text))
            self._current_label_for = ""
            self._current_label_text = []
        elif tag == "option" and self._current_select is not None and self._current_option is not None:
            self._current_option["label"] = _clean_text(" ".join(self._current_option_text))
            options = self._current_select["options"]
            if isinstance(options, list):
                options.append(self._current_option)
            if self._current_option.get("selected"):
                self._current_select["default"] = self._current_option.get("value", "")
            self._current_option = None
            self._current_option_text = []
        elif tag == "select" and self._current_select is not None:
            options = self._current_select["options"]
            if isinstance(options, list) and not self._current_select.get("default") and options:
                first_value = options[0].get("value", "") if isinstance(options[0], dict) else ""
                self._current_select["default"] = first_value
            self.fields.append(self._current_select)
            self._current_select = None

    def handle_data(self, data: str) -> None:
        if self._current_label_for:
            self._current_label_text.append(data)
        if self._current_option is not None:
            self._current_option_text.append(data)


def profile_search_form_html(
    *,
    html: str,
    source_id: str,
    engine: str,
    discovery: dict[str, str] | None = None,
) -> SourceSearchProfile:
    parser = _FormFieldParser()
    parser.feed(html)

    fields: list[SourceSearchField] = []
    seen_ids: set[str] = set()
    for item in parser.fields:
        field_id = str(item.get("id", ""))
        if not field_id or field_id in seen_ids:
            continue
        seen_ids.add(field_id)
        html_id = str(item.get("html_id", ""))
        label = parser.labels_by_for.get(html_id, "") or parser.labels_by_for.get(field_id, "")
        options = [
            SourceSearchOption(value=str(option.get("value", "")), label=str(option.get("label", "")))
            for option in item.get("options", [])
            if isinstance(option, dict)
        ]
        fields.append(
            SourceSearchField(
                field_id=field_id,
                label=label or field_id,
                field_type=str(item.get("type", "unknown")),
                required=bool(item.get("required", False)),
                default=str(item.get("default", "")),
                options=options,
                metadata={"html_id": html_id} if html_id else {},
            )
        )

    return SourceSearchProfile(
        source_id=source_id,
        engine=engine,
        discovery=discovery or {},
        fields=fields,
    )


def _clean_text(value: str) -> str:
    return " ".join(value.split())
