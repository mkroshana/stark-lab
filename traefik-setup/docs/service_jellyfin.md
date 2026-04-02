# Service Guide: Jellyfin

> **Prerequisites:** Complete [traefik_core_setup.md](traefik_core_setup.md) first.

## Overview

| Property | Value |
|----------|-------|
| Subdomain | `jellyfin.starklab.mkroshana.com` |
| Backend | `10.10.10.121:8096` |
| CTID | 121 |
| Config | `conf.d/jellyfin.yaml` |
| Protection | CrowdSec, rate limiting, endpoint blocking |

---

## Step 1: Deploy Config

The Jellyfin config is already included in the repo at `conf.d/jellyfin.yaml`. It includes:

- **Main router** — routes all Jellyfin traffic with CrowdSec + security headers + rate limiting
- **Auth router** — strict 5 req/min rate limit on `/Users/AuthenticateByName` (login endpoint)
- **Swagger blocker** — blocks `/api-docs` from external access (LAN-only)
- **QuickConnect blocker** — blocks `/QuickConnect` from external access (LAN-only)

Deploy with:

```bash
cd /opt/stark-lab/traefik-setup
sudo ./deploy.sh
```

Traefik auto-reloads dynamic configs — no restart needed.

---

## Step 2: Jellyfin App Settings (Optional)

In Jellyfin Dashboard → **Networking**:

1. Set **Base URL** to empty (leave blank)
2. Ensure **Allow remote connections** is enabled
3. If using a custom CSS from a CDN, pin it to a specific commit hash for supply-chain safety

---

## Step 3: Verify

### Service responds
```bash
curl -sk -o /dev/null -w "%{http_code}" https://jellyfin.starklab.mkroshana.com
# Expected: 200 or 302
```

### Blocked endpoints return 403
```bash
echo "Swagger: $(curl -sk -o /dev/null -w '%{http_code}' https://jellyfin.starklab.mkroshana.com/api-docs/swagger/index.html)"
echo "QuickConnect: $(curl -sk -o /dev/null -w '%{http_code}' https://jellyfin.starklab.mkroshana.com/QuickConnect/Enabled)"
# Both should return 403
```

### Security headers present
```bash
curl -sIk https://jellyfin.starklab.mkroshana.com | grep -iE "strict|frame|content-type-opt|xss|referrer"
```

### Rate limiting works
Try 5+ wrong logins quickly — should get HTTP 429 after ~3 attempts.

### SSL rating
Test at: [SSLLabs](https://www.ssllabs.com/ssltest/analyze.html?d=jellyfin.starklab.mkroshana.com) — target **A+**.

---

## Security Hardening Summary

| Protection | How |
|-----------|-----|
| HTTPS/TLS | Let's Encrypt wildcard via DNS-01, min TLS 1.2, sniStrict |
| Brute-force | `auth-rate-limit` (5 req/min on `/Users/AuthenticateByName`) |
| Bot/threat blocking | CrowdSec bouncer |
| Swagger API docs | `block-external` middleware (LAN-only) |
| QuickConnect | `block-external` middleware (LAN-only) |
| Security headers | HSTS, X-Frame-Options, nosniff, XSS filter |

---

## Troubleshooting

### Icons not showing
The CSP header may block icon fonts. The shared middlewares in `_shared.yaml` intentionally omit CSP to avoid breaking Jellyfin themes and plugins.

### "Select Server" page on first visit
Click **Add Server** → enter `https://jellyfin.starklab.mkroshana.com`.

### Login returns "Connection Failure"
```bash
# Check if Jellyfin is running
curl http://10.10.10.121:8096/System/Ping

# If 500 error → restart Jellyfin (SQLite cache issue)
ssh root@10.10.10.121
systemctl restart jellyfin
```
