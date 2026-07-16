from pathlib import Path
import os
import typer

app = typer.Typer(help="Me.Mo.Ri.A engine CLI")


def workspace_path() -> Path:
    return Path(os.environ.get("MEMORIA_WORKSPACE_PATH", "../memoria-workspace")).resolve()


@app.command()
def doctor():
    """Validate sibling repository layout and workspace availability."""
    paths = {
        "workspace": workspace_path(),
        "rules": Path(os.environ.get("MEMORIA_RULES_PATH", "../memoria-rules")).resolve(),
        "knowledge": Path(os.environ.get("MEMORIA_KNOWLEDGE_PATH", "../memoria-knowledge")).resolve(),
        "sources": Path(os.environ.get("MEMORIA_SOURCES_PATH", "../memoria-sources")).resolve(),
    }
    for name, path in paths.items():
        status = "OK" if path.exists() else "MISSING"
        typer.echo(f"{name}: {path} [{status}]")


@app.command()
def graph_status():
    """Show basic workspace graph status."""
    graph_dir = workspace_path() / "graph" / "jsonld"
    count = len(list(graph_dir.glob("*.jsonld"))) if graph_dir.exists() else 0
    typer.echo(f"JSON-LD files: {count}")


if __name__ == "__main__":
    app()
