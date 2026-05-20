"""ASCII banner and attribution strings."""

from citable import __version__

BANNER = r"""
  ___ _ _        _    _
 / __(_) |_ __ _| |__| |___
| (__| |  _/ _` | '_ \ / -_)
 \___|_|\__\__,_|_.__/_\___|
"""

TAGLINE = "AI search visibility audit for ChatGPT, Claude, Perplexity, Google AI"
ATTRIBUTION = "Built by Work-Smart.ai"


def render_banner() -> str:
    """Return the full banner block ready to print."""
    lines = [
        BANNER.rstrip(),
        f"                            v{__version__}",
        "",
        f" {TAGLINE}",
        "",
        f" {ATTRIBUTION}",
        "",
    ]
    return "\n".join(lines)
