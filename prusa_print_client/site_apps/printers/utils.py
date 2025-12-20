########## Helper functions ##########

# used gpt to map the status flags
def map_printer_status(state: str) -> str:
    """
    Map raw printer state string -> one of:
    'operational', 'paused', 'printing', 'error', 'ready', 'busy'
    """
    s = (state or "").strip().lower()

    # Error-ish states: treat anything with 'error' as error
    if "error" in s or "fault" in s:
        return "error"

    if s == "printing":
        return "printing"

    if s == "paused":
        return "paused"

    # Finished prints: you might want this to look "ready" in the UI
    if s == "finished":
        return "ready"

    # Stopped / cancelled / attention → busy-ish
    if s in ("stopped", "attention", "busy"):
        return "busy"

    # Idle = ready to go
    if s == "idle":
        return "ready"

    # Operational: generic "on but nothing special"
    if s in ("operational", "online"):
        return "operational"

    # Unknown state: safest to call it busy
    return "busy"