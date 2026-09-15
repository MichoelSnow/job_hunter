# Server deployment

This deployment runs the backend and frontend as user-level `systemd` services. They restart after failures and, with user lingering enabled, continue after logout and start at boot.

## Initial installation

Run these commands as the account that should own the app and SQLite database.
Before installing, configure `.env` and `config/user_profile.yaml`.

```bash
cd /path/to/job_hunter
chmod +x deploy/install-systemd.sh
```

Approve the frontend dependency build script. This is an interactive pnpm
security step and is normally needed only once per checkout or server:

```bash
cd frontend
pnpm approve-builds
# Select esbuild, then press Enter.
cd ..
```

Install dependencies, build the frontend, create both user-level systemd
services, and start the application:

```bash
./deploy/install-systemd.sh
```

The installer runs `poetry install`, installs frontend packages, builds the
frontend, and enables and starts both services.

The frontend listens on all interfaces at port `5173`; the backend listens only on loopback at port `8000`. The frontend proxies `/api` to the backend, so browse from another LAN machine to:

```text
http://<server-lan-ip>:5173
```

Find the LAN address with `hostname -I`. If Ubuntu's firewall is enabled, allow the frontend port only from the local network, replacing the subnet as needed:

```bash
sudo ufw allow from 192.168.1.0/24 to any port 5173 proto tcp
```

Do not expose port `8000` to the internet. Cloudflare Tunnel should point to `http://127.0.0.1:5173`.

## Operations

The deployment consists of two user-level services:

- `job-hunter-backend` — backend API on `127.0.0.1:8000`
- `job-hunter-frontend` — frontend on port `5173`, including the `/api` proxy

Run the following commands as the same Linux user that installed the services.

### Check status

```bash
systemctl --user status job-hunter-backend job-hunter-frontend
```

### Stop the application

Stop both services. This does not delete the deployment or its configuration.

```bash
systemctl --user stop job-hunter-backend job-hunter-frontend
```

### Start the application

```bash
systemctl --user start job-hunter-backend job-hunter-frontend
```

### Restart the application

Use this after a configuration change or a manual rebuild:

```bash
systemctl --user restart job-hunter-backend job-hunter-frontend
```

### View logs

Follow both service logs until you stop them with `Ctrl+C`:

```bash
journalctl --user -u job-hunter-backend -u job-hunter-frontend -f
```

### Disable or re-enable automatic startup

Disabling prevents the services from starting automatically at login or boot;
it does not stop services that are already running. Stop them separately if
needed.

```bash
systemctl --user disable job-hunter-backend job-hunter-frontend
```

Re-enable automatic startup and start both services immediately:

```bash
systemctl --user enable --now job-hunter-backend job-hunter-frontend
```

## Updating an existing deployment

After pulling updates, reinstall frontend packages, rebuild the frontend, and
restart both services:

```bash
cd /path/to/job_hunter
pnpm --dir frontend install
pnpm --dir frontend build
systemctl --user restart job-hunter-backend job-hunter-frontend
```

If backend dependencies changed, rerun `./deploy/install-systemd.sh` instead;
it reinstalls backend dependencies and also rebuilds and starts the frontend.

For Cloudflare Tunnel, route your hostname to `http://127.0.0.1:5173`. Add authentication before exposing this personal application publicly; the current app has no login layer.
