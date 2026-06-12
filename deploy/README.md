# Raspberry Pi deployment (Phase 5)

These steps assume Raspberry Pi OS (Debian-based) on a Raspberry Pi 5, with
this repo cloned to `/home/pi/parts-library` and run as user `pi`. If your
path or username differ, edit `User=`/`WorkingDirectory=`/`ExecStart=` in the
unit files below to match before copying them.

## 1. Clone the repo

If `git` isn't installed yet (common on Raspberry Pi OS Lite):

```bash
sudo apt update
sudo apt install -y git
```

Then clone:

```bash
cd ~
git clone https://github.com/janni0609/parts-library.git
```

GitHub no longer accepts your account password for HTTPS clones. When
prompted for a password, use a [personal access
token](https://github.com/settings/tokens) (classic, `repo` scope) instead,
or set up an SSH key on the Pi and clone via
`git@github.com:janni0609/parts-library.git`.

## 2. Install the app

```bash
cd ~/parts-library/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

The SQLite database is created automatically at `backend/data/parts.db` on
first run.

## 3. Run as a systemd service

```bash
cd ~/parts-library
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

## 4. Periodic database backups

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

## 5. Updating after a `git pull`

```bash
cd ~/parts-library
git pull
backend/.venv/bin/pip install -r backend/requirements.txt
sudo systemctl restart parts-library
```
