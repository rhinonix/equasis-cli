"""
Banner and startup information display for Equasis CLI
"""

import sys
import os
from typing import Optional

# ANSI color codes for terminal formatting
class Colors:
    # Bright text colors (for emphasis)
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'

    # Dim/subdued colors for banner text
    DIM_RED = '\033[31m'        # Darker red
    DIM_GREEN = '\033[32m'      # Darker green
    DIM_YELLOW = '\033[33m'     # Darker yellow
    DIM_BLUE = '\033[34m'       # Darker blue
    DIM_MAGENTA = '\033[35m'    # Darker magenta
    DIM_CYAN = '\033[36m'       # Darker cyan
    DIM_WHITE = '\033[37m'      # Darker white/gray
    DIM = '\033[2m'             # Dim/faint text

    # Text styles
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    # Reset
    RESET = '\033[0m'

    @staticmethod
    def supports_color():
        """Check if terminal supports color"""
        return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

# Version information - should match setup.py
__version__ = "2.0.0"

BANNER_ART = r"""
                               _                 ___
  ___  ____ ___  ______ ______(_)____      _____/ (_)
 / _ \/ __ `/ / / / __ `/ ___/ / ___/_____/ ___/ / /
/  __/ /_/ / /_/ / /_/ (__  ) (__  )_____/ /__/ / /
\___/\__, /\__,_/\__,_/____/_/____/      \___/_/_/
       /_/

            Maritime Intelligence Tool
"""

def get_version() -> str:
    """Get the current version string"""
    return __version__

def check_credentials() -> bool:
    """Check if Equasis credentials are configured"""
    try:
        from .credentials import get_credential_manager
        credential_manager = get_credential_manager()
        username, password = credential_manager.get_credentials()
        return bool(username and password)
    except ImportError:
        # Fallback to environment variables if credential module not available
        username = os.getenv('EQUASIS_USERNAME')
        password = os.getenv('EQUASIS_PASSWORD')
        return bool(username and password)

def display_credentials_note() -> None:
    """Display a colorized credentials setup note"""
    color_support = Colors.supports_color()

    if color_support:
        # Fully colorized note
        print(f"{Colors.YELLOW}{Colors.BOLD}┌{'─' * 76}┐{Colors.RESET}")
        print(f"{Colors.YELLOW}│{Colors.RESET}{Colors.YELLOW} CREDENTIALS REQUIRED                                                      │{Colors.RESET}")
        print(f"{Colors.YELLOW}│{Colors.RESET}{Colors.YELLOW}                                                                          │{Colors.RESET}")
        print(f"{Colors.YELLOW}│{Colors.RESET}{Colors.YELLOW} To use this tool, set your Equasis credentials:                         │{Colors.RESET}")
        print(f"{Colors.YELLOW}│{Colors.RESET}{Colors.YELLOW}                                                                          │{Colors.RESET}")
        print(f"{Colors.YELLOW}│{Colors.RESET}{Colors.YELLOW}   Option 1 (Recommended): Use credential manager:                       │{Colors.RESET}")
        print(f"{Colors.YELLOW}│{Colors.RESET}{Colors.YELLOW}     equasis configure --setup                                            │{Colors.RESET}")
        print(f"{Colors.YELLOW}│{Colors.RESET}{Colors.YELLOW}                                                                          │{Colors.RESET}")
        print(f"{Colors.YELLOW}│{Colors.RESET}{Colors.YELLOW}   Option 2: Set environment variables:                                   │{Colors.RESET}")
        print(f"{Colors.YELLOW}│{Colors.RESET}{Colors.YELLOW}     export EQUASIS_USERNAME=your_username                                │{Colors.RESET}")
        print(f"{Colors.YELLOW}│{Colors.RESET}{Colors.YELLOW}     export EQUASIS_PASSWORD=your_password                                │{Colors.RESET}")
        print(f"{Colors.YELLOW}│{Colors.RESET}{Colors.YELLOW}                                                                          │{Colors.RESET}")
        print(f"{Colors.YELLOW}│{Colors.RESET}{Colors.YELLOW}   Option 3: Use command line flags:                                      │{Colors.RESET}")
        print(f"{Colors.YELLOW}│{Colors.RESET}{Colors.YELLOW}     equasis --username your_user --password your_pass vessel --imo 123  │{Colors.RESET}")
        print(f"{Colors.YELLOW}│{Colors.RESET}{Colors.YELLOW}                                                                          │{Colors.RESET}")
        print(f"{Colors.YELLOW}└{'─' * 76}┘{Colors.RESET}")
    else:
        print("┌" + "─" * 76 + "┐")
        print("│ CREDENTIALS REQUIRED                                                   │")
        print("│                                                                        │")
        print("│ To use this tool, set your Equasis credentials:                       │")
        print("│                                                                        │")
        print("│   Option 1 (Recommended): Use credential manager:                     │")
        print("│     equasis configure --setup                                          │")
        print("│                                                                        │")
        print("│   Option 2: Set environment variables:                                │")
        print("│     export EQUASIS_USERNAME=your_username                             │")
        print("│     export EQUASIS_PASSWORD=your_password                             │")
        print("│                                                                        │")
        print("│   Option 3: Use command line flags:                                   │")
        print("│     equasis --username your_user --password your_pass vessel --imo 123│")
        print("│                                                                        │")
        print("└" + "─" * 76 + "┘")
    print()

def display_banner(show_banner: bool = True, show_info: bool = True) -> None:
    """
    Display startup banner and information

    Args:
        show_banner: Whether to show ASCII art banner
        show_info: Whether to show startup information and disclaimers
    """
    if not show_banner and not show_info:
        return

    # Only display banner if output is going to a terminal (not piped)
    if not sys.stdout.isatty():
        return

    if show_banner:
        print(BANNER_ART)
        color_support = Colors.supports_color()
        if color_support:
            print(f"                            {Colors.DIM}Version {__version__}{Colors.RESET}")
        else:
            print(f"                            Version {__version__}")
        print()

    if show_info:
        color_support = Colors.supports_color()

        # Feature highlights with subdued bullets
        if color_support:
            print(f"{Colors.DIM_BLUE}•{Colors.RESET} {Colors.DIM}Professional maritime intelligence tool for Equasis data{Colors.RESET}")
            print(f"{Colors.DIM_BLUE}•{Colors.RESET} {Colors.DIM}Comprehensive vessel profiles with {Colors.DIM_WHITE}50+ data points{Colors.RESET}")
            print(f"{Colors.DIM_BLUE}•{Colors.RESET} {Colors.DIM}Management companies, PSC inspections, historical data{Colors.RESET}")
        else:
            print("• Professional maritime intelligence tool for Equasis data")
            print("• Comprehensive vessel profiles with 50+ data points")
            print("• Management companies, PSC inspections, historical data")
        print()

        # Important disclaimers with properly aligned border
        border_width = 78
        if color_support:
            print(f"{Colors.DIM_RED}┌" + "─" * border_width + f"┐{Colors.RESET}")
            # Header - centered
            header = "IMPORTANT DISCLAIMERS"
            padding = (border_width - len(header)) // 2
            print(f"{Colors.DIM_RED}│{Colors.RESET}" + " " * padding + f"{Colors.DIM}{header}{Colors.RESET}" + " " * (border_width - len(header) - padding) + f"{Colors.DIM_RED}│{Colors.RESET}")
            print(f"{Colors.DIM_RED}├" + "─" * border_width + f"┤{Colors.RESET}")

            # Content lines - each padded to exact width
            lines = [
                " • This tool is NOT associated with, endorsed by, or affiliated with",
                "   Equasis",
                " • May break if Equasis changes their website structure",
                " • Users must monitor for changes and update parsing logic",
                "   accordingly",
                " • Respect Equasis Terms of Service and rate limiting",
                " • Use for legitimate maritime research and safety purposes only"
            ]

            for line in lines:
                padding_needed = border_width - len(line)
                if line.startswith(" •"):
                    # Bullet point line - fully subdued
                    plain_text = line.replace(" •", " •")  # Keep bullet as plain text
                    if "NOT" in plain_text:
                        # Even "NOT" should be subdued
                        plain_text = plain_text.replace("NOT", "NOT")
                    formatted_line = f"{Colors.DIM_RED}│{Colors.RESET} {Colors.DIM}•{Colors.RESET} {Colors.DIM}{plain_text[3:]}{Colors.RESET}"
                    print(formatted_line + " " * padding_needed + f"{Colors.DIM_RED}│{Colors.RESET}")
                else:
                    # Continuation line - fully subdued
                    formatted_line = f"{Colors.DIM_RED}│{Colors.RESET}{Colors.DIM}{line}{Colors.RESET}"
                    print(formatted_line + " " * padding_needed + f"{Colors.DIM_RED}│{Colors.RESET}")

            print(f"{Colors.DIM_RED}└" + "─" * border_width + f"┘{Colors.RESET}")
        else:
            print("┌" + "─" * border_width + "┐")
            header = "IMPORTANT DISCLAIMERS"
            padding = (border_width - len(header)) // 2
            print("│" + " " * padding + header + " " * (border_width - len(header) - padding) + "│")
            print("├" + "─" * border_width + "┤")

            lines = [
                " • This tool is NOT associated with, endorsed by, or affiliated with",
                "   Equasis",
                " • May break if Equasis changes their website structure",
                " • Users must monitor for changes and update parsing logic",
                "   accordingly",
                " • Respect Equasis Terms of Service and rate limiting",
                " • Use for legitimate maritime research and safety purposes only"
            ]

            for line in lines:
                padding_needed = border_width - len(line)
                print("│" + line + " " * padding_needed + "│")

            print("└" + "─" * border_width + "┘")
        print()

        # Quick help with subdued highlighting
        if color_support:
            print(f"{Colors.DIM_GREEN}Quick Start:{Colors.RESET}")
            print(f"   {Colors.DIM_CYAN}equasis vessel --imo 9074729{Colors.RESET}          {Colors.DIM}# Get comprehensive vessel data{Colors.RESET}")
            print(f"   {Colors.DIM_CYAN}equasis search --name \"MAERSK\"{Colors.RESET}         {Colors.DIM}# Search vessels by name{Colors.RESET}")
            print(f"   {Colors.DIM_CYAN}equasis --help{Colors.RESET}                        {Colors.DIM}# Show full help{Colors.RESET}")
        else:
            print("Quick Start:")
            print("   equasis vessel --imo 9074729          # Get comprehensive vessel data")
            print("   equasis search --name \"MAERSK\"         # Search vessels by name")
            print("   equasis --help                        # Show full help")
        print()

        # Check credentials and show note if needed
        if not check_credentials():
            display_credentials_note()

        if color_support:
            print(f"{Colors.DIM}{'─' * 80}{Colors.RESET}")
        else:
            print("─" * 80)
        print()

def get_interactive_banner() -> str:
    """
    Get banner text for interactive TUI mode
    Returns plain text - styling will be applied by lexer with gradient
    """
    banner = f"""                               _                 ___
  ___  ____ ___  ______ ______(_)____      _____/ (_)
 / _ \\/ __ `/ / / / __ `/ ___/ / ___/_____/ ___/ / /
/  __/ /_/ / /_/ / /_/ (__  ) (__  )_____/ /__/ / /
\\___/\\__, /\\__,_/\\__,_/____/_/____/      \\___/_/_/
       /_/

Maritime Intelligence Tool                                         v{__version__}

┌──────────────────────────────────────────────────────────────────────────┐
│ Important Disclaimers                                                    │
└──────────────────────────────────────────────────────────────────────────┘
• This tool is NOT associated with, endorsed by, or affiliated with Equasis
• May break if Equasis changes their website structure
• Users must monitor for changes and update parsing logic accordingly
• Respect Equasis Terms of Service and rate limiting
• Use for legitimate maritime research and safety purposes only

Type 'help' for available commands or 'exit' to quit.
Press ? for quick help."""

    return banner

def display_compact_info() -> None:
    """Display minimal startup info for non-interactive use"""
    if sys.stdout.isatty():
        color_support = Colors.supports_color()
        if color_support:
            print(f"{Colors.DIM}Equasis CLI v{__version__} | Maritime Intelligence Tool{Colors.RESET}")
            print(f"{Colors.DIM_YELLOW}WARNING:{Colors.RESET} {Colors.DIM}Not affiliated with Equasis | Web scraping tool - monitor for changes{Colors.RESET}")
        else:
            print(f"Equasis CLI v{__version__} | Maritime Intelligence Tool")
            print("WARNING: Not affiliated with Equasis | Web scraping tool - monitor for changes")
        print()

def display_error_banner(error_type: str, message: str) -> None:
    """
    Display error information with consistent formatting

    Args:
        error_type: Type of error (e.g., "Authentication", "Connection", "Parsing")
        message: Error message to display
    """
    color_support = Colors.supports_color()

    print()
    if color_support:
        print(f"{Colors.RED}{Colors.BOLD}ERROR:{Colors.RESET} " + "=" * 56)
        print(f"   {Colors.BOLD}{Colors.RED}{error_type.upper()} ERROR{Colors.RESET}")
        print("=" * 62)
        print()
        print(f"   {message}")
        print()
    else:
        print("ERROR: " + "=" * 56)
        print(f"   {error_type.upper()} ERROR")
        print("=" * 62)
        print()
        print(f"   {message}")
        print()

    if error_type.lower() == "authentication":
        if color_support:
            print(f"{Colors.BOLD}{Colors.GREEN}Quick Fix:{Colors.RESET}")
            print(f"   {Colors.YELLOW}•{Colors.RESET} Check your .env file has correct EQUASIS_USERNAME and EQUASIS_PASSWORD")
            print(f"   {Colors.YELLOW}•{Colors.RESET} Verify credentials work by logging into equasis.org manually")
            print(f"   {Colors.YELLOW}•{Colors.RESET} Use --username and --password flags as alternative")
        else:
            print("Quick Fix:")
            print("   • Check your .env file has correct EQUASIS_USERNAME and EQUASIS_PASSWORD")
            print("   • Verify credentials work by logging into equasis.org manually")
            print("   • Use --username and --password flags as alternative")
        print()
    elif error_type.lower() == "parsing":
        if color_support:
            print(f"{Colors.BOLD}{Colors.BLUE}Possible Causes:{Colors.RESET}")
            print(f"   {Colors.YELLOW}•{Colors.RESET} Equasis may have changed their website structure")
            print(f"   {Colors.YELLOW}•{Colors.RESET} IMO number may not exist in Equasis database")
            print(f"   {Colors.YELLOW}•{Colors.RESET} Network issues or temporary Equasis downtime")
            print(f"   {Colors.YELLOW}•{Colors.RESET} Enable debug mode to inspect HTML response")
        else:
            print("Possible Causes:")
            print("   • Equasis may have changed their website structure")
            print("   • IMO number may not exist in Equasis database")
            print("   • Network issues or temporary Equasis downtime")
            print("   • Enable debug mode to inspect HTML response")
        print()
    elif error_type.lower() == "connection":
        if color_support:
            print(f"{Colors.BOLD}{Colors.CYAN}Troubleshooting:{Colors.RESET}")
            print(f"   {Colors.YELLOW}•{Colors.RESET} Check internet connection")
            print(f"   {Colors.YELLOW}•{Colors.RESET} Verify equasis.org is accessible")
            print(f"   {Colors.YELLOW}•{Colors.RESET} Check firewall/proxy settings")
            print(f"   {Colors.YELLOW}•{Colors.RESET} Try again later if Equasis servers are down")
        else:
            print("Troubleshooting:")
            print("   • Check internet connection")
            print("   • Verify equasis.org is accessible")
            print("   • Check firewall/proxy settings")
            print("   • Try again later if Equasis servers are down")
        print()

    print("=" * 62)
    print()

def display_success_summary(operation: str, details: Optional[str] = None) -> None:
    """
    Display success information with consistent formatting

    Args:
        operation: Operation that succeeded (e.g., "Vessel Lookup", "Search")
        details: Optional additional details
    """
    if sys.stdout.isatty():
        color_support = Colors.supports_color()
        print()
        if color_support:
            print(f"{Colors.BOLD}{Colors.GREEN}SUCCESS:{Colors.RESET} {operation} completed successfully")
            if details:
                print(f"   {Colors.CYAN}{details}{Colors.RESET}")
        else:
            print(f"SUCCESS: {operation} completed successfully")
            if details:
                print(f"   {details}")
        print()

class StatusBar:
    """Persistent status bar for interactive mode"""

    def __init__(self):
        self.connected = False
        self.last_result_success: Optional[bool] = None
        self.last_result_message: str = ""
        self.output_format: str = "table"
        self.color_support = Colors.supports_color()

    def set_connection_status(self, connected: bool) -> None:
        """Update connection status"""
        self.connected = connected

    def set_last_result(self, success: bool, message: str = "") -> None:
        """Update last command result"""
        self.last_result_success = success
        self.last_result_message = message

    def set_format(self, format_type: str) -> None:
        """Update output format"""
        self.output_format = format_type

    def clear_last_result(self) -> None:
        """Clear last result (for commands that don't need result tracking)"""
        self.last_result_success = None
        self.last_result_message = ""

    def render(self) -> str:
        """Render status bar as a single line string"""
        parts = []

        # Connection status
        if self.color_support:
            if self.connected:
                parts.append(f"{Colors.GREEN}●{Colors.RESET} {Colors.DIM}Connected{Colors.RESET}")
            else:
                parts.append(f"{Colors.DIM_RED}○{Colors.RESET} {Colors.DIM}Not connected{Colors.RESET}")
        else:
            if self.connected:
                parts.append("● Connected")
            else:
                parts.append("○ Not connected")

        # Output format
        if self.color_support:
            parts.append(f"{Colors.DIM}Format: {Colors.DIM_CYAN}{self.output_format}{Colors.RESET}")
        else:
            parts.append(f"Format: {self.output_format}")

        # Last result (if available)
        if self.last_result_success is not None:
            if self.color_support:
                if self.last_result_success:
                    status_icon = f"{Colors.GREEN}✓{Colors.RESET}"
                    result_text = self.last_result_message or "Success"
                    parts.append(f"{status_icon} {Colors.DIM}{result_text}{Colors.RESET}")
                else:
                    status_icon = f"{Colors.RED}✗{Colors.RESET}"
                    result_text = self.last_result_message or "Failed"
                    parts.append(f"{status_icon} {Colors.DIM}{result_text}{Colors.RESET}")
            else:
                if self.last_result_success:
                    parts.append(f"✓ {self.last_result_message or 'Success'}")
                else:
                    parts.append(f"✗ {self.last_result_message or 'Failed'}")

        # Join with separators
        if self.color_support:
            separator = f" {Colors.DIM}|{Colors.RESET} "
        else:
            separator = " | "

        return separator.join(parts)