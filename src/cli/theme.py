import sys
import json as json_lib
from typing import Any
from rich.console import Console
from rich.theme import Theme
from rich.panel import Panel
from rich.markdown import Markdown

_supports_unicode_cache = None


def get_symbols() -> dict[str, str]:
    """Retrieve symbols based on terminal capabilities."""
    global _supports_unicode_cache
    if _supports_unicode_cache is None:
        try:
            for f in (sys.stdout, sys.stderr):
                if f and hasattr(f, "encoding") and f.encoding:
                    "✓".encode(f.encoding)
                    "⚠".encode(f.encoding)
                    "✗".encode(f.encoding)
            _supports_unicode_cache = True
        except Exception:
            _supports_unicode_cache = False

    if _supports_unicode_cache:
        return {
            "CHECK": "✓",
            "CROSS": "✗",
            "WARN": "⚠",
            "INFO": "ℹ",
            "SUCCESS_PREFIX": "✓ SUCCESS:",
            "WARNING_PREFIX": "⚠ WARNING:",
            "SAFE_VERDICT": "✓ SAFE TO EXECUTE",
            "BLOCK_VERDICT": "✗ BLOCK EXECUTION",
            "REQUIRES_PREFIX": "└── requires: ",
        }
    else:
        return {
            "CHECK": "[OK]",
            "CROSS": "[FAIL]",
            "WARN": "[WARN]",
            "INFO": "[INFO]",
            "SUCCESS_PREFIX": "SUCCESS:",
            "WARNING_PREFIX": "WARNING:",
            "SAFE_VERDICT": "SAFE TO EXECUTE",
            "BLOCK_VERDICT": "BLOCK EXECUTION",
            "REQUIRES_PREFIX": "+-- requires: ",
        }


CLI_THEME = Theme(
    {
        "cyan": "#00f0ff",
        "green": "#39ff14",
        "amber": "#ffb300",
        "red": "#ff073a",
        "gray": "#708090",
        "white": "#ffffff",
        "info": "bold #00f0ff",
        "success": "bold #39ff14",
        "warning": "bold #ffb300",
        "critical": "bold #ff073a",
        "meta": "#708090",
        "primary": "#ffffff",
    }
)

console = Console(theme=CLI_THEME)


def mask_secrets(val: Any) -> Any:
    """Recursively mask sensitive values matching password, token, key, secret, ssn, authorization."""
    if isinstance(val, dict):
        masked_dict = {}
        for k, v in val.items():
            k_lower = k.lower()
            if any(
                secret_word in k_lower
                for secret_word in [
                    "password",
                    "token",
                    "secret",
                    "authorization",
                    "ssn",
                    "key",
                ]
            ):
                if isinstance(v, str):
                    masked_dict[k] = "*" * len(v) if len(v) > 0 else "********"
                else:
                    masked_dict[k] = "********"
            else:
                masked_dict[k] = mask_secrets(v)
        return masked_dict
    elif isinstance(val, list):
        return [mask_secrets(item) for item in val]
    return val


def render_panel(content: Any, title: str = "", border_style: str = "cyan") -> Panel:
    """Render a content block inside a structured Panel."""
    return Panel(content, title=title, border_style=border_style, padding=(1, 2))


def render_success(message: str) -> None:
    """Print success message."""
    symbols = get_symbols()
    console.print(
        f"[success]{symbols['SUCCESS_PREFIX']}[/success] [primary]{message}[/primary]"
    )


def render_warning(message: str) -> None:
    """Print warning message."""
    symbols = get_symbols()
    console.print(
        f"[warning]{symbols['WARNING_PREFIX']}[/warning] [primary]{message}[/primary]"
    )


def render_error(title: str, cause: str, impact: str, action: str) -> None:
    """Print structured operational error block."""
    content = (
        f"[bold red]CAUSE:[/bold red]\n{cause}\n\n"
        f"[bold yellow]IMPACT:[/bold yellow]\n{impact}\n\n"
        f"[bold cyan]ACTION:[/bold cyan]\n{action}"
    )
    console.print(
        Panel(content, title=f"[bold red]ERROR: {title}[/bold red]", border_style="red")
    )


def render_json(data: Any) -> None:
    """Print structured raw JSON without Rich styling."""
    masked = mask_secrets(data)
    # Using python's print to bypass rich styling and guarantee clean machine output
    print(json_lib.dumps(masked, indent=2))


def render_markdown(text: str) -> None:
    """Print formatted markdown text."""
    console.print(Markdown(text))
