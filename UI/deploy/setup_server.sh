#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu server (e.g. Oracle Cloud Always Free) for the
# Protein Function Predictor. Run it as the normal user from the deploy folder:
#
#     bash setup_server.sh
#
# It opens the web ports, installs Docker, asks for the web address and the
# EMBL-EBI contact e-mail (saved in deploy/.env), then builds and starts the app.
# Safe to run again: finished steps are skipped.
set -euo pipefail
cd "$(dirname "$0")"   # the deploy folder

say() { printf '\n==> %s\n' "$1"; }
fail() { printf '\nERROR: %s\n' "$1" >&2; exit 1; }

[ "$(id -u)" -ne 0 ] || fail "Run this as your normal user (e.g. ubuntu), not as root; it uses sudo itself."
command -v sudo >/dev/null 2>&1 || fail "sudo is not available."
[ -f /etc/os-release ] && . /etc/os-release
[ "${ID:-}" = "ubuntu" ] || echo "Warning: this script was written for Ubuntu; continuing anyway."

# --- 1. Web ports in the server's own firewall -----------------------------------
# Oracle's Ubuntu images block every incoming port except SSH (22) with iptables,
# in addition to the cloud firewall (the subnet's security list). Done before
# Docker is installed, so the saved rules contain only these two.
say "1/5  Opening ports 80 and 443 in the server firewall"
opened=0
for port in 80 443; do
  if ! sudo iptables -C INPUT -p tcp --dport "$port" -m state --state NEW -j ACCEPT 2>/dev/null; then
    sudo iptables -I INPUT 1 -p tcp --dport "$port" -m state --state NEW -j ACCEPT
    opened=1
  fi
done
if [ "$opened" -eq 1 ]; then
  if ! command -v netfilter-persistent >/dev/null 2>&1; then
    sudo apt-get update -y
    echo "iptables-persistent iptables-persistent/autosave_v4 boolean true" | sudo debconf-set-selections
    echo "iptables-persistent iptables-persistent/autosave_v6 boolean true" | sudo debconf-set-selections
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent
  fi
  sudo netfilter-persistent save
fi

# --- 2. Docker ------------------------------------------------------------------------
say "2/5  Installing Docker"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
  sudo sh /tmp/get-docker.sh
fi
sudo systemctl enable --now docker
sudo docker compose version >/dev/null 2>&1 || fail "Docker Compose is missing. Run: sudo apt-get install -y docker-compose-plugin"

# --- 3. Extra memory on small machines --------------------------------------------------
memory_kb=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
if [ "$memory_kb" -lt 7000000 ] && ! sudo swapon --show | grep -q /swapfile; then
  say "3/5  Less than 7 GB of memory: adding a 4 GB swap file"
  sudo fallocate -l 4G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile >/dev/null
  sudo swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
else
  say "3/5  Memory is sufficient (no swap file needed)"
fi

# --- 4. Settings (deploy/.env) ---------------------------------------------------------
say "4/5  Settings"
if [ -f .env ]; then
  echo "Using the existing deploy/.env (delete it and run this script again to re-enter the settings)."
else
  read -rp "Web address, without https:// (e.g. protfunc.duckdns.org): " site
  site="${site#http://}"; site="${site#https://}"; site="${site%%/*}"; site="${site// /}"
  [ -n "$site" ] || fail "A web address is needed."
  read -rp "Contact e-mail for EMBL-EBI BLASTp and InterProScan (press Enter to skip them): " ebi_email
  ebi_email="${ebi_email// /}"
  umask 077
  {
    echo "SITE_ADDRESS=$site"
    echo "PFP_EBI_EMAIL=$ebi_email"
    echo "PFP_PRELOAD_MODELS=on"
  } > .env
  echo "Saved deploy/.env (readable only by you)."
fi

# --- 5. Build and start ---------------------------------------------------------------
say "5/5  Building and starting (the first build takes about 30-40 minutes)"
sudo docker compose up -d --build

echo "Waiting for the app to answer..."
for _ in $(seq 1 60); do
  if sudo docker compose exec -T app curl -fs http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
    site_address=$(grep '^SITE_ADDRESS=' .env | cut -d= -f2-)
    say "Done. Open https://${site_address}"
    echo "(The HTTPS certificate is fetched on the first visit; if the page does not load at once, wait a minute.)"
    exit 0
  fi
  sleep 5
done
fail "The app did not start within 5 minutes. Show its log with: sudo docker compose logs app"
