from __future__ import annotations

from .models import Caduto


def default_query(caduto: Caduto) -> str:
    return caduto.nome


def foreign_query(caduto: Caduto) -> str:
    return f'{caduto.nome} "{caduto.origine_sulla_lapide}"'


QUERY_BUILDERS = {
    "default": default_query,
    "foreign": foreign_query,
}
