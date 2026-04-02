#!/bin/bash
# ==============================================
# Cloudflare DDNS Updater
# Location: /usr/local/bin/cloudflare-ddns.sh
# Updates jellyfin.mkroshana.com A record when IP changes
# ==============================================

# --- Configuration (loaded from .env) ---
ENV_FILE="/etc/traefik/.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "$(date): ERROR - .env file not found at $ENV_FILE" >> "/var/log/cloudflare-ddns.log"
  exit 1
fi
# shellcheck source=/dev/null
source "$ENV_FILE"

# Validate required variables
for VAR in CF_API_TOKEN CF_ZONE_NAME CF_RECORD_NAME; do
  if [ -z "${!VAR}" ]; then
    echo "$(date): ERROR - $VAR is not set in $ENV_FILE" >> "/var/log/cloudflare-ddns.log"
    exit 1
  fi
done

ZONE_NAME="$CF_ZONE_NAME"
RECORD_NAME="$CF_RECORD_NAME"
PROXIED="${CF_PROXIED:-false}"
TTL="${CF_TTL:-120}"

# --- Script (don't edit below) ---
LOG_FILE="/var/log/cloudflare-ddns.log"

# Get current public IP
CURRENT_IP=$(curl -4 -s https://api.ipify.org)
if [[ -z "$CURRENT_IP" ]]; then
  echo "$(date): ERROR - Could not determine public IP" >> "$LOG_FILE"
  exit 1
fi

# Get Zone ID
ZONE_ID=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones?name=${ZONE_NAME}" \
  -H "Authorization: Bearer ${CF_API_TOKEN}" \
  -H "Content-Type: application/json" | grep -oP '"id":"\K[^"]+' | head -1)

if [[ -z "$ZONE_ID" ]]; then
  echo "$(date): ERROR - Could not get Zone ID" >> "$LOG_FILE"
  exit 1
fi

# Get existing record
RECORD_DATA=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/dns_records?name=${RECORD_NAME}&type=A" \
  -H "Authorization: Bearer ${CF_API_TOKEN}" \
  -H "Content-Type: application/json")

RECORD_ID=$(echo "$RECORD_DATA" | grep -oP '"id":"\K[^"]+' | head -1)
RECORD_IP=$(echo "$RECORD_DATA" | grep -oP '"content":"\K[^"]+' | head -1)

# Only update if IP has changed
if [[ "$CURRENT_IP" == "$RECORD_IP" ]]; then
  # IP unchanged — silent exit (no log spam)
  exit 0
fi

# Update the record
RESPONSE=$(curl -s -X PUT "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/dns_records/${RECORD_ID}" \
  -H "Authorization: Bearer ${CF_API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data "{\"type\":\"A\",\"name\":\"${RECORD_NAME}\",\"content\":\"${CURRENT_IP}\",\"ttl\":${TTL},\"proxied\":${PROXIED}}")

SUCCESS=$(echo "$RESPONSE" | grep -oP '"success":\K[^,]+')

if [[ "$SUCCESS" == "true" ]]; then
  echo "$(date): Updated ${RECORD_NAME} from ${RECORD_IP} to ${CURRENT_IP}" >> "$LOG_FILE"
else
  echo "$(date): ERROR - Failed to update: ${RESPONSE}" >> "$LOG_FILE"
fi
