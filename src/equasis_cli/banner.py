"""Banner and disclaimer text."""

from __future__ import annotations

from ._version import __version__

ASCII_ART = r"""                               _                 ___
  ___  ____ ___  ______ ______(_)____      _____/ (_)
 / _ \/ __ `/ / / / __ `/ ___/ / ___/_____/ ___/ / /
/  __/ /_/ / /_/ / /_/ (__  ) (__  )_____/ /__/ / /
\___/\__, /\__,_/\__,_/____/_/____/      \___/_/_/
       /_/"""

DISCLAIMER = (
    "equasis-cli is not affiliated with or endorsed by Equasis. It reads the Equasis "
    "website, which may change without notice. Use it in line with the Equasis terms "
    "and conditions, keep request volumes modest, and verify important findings on "
    "equasis.org."
)

TAGLINE = "Maritime Intelligence Tool"


def interactive_banner() -> str:
    """Banner shown at the top of the interactive shell."""
    return "\n".join(
        [
            ASCII_ART,
            "",
            f"{TAGLINE:<67}v{__version__}",
            "",
            "Not affiliated with Equasis. The Equasis website may change without notice;",
            "use in line with the Equasis terms and keep request volumes modest.",
            "",
            "Type 'help' for commands or 'exit' to quit.",
            "Press ? for quick help.",
        ]
    )
