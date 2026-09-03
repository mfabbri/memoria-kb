from __future__ import annotations


def print_status_line(label: str, ok: bool) -> None:
    status = "OK" if ok else "MISSING"
    print(f"{status} {label}")


def print_inventory_text(resolution: object, inventories: list[object]) -> None:
    print(f"Data root: {resolution.path}")
    print(f"Source: {resolution.source}")
    for inventory in inventories:
        print("")
        print(f"Section: {inventory.name}")
        print(f"Path: {inventory.path}")
        print(f"exists: {str(inventory.exists).lower()}")
        print(f"top_level_files: {inventory.top_level_files}")
        print(f"top_level_dirs: {inventory.top_level_dirs}")
        print("entries:")
        if inventory.names:
            for name in inventory.names:
                print(f"- {name}")
        else:
            print("- none")


def print_inventory_markdown(resolution: object, inventories: list[object]) -> None:
    print("# Memoria inventory")
    print("")
    print(f"- Data root: `{resolution.path}`")
    print(f"- Source: `{resolution.source}`")
    for inventory in inventories:
        print("")
        print(f"## {inventory.name}")
        print("")
        print(f"- Path: `{inventory.path}`")
        print(f"- Exists: {'yes' if inventory.exists else 'no'}")
        print(f"- Top-level files: {inventory.top_level_files}")
        print(f"- Top-level directories: {inventory.top_level_dirs}")
        print("")
        print("### Entries")
        print("")
        if inventory.names:
            for name in inventory.names:
                print(f"- `{name}`")
        else:
            print("- none")


def print_profiles_status_text(resolution: object, status: object) -> None:
    print(f"Data root: {resolution.path}")
    print(f"Source: {resolution.source}")
    print(f"Profiles index: {status.index_path}")
    print(f"exists: {str(status.index_exists).lower()}")
    print(f"index_profiles: {status.index_count}")
    print(f"loaded_profiles: {status.loaded_profiles}")
    print(f"missing_profile_files: {len(status.missing_profile_files)}")
    print_count_block("profile_status", status.profile_statuses)
    print_count_block("review_status", status.review_statuses)
    print_count_block("publication_status", status.publication_statuses)
    if status.missing_profile_files:
        print("missing_files:")
        for file_name in status.missing_profile_files:
            print(f"- {file_name}")


def print_profiles_status_markdown(resolution: object, status: object) -> None:
    print("# Memoria profiles status")
    print("")
    print(f"- Data root: `{resolution.path}`")
    print(f"- Source: `{resolution.source}`")
    print(f"- Profiles index: `{status.index_path}`")
    print(f"- Exists: {'yes' if status.index_exists else 'no'}")
    print(f"- Index profiles: {status.index_count}")
    print(f"- Loaded profiles: {status.loaded_profiles}")
    print(f"- Missing profile files: {len(status.missing_profile_files)}")
    print("")
    print_count_markdown("Profile status", status.profile_statuses)
    print_count_markdown("Review status", status.review_statuses)
    print_count_markdown("Publication status", status.publication_statuses)
    if status.missing_profile_files:
        print("## Missing files")
        print("")
        for file_name in status.missing_profile_files:
            print(f"- `{file_name}`")


def print_required_dirs_markdown(resolution: object, checks: list[tuple[str, bool]]) -> None:
    print("# Memoria inventory")
    print("")
    print(f"- Data root: `{resolution.path}`")
    print(f"- Source: `{resolution.source}`")
    print("")
    print("## Required folders")
    print("")
    for name, ok in checks:
        print(f"- [{'x' if ok else ' '}] `{name}`")


def print_count_block(label: str, counts: tuple[tuple[str, int], ...]) -> None:
    print(f"{label}:")
    if counts:
        for status, count in counts:
            print(f"- {status}: {count}")
    else:
        print("- none: 0")


def print_count_markdown(title: str, counts: tuple[tuple[str, int], ...]) -> None:
    print(f"## {title}")
    print("")
    if counts:
        for status, count in counts:
            print(f"- `{status}`: {count}")
    else:
        print("- none")
    print("")
