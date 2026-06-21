from pathlib import Path

_ENABLED = False
_LOG_FILE = Path("debug/pipeline_trace.log")

def set_explain_mode(enabled: bool):
    global _ENABLED
    _ENABLED = enabled
    if enabled:
        _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_LOG_FILE, "w", encoding="utf-8") as f:
            f.write("Pipeline Trace Log\n==================\n")

def is_explain_mode() -> bool:
    return _ENABLED

def explain_print(section: str, content: str):
    if not _ENABLED:
        return
    output = f"\n{'='*50}\n{section}\n{'='*50}\n\n{content}\n"
    print(output)
    
    # Append to log file
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(output)
            f.write("\n")
    except Exception:
        pass  # Fail gracefully if logging fails
