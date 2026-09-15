#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

# systemd and non-interactive shells do not load NVM's profile automatically.
nvm_dir="${NVM_DIR:-$HOME/.nvm}"
if [[ -s "$nvm_dir/nvm.sh" ]]; then
  # shellcheck disable=SC1090
  source "$nvm_dir/nvm.sh"
fi

poetry_bin=$(command -v poetry || true)
pnpm_bin=$(command -v pnpm || true)
node_bin=$(dirname "$(command -v node || true)")

if [[ -z "$poetry_bin" ]]; then echo "poetry was not found on PATH" >&2; exit 1; fi
if [[ -z "$pnpm_bin" ]]; then echo "pnpm was not found on PATH" >&2; exit 1; fi
if [[ -z "$node_bin" || "$node_bin" == "." ]]; then echo "node was not found on PATH" >&2; exit 1; fi

echo "Installing backend dependencies"
(cd "$repo_dir" && "$poetry_bin" install)
echo "Building frontend"
(cd "$repo_dir/frontend" && "$pnpm_bin" install && "$pnpm_bin" build)

unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$unit_dir"
sed -e "s|__REPO_DIR__|$repo_dir|g" -e "s|__POETRY__|$poetry_bin|g" deploy/job-hunter-backend.service.template > "$unit_dir/job-hunter-backend.service"
sed -e "s|__REPO_DIR__|$repo_dir|g" -e "s|__PNPM__|$pnpm_bin|g" -e "s|__NODE_BIN__|$node_bin|g" deploy/job-hunter-frontend.service.template > "$unit_dir/job-hunter-frontend.service"

systemctl --user daemon-reload
systemctl --user enable --now job-hunter-backend.service job-hunter-frontend.service

if ! loginctl enable-linger "$USER"; then
  echo "Could not enable user lingering automatically; run: sudo loginctl enable-linger $USER" >&2
fi

echo
echo "Job Hunter is running at http://127.0.0.1:5173"
echo "From another LAN machine, use http://<server-lan-ip>:5173"
echo
echo "Useful commands:"
echo "  systemctl --user status job-hunter-backend job-hunter-frontend"
echo "  journalctl --user -u job-hunter-backend -u job-hunter-frontend -f"
