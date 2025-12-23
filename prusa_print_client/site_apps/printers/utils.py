# used gpt to map the status flags
def map_printer_status(state: str) -> str:
    """
    Map raw printer state string -> one of:
    'operational', 'paused', 'printing', 'error', 'ready', 'stopped', 'busy'
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
    
    if s == "stopped":
        return "stopped"

    # cancelled / attention → busy-ish
    if s in ("attention", "busy"):
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



def get_filament_usage_from_file(file_obj) -> dict:
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

def estimate_filament_for_stopped_job(job_data, pending_usage):
    """
    pending_usage: PendingJobUsage instance with filament_mm / filament_g
    """
    job = job_data.get("job") or {}
    progress = job.get("progress") or {}

    completion = progress.get("completion")  # 0..100%
    if completion is None:
        return None, None, None

    frac = completion / 100.0

    used_mm = used_g = used_cm3 = None
    if pending_usage.filament_mm is not None:
        used_mm = pending_usage.filament_mm * frac
    if pending_usage.filament_g is not None:
        used_g = pending_usage.filament_g * frac
    if pending_usage.filament_cm3 is not None:
        used_cm3 = pending_usage.filament_cm3 * frac

    return used_mm, used_g, used_cm3

def get_filament_usage_from_job(printer, job_data):
    """
    For a single printer (django object) + its /api/v1/job JSON:
      - If the current job is FINISHED or STOPPED
      - And we have a PendingJobUsage for its file
      → add filament usage and delete the pending record
      
    Also, this func is a little jank, modded it to be used in views as 
        well as commands with the OG use being the latter
    """
    
    from .models import PendingJobUsage
    
    
    job = job_data.get("job") or {}
    state = (job.get("state") or "").upper()

    if state not in ("FINISHED", "STOPPED"):
        return None, None, None, None

    file_info = job.get("file") or {}
    refs = file_info.get("refs") or {}
    download_path = refs.get("download")
    if not download_path:
        return None, None, None, None

    pending = PendingJobUsage.objects.filter(
        printer=printer,
        remote_path=download_path,
    ).first()

    # if theres no pending record, we either:
    # - never uploaded this via our app, or
    # - already processed it
    if not pending:
        return None, None, None, None

    # FINISHED vs STOPPED logic
    if state == "FINISHED":
        used_mm = pending.filament_mm or 0.0
        used_g = pending.filament_g or 0.0
        used_cm3 = pending.filament_cm3 or 0.0
    else:  # STOPPED
        used_mm, used_g, used_cm3 = estimate_filament_for_stopped_job(job_data, pending)
        
    return used_mm, used_g, used_cm3, pending

