# Scheduled Jobs (Cron + Django Management Commands)

This project uses Django management commands triggered by **cron** to automate housekeeping and usage tracking for the Nolop Prusa printers.

There are currently two scheduled jobs:

1. **Printer Polling & Usage Stats** – runs every minute
2. **Print Queue Cleanup** – runs weekly 

Both operate on the `Printers` model and communicate with the printers via `PrusaLinkPy`.

## Printer Polling & Usage Stats (`poll_printers`)

**Purpose**

Continuously collect usage data for each printer to track performance and degradation over time. This includes:

- Incrementing each printer’s **total print count** when a new job starts.
- Aggregating **filament usage** in:
  - millimeters (`filament_usage_mm`)
  - grams (`filament_usage_g`)
  - cubic centimeters (`filament_usage_cm3`)
- Remembering the **last seen job ID** to avoid double-counting the same print.

**Where it lives**

- Management command:  
  `printers/management/commands/poll_printers.py`

**What it does (high level)**

- Loops over all `Printers` in the database.
- Uses `PrusaLinkPy` to call `get_status()` on each printer.
- Normalizes the raw printer state via `map_printer_status(...)` (from `printers.utils`).
- If a printer is printing and the job ID has changed since the last run:
  - Atomically increments `total_print_count`.
  - Updates `last_job_id`.
- Uses `get_filament_usage_from_job(...)` (from `printers.utils`) to compute filament deltas and accumulates them into `filament_usage_mm`, `filament_usage_g`, and `filament_usage_cm3`.
- Cleans up any “pending” usage objects so the next run doesn’t double-count.

**Cron schedule (example)**

Run every minute:

```cron
* * * * * cd /home/nolop/Documents/prusa-printer-manager/prusa_print_client && \
/home/nolop/miniconda3/condabin/conda run -n nolop-printers \
  python manage.py poll_printers >> logs/poll_printers.log 2>&1
```

## Print Queue Cleanup (`delete_files`)

**Purpose**

Automatically clean out uploaded binary G-code files from the `/PRINT_QUEUE` directory on each printer so on-printer storage doesn’t fill up with old jobs.

**Where it lives**

- Management command:  
  `printers/management/commands/delete_files.py`

**What it does (high level)**

- Loops over all `Printers` in the database.
- Uses `PrusaLinkPy` to connect to each printer with its `host` and `api_key`.
- Calls `get_recursive_files("/PRINT_QUEUE")` to list everything under the `PRINT_QUEUE` directory (where uploaded prints are stored).
- Iterates through the returned files and issues `delete(...)` calls to remove them from the printer.
- If a printer is offline or an API call fails, it simply skips that printer for this run.

**Cron schedule (example)**

Run once a week (Sunday at 03:30):

```cron
30 3 * * 0 cd /home/nolop/Documents/prusa-printer-manager/prusa_print_client && \
/home/nolop/miniconda3/condabin/conda run -n nolop-printers \
  python manage.py delete_files >> logs/delete_files.log 2>&1