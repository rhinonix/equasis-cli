"""Status messages for people, written to stderr so stdout stays machine-readable."""

from __future__ import annotations

import os
import sys
from typing import IO, ClassVar


class Console:
    """Writes progress, warnings, and errors to a text stream (stderr by default).

    Color is used only when the stream is a terminal and neither ``NO_COLOR``
    (https://no-color.org) nor ``--no-color`` is set.
    """

    _CODES: ClassVar[dict[str, str]] = {
        "red": "31",
        "green": "32",
        "yellow": "33",
        "dim": "2",
        "bold": "1",
    }

    def __init__(
        self, stream: IO[str] | None = None, *, quiet: bool = False, color: bool | None = None
    ) -> None:
        self.stream = stream or sys.stderr
        self.quiet = quiet
        if color is None:
            color = self.is_terminal and not os.environ.get("NO_COLOR")
        self.color = color

    @property
    def is_terminal(self) -> bool:
        isatty = getattr(self.stream, "isatty", None)
        return bool(isatty and isatty())

    def style(self, text: str, *styles: str) -> str:
        if not self.color or not styles:
            return text
        codes = ";".join(self._CODES[s] for s in styles)
        return f"\033[{codes}m{text}\033[0m"

    def _write(self, text: str) -> None:
        self.stream.write(text + "\n")
        self.stream.flush()

    def info(self, message: str) -> None:
        if not self.quiet:
            self._write(message)

    def progress(self, message: str) -> None:
        if not self.quiet:
            self._write(self.style(message, "dim"))

    def success(self, message: str) -> None:
        if not self.quiet:
            self._write(self.style(message, "green"))

    def warn(self, message: str) -> None:
        self._write(self.style(f"warning: {message}", "yellow"))

    def error(self, message: str, hint: str | None = None) -> None:
        self._write(self.style(f"error: {message}", "red", "bold"))
        if hint:
            self._write(f"hint: {hint}")
