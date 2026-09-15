# Server deployment

This deployment runs the backend and frontend as user-level `systemd` services. They restart after failures and, with user lingering enabled, continue after logout and start at boot.

## Install on Ubuntu

Run as the account that should own the app and SQLite database:

```bash
cd /path/to/job_hunter
chmod +x deploy/install-systemd.sh
./deploy/install-systemd.sh
```

Configure `.env` and `config/user_profile.yaml` first. The installer runs `poetry install`, installs frontend packages, builds the frontend, and starts both services.

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

```bash
systemctl --user status job-hunter-backend job-hunter-frontend
systemctl --user restart job-hunter-backend job-hunter-frontend
journalctl --user -u job-hunter-backend -u job-hunter-frontend -f
```

After pulling updates, rebuild and restart:

```bash
cd /path/to/job_hunter
pnpm --dir frontend install
pnpm --dir frontend build
systemctl --user restart job-hunter-backend job-hunter-frontend
```

For Cloudflare Tunnel, route your hostname to `http://127.0.0.1:5173`. Add authentication before exposing this personal application publicly; the current app has no login layer.
