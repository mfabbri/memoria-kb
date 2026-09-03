from __future__ import annotations

import time
from collections.abc import Callable


class ProgressReporter:
    def __init__(
        self,
        callback: Callable[[str], None] | None,
        *,
        item_interval: int = 500,
        seconds_interval: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.callback = callback
        self.item_interval = item_interval
        self.seconds_interval = seconds_interval
        self.clock = clock
        self.last_item = 0
        self.last_time = clock()

    def report(self, message: str, *, force: bool = False) -> None:
        if self.callback is None:
            return
        item = progress_item(message)
        now = self.clock()
        if force or item - self.last_item >= self.item_interval or now - self.last_time >= self.seconds_interval:
            self.callback(message)
            self.last_item = item
            self.last_time = now


def progress_item(message: str) -> int:
    for token in message.split():
        value = token
        if "=" in token:
            _name, _sep, value = token.partition("=")
        if "/" in value:
            current, _sep, _total = value.partition("/")
        else:
            current = value
        try:
            return int(current)
        except ValueError:
            continue
    return 0
