#!/usr/bin/env bash
# ==============================================
# NeutralFin Theme Deploy Script
# Builds neutralfin.min.css and copies it into Jellyfin (CT 121 on pve1).
#
#   ./deploy.sh --stage   -> /usr/share/jellyfin/web/neutralfin-staging.css
#                            No page loads this file, so viewers see nothing.
#                            Used to preview a change in one browser tab.
#   ./deploy.sh --live    -> /usr/share/jellyfin/web/themes/dark/theme.css
#                            Every viewer gets it on their next page load.
#
# A jellyfin-web package update restores the stock theme.css, so run
# --live again after every Jellyfin update.
# ==============================================

set -euo pipefail

PVE_HOST="root@10.10.10.31"
CTID=121
WEB_ROOT="/usr/share/jellyfin/web"
TMP="/tmp/neutralfin.min.css"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIN_CSS="${SCRIPT_DIR}/neutralfin.min.css"

case "${1:-}" in
  --stage) DEST="${WEB_ROOT}/neutralfin-staging.css" ;;
  --live)  DEST="${WEB_ROOT}/themes/dark/theme.css" ;;
  *) echo "Usage: $0 --stage | --live" >&2; exit 2 ;;
esac

PYTHON="$(command -v python || command -v python3)"
"$PYTHON" "${SCRIPT_DIR}/build.py"
LOCAL_MD5="$(md5sum "$MIN_CSS" | cut -d' ' -f1)"

if [ "$1" = "--live" ]; then
  # Keep a copy of the stock theme.css whenever the current one is still stock
  # (dpkg -V lists only files that differ from the package).
  ssh "$PVE_HOST" "pct exec $CTID -- bash -c 'dpkg -V jellyfin-web | grep -q themes/dark/theme.css \
    || cp ${WEB_ROOT}/themes/dark/theme.css ${WEB_ROOT}/themes/dark/theme.css.orig'"
fi

scp -q "$MIN_CSS" "${PVE_HOST}:${TMP}"
ssh "$PVE_HOST" "pct push $CTID $TMP $DEST --perms 0644 && rm -f $TMP"

REMOTE_MD5="$(ssh "$PVE_HOST" "pct exec $CTID -- md5sum $DEST" | cut -d' ' -f1)"
if [ "$LOCAL_MD5" != "$REMOTE_MD5" ]; then
  echo "md5 mismatch: local $LOCAL_MD5, CT $CTID $REMOTE_MD5" >&2
  exit 1
fi
echo "Deployed to CT $CTID:$DEST (md5 $REMOTE_MD5)"

if [ "$1" = "--live" ]; then
  echo "Files in jellyfin-web that differ from the package (expect only theme.css):"
  ssh "$PVE_HOST" "pct exec $CTID -- dpkg -V jellyfin-web" || true
fi
