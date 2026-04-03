#!/bin/bash
# ==============================================
# Traefik Deploy Script
# Location: /etc/traefik/deploy.sh (or run from repo)
#
# Processes config templates, substitutes env vars
# from .env, and deploys to /etc/traefik/.
# ==============================================

set -euo pipefail

# --- Paths ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="/etc/traefik"
ENV_FILE="${SCRIPT_DIR}/.env"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }

# --- Pre-flight Checks ---
if [ ! -f "$ENV_FILE" ]; then
  log_error ".env file not found at $ENV_FILE"
  log_warn "Copy .env.example to .env and fill in your values:"
  echo "    cp ${SCRIPT_DIR}/.env.example ${SCRIPT_DIR}/.env"
  exit 1
fi

if ! command -v envsubst &>/dev/null; then
  log_error "'envsubst' not found. Install with: sudo apt install gettext-base"
  exit 1
fi

# --- Load Environment (without expanding $ in values) ---
while IFS= read -r line; do
  # Skip empty lines and comments
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
  # Split on first = only (values may contain =)
  key="${line%%=*}"
  value="${line#*=}"
  # Trim whitespace from key
  key=$(echo "$key" | tr -d '[:space:]')
  [[ -z "$key" ]] && continue
  export "$key=$value"
done < "$ENV_FILE"

# --- Validate Required Variables ---
REQUIRED_VARS=(
  "CF_API_TOKEN"
  "CF_DNS_API_TOKEN"
  "CF_ZONE_API_TOKEN"
  "CF_ZONE_NAME"
  "CF_RECORD_NAME"
  "ACME_EMAIL"
  "CROWDSEC_BOUNCER_API_KEY"
  "DASHBOARD_PASSWORD"
)

MISSING=0
for VAR in "${REQUIRED_VARS[@]}"; do
  VALUE="${!VAR:-}"
  if [ -z "$VALUE" ] || [[ "$VALUE" == *"REPLACE"* ]] || [[ "$VALUE" == *"your_"* ]]; then
    log_error "Missing or placeholder value for: $VAR"
    MISSING=1
  fi
done

if [ "$MISSING" -eq 1 ]; then
  log_error "Fix the above variables in $ENV_FILE before deploying."
  exit 1
fi

log_info "All required environment variables are set."

# --- Handle Dashboard Credentials ---
log_info "Generating hash for DASHBOARD_PASSWORD..."
# Generate the hash for user 'admin' using the provided password
DASHBOARD_AUTH_HASH="admin:$(openssl passwd -apr1 "$DASHBOARD_PASSWORD")"

# --- Escape ALL $ signs in DASHBOARD_AUTH_HASH for YAML ---
# Use a specific variable for the YAML-safe version to avoid confusion
export DASH_AUTH_YAML_READY=$(echo "$DASHBOARD_AUTH_HASH" | sed 's/\$/\$\$/g')

# --- Create Deploy Directory Structure ---
sudo mkdir -p "${DEPLOY_DIR}/conf.d"
sudo mkdir -p "${DEPLOY_DIR}/ssl"

# --- Process Static Config (traefik.yaml) ---
log_info "Processing traefik.yaml..."
envsubst '${ACME_EMAIL}' < "${SCRIPT_DIR}/traefik.yaml" | sudo tee "${DEPLOY_DIR}/traefik.yaml" > /dev/null

# --- Process Dynamic Configs (conf.d/) ---
for FILE in "${SCRIPT_DIR}"/conf.d/*.yaml; do
  FILENAME=$(basename "$FILE")
  log_info "Processing conf.d/${FILENAME}..."
  
  if [ "$FILENAME" == "dashboard.yaml" ]; then
    # Special handling for dashboard.yaml to avoid envsubst eating the hash $ signs
    sed "s|\${DASH_AUTH_YAML_READY}|${DASH_AUTH_YAML_READY}|g" "$FILE" \
      | sudo tee "${DEPLOY_DIR}/conf.d/${FILENAME}" > /dev/null
  else
    envsubst '${CROWDSEC_BOUNCER_API_KEY}' < "$FILE" \
      | sudo tee "${DEPLOY_DIR}/conf.d/${FILENAME}" > /dev/null
  fi
done

# --- Deploy DDNS Script ---
log_info "Deploying cloudflare-ddns.sh..."
sudo cp "${SCRIPT_DIR}/scripts/cloudflare-ddns.sh" /usr/local/bin/cloudflare-ddns.sh
sudo chmod +x /usr/local/bin/cloudflare-ddns.sh

# --- Deploy .env to Server ---
log_info "Deploying .env to ${DEPLOY_DIR}/.env..."
sudo cp "$ENV_FILE" "${DEPLOY_DIR}/.env"
sudo chmod 600 "${DEPLOY_DIR}/.env"
sudo chown root:root "${DEPLOY_DIR}/.env"

# --- Set Permissions ---
sudo chmod 644 "${DEPLOY_DIR}/traefik.yaml"
sudo chmod 644 "${DEPLOY_DIR}"/conf.d/*.yaml
sudo chmod 600 "${DEPLOY_DIR}/ssl/acme.json" 2>/dev/null || true

# --- Create/Update systemd Environment Override ---
log_info "Setting up systemd EnvironmentFile for Traefik..."
sudo mkdir -p /etc/systemd/system/traefik.service.d
sudo tee /etc/systemd/system/traefik.service.d/env.conf > /dev/null <<EOF
[Service]
EnvironmentFile=/etc/traefik/.env
EOF
sudo systemctl daemon-reload

# --- Summary ---
echo ""
echo "=============================================="
log_info "Deployment complete!"
echo "=============================================="
echo ""
echo "  Files deployed to: ${DEPLOY_DIR}/"
echo "  .env permissions:  600 (root only)"
echo "  systemd override:  EnvironmentFile configured"
echo ""
echo "  Next steps:"
echo "    1. Verify configs:  sudo traefik --configFile=${DEPLOY_DIR}/traefik.yaml --check"
echo "    2. Restart Traefik: sudo systemctl restart traefik"
echo "    3. Check status:    sudo systemctl status traefik"
echo "    4. Check logs:      sudo journalctl -u traefik -n 50 --no-pager"
echo ""
