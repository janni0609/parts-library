# Raspberry Pi deployment (Phase 5)

These steps assume Raspberry Pi OS (Debian-based) on a Raspberry Pi 5, with
this repo cloned to `/home/pi/parts-library` and run as user `pi`. If your
path or username differ, edit `User=`/`WorkingDirectory=`/`ExecStart=` in the
unit files below to match before copying them.

## 1. Install the app

```bash
cd ~/parts-library/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

The SQLite database is created automatically at `backend/data/parts.db` on
first run.

## 2. Run as a systemd service

```bash
sudo cp deploy/parts-library.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now parts-library
```

Check status / logs:

```bash
systemctl status parts-library
journalctl -u parts-library -f
```

The service binds `0.0.0.0:8000` with no `--reload`, so it survives SSH
disconnects and restarts automatically on crash or reboot. From any other
device on the LAN, open `http://<pi-hostname>.local:8000` or
`http://<pi-ip-address>:8000`.

## 3. Periodic database backups

`backend/scripts/backup_db.py <destination> [--keep N]` copies `parts.db` to
`<destination>` using SQLite's online backup API (safe to run while the app
is serving requests), keeping the `N` most recent copies (default 14) and
deleting older ones.

Edit `deploy/parts-library-backup.service` so `ExecStart`'s destination
argument points at where you want backups stored (e.g. a mounted USB drive
or NAS share — the directory is created if it doesn't exist), then:

```bash
sudo cp deploy/parts-library-backup.service deploy/parts-library-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now parts-library-backup.timer
```

Run a backup immediately, or check when the timer last/next ran:

```bash
sudo systemctl start parts-library-backup
systemctl list-timers parts-library-backup.timer
```

## 4. Updating after a `git pull`

```bash
cd ~/parts-library
git pull
backend/.venv/bin/pip install -r backend/requirements.txt
sudo systemctl restart parts-library
```
