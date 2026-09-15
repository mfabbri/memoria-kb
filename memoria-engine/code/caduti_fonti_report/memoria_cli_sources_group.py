from __future__ import annotations

import argparse
from collections.abc import Callable


CommandHandler = Callable[[argparse.Namespace], int]


def register_sources_group(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    online_discover_handler: CommandHandler,
    online_status_handler: CommandHandler,
    offline_discover_handler: CommandHandler,
    offline_status_handler: CommandHandler,
) -> None:
    """Register the read-only ``sources`` argparse command tree."""
    sources = subparsers.add_parser("sources", help="Bridge read-only dei workflow sources MVP.")
    sources_subparsers = sources.add_subparsers(dest="sources_kind", required=True)
    sources_online = sources_subparsers.add_parser("online", help="Orientamento read-only sulle fonti online.")
    sources_online_subparsers = sources_online.add_subparsers(dest="sources_online_command", required=True)
    for command_name, command_help, handler in (
        ("discover", "Mostra registry, profili e fonti candidate senza avviare rete.", online_discover_handler),
        ("status", "Mostra sessione sources online attiva o discovery read-only.", online_status_handler),
    ):
        command = sources_online_subparsers.add_parser(command_name, help=command_help)
        command.add_argument("--data-root", default="", help="Path esplicito al data root esterno.")
        command.add_argument("--limit", type=int, default=5, help="Numero massimo di elementi da mostrare.")
        command.add_argument("--profile-id", default="", help="Profilo persona candidato per il contesto sources online.")
        command.add_argument("--subject-kind", default="", help="Tipo soggetto candidato: person, place o event.")
        command.add_argument("--subject-id", default="", help="ID soggetto candidato.")
        command.add_argument("--subject-label", default="", help="Etichetta soggetto candidata.")
        command.set_defaults(handler=handler)

    sources_offline = sources_subparsers.add_parser("offline", help="Orientamento read-only sulle fonti offline.")
    sources_offline_subparsers = sources_offline.add_subparsers(dest="sources_offline_command", required=True)
    for command_name, command_help, handler in (
        ("discover", "Mostra documenti offline candidati senza creare run.", offline_discover_handler),
        ("status", "Mostra stato offline read-only senza creare run.", offline_status_handler),
    ):
        command = sources_offline_subparsers.add_parser(command_name, help=command_help)
        command.add_argument("--data-root", default="", help="Path esplicito al data root esterno.")
        command.add_argument("--limit", type=int, default=5, help="Numero massimo di elementi da mostrare.")
        command.set_defaults(handler=handler)
