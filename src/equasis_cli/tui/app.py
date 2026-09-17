"""Full-screen interactive shell built with prompt_toolkit.

Output scrolls above a fixed input line and a status bar. Commands run in a
worker thread so the interface stays responsive; results are posted back to the
event loop, which owns all interface state.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import (
    ConditionalContainer,
    HSplit,
    Layout,
    ScrollbarMargin,
    VSplit,
    Window,
)
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.output import Output
from prompt_toolkit.styles import Style

from ..banner import ASCII_ART, interactive_banner
from .commands import COMMANDS, CommandRunner, split_words

MAX_OUTPUT_LINES = 5000
PROMPT = "❯ "
SPINNER = ("◐", "◓", "◑", "◒")
MENU_HEIGHT = 9

HELP_OVERLAY = (
    ("/", "show commands, or parameters after a command"),
    ("Tab", "complete the highlighted menu item"),
    ("Up/Down", "move in the menu, or recall previous commands"),
    ("Esc", "close the menu, or scroll the output (i or q to return)"),
    ("PgUp/PgDn", "scroll the output (also Shift+Up/Down, Ctrl+K/J)"),
    ("Ctrl+C", "clear the input line"),
    ("Ctrl+D", "exit"),
)

STYLE = Style.from_dict(
    {
        "separator": "fg:#5c6370",
        "prompt": "fg:#61afef bold",
        "echo": "fg:#5c6370",
        "banner": "fg:#5c6370",
        "banner-art": "fg:#61afef",
        "error": "fg:#e06c75",
        "warning": "fg:#e5c07b",
        "success": "fg:#98c379",
        "toolbar": "fg:#abb2bf",
        "toolbar.connected": "fg:#98c379",
        "toolbar.disconnected": "fg:#e06c75",
        "toolbar.dim": "fg:#5c6370",
        "toolbar.format": "fg:#61afef",
        "menu": "fg:#5c6370",
        "menu.selected": "fg:#61afef bold",
        "loading": "fg:#61afef",
        "loading.detail": "fg:#5c6370",
    }
)


class OutputLexer(Lexer):
    """Colors the banner, echoed commands, errors, warnings, and confirmations."""

    def __init__(self, banner_lines: int, art_lines: int) -> None:
        self.banner_lines = banner_lines
        self.art_lines = art_lines

    def lex_document(self, document: Document) -> Callable[[int], StyleAndTextTuples]:
        lines = document.lines

        def line_style(number: int) -> StyleAndTextTuples:
            if number >= len(lines):
                return []
            line = lines[number]
            if number < self.art_lines:
                return [("class:banner-art", line)]
            if number < self.banner_lines:
                return [("class:banner", line)]
            if line.startswith(PROMPT):
                return [("class:echo", line)]
            stripped = line.lstrip()
            if stripped.startswith(("Error:", "Login failed:")):
                return [("class:error", line)]
            if stripped.startswith(("Warning:", "warning:", "Note:")):
                return [("class:warning", line)]
            if stripped.startswith("Saved "):
                return [("class:success", line)]
            return [("", line)]

        return line_style


class _ShellLogHandler(logging.Handler):
    def __init__(self, shell: InteractiveShell) -> None:
        super().__init__(level=logging.WARNING)
        self.shell = shell

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.shell.write(f"Warning: {record.getMessage()}")
        except Exception:  # logging must never break the interface
            self.handleError(record)


class InteractiveShell:
    """The ``equasis`` interactive shell."""

    def __init__(
        self,
        *,
        runner: CommandRunner | None = None,
        input: Input | None = None,  # mirrors prompt_toolkit
        output: Output | None = None,
    ) -> None:
        self.runner = runner or CommandRunner(self.write, self.set_status)
        self.runner.write = self.write
        self.runner.status = self.set_status

        self.busy = False
        self.status_text = ""
        self.show_help = False
        self.menu_index = 0
        self.menu_dismissed = False
        self._spinner = 0
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: int | None = None

        banner = interactive_banner()
        self.lexer = OutputLexer(
            banner_lines=len(banner.splitlines()), art_lines=len(ASCII_ART.splitlines())
        )
        initial = f"{banner}\n\n"
        self.output_buffer = Buffer(
            document=Document(initial, len(initial)), read_only=True, multiline=True
        )
        self.input_buffer = Buffer(
            multiline=False, history=InMemoryHistory(), on_text_changed=self._on_input_changed
        )

        self.app: Application[None] = Application(
            layout=self._layout(),
            key_bindings=self._key_bindings(),
            style=STYLE,
            full_screen=True,
            mouse_support=False,
            input=input,
            output=output,
        )

    # ---------------------------------------------------------------- output

    def write(self, text: str) -> None:
        """Append text to the output area; safe to call from any thread."""
        if self._loop is not None and threading.get_ident() != self._loop_thread:
            self._loop.call_soon_threadsafe(self._append, text)
        else:
            self._append(text)

    def set_status(self, text: str) -> None:
        """Update the loading line; safe to call from any thread."""
        if self._loop is not None and threading.get_ident() != self._loop_thread:
            self._loop.call_soon_threadsafe(self._set_status, text)
        else:
            self._set_status(text)

    def _set_status(self, text: str) -> None:
        self.status_text = text
        self._invalidate()

    def _append(self, text: str) -> None:
        current = self.output_buffer.text
        combined = f"{current}{text}\n" if current else f"{text}\n"
        lines = combined.split("\n")
        if len(lines) > MAX_OUTPUT_LINES:
            combined = "\n".join(lines[-MAX_OUTPUT_LINES:])
            self._forget_banner()
        scrolling = self.app.layout.has_focus(self.output_buffer)
        position = (
            min(self.output_buffer.cursor_position, len(combined)) if scrolling else len(combined)
        )
        self.output_buffer.set_document(Document(combined, position), bypass_readonly=True)
        self._invalidate()

    def clear(self) -> None:
        self.output_buffer.set_document(Document("", 0), bypass_readonly=True)
        self._forget_banner()

    def _forget_banner(self) -> None:
        """Stop styling the first lines as the banner once it is no longer there."""
        self.lexer.banner_lines = 0
        self.lexer.art_lines = 0

    def _invalidate(self) -> None:
        if self.app.is_running:
            self.app.invalidate()

    # ------------------------------------------------------------------ menus

    def menu_items(self) -> list[tuple[str, str]]:
        """Commands or parameters matching what is being typed."""
        text = self.input_buffer.document.text_before_cursor
        words = split_words(text)
        ends_with_space = text.endswith(" ")
        if not words:
            return []
        if len(words) == 1 and not ends_with_space and text.lstrip().startswith("/"):
            prefix = words[0][1:].lower()
            return [
                (name, spec.summary) for name, spec in COMMANDS.items() if name.startswith(prefix)
            ]
        last = words[-1]
        spec = COMMANDS.get(words[0].lower().lstrip("/"))
        if spec and len(words) > 1 and not ends_with_space and last.startswith("/"):
            prefix = last[1:].lower()
            used = {w[1:].lower() for w in words[1:-1] if w.startswith("/")}
            return [
                (f"/{p.name}", p.help)
                for p in spec.params
                if p.name.startswith(prefix) and p.name not in used
            ]
        return []

    @property
    def menu_visible(self) -> bool:
        return (
            not self.menu_dismissed
            and self.app.layout.has_focus(self.input_buffer)
            and bool(self.menu_items())
        )

    def _on_input_changed(self, _: Buffer) -> None:
        self.menu_dismissed = False
        self.menu_index = 0
        if self.input_buffer.text:
            self.show_help = False

    def accept_menu_item(self) -> bool:
        items = self.menu_items()
        if not items:
            return False
        choice = items[min(self.menu_index, len(items) - 1)][0]
        document = self.input_buffer.document
        words_before = document.text_before_cursor
        start = len(words_before) - len(words_before.split(" ")[-1])
        new_text = words_before[:start] + choice + " " + document.text_after_cursor.lstrip()
        self.input_buffer.document = Document(new_text, start + len(choice) + 1)
        self.menu_dismissed = True
        return True

    def complete_command(self) -> None:
        """Tab without a menu: complete a partially typed command name."""
        text = self.input_buffer.text
        if " " in text or not text:
            return
        matches = [name for name in COMMANDS if name.startswith(text.lower())]
        if len(matches) == 1:
            self.input_buffer.document = Document(matches[0] + " ", len(matches[0]) + 1)
        elif matches:
            self.input_buffer.document = Document("/" + text, len(text) + 1)

    # ---------------------------------------------------------------- running

    def submit(self) -> None:
        line = self.input_buffer.text.strip()
        if not line:
            return
        if self.busy:
            self.write("Warning: wait for the current command to finish")
            return
        self.input_buffer.history.append_string(line)
        self.input_buffer.reset()
        self.show_help = False
        self.write(f"{PROMPT}{line}")

        word = line.split()[0].lower().lstrip("/")
        if word in ("exit", "quit"):
            self.app.exit()
            return
        if word == "clear":
            self.clear()
            return
        self.app.create_background_task(self._run(line))

    async def _run(self, line: str) -> None:
        self.busy = True
        self.status_text = "Working..."
        animation = asyncio.ensure_future(self._animate())
        try:
            loop = asyncio.get_running_loop()
            keep_running = await loop.run_in_executor(None, self.runner.run, line)
        finally:
            self.busy = False
            self.status_text = ""
            animation.cancel()
            self._invalidate()
        if not keep_running:
            self.app.exit()

    async def _animate(self) -> None:
        while True:
            await asyncio.sleep(0.15)
            self._spinner += 1
            self._invalidate()

    def start(self) -> None:
        """Run the shell until the user exits."""
        package_logger = logging.getLogger("equasis_cli")
        handler = _ShellLogHandler(self)
        propagate = package_logger.propagate
        package_logger.addHandler(handler)
        package_logger.propagate = False

        def pre_run() -> None:
            self._loop = asyncio.get_running_loop()
            self._loop_thread = threading.get_ident()

        try:
            self.app.run(pre_run=pre_run)
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            package_logger.removeHandler(handler)
            package_logger.propagate = propagate
            self.runner.close()

    # ----------------------------------------------------------------- layout

    def _toolbar(self) -> StyleAndTextTuples:
        parts: StyleAndTextTuples = []
        if self.runner.connected:
            parts.append(("class:toolbar.connected", "● Connected"))
        else:
            parts.append(("class:toolbar.disconnected", "○ Not connected"))
        parts.append(("class:toolbar.dim", "  Format: "))
        parts.append(("class:toolbar.format", self.runner.state.output_format))
        if self.app.layout.has_focus(self.output_buffer):
            hint = "Scrolling: arrows, j/k, PgUp/PgDn; i or q to type"
        else:
            hint = "? for keys, help for commands"
        parts.append(("class:toolbar.dim", f"  {hint}"))
        return parts

    def _loading(self) -> StyleAndTextTuples:
        spinner = SPINNER[self._spinner % len(SPINNER)]
        return [("class:loading", f"{spinner} "), ("class:loading.detail", self.status_text)]

    def _menu(self) -> StyleAndTextTuples:
        items = self.menu_items()[:MENU_HEIGHT]
        if not items:
            return []
        self.menu_index = min(self.menu_index, len(items) - 1)
        width = max(len(name) for name, _ in items) + 3
        fragments: StyleAndTextTuples = []
        for index, (name, description) in enumerate(items):
            style = "class:menu.selected" if index == self.menu_index else "class:menu"
            fragments.append((style, f"{name.ljust(width)}{description}\n"))
        return fragments

    def _help_overlay(self) -> StyleAndTextTuples:
        width = max(len(key) for key, _ in HELP_OVERLAY) + 3
        return [("class:menu", f"{key.ljust(width)}{text}\n") for key, text in HELP_OVERLAY]

    def _layout(self) -> Layout:
        output_window = Window(
            BufferControl(buffer=self.output_buffer, lexer=self.lexer, focusable=True),
            wrap_lines=True,
            right_margins=[ScrollbarMargin(display_arrows=True)],
        )

        separator = Window(height=1, char="─", style="class:separator")
        input_line = VSplit(
            [
                Window(
                    FormattedTextControl([("class:prompt", PROMPT)]),
                    width=len(PROMPT),
                    dont_extend_width=True,
                ),
                Window(BufferControl(buffer=self.input_buffer), height=1),
            ]
        )
        return Layout(
            HSplit(
                [
                    output_window,
                    separator,
                    ConditionalContainer(
                        Window(FormattedTextControl(self._loading), height=1),
                        filter=Condition(lambda: self.busy),
                    ),
                    input_line,
                    ConditionalContainer(
                        Window(FormattedTextControl(self._menu), height=MENU_HEIGHT),
                        filter=Condition(lambda: self.menu_visible),
                    ),
                    ConditionalContainer(
                        Window(FormattedTextControl(self._help_overlay), height=len(HELP_OVERLAY)),
                        filter=Condition(lambda: self.show_help and not self.menu_visible),
                    ),
                    separator,
                    Window(FormattedTextControl(self._toolbar), height=1, style="class:toolbar"),
                ]
            ),
            focused_element=self.input_buffer,
        )

    def _key_bindings(self) -> KeyBindings:
        bindings = KeyBindings()
        scrolling = Condition(lambda: self.app.layout.has_focus(self.output_buffer))
        typing = ~scrolling
        menu = Condition(lambda: self.menu_visible)

        def scroll(lines: int) -> None:
            buffer = self.output_buffer
            if lines < 0:
                buffer.cursor_up(count=-lines)
            else:
                buffer.cursor_down(count=lines)

        @bindings.add("enter", filter=typing)
        def _submit(event: KeyPressEvent) -> None:
            self.submit()

        @bindings.add("tab", filter=typing)
        def _tab(event: KeyPressEvent) -> None:
            if not self.accept_menu_item():
                self.complete_command()

        @bindings.add("up", filter=typing & menu)
        def _menu_up(event: KeyPressEvent) -> None:
            self.menu_index = max(0, self.menu_index - 1)

        @bindings.add("down", filter=typing & menu)
        def _menu_down(event: KeyPressEvent) -> None:
            self.menu_index = min(len(self.menu_items()) - 1, self.menu_index + 1)

        @bindings.add("up", filter=typing & ~menu)
        def _history_back(event: KeyPressEvent) -> None:
            self.input_buffer.history_backward()

        @bindings.add("down", filter=typing & ~menu)
        def _history_forward(event: KeyPressEvent) -> None:
            self.input_buffer.history_forward()

        @bindings.add("escape", filter=typing, eager=True)
        def _escape(event: KeyPressEvent) -> None:
            if self.menu_visible:
                self.menu_dismissed = True
            elif self.show_help:
                self.show_help = False
            else:
                event.app.layout.focus(self.output_buffer)

        @bindings.add("?", filter=typing)
        def _question(event: KeyPressEvent) -> None:
            if self.input_buffer.text:
                self.input_buffer.insert_text("?")
            else:
                self.show_help = not self.show_help

        @bindings.add("c-c")
        def _cancel(event: KeyPressEvent) -> None:
            if self.busy and not self.input_buffer.text:
                self.write("Warning: the running command cannot be interrupted; it will finish")
            self.input_buffer.reset()
            self.show_help = False
            event.app.layout.focus(self.input_buffer)

        @bindings.add("c-d")
        def _exit(event: KeyPressEvent) -> None:
            event.app.exit()

        for key in ("i", "q", "escape", "enter"):

            @bindings.add(key, filter=scrolling)
            def _return_to_input(event: KeyPressEvent) -> None:
                event.app.layout.focus(self.input_buffer)

        @bindings.add(Keys.Any, filter=scrolling)
        def _type_to_return(event: KeyPressEvent) -> None:
            event.app.layout.focus(self.input_buffer)
            if event.data.isprintable():
                self.input_buffer.insert_text(event.data)

        for key, lines in (("up", -1), ("k", -1), ("down", 1), ("j", 1)):

            @bindings.add(key, filter=scrolling)
            def _scroll_line(event: KeyPressEvent, lines: int = lines) -> None:
                scroll(lines)

        for key, lines in (
            ("pageup", -15),
            ("pagedown", 15),
            ("s-up", -1),
            ("s-down", 1),
            ("c-k", -5),
            ("c-j", 5),
        ):

            @bindings.add(key)
            def _scroll_page(event: KeyPressEvent, lines: int = lines) -> None:
                scroll(lines)

        return bindings
