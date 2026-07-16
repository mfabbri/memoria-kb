from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

from ..models import Caduto, SearchHit, Source, SourceResult


def normalize_value(value: Any) -> str:
    text = str(value or "").strip()
    return " ".join(text.lower().split())


def split_person_name(query: str, order: str) -> tuple[str, str]:
    parts = [part for part in query.split() if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return "", parts[0]
    if order == "surname_first":
        return parts[0], " ".join(parts[1:])
    return " ".join(parts[:-1]), parts[-1]


def build_file_url(path: Path) -> str:
    return f"file:///{quote(str(path.resolve()).replace(chr(92), '/'))}"


def load_excel_rows_from_workbook(workbook_path: Path, source: Source) -> tuple[Path, str, list[dict[str, str]]]:
    try:
        import xlrd
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Modulo `xlrd` non disponibile per leggere file .xls.") from exc

    if not workbook_path.exists():
        raise FileNotFoundError(f"Workbook non trovato: {workbook_path}")

    workbook = xlrd.open_workbook(str(workbook_path))
    sheet_name = source.local.get("sheet_name") or workbook.sheet_names()[0]
    sheet = workbook.sheet_by_name(sheet_name)
    headers = [str(sheet.cell_value(0, col)).strip() for col in range(sheet.ncols)]
    rows: list[dict[str, str]] = []
    for row_idx in range(1, sheet.nrows):
        row: dict[str, str] = {"__row_number__": str(row_idx + 1)}
        for col_idx, header in enumerate(headers):
            if not header:
                continue
            row[header] = str(sheet.cell_value(row_idx, col_idx)).strip()
        rows.append(row)
    return workbook_path, sheet_name, rows


def load_excel_rows(source: Source) -> list[tuple[Path, str, list[dict[str, str]]]]:
    workbook_dir = source.local.get("workbook_dir", "").strip()
    workbook_glob = source.local.get("workbook_glob", "*.xls").strip() or "*.xls"
    workbook_path = source.local.get("workbook_path", "").strip()

    if workbook_dir:
        base_dir = Path(workbook_dir)
        if not base_dir.exists():
            raise FileNotFoundError(f"Cartella workbook non trovata: {base_dir}")
        workbook_paths = sorted(path for path in base_dir.glob(workbook_glob) if path.is_file())
        if not workbook_paths:
            raise FileNotFoundError(f"Nessun workbook trovato in {base_dir} con pattern {workbook_glob}")
        return [load_excel_rows_from_workbook(path, source) for path in workbook_paths]

    if workbook_path:
        return [load_excel_rows_from_workbook(Path(workbook_path), source)]

    raise FileNotFoundError("Nessun workbook_path o workbook_dir configurato per la fonte locale.")


def row_matches_query(row: dict[str, str], query: str, source: Source) -> bool:
    order = source.local.get("name_order", "surname_first")
    surname_query, given_query = split_person_name(query, order)
    surname_column = source.local.get("surname_column", "Cognome")
    given_name_column = source.local.get("given_name_column", "Nome")
    alias_columns = [col.strip() for col in source.local.get("alias_columns", "").split(",") if col.strip()]

    row_surname = normalize_value(row.get(surname_column, ""))
    row_given = normalize_value(row.get(given_name_column, ""))
    normalized_query = normalize_value(query)

    if surname_query and given_query:
        if row_surname == normalize_value(surname_query) and row_given == normalize_value(given_query):
            return True
    elif given_query:
        if row_given == normalize_value(given_query) or row_surname == normalize_value(given_query):
            return True

    if not normalized_query:
        return False

    combined_fields = [row_surname, row_given]
    combined_fields.extend(normalize_value(row.get(column, "")) for column in alias_columns)
    return any(normalized_query == field for field in combined_fields if field)


def build_row_snippet(row: dict[str, str], source: Source) -> str:
    snippet_columns = [col.strip() for col in source.local.get("snippet_columns", "").split(",") if col.strip()]
    parts = []
    for column in snippet_columns:
        value = row.get(column, "").strip()
        if value:
            parts.append(f"{column}: {value}")
    row_number = row.get("__row_number__", "")
    if row_number:
        parts.insert(0, f"Riga Excel: {row_number}")
    return " | ".join(parts)


def run_local_excel_source(source: Source, caduto: Caduto, query: str, search_url: str) -> SourceResult:
    try:
        workbooks = load_excel_rows(source)
        hits: list[SearchHit] = []
        for workbook_path, sheet_name, rows in workbooks:
            matches = [row for row in rows if row_matches_query(row, query, source)]
            for row in matches:
                hits.append(
                    SearchHit(
                        title=" ".join(
                            part
                            for part in [
                                row.get(source.local.get("surname_column", "Cognome"), ""),
                                row.get(source.local.get("given_name_column", "Nome"), ""),
                            ]
                            if part
                        ).strip()
                        or query,
                        url=build_file_url(workbook_path),
                        snippet=f"File {workbook_path.name}; foglio {sheet_name}. {build_row_snippet(row, source)}",
                    )
                )
                if len(hits) >= 3:
                    break
            if len(hits) >= 3:
                break
        status = "ok" if hits else "no_results"
        note = source.note if hits else f"{source.note} Nessuna riga corrispondente trovata nei file Excel locali."
        return SourceResult(
            source_id=source.source_id,
            source_name=source.source_name,
            status=status,
            note=note,
            query=query,
            search_url=search_url or (build_file_url(workbooks[0][0]) if workbooks else ""),
            hits=hits,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        return SourceResult(
            source_id=source.source_id,
            source_name=source.source_name,
            status="error",
            note=f"{source.note} Errore durante la lettura del file Excel locale: {exc}.",
            query=query,
            search_url=search_url,
        )
