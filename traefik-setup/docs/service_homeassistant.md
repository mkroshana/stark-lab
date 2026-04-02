# Service Guide: Home Assistant

> **Prerequisites:** Complete [traefik_core_setup.md](traefik_core_setup.md) first.

## Overview

| Property | Value |
|----------|-------|
| Subdomain | `ha.starklab.mkroshana.com` |
| Backend | `10.10.10.154:8123` |
| CTID | 150 |
| Config | `conf.d/homeassistant.yaml` |
| Protection | CrowdSec, rate limiting, auth rate limiting, security headers |

---

## Step 1: Deploy Config

The Home Assistant config is already included in the repo at `conf.d/homeassistant.yaml`. It includes:

- **Main router** — routes all HA traffic with CrowdSec + security headers + rate limiting
- **Auth router** — strict 5 req/min rate limit on `/auth` endpoint (login brute-force protection)

Deploy with:

```bash
cd /opt/stark-lab/traefik-setup
sudo ./deploy.sh
```

Traefik auto-reloads dynamic configs — no restart needed.

---

## Step 2: Configure Home Assistant

> [!IMPORTANT]
> Without `trusted_proxies`, Home Assistant will reject all requests from Traefik with a **400 Bad Request** error.

### 2.1 SSH into Home Assistant LXC

```bash
ssh root@10.10.10.154
```

### 2.2 Edit configuration.yaml

Find and edit the HA configuration file:

```bash
# Common locations depending on install type:
nano /config/configuration.yaml          # HA OS / Container
nano /root/.homeassistant/configuration.yaml   # Manual install
nano /home/homeassistant/.homeassistant/configuration.yaml  # venv install
```

Add or update the `http` section:

```yaml
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 10.10.10.100    # Traefik LXC IP
```

> [!NOTE]
> If there's already an `http:` section, merge the settings — don't create a duplicate. YAML does not allow duplicate keys.

### 2.3 Restart Home Assistant

```bash
# Depends on install method — try in order:
ha core restart                          # HA OS
systemctl restart home-assistant@homeassistant   # systemd
systemctl restart hass                   # some installs
```

---

## Step 3: Verify

### Service responds
```bash
curl -sk -o /dev/null -w "%{http_code}" https://ha.starklab.mkroshana.com
# Expected: 200 or 302 (redirect to login)
```

### WebSocket works
Home Assistant's UI depends entirely on WebSocket connections. If you see the login page and can interact with the UI, WebSockets are working.

> Traefik v3 handles WebSocket upgrade natively — no special middleware needed.

### Security headers present
```bash
curl -sIk https://ha.starklab.mkroshana.com | grep -iE "strict|frame|content-type-opt|xss|referrer"
```

### Auth rate limiting works
Try 5+ wrong logins quickly — should get rate limited after ~3 attempts.

### Test from mobile (on cellular data)
Open `https://ha.starklab.mkroshana.com` — should show the HA login page with a valid certificate.

---

## HA Mobile App Configuration

To use the Home Assistant Companion app remotely:

1. Open the app → **Settings** → **Companion App** → **Server**
2. Set **External URL**: `https://ha.starklab.mkroshana.com`
3. Set **Internal URL**: `http://10.10.10.154:8123`

The app will automatically use the internal URL when on your home WiFi and the external URL when away.

---

## Troubleshooting

### 400 Bad Request
```
You are not allowed to access this resource.
```
- `trusted_proxies` is not set or wrong IP
- Verify: `grep trusted_proxies /config/configuration.yaml`
- Ensure the IP matches Traefik's LXC: `10.10.10.100`
- Restart HA after changes

### Page loads but UI is blank / spinning
- WebSocket issue — check browser console for WS errors
- Ensure no other middleware is stripping upgrade headers
- Try a hard refresh: `Ctrl+Shift+R`

### "Unable to connect to Home Assistant"
```bash
# Check if HA is running
curl http://10.10.10.154:8123
# If fails → HA is down
ssh root@10.10.10.154
systemctl status home-assistant@homeassistant
```

### HA automations/integrations break after proxy
Some integrations hardcode the internal URL. In HA settings:
- Go to **Settings** → **System** → **Network**
- Set the **External URL** to `https://ha.starklab.mkroshana.com`
- Set the **Internal URL** to `http://10.10.10.154:8123`
