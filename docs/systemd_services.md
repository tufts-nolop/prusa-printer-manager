# Raspberry Pi systemd services (Django + Gunicorn)

This repo is deployed on the Pi using two **systemd services**:

1) **`nolop-print-update.service`**  
   Pulls the latest code from GitHub (branch: `main`) and runs Django maintenance tasks

2) **`nolop-print.service`**  
   Runs the Django app via Gunicorn (the web server process)

These two services are designed so that on boot:
- the Pi updates the code + runs migrations/collectstatic
- then starts Gunicorn to host the Django site


## Locations

Systemd unit files live here:

- `/etc/systemd/system/nolop-print-update.service`
- `/etc/systemd/system/nolop-print.service`

Project directory (repo root; contains `manage.py`):

- `/home/nolop/Documents/prusa-printer-manager/prusa_print_client`

Conda used by the services:

- Conda executable: `/home/nolop/miniconda3/bin/conda`
- Conda env: `nolop-printers`


## What each service does

### 1) `nolop-print-update.service` (oneshot updater)
**Type:** oneshot (runs, then exits)

**Purpose:** Ensure the local repo is synced to GitHub `main`, then prepare Django artifacts.

**Typical steps performed:**
- `git fetch --all --prune`
- `git checkout main`
- `git reset --hard origin/main`  
  (forces the working directory to exactly match `origin/main`)
- `python manage.py migrate --noinput`  
  Note: it **does** apply existing migrations to the DB, but **does NOT** create migrations (`makemigrations` should be done on dev and committed)
- `python manage.py collectstatic --noinput`  
  collects static assets into `STATIC_ROOT` (e.g., `staticfiles/`)

**When it runs:**
- On boot (because the Gunicorn service depends on it)
- Anytime you manually run it:
  ```bash
  sudo systemctl start nolop-print-update.service
  ```

### 2) `nolop-print.service` (Gunicorn web server)

**Type:** long-running service

**Purpose:** Host the Django app over HTTP using Gunicorn workers.

**Key behavior:**
- Starts Gunicorn with something like:
  - `--bind 0.0.0.0:8000`
  - `--workers <N>`
- Restarts automatically if it crashes

**Dependency behavior (important):**
- This service should include, in its `[Unit]` section:
  - `After=nolop-print-update.service`
  - `Requires=nolop-print-update.service`

That ensures Gunicorn won’t start until the update/collectstatic/migrate step has succeeded.

## Common commands

### Reload systemd after editing service files
```bash
sudo systemctl daemon-reload
```

### Enable services at boot
```bash 
sudo systemctl enable nolop-print-update.service
sudo systemctl enable nolop-print.service
```

### Start/restart
```bash 
sudo systemctl start nolop-print-update.service
sudo systemctl restart nolop-print.service
```

### Check status
```bash 
sudo systemctl status nolop-print-update.service --no-pager
sudo systemctl status nolop-print.service --no-pager
```

### View logs
```bash 
sudo journalctl -u nolop-print-update.service -e
sudo journalctl -u nolop-print.service -e
```

### Follow logs live
```bash 
sudo journalctl -u nolop-print.service -f
```