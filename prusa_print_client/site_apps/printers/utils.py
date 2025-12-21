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

import re



def extract_filament_usage(file_obj) -> dict:
    """
    Given a Prusa sliced .bgcode file, extracts the filament usage of a print 

    Returns a dict like:
      {
        "mm": 12345.67,
        "g": 98.7,
        "cm3": 12.34,
      }
    """
    
    FILAMENT_RE = re.compile(r";\s*filament used \[([^\]]+)\]\s*=\s*([0-9.+-eE]+)")
    usage = {}

    # reading only the first 100 lines to avoid slurping the whole file
    for _ in range(100):
        line = file_obj.readline()
        if not line:
            break  # EOF

        try:
            line_str = line.decode("utf-8", errors="ignore")
        except AttributeError:
            # already str
            line_str = line

        m = FILAMENT_RE.match(line_str.strip())
        if m:
            unit = m.group(1).strip()   # e.g. "mm", "g", "cm3"
            value = float(m.group(2))
            usage[unit] = value

    # rewind so later code can re-read the file if needed
    try:
        file_obj.seek(0)
    except Exception:
        pass

    return usage