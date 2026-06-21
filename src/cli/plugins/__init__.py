import os
import importlib
from pathlib import Path
import typer


def load_plugins(app: typer.Typer) -> None:
    """
    Dynamically discover and load CLI plugins from this directory.
    Isolates plugin failures so a broken plugin does not crash CLI startup.
    """
    plugins_dir = Path(__file__).parent

    # Ensure the plugins directory is scanned for sub-modules
    if not plugins_dir.exists():
        return

    for entry in os.scandir(plugins_dir):
        if entry.name.startswith("_"):
            continue

        module_name = None
        if entry.is_file() and entry.name.endswith(".py"):
            module_name = entry.name[:-3]
        elif entry.is_dir() and os.path.isfile(os.path.join(entry.path, "__init__.py")):
            module_name = entry.name

        if module_name:
            try:
                # Import module dynamically relative to this package
                module = importlib.import_module(f"src.cli.plugins.{module_name}")

                # Check for registration helper or raw Typer app attribute
                if hasattr(module, "register_plugin"):
                    module.register_plugin(app)
                elif hasattr(module, "app") and isinstance(module.app, typer.Typer):
                    # Add as a subcommand group named after the module
                    app.add_typer(
                        module.app, name=module_name, help=f"Plugin: {module_name}"
                    )
            except Exception as e:
                # Prevent plugin import crashes from breaking core command line initialization
                from src.cli.theme import console, get_symbols

                symbols = get_symbols()
                console.print(
                    f"[warning]{symbols['WARNING_PREFIX']} Plugin load failed for '{module_name}' -> {e}[/warning]"
                )
