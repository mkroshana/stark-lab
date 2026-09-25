#!/bin/bash
# ==============================================================================
# CrowdSec Traefik Plugin Auto-Updater
# Location: /usr/local/bin/update-crowdsec-plugin.sh
#
# Safely checks for newer releases of the CrowdSec Traefik bouncer plugin,
# stages and verifies the files, and applies them locally with automatic rollback
# if Traefik fails to start or healthcheck fails.
# ==============================================================================

set -euo pipefail

PLUGIN_MODULE="github.com/maxlerebourg/crowdsec-bouncer-traefik-plugin"
REPO_OWNER_NAME="maxlerebourg/crowdsec-bouncer-traefik-plugin"
TRAEFIK_DIR="/etc/traefik"
PLUGINS_LOCAL_DIR="${TRAEFIK_DIR}/plugins-local"
TARGET_DIR="${PLUGINS_LOCAL_DIR}/src/${PLUGIN_MODULE}"
VERSION_FILE="${PLUGINS_LOCAL_DIR}/.crowdsec-version"
BACKUP_DIR="${PLUGINS_LOCAL_DIR}.bak"
LOG_FILE="/var/log/traefik/plugin-update.log"

FORCE=false
CHECK_ONLY=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)
      FORCE=true
      shift
      ;;
    --check)
      CHECK_ONLY=true
      shift
      ;;
    *)
      echo "Usage: $0 [--check] [--force]"
      exit 1
      ;;
  esac
done

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

log() {
  local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
  echo "$msg"
  echo "$msg" >> "$LOG_FILE"
}

log_err() {
  local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $1"
  echo -e "\033[0;31m$msg\033[0m" >&2
  echo "$msg" >> "$LOG_FILE"
}

if [ "$(id -u)" -ne 0 ]; then
  log_err "This script must be run as root."
  exit 1
fi

for cmd in curl unzip systemctl; do
  if ! command -v "$cmd" &>/dev/null; then
    log_err "Missing required dependency: $cmd"
    exit 1
  fi
done

# Current installed version
CURRENT_VERSION=""
if [ -f "$VERSION_FILE" ]; then
  CURRENT_VERSION=$(tr -d '[:space:]' < "$VERSION_FILE")
fi

log "Checking latest release for ${REPO_OWNER_NAME}..."
RELEASE_JSON=$(curl -sSL -m 10 "https://api.github.com/repos/${REPO_OWNER_NAME}/releases/latest" 2>/dev/null || true)
LATEST_TAG=$(echo "$RELEASE_JSON" | grep -m 1 '"tag_name":' | sed -E 's/.*"tag_name": *"([^"]+)".*/\1/' || true)

if [ -z "$LATEST_TAG" ]; then
  log "Unable to fetch latest release from GitHub API (rate-limited or offline). Skipping check."
  exit 0
fi

log "Current version: ${CURRENT_VERSION:-unknown} | Latest upstream: ${LATEST_TAG}"

if [ "$CHECK_ONLY" = true ]; then
  if [ "$CURRENT_VERSION" != "$LATEST_TAG" ]; then
    echo "Update available: $CURRENT_VERSION -> $LATEST_TAG"
    exit 10
  else
    echo "Up to date: $CURRENT_VERSION"
    exit 0
  fi
fi

if [ "$CURRENT_VERSION" = "$LATEST_TAG" ] && [ "$FORCE" = false ]; then
  log "CrowdSec bouncer plugin is already up to date (${CURRENT_VERSION})."
  exit 0
fi

log "Starting update to ${LATEST_TAG}..."

# Setup temporary staging directory
STAGE_DIR=$(mktemp -d /tmp/crowdsec-stage.XXXXXX)
cleanup() {
  rm -rf "$STAGE_DIR"
}
trap cleanup EXIT

ZIP_PATH="${STAGE_DIR}/plugin.zip"

# Download package (prefer Traefik plugin catalog bundle, fallback to GitHub release zipball)
DOWNLOAD_URL="https://plugins.traefik.io/public/download/${PLUGIN_MODULE}/${LATEST_TAG}"
HTTP_STATUS=$(curl -sSL -w "%{http_code}" -o "$ZIP_PATH" -m 30 "$DOWNLOAD_URL" 2>/dev/null || echo "000")

if [ "$HTTP_STATUS" != "200" ]; then
  log "Catalog download returned $HTTP_STATUS, falling back to GitHub archive..."
  DOWNLOAD_URL="https://github.com/${REPO_OWNER_NAME}/archive/refs/tags/${LATEST_TAG}.zip"
  HTTP_STATUS=$(curl -sSL -w "%{http_code}" -o "$ZIP_PATH" -m 30 "$DOWNLOAD_URL" 2>/dev/null || echo "000")
fi

if [ "$HTTP_STATUS" != "200" ] || [ ! -s "$ZIP_PATH" ]; then
  log_err "Failed to download plugin release from ${DOWNLOAD_URL} (HTTP status: ${HTTP_STATUS})"
  exit 1
fi

# Extract and verify
unzip -q "$ZIP_PATH" -d "${STAGE_DIR}/extracted"
EXTRACTED_SRC=$(find "${STAGE_DIR}/extracted" -maxdepth 2 -type f -name ".traefik.yml" -exec dirname {} \; | head -n 1)

if [ -z "$EXTRACTED_SRC" ] || [ ! -f "${EXTRACTED_SRC}/.traefik.yml" ] || [ ! -f "${EXTRACTED_SRC}/bouncer.go" ]; then
  log_err "Extracted archive is missing required plugin files (.traefik.yml or bouncer.go). Aborting update."
  exit 1
fi

log "Plugin integrity verified in staging."

# Backup existing installation if present
if [ -d "$TARGET_DIR" ]; then
  rm -rf "$BACKUP_DIR"
  cp -a "$PLUGINS_LOCAL_DIR" "$BACKUP_DIR"
fi

# Install new version
mkdir -p "$TARGET_DIR"
# Clear existing plugin files (including hidden dotfiles)
rm -rf "${TARGET_DIR:?}"/* "${TARGET_DIR}"/.[!.]* "${TARGET_DIR}"/..?* 2>/dev/null || true
cp -a "${EXTRACTED_SRC}/." "$TARGET_DIR/"

log "Files staged into ${TARGET_DIR}. Restarting Traefik to verify..."

# Restart Traefik and perform healthcheck
systemctl restart traefik || true

HEALTHY=false
for i in {1..15}; do
  sleep 1
  if systemctl is-active --quiet traefik; then
    # Verify no plugin error occurred in log during startup
    if ! tail -n 25 /var/log/traefik/traefik.log 2>/dev/null | grep -q 'failed to open the plugin manifest\|Plugins are disabled because an error has occurred\|invalid middleware "crowdsec-bouncer@file"'; then
      HEALTHY=true
      break
    fi
  fi
done

if [ "$HEALTHY" = true ]; then
  echo "$LATEST_TAG" > "$VERSION_FILE"
  rm -rf "$BACKUP_DIR"
  log "Successfully updated CrowdSec bouncer plugin to ${LATEST_TAG}."
  exit 0
else
  log_err "Traefik failed health check after updating plugin to ${LATEST_TAG}."
  if [ -d "$BACKUP_DIR" ]; then
    log "Initiating automatic rollback to previous version..."
    rm -rf "$PLUGINS_LOCAL_DIR"
    mv "$BACKUP_DIR" "$PLUGINS_LOCAL_DIR"
    systemctl restart traefik
    log "Rollback completed. Restored ${CURRENT_VERSION:-previous version}."
  fi
  exit 1
fi
