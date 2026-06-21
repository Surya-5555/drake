from dataclasses import dataclass


@dataclass(slots=True)
class CLIContext:
    verbose: bool = False
    json_output: bool = False
    debug: bool = False
