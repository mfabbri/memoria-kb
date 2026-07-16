"""caduti_fonti_report package.

The package keeps imports lazy so utility modules can be executed with
``python -m caduti_fonti_report.<module>`` without preloading the CLI runner.
"""
from __future__ import annotations

__all__ = ["main"]


def main(*args, **kwargs):
    """CLI entrypoint, loaded lazily to avoid import side effects."""
    from .runner import main as _main

    return _main(*args, **kwargs)