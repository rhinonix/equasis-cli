#!/usr/bin/env python3
"""
Interactive Shell for Equasis CLI with proper Application layout
Output stays above, prompt stays fixed at bottom
"""

import re
import os
import sys
import logging
from typing import Dict, Optional, Tuple

from prompt_toolkit import Application
from prompt_toolkit.layout import (
    HSplit, Layout, Window, FloatContainer, Float,
    ScrollbarMargin, ConditionalContainer, WindowAlign
)
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import FormattedText, HTML, StyleAndTextTuples
from prompt_toolkit.styles import Style
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.completion import Completer, Completion, CompleteEvent
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition

from .client import EquasisClient
from .formatter import OutputFormatter
from .banner import display_banner, display_credentials_note, check_credentials, Colors, get_interactive_banner
from .credentials import get_credential_manager

logger = logging.getLogger(__name__)


class OutputLexer(Lexer):
    """Custom lexer to style output buffer text with gradient for ASCII art"""

    def __init__(self):
        self.banner_end_line = None  # Track where banner ends
        self.ascii_art_end_line = 5  # ASCII art is lines 0-5

    def lex_document(self, document: Document) -> callable:
        # Find where banner ends (after "Press ? for quick help.")
        if self.banner_end_line is None:
            for i, line in enumerate(document.lines):
                if 'Press ? for quick help.' in line:
                    self.banner_end_line = i
                    break

        def get_line_styles(line_number: int) -> StyleAndTextTuples:
            try:
                line = document.lines[line_number]

                # User prompt lines (commands executed by user)
                if line.startswith('❯ '):
                    return [('class:user-prompt', line)]

                # ASCII art gradient (lines 0-5): pink to purple
                if line_number <= self.ascii_art_end_line:
                    # Gradient: magenta #c678dd -> purple #a464c2 -> violet #8b4fa8
                    gradient_colors = [
                        'class:ascii-line-0',  # Lightest magenta
                        'class:ascii-line-1',
                        'class:ascii-line-2',
                        'class:ascii-line-3',
                        'class:ascii-line-4',
                        'class:ascii-line-5',  # Darkest purple
                    ]
                    if line_number < len(gradient_colors):
                        return [(gradient_colors[line_number], line)]

                # "Maritime Intelligence Tool" line - title white, version grey
                if 'Maritime Intelligence Tool' in line:
                    # Split the line to style title and version separately
                    if 'v' in line:
                        parts = line.split('v')
                        return [
                            ('', parts[0]),  # "Maritime Intelligence Tool" in white
                            ('class:banner-text', 'v' + parts[1])  # version in grey
                        ]
                    return [('', line)]

                # Rest of banner - subdued grey
                if self.banner_end_line is not None and line_number <= self.banner_end_line:
                    return [('class:banner-text', line)]

                # Normal output (results)
                return [('', line)]
            except IndexError:
                return []
        return get_line_styles


class SlashCommandCompleter(Completer):
    """Auto-completion for slash parameters"""

    def __init__(self):
        self.command_params = {
            'vessel': ['/imo', '/format', '/output'],
            'search': ['/name', '/format', '/output'],
            'fleet': ['/company', '/format', '/output'],
            'batch': ['/imos', '/file', '/companies', '/company-file', '/format', '/output'],
            'format': [],
            'status': [],
            'clear': [],
            'help': [],
            'exit': [],
            'quit': [],
        }

    def get_completions(self, document: Document, complete_event: CompleteEvent):
        """Generate completions based on current input"""
        text = document.text_before_cursor
        words = text.split()

        if not words:
            return

        # First word - complete command names
        if len(words) == 1 and not text.endswith(' '):
            for cmd in self.command_params.keys():
                if cmd.startswith(words[0]):
                    yield Completion(cmd, start_position=-len(words[0]))

        # Slash parameter completion
        elif '/' in text:
            command = words[0] if words else ''
            if command in self.command_params:
                params = self.command_params[command]
                last_word = words[-1] if words else ''
                if last_word.startswith('/'):
                    for param in params:
                        if param.startswith(last_word):
                            yield Completion(param, start_position=-len(last_word))


class InteractiveShell:
    """Interactive shell with proper layout - output above, prompt below"""

    def __init__(self):
        self.client: Optional[EquasisClient] = None
        self.formatter = OutputFormatter()
        self.output_format = 'table'
        self.debug_mode = False
        self.logged_in = False
        self.running = True

        # Connection and status tracking
        self.connection_status = "Not connected"
        self.last_operation = ""

        # Color support
        self.color_support = Colors.supports_color()

        # Menu visibility flags
        self.show_help_menu = False
        self.show_slash_menu = False
        self.slash_menu_index = 0  # Selected index in slash menu

        # Loading indicator state
        self.is_loading = False
        self.loading_message = ""
        self.loading_detail = ""
        self.spinner_frame = 0
        self.shine_offset = 0

        # Create buffers
        # Output buffer with unlimited history (no max_line_count)
        self.output_buffer = Buffer(read_only=True, multiline=True)

        # Input buffer with command history enabled
        from prompt_toolkit.history import InMemoryHistory
        self.history = InMemoryHistory()
        self.input_buffer = Buffer(
            multiline=False,
            completer=SlashCommandCompleter(),
            history=self.history,  # Attach history object
            enable_history_search=True,
        )

        # Setup key bindings
        self.kb = KeyBindings()
        self._setup_key_bindings()

        # Create layout
        self.layout = self._create_layout()

        # Create application
        self.app = Application(
            layout=self.layout,
            key_bindings=self.kb,
            style=self._get_style(),
            full_screen=True,
            mouse_support=False,
        )

    def _setup_key_bindings(self):
        """Setup custom key bindings"""
        @self.kb.add('c-c')
        def _(event):
            """Ctrl+C: Cancel current input"""
            self.input_buffer.text = ''
            self.show_help_menu = False
            self.show_slash_menu = False

        @self.kb.add('c-d')
        def _(event):
            """Ctrl+D: Exit"""
            event.app.exit()

        @self.kb.add('enter', eager=True)
        def _(event):
            """Enter: Process command (menu just provides hints)"""
            # Close menus
            self.show_slash_menu = False
            self.show_help_menu = False
            self.slash_menu_index = 0
            # Process the command as typed
            self._process_input()

        @self.kb.add('tab')
        def _(event):
            """Tab: Select from slash menu"""
            if self.show_slash_menu:
                # Insert selected command from filtered list
                filtered_commands = self._get_filtered_commands()
                if filtered_commands and self.slash_menu_index < len(filtered_commands):
                    selected = filtered_commands[self.slash_menu_index][0]

                    buffer_text = self.input_buffer.text
                    slash_count = buffer_text.count('/')
                    is_primary = slash_count == 0 or (slash_count == 1 and buffer_text.startswith('/'))

                    if is_primary:
                        # Primary command - replace everything (including leading / if present)
                        self.input_buffer.text = selected + ' '
                        self.input_buffer.cursor_position = len(self.input_buffer.text)
                    else:
                        # Parameter - replace from last / onwards
                        last_slash_pos = buffer_text.rfind('/')
                        if last_slash_pos >= 0:
                            new_text = buffer_text[:last_slash_pos] + '/' + selected + ' '
                            self.input_buffer.text = new_text
                            self.input_buffer.cursor_position = len(new_text)

                self.show_slash_menu = False
                self.slash_menu_index = 0

        # Command history navigation with Up/Down arrows
        # Use eager=True to make these bindings take priority over buffer defaults
        @self.kb.add('up', eager=True)
        def _(event):
            """Up arrow: Navigate menu, history, or scroll output"""
            from prompt_toolkit.application import get_app
            # Check if we're in scroll mode (output buffer focused)
            if get_app().layout.has_focus(self.output_buffer):
                # Scroll output up one line
                self.output_buffer.cursor_up()
            elif self.show_slash_menu:
                # Navigate slash menu using filtered list count - DON'T modify buffer
                filtered_commands = self._get_filtered_commands()
                if filtered_commands:
                    self.slash_menu_index = max(0, self.slash_menu_index - 1)
                # Don't do anything else - prevents buffer modification
            else:
                buff = event.app.current_buffer
                # Use the history object directly to get previous item
                history_strings = list(buff.history.get_strings())
                if history_strings:
                    # Get current working index
                    if not hasattr(self, '_history_index'):
                        self._history_index = len(history_strings)

                    self._history_index = max(0, self._history_index - 1)
                    if self._history_index < len(history_strings):
                        buff.text = history_strings[self._history_index]
                        buff.cursor_position = len(buff.text)

        @self.kb.add('down', eager=True)
        def _(event):
            """Down arrow: Navigate menu, history, or scroll output"""
            from prompt_toolkit.application import get_app
            # Check if we're in scroll mode (output buffer focused)
            if get_app().layout.has_focus(self.output_buffer):
                # Scroll output down one line
                self.output_buffer.cursor_down()
            elif self.show_slash_menu:
                # Navigate slash menu using filtered list count - DON'T modify buffer
                filtered_commands = self._get_filtered_commands()
                if filtered_commands:
                    self.slash_menu_index = min(len(filtered_commands) - 1, self.slash_menu_index + 1)
                # Don't do anything else - prevents buffer modification
            else:
                buff = event.app.current_buffer
                # Use the history object directly to get next item
                history_strings = list(buff.history.get_strings())
                if history_strings and hasattr(self, '_history_index'):
                    self._history_index = min(len(history_strings), self._history_index + 1)

                    if self._history_index < len(history_strings):
                        buff.text = history_strings[self._history_index]
                        buff.cursor_position = len(buff.text)
                    else:
                        # At the end of history, show empty prompt
                        buff.text = ''
                        buff.cursor_position = 0

        # Scrolling keys for output buffer
        # Multiple options for users without Fn key
        @self.kb.add('pageup')
        def _(event):
            """Page Up: Scroll output up (requires Fn on Mac)"""
            for _ in range(10):
                self.output_buffer.cursor_up()

        @self.kb.add('pagedown')
        def _(event):
            """Page Down: Scroll output down (requires Fn on Mac)"""
            for _ in range(10):
                self.output_buffer.cursor_down()

        @self.kb.add('s-up')  # Shift+Up
        def _(event):
            """Shift+Up: Scroll output up one line"""
            self.output_buffer.cursor_up()

        @self.kb.add('s-down')  # Shift+Down
        def _(event):
            """Shift+Down: Scroll output down one line"""
            self.output_buffer.cursor_down()

        # Scroll mode: Press Esc to enter scroll mode (vim/less-style)
        @self.kb.add('escape')
        def _(event):
            """Esc: Enter scroll mode (focus output buffer)"""
            from prompt_toolkit.application import get_app
            # Only enter scroll mode if not showing menus
            if not self.show_help_menu and not self.show_slash_menu:
                get_app().layout.focus(self.output_buffer)
                self.last_operation = "Scroll mode • Press i or type to return to input"

        # Return to input mode: Press 'i' or any letter starts typing
        @self.kb.add('i')
        def _(event):
            """i: Return to input mode from scroll mode"""
            from prompt_toolkit.application import get_app
            # Check if we're focused on output buffer
            if get_app().layout.has_focus(self.output_buffer):
                # Return to input mode
                get_app().layout.focus(self.input_buffer)
                self.last_operation = ""
            else:
                # Already in input, insert 'i'
                self.input_buffer.insert_text('i')

        # Vim-style scrolling (work in both modes but better in scroll mode)
        @self.kb.add('c-k')  # Ctrl+K
        def _(event):
            """Ctrl+K: Scroll output up"""
            for _ in range(5):
                self.output_buffer.cursor_up()
            event.app.invalidate()

        @self.kb.add('c-j')  # Ctrl+J
        def _(event):
            """Ctrl+J: Scroll output down"""
            for _ in range(5):
                self.output_buffer.cursor_down()
            event.app.invalidate()

        @self.kb.add('?')
        def _(event):
            """? key: Toggle help menu (simple on/off)"""
            self.show_help_menu = not self.show_help_menu
            self.show_slash_menu = False

        @self.kb.add('/')
        def _(event):
            """/ key: Insert / and show slash menu"""
            self.input_buffer.insert_text('/')
            self.show_slash_menu = True
            self.show_help_menu = False
            self.slash_menu_index = 0

        @self.kb.add('backspace')
        def _(event):
            """Backspace: Hide slash menu if / is deleted, reset index on filter change"""
            buff = event.app.current_buffer
            # Delete character first
            if buff.text:
                buff.delete_before_cursor(count=1)
            # Check if buffer no longer starts with /
            if not buff.text.startswith('/'):
                self.show_slash_menu = False
                self.slash_menu_index = 0
            else:
                # Reset index when filter changes
                self.slash_menu_index = 0

    def _create_help_menu_content(self):
        """Generate help menu text"""
        return FormattedText([
            ('class:menu-text', '/              For commands\n'),
            ('class:menu-text', 'Up/Down        Navigate command history\n'),
            ('class:menu-text', 'Esc            Enter scroll mode (navigate output)\n'),
            ('class:menu-text', 'i              Return to input mode\n'),
            ('class:menu-text', 'Ctrl+K/J       Quick scroll (5 lines)\n'),
            ('class:menu-text', 'Page Up/Down   Scroll output\n'),
            ('class:menu-text', 'Shift+Up/Down  Scroll output (one line)\n'),
            ('class:menu-text', '\n'),
            ('class:menu-text', 'Ctrl+C         Cancel current input\n'),
            ('class:menu-text', 'Ctrl+D         Exit'),
        ])

    def _get_filtered_commands(self):
        """Get list of commands/parameters filtered by current input"""
        buffer_text = self.input_buffer.text

        # Check if this is at the start (main commands) or after a command (parameters)
        parts = buffer_text.split()

        # If we're at the beginning or typing the first /command
        if len(parts) <= 1 or not buffer_text.count('/'):
            all_commands = [
                ('vessel', 'Get vessel information by IMO'),
                ('search', 'Search vessels by name or IMO'),
                ('fleet', 'Get company fleet information'),
                ('batch', 'Process multiple vessels/companies'),
                ('format', 'Set default output format'),
                ('status', 'Show connection status'),
                ('clear', 'Clear output screen'),
                ('help', 'Show detailed help for command'),
                ('exit', 'Exit interactive mode'),
            ]

            if buffer_text.startswith('/'):
                filter_text = buffer_text[1:].lower()
                if filter_text:
                    return [(cmd, desc) for cmd, desc in all_commands if filter_text in cmd.lower()]
                else:
                    return all_commands
            return all_commands

        # If typing a parameter (second / or later)
        else:
            # Determine which command was typed to show relevant parameters
            first_part = parts[0].lower()

            # Define parameters for each command
            if first_part == 'vessel':
                params = [
                    ('imo', 'IMO number (required)'),
                    ('format', 'Output format: table, json, csv'),
                    ('output', 'Save to file'),
                ]
            elif first_part == 'search':
                params = [
                    ('name', 'Vessel name to search'),
                    ('imo', 'IMO number to search'),
                    ('format', 'Output format: table, json, csv'),
                    ('output', 'Save to file'),
                ]
            elif first_part == 'fleet':
                params = [
                    ('company', 'Company name (required)'),
                    ('format', 'Output format: table, json, csv'),
                    ('output', 'Save to file'),
                ]
            elif first_part == 'batch':
                params = [
                    ('imos', 'Comma-separated IMO numbers'),
                    ('file', 'File with IMO numbers'),
                    ('companies', 'Comma-separated company names'),
                    ('company-file', 'File with company names'),
                    ('format', 'Output format: table, json, csv'),
                    ('output', 'Save to file'),
                ]
            else:
                # Default common parameters
                params = [
                    ('format', 'Output format: table, json, csv'),
                    ('output', 'Save to file'),
                ]

            # Filter parameters based on what's being typed after the last /
            last_slash_pos = buffer_text.rfind('/')
            if last_slash_pos >= 0:
                filter_text = buffer_text[last_slash_pos + 1:].lower()
                if filter_text:
                    return [(cmd, desc) for cmd, desc in params if filter_text in cmd.lower()]
                else:
                    return params

            return params

    def _create_slash_menu_content(self):
        """Generate slash command menu text with selection highlighting and filtering"""
        commands = self._get_filtered_commands()

        # Ensure index is within bounds
        if self.slash_menu_index >= len(commands):
            self.slash_menu_index = len(commands) - 1 if commands else 0

        # Determine if we're showing primary commands or parameters
        buffer_text = self.input_buffer.text
        slash_count = buffer_text.count('/')
        is_primary = slash_count == 0 or (slash_count == 1 and buffer_text.startswith('/'))

        # Find max command length for alignment
        max_cmd_len = max(len(cmd) for cmd, _ in commands) if commands else 0
        # Add 1 for the / prefix on parameters
        if not is_primary:
            max_cmd_len += 1

        lines = []
        for i, (cmd, desc) in enumerate(commands):
            # Format: primary commands have no /, parameters have /
            prefix = '' if is_primary else '/'
            full_cmd = f'{prefix}{cmd}'

            # Calculate padding to align descriptions
            padding = ' ' * (max_cmd_len - len(full_cmd) + 4)

            if i == self.slash_menu_index:
                # Highlighted item - colored
                lines.append(('class:menu-item-selected', full_cmd))
                lines.append(('class:menu-desc-selected', f'{padding}{desc}'))
            else:
                # Normal item - grey
                lines.append(('class:menu-item-unselected', full_cmd))
                lines.append(('class:menu-desc-unselected', f'{padding}{desc}'))

            if i < len(commands) - 1:
                lines.append(('', '\n'))

        return FormattedText(lines)

    def _create_layout(self):
        """Create the application layout"""
        # Output window (scrollable, takes most space)
        output_window = Window(
            content=BufferControl(
                buffer=self.output_buffer,
                lexer=OutputLexer(),  # Use custom lexer to style user prompts
            ),
            wrap_lines=True,
            # Scrollbar is added via ScrollbarMargin in prompt_toolkit
            right_margins=[ScrollbarMargin(display_arrows=True)],
        )

        # Separator line
        separator = Window(
            height=1,
            char='─',
            style='class:separator',
        )

        # Input prompt window (fixed at bottom)
        input_window = Window(
            content=BufferControl(
                buffer=self.input_buffer,
                focusable=True,
            ),
            height=1,
            dont_extend_height=True,
        )

        # Prompt character ("❯ ")
        prompt_window = Window(
            content=FormattedTextControl(
                lambda: FormattedText([('class:prompt', '❯ ')])
            ),
            width=2,
            dont_extend_width=True,
        )

        # Bottom toolbar (status bar)
        def get_toolbar_text():
            parts = []
            if self.logged_in:
                parts.append(('class:status-connected', '● Connected'))
            else:
                parts.append(('class:status-disconnected', '○ Not connected'))

            parts.append(('class:status-dim', f' • Format: '))
            parts.append(('class:status-format', self.output_format))

            if self.last_operation:
                parts.append(('class:status-dim', f' • {self.last_operation}'))
            else:
                parts.append(('class:status-dim', ' • Press ? for help'))

            return FormattedText(parts)

        toolbar = Window(
            content=FormattedTextControl(get_toolbar_text),
            height=1,
            style='class:bottom-toolbar',
        )

        # Help menu (ephemeral, appears below prompt)
        help_menu = ConditionalContainer(
            Window(
                content=FormattedTextControl(self._create_help_menu_content),
                height=9,
                style='class:menu',
            ),
            filter=Condition(lambda: self.show_help_menu),
        )

        # Slash command menu (ephemeral, appears below prompt)
        slash_menu = ConditionalContainer(
            Window(
                content=FormattedTextControl(self._create_slash_menu_content),
                height=9,
                style='class:menu',
            ),
            filter=Condition(lambda: self.show_slash_menu),
        )

        # Loading indicator (appears above input when processing)
        def get_loading_text():
            parts = []
            if self.is_loading:
                # Animated spinner
                spinner_chars = ['◐', '◓', '◑', '◒']
                spinner = spinner_chars[self.spinner_frame % len(spinner_chars)]
                parts.append(('class:loading-spinner', f'{spinner} '))

                # Shine effect on message text - sweeping highlight
                message = self.loading_message
                if message:
                    # Create shine effect with a bright highlight sweeping left to right
                    shined_text = []
                    shine_width = 4  # Width of the shine effect
                    # Position wraps around with padding so shine fully exits before restarting
                    shine_pos = (self.shine_offset % (len(message) + shine_width * 2)) - shine_width

                    for i, char in enumerate(message):
                        # Calculate distance from shine center
                        distance = i - shine_pos

                        # Shine gradient: bright in center, fades out
                        if distance == 0:
                            # Center of shine - brightest (white/very bright)
                            shined_text.append(('class:loading-message-shine-center', char))
                        elif distance in [1, -1]:
                            # Near shine - bright blue
                            shined_text.append(('class:loading-message-shine-near', char))
                        elif distance in [2, -2]:
                            # Edge of shine - normal blue
                            shined_text.append(('class:loading-message-shine-edge', char))
                        else:
                            # Outside shine - dimmed
                            shined_text.append(('class:loading-message', char))
                    parts.extend(shined_text)

                if self.loading_detail:
                    parts.append(('class:loading-detail', f'  {self.loading_detail}'))
            return FormattedText(parts)

        loading_indicator = ConditionalContainer(
            Window(
                content=FormattedTextControl(get_loading_text),
                height=1,
                style='class:loading',
            ),
            filter=Condition(lambda: self.is_loading),
        )

        # Combine prompt + input on same line
        from prompt_toolkit.layout.containers import VSplit
        input_line = VSplit([prompt_window, input_window])

        # Stack everything vertically
        root_container = HSplit([
            output_window,      # Top: scrollable output
            separator,          # Separator line
            loading_indicator,  # Loading status (conditional)
            input_line,         # Middle: prompt + input
            help_menu,          # Ephemeral help menu (conditional)
            slash_menu,         # Ephemeral slash menu (conditional)
            separator,          # Separator line
            toolbar,            # Bottom: status bar
        ])

        return Layout(root_container, focused_element=self.input_buffer)

    def _get_style(self):
        """Define color style for prompt_toolkit"""
        return Style.from_dict({
            # Separator
            'separator': 'fg:#5c6370 bg:default',

            # Bottom toolbar
            'bottom-toolbar': 'fg:#abb2bf bg:default noreverse',

            # Status bar colors
            'status-connected': 'fg:#98c379 bg:default noreverse',
            'status-disconnected': 'fg:#e06c75 bg:default noreverse',
            'status-dim': 'fg:#5c6370 bg:default noreverse',
            'status-format': 'fg:#61afef bg:default noreverse',
            'status-warning': 'fg:#e5c07b bg:default noreverse',
            'prompt': 'fg:#abb2bf bg:default noreverse',  # White/default color

            # Output buffer
            'user-prompt': 'fg:#5c6370 bg:default noreverse',  # Subdued grey for user prompts
            'banner-text': 'fg:#5c6370 bg:default noreverse',  # Subdued grey for banner

            # ASCII art gradient (cyan to blue - heavier on blue)
            'ascii-line-0': 'fg:#56b6c2 bg:default noreverse',  # Cyan (top)
            'ascii-line-1': 'fg:#5caec8 bg:default noreverse',  # Cyan-blue
            'ascii-line-2': 'fg:#5fa9d5 bg:default noreverse',  # More blue
            'ascii-line-3': 'fg:#60abe0 bg:default noreverse',  # Much more blue
            'ascii-line-4': 'fg:#61aeea bg:default noreverse',  # Almost full blue
            'ascii-line-5': 'fg:#61afef bg:default noreverse',  # Blue (matches prompt)

            # Ephemeral menus
            'menu': 'bg:default noreverse',
            'menu-item-unselected': 'fg:#5c6370 bg:default noreverse',  # Grey when not selected
            'menu-desc-unselected': 'fg:#5c6370 bg:default noreverse',  # Grey when not selected
            'menu-item-selected': 'fg:#61afef bold bg:default noreverse',  # Blue when selected
            'menu-desc-selected': 'fg:#61afef bg:default noreverse',  # Blue when selected (same as command)
            'menu-text': 'fg:#5c6370 bg:default noreverse',  # For help menu

            # Loading indicator
            'loading': 'bg:default noreverse',
            'loading-spinner': 'fg:#61afef bg:default noreverse',  # Blue spinner (same as prompt)
            'loading-message': 'fg:#61afef bg:default noreverse',  # Same blue as prompt (outside shine)
            'loading-message-shine-edge': 'fg:#61afef bg:default noreverse',  # Same blue (edge of shine)
            'loading-message-shine-near': 'fg:#7dc4f4 bold bg:default noreverse',  # Bright blue (near shine)
            'loading-message-shine-center': 'fg:#ffffff bold bg:default noreverse',  # White/very bright (center of shine)
            'loading-detail': 'fg:#5c6370 bg:default noreverse',  # Grey for detail messages

            # Completion menu
            'completion-menu': 'bg:default noreverse',
            'completion-menu.completion': 'fg:#abb2bf bg:default noreverse',
            'completion-menu.completion.current': 'fg:#61afef bold bg:default noreverse',
            'completion-menu.meta': 'fg:#5c6370 bg:default noreverse',
            'scrollbar.background': 'bg:default noreverse',
            'scrollbar.button': 'bg:default noreverse',
        })

    def _append_output(self, text: str):
        """Append text to output buffer"""
        # Temporarily make buffer writable to append text
        self.output_buffer.read_only = lambda: False
        current = self.output_buffer.text
        new_text = current + text + '\n' if current else text + '\n'
        self.output_buffer.set_document(Document(text=new_text, cursor_position=len(new_text)))
        self.output_buffer.read_only = lambda: True  # Make read-only again

    def _process_input(self):
        """Process the current input command"""
        command_text = self.input_buffer.text.strip()

        if not command_text:
            return

        # Add to history before clearing
        self.history.append_string(command_text)

        # Reset history index for next navigation
        self._history_index = len(list(self.history.get_strings()))

        # Clear input immediately for better UX
        self.input_buffer.text = ''

        # Show the command in output with special prefix for styling
        # Use a unique prefix that can be styled by a lexer
        self._append_output(f"❯ {command_text}")

        # Handle special commands
        if command_text == 'exit' or command_text == 'quit':
            self.app.exit()
            return

        if command_text == 'clear':
            # Clear the output buffer (make it writable first)
            self.output_buffer.read_only = lambda: False
            self.output_buffer.set_document(Document(text='', cursor_position=0))
            self.output_buffer.read_only = lambda: True
            return

        # Process command in background task to allow UI updates
        async def process_async():
            import asyncio

            # Show loading indicator
            self.is_loading = True
            self.loading_message = "Processing..."
            self.loading_detail = ""
            self.spinner_frame = 0
            self.shine_offset = 0
            self.app.invalidate()

            # Animation task to update spinner and shine
            animation_counter = 0
            async def animate():
                nonlocal animation_counter
                while self.is_loading:
                    await asyncio.sleep(0.1)  # 10 FPS animation
                    animation_counter += 1

                    # Update spinner every 2 frames (slower rotation)
                    if animation_counter % 2 == 0:
                        self.spinner_frame += 1

                    # Update shine every frame (smooth sweep)
                    self.shine_offset += 1
                    self.app.invalidate()

            # Start animation task
            animation_task = asyncio.create_task(animate())

            # Run the synchronous command in executor
            loop = asyncio.get_event_loop()

            try:
                await loop.run_in_executor(None, self._process_command, command_text)
            finally:
                # Hide loading indicator
                self.is_loading = False
                self.loading_message = ""
                self.loading_detail = ""
                self.app.invalidate()

                # Wait for animation to stop
                await animation_task

        # Create background task
        self.app.create_background_task(process_async())

    def _process_command(self, line: str):
        """Process a command line"""
        # Parse command
        parts = line.split(maxsplit=1)
        if not parts:
            return

        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ''

        # Route to command handlers
        command_map = {
            'vessel': self._cmd_vessel,
            'search': self._cmd_search,
            'fleet': self._cmd_fleet,
            'batch': self._cmd_batch,
            'format': self._cmd_format,
            'status': self._cmd_status,
            'help': self._cmd_help,
        }

        handler = command_map.get(command)
        if handler:
            # Redirect stdout/stderr to capture any print statements
            import io
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()

            try:
                handler(args)

                # Get any captured output
                stdout_output = sys.stdout.getvalue()
                stderr_output = sys.stderr.getvalue()

                if stdout_output:
                    self._append_output(stdout_output.rstrip())
                if stderr_output:
                    self._append_output(stderr_output.rstrip())
            finally:
                # Restore stdout/stderr
                sys.stdout = old_stdout
                sys.stderr = old_stderr
        else:
            self._append_output(f"Unknown command: {command}")
            self._append_output("Type 'help' for available commands")

    def parse_slash_command(self, line: str, expected_params: Dict[str, bool]) -> Tuple[Dict[str, str], bool]:
        """Parse slash parameters"""
        params = {}

        patterns = [
            r'/(\w+)\s+"([^"]+)"',
            r'/(\w+)\s+"([^"]+)"',
            r'/(\w+)\s+"([^"]+)"',
            r"/(\w+)\s+'([^']+)'",
            r'/(\w+)\s+(\S+)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, line)
            for match in matches:
                param = match[0]
                value = match[1]
                if param not in params:
                    params[param] = value

        all_required_present = all(
            param in params
            for param, required in expected_params.items()
            if required
        )

        return params, all_required_present

    def ensure_authenticated(self) -> bool:
        """Ensure client is authenticated"""
        if not self.client:
            credential_manager = get_credential_manager()
            username, password = credential_manager.get_credentials()

            if not username or not password:
                self._append_output("\nNo credentials found. Please configure credentials first.")
                self._append_output("Run: equasis configure --setup")
                return False

            try:
                self.loading_message = "Connecting..."
                self.loading_detail = "Authenticating with Equasis"
                self.last_operation = "Connecting..."

                self.client = EquasisClient(username, password)
                self.logged_in = self.client.login()

                if self.logged_in:
                    self.connection_status = "Connected"
                    self.last_operation = ""
                else:
                    self._append_output("✗ Authentication failed")
                    self.last_operation = "Auth failed"
                    return False

            except Exception as e:
                self._append_output(f"✗ Connection error: {e}")
                self.last_operation = "Connection error"
                return False

        if not self.logged_in:
            self.last_operation = "Reconnecting..."
            self.logged_in = self.client.login()
            self.last_operation = "" if self.logged_in else "Reconnect failed"

        return self.logged_in

    def _cmd_vessel(self, args: str):
        """Handle vessel command"""
        expected_params = {'imo': True, 'format': False, 'output': False}
        params, all_required = self.parse_slash_command(args, expected_params)

        if not all_required:
            self._append_output("Error: Missing required parameter /imo")
            self._append_output("Usage: vessel /imo <IMO_NUMBER> [/format table|json|csv]")
            return

        if not self.ensure_authenticated():
            return

        output_format = params.get('format', self.output_format)
        output_file = params.get('output')

        try:
            self.loading_message = "Osinting..."
            self.loading_detail = f"Searching IMO {params['imo']}"
            self.last_operation = f"Fetching IMO {params['imo']}..."

            vessel = self.client.search_vessel_by_imo(params['imo'])

            if vessel:
                output = self.formatter.format_vessel_info(vessel, output_format)
                if output_file:
                    with open(output_file, 'w') as f:
                        f.write(output)
                    self._append_output(f"✓ Vessel data saved to {output_file}")
                else:
                    self._append_output(output)
                self.last_operation = f"✓ Vessel {params['imo']} found"
            else:
                self._append_output(f"No vessel found with IMO: {params['imo']}")
                self.last_operation = f"✗ Vessel {params['imo']} not found"

        except Exception as e:
            self._append_output(f"Error: {e}")
            self.last_operation = f"✗ Error"

    def _cmd_search(self, args: str):
        """Handle search command"""
        expected_params = {'name': False, 'imo': False, 'format': False, 'output': False}
        params, _ = self.parse_slash_command(args, expected_params)

        # Require either /name or /imo
        if not params.get('name') and not params.get('imo'):
            self._append_output("Error: Missing required parameter /name or /imo")
            return

        if not self.ensure_authenticated():
            return

        output_format = params.get('format', self.output_format)

        try:
            if params.get('imo'):
                # Search by IMO
                self.last_operation = f"Searching IMO '{params['imo']}'..."
                vessels = self.client.search_vessel_by_name(params['imo'])
            else:
                # Search by name
                self.last_operation = f"Searching '{params['name']}'..."
                vessels = self.client.search_vessel_by_name(params['name'])

            if vessels:
                output = self.formatter.format_simple_vessel_list(vessels, output_format)
                self._append_output(output)
                self.last_operation = f"✓ Found {len(vessels)} vessel(s)"
            else:
                search_term = params.get('imo') or params.get('name')
                self._append_output(f"No vessels found matching: {search_term}")
                self.last_operation = "✗ No vessels found"

        except Exception as e:
            self._append_output(f"Error: {e}")
            self.last_operation = "✗ Error"

    def _cmd_fleet(self, args: str):
        """Handle fleet command"""
        self._append_output("Fleet command - to be implemented")

    def _cmd_batch(self, args: str):
        """Handle batch command"""
        self._append_output("Batch command - to be implemented")

    def _cmd_format(self, args: str):
        """Handle format command"""
        args = args.strip().lower()
        if args in ['table', 'json', 'csv']:
            self.output_format = args
            self.last_operation = f"Format set to {args}"
            self._append_output(f"Default output format set to: {args}")
        else:
            self._append_output("Invalid format. Use: table, json, or csv")

    def _cmd_status(self, args: str):
        """Handle status command"""
        self.last_operation = ""
        self._append_output("\nSession Status:")
        status_text = 'Connected' if self.logged_in else 'Not connected'
        self._append_output(f"  Authentication: {status_text}")
        self._append_output(f"  Default Format: {self.output_format}")
        self._append_output(f"  Debug Mode: {self.debug_mode}\n")

    def _cmd_help(self, args: str):
        """Handle help command"""
        self._append_output("\n" + "=" * 60)
        self._append_output("EQUASIS CLI - INTERACTIVE MODE HELP")
        self._append_output("=" * 60)
        self._append_output("\nCommands:")
        self._append_output("  vessel /imo <NUMBER>     Get vessel information")
        self._append_output("  search /name \"<NAME>\"    Search vessels by name")
        self._append_output("  search /imo <NUMBER>     Search by IMO number")
        self._append_output("  fleet /company \"<NAME>\"  Get fleet information")
        self._append_output("  format <table|json|csv>  Set output format")
        self._append_output("  status                   Show session status")
        self._append_output("  clear                    Clear output")
        self._append_output("  help                     Show this help")
        self._append_output("  exit                     Exit interactive mode")
        self._append_output("\nKeyboard shortcuts:")
        self._append_output("  ?              Show quick help")
        self._append_output("  Up/Down        Navigate command history")
        self._append_output("  Page Up/Down   Scroll output")
        self._append_output("  Shift+Up/Down  Scroll output (one line)")
        self._append_output("  Ctrl+C         Cancel current input")
        self._append_output("  Ctrl+D         Exit")
        self._append_output("=" * 60 + "\n")

    def start(self):
        """Start the interactive shell"""
        # Redirect ALL logging to our output buffer instead of console
        class OutputBufferHandler(logging.Handler):
            def __init__(self, shell):
                super().__init__()
                self.shell = shell

            def emit(self, record):
                try:
                    msg = self.format(record)
                    self.shell._append_output(msg)
                except:
                    pass  # Silently fail if we can't append

        # Remove ALL existing handlers from root logger and add our custom one
        root_logger = logging.getLogger()
        root_logger.handlers = []
        root_logger.addHandler(OutputBufferHandler(self))
        root_logger.setLevel(logging.WARNING)

        # Also set client logger specifically
        client_logger = logging.getLogger('equasis_cli.client')
        client_logger.handlers = []
        client_logger.addHandler(OutputBufferHandler(self))
        client_logger.setLevel(logging.WARNING)

        # Show banner in output buffer
        banner_text = get_interactive_banner()
        self._append_output(banner_text)

        # Run the application
        try:
            self.app.run()
        except KeyboardInterrupt:
            pass
        except EOFError:
            pass

        self._append_output("\nGoodbye!")


def main():
    """Entry point for interactive shell"""
    shell = InteractiveShell()
    shell.start()


if __name__ == '__main__':
    main()
