#!/usr/bin/env bash
# ==============================================
# NeutralFin Theme: one-command release
#
#   ./ship.sh           check everything, ask once, deploy to live, verify
#   ./ship.sh --check   check everything, change nothing
#
# Steps: build -> package state on CT 121 -> compare with the live theme ->
# who is watching -> confirm -> deploy.sh --live -> verify through Traefik.
# It never commits; it prints the git commands at the end.
#
# The "who is watching" check needs a Jellyfin API key in .env next to this
# script (see .env.example). Without one it warns and carries on.
# ==============================================

set -euo pipefail

PVE_HOST="root@10.10.10.31"
JF_CT=121
TRAEFIK_CT=100
WEB_ROOT="/usr/share/jellyfin/web"
LIVE_CSS="${WEB_ROOT}/themes/dark/theme.css"
TRAEFIK_HOSTS="jellyfin.starklab.mkroshana.com jellyfin.local.starklab.mkroshana.com"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CHECK_ONLY=false
case "${1:-}" in
  "") ;;
  --check) CHECK_ONLY=true ;;
  *) echo "Usage: $0 [--check]" >&2; exit 2 ;;
esac

PYTHON="$(command -v python || command -v python3)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

step() { printf '\n[%s] %s\n' "$1" "$2"; }
warn() { printf '  ! %s\n' "$1"; }

# Read .env without executing it (and tolerate Windows line endings)
env_value() {
  [ -f .env ] || return 0
  grep -E "^$1=" .env | tail -n 1 | cut -d= -f2- | tr -d '\r' || true
}
JELLYFIN_API_KEY="$(env_value JELLYFIN_API_KEY)"
JELLYFIN_URL="$(env_value JELLYFIN_URL)"
JELLYFIN_URL="${JELLYFIN_URL:-https://jellyfin.local.starklab.mkroshana.com}"

# ----------------------------------------------
step "1/5" "Build"
"$PYTHON" build.py
NEW_MD5="$(md5sum neutralfin.min.css | cut -d' ' -f1)"

# ----------------------------------------------
step "2/5" "Package state on CT $JF_CT"
DPKG="$(ssh "$PVE_HOST" "pct exec $JF_CT -- dpkg -V jellyfin-web" || true)"
STOCK=true
if printf '%s\n' "$DPKG" | grep -q "themes/dark/theme.css"; then STOCK=false; fi
OTHERS="$(printf '%s\n' "$DPKG" | grep -v "themes/dark/theme.css" | grep -v '^\s*$' || true)"
if [ -n "$OTHERS" ]; then
  warn "Other jellyfin-web files differ from the package (expected none):"
  printf '%s\n' "$OTHERS" | sed 's/^/      /'
else
  echo "  jellyfin-web is stock apart from theme.css."
fi

# ----------------------------------------------
step "3/5" "Compare with the live theme"
ssh "$PVE_HOST" "pct exec $JF_CT -- cat $LIVE_CSS" > "$TMP/live.css"
LIVE_MD5="$(md5sum "$TMP/live.css" | cut -d' ' -f1)"
if [ "$STOCK" = true ]; then
  echo "  theme.css is Jellyfin's stock file: a jellyfin-web update has reset it."
  echo "  Deploying restores the NeutralFin theme."
elif [ "$LIVE_MD5" = "$NEW_MD5" ]; then
  echo "  Live theme.css already matches this build (md5 $NEW_MD5). Nothing to deploy."
  exit 0
else
  echo "  Live md5 $LIVE_MD5 -> new build md5 $NEW_MD5"
  "$PYTHON" tools/css_equiv.py "$TMP/live.css" neutralfin.css > "$TMP/equiv.txt" || true
  grep -E "^(keys|REMOVED|ADDED|CHANGED)" "$TMP/equiv.txt" | sed 's/^/  /'
  echo "  First differences:"
  grep -E "^   " "$TMP/equiv.txt" | head -n 12 | cut -c1-150 | sed 's/^/  /'
fi

# ----------------------------------------------
step "4/5" "Who is watching"
if [ -z "$JELLYFIN_API_KEY" ]; then
  warn "No JELLYFIN_API_KEY in .env, so this check is skipped (see .env.example)."
else
  if curl -fsS --max-time 15 \
      -H "Authorization: MediaBrowser Token=\"${JELLYFIN_API_KEY}\"" \
      "${JELLYFIN_URL}/Sessions?activeWithinSeconds=960" > "$TMP/sessions.json"; then
    "$PYTHON" - "$TMP/sessions.json" <<'PY'
import json, sys
sessions = json.load(open(sys.argv[1], encoding="utf-8"))
playing = [s for s in sessions if s.get("NowPlayingItem")]
if not playing:
    print("  Nobody is playing anything.")
for s in playing:
    state = "paused" if (s.get("PlayState") or {}).get("IsPaused") else "playing"
    print(f'  {s.get("UserName", "?")} on {s.get("DeviceName", "?")} ({s.get("Client", "?")}): '
          f'{s["NowPlayingItem"].get("Name", "?")} [{state}]')
if playing:
    print("  A theme deploy does not interrupt playback; viewers get it on their next page load.")
PY
  else
    warn "Could not reach ${JELLYFIN_URL}/Sessions (wrong key or URL?)."
  fi
fi

# ----------------------------------------------
step "5/5" "Deploy"
if [ "$CHECK_ONLY" = true ]; then
  echo "  --check: nothing changed."
  exit 0
fi
ANSWER=""
read -r -p "  Deploy this build to live theme.css now? [y/N] " ANSWER || true
case "$ANSWER" in
  [Yy]*) ;;
  *) echo "  Not deployed."; exit 0 ;;
esac

./deploy.sh --live

echo "  Checking what Traefik serves:"
FAIL=0
for H in $TRAEFIK_HOSTS; do
  RESULT="$(ssh "$PVE_HOST" "pct exec $TRAEFIK_CT -- bash -s $H" <<'REMOTE'
H="$1"
U="https://$H/web/themes/dark/theme.css"
curl -s --resolve "$H:443:127.0.0.1" "$U" | md5sum | cut -d' ' -f1
curl -s -o /dev/null -D - --resolve "$H:443:127.0.0.1" "$U" | tr -d '\r' | grep -i '^cache-control:' || echo 'cache-control: none'
REMOTE
)"
  SERVED_MD5="$(printf '%s\n' "$RESULT" | head -n 1)"
  CACHE="$(printf '%s\n' "$RESULT" | tail -n 1)"
  if [ "$SERVED_MD5" = "$NEW_MD5" ]; then
    echo "    $H: md5 ok, $CACHE"
  else
    echo "    $H: md5 $SERVED_MD5 does not match the build $NEW_MD5" >&2
    FAIL=1
  fi
done

ssh "$PVE_HOST" "pct exec $JF_CT -- rm -f ${WEB_ROOT}/neutralfin-staging.css"

if [ "$FAIL" -ne 0 ]; then
  echo "  Deployed, but Traefik is not serving the new file. Check CT $TRAEFIK_CT." >&2
  exit 1
fi
echo "  Live. Viewers get it on their next page load."

if [ -n "$(git status --short -- neutralfin.css neutralfin.min.css 2>/dev/null)" ]; then
  echo
  echo "  Not committed yet. When you are ready:"
  echo "    git add jellyfin/themes/neutralfin.css jellyfin/themes/neutralfin.min.css"
  echo "    git commit -m \"<one-line message>\""
fi
