# Service Guide: Plex

> **Prerequisites:** Complete [traefik_core_setup.md](traefik_core_setup.md) first.

## Overview

| Property | Value |
|----------|-------|
| Subdomain | `plex.starklab.mkroshana.com` |
| Backend | `10.10.10.120:32400` |
| CTID | 120 |
| Config | `conf.d/plex.yaml` |
| Protection | CrowdSec, rate limiting, auth rate limiting, security headers |

---

## Step 1: Deploy Config

The Plex config is already included in the repo at `conf.d/plex.yaml`. It includes:

- **Main router** — routes all Plex traffic with CrowdSec + security headers + rate limiting
- **Auth router** — strict 5 req/min rate limit on `/users/sign_in` endpoint (login brute-force protection)

Deploy with:

```bash
cd /opt/stark-lab/traefik-setup
sudo ./deploy.sh
```

Traefik auto-reloads dynamic configs — no restart needed.

---

## Step 2: Configure Plex App Settings

> [!IMPORTANT]
> These Plex-side changes are **required** — without them, Plex will conflict with Traefik.

### 2.1 Open Plex Settings

Go to `http://10.10.10.120:32400/web` → **Settings** (wrench icon)

### 2.2 Network Settings

Navigate to **Settings** → **Network** (under "Settings"):

1. **Custom server access URLs:** `https://plex.starklab.mkroshana.com:443`
2. **Secure connections:** `Preferred`
   - Do NOT set to `Required` — Traefik terminates SSL, so the connection from Traefik → Plex is HTTP internally
3. **List of IP addresses and networks that are allowed without auth:** `10.10.10.0/24`
   - This allows LAN clients to connect without re-authenticating through Plex.tv

### 2.3 Remote Access

Navigate to **Settings** → **Remote Access**:

1. **Disable Remote Access** (uncheck / turn off)

> [!WARNING]
> If you leave Remote Access enabled, Plex will try to open port 32400 directly to the internet, bypassing all of Traefik's security (CrowdSec, rate limiting, headers).

### 2.4 Save and restart Plex

```bash
# On the Plex LXC
ssh root@10.10.10.120
systemctl restart plexmediaserver
```

---

## Step 3: Verify

### Service responds
```bash
curl -sk -o /dev/null -w "%{http_code}" https://plex.starklab.mkroshana.com
# Expected: 200 or 301
```

### Security headers present
```bash
curl -sIk https://plex.starklab.mkroshana.com | grep -iE "strict|frame|content-type-opt|xss|referrer"
```

### Plex clients can find server
1. Open `https://plex.starklab.mkroshana.com` in browser
2. Sign in with your Plex account
3. The server should appear in the sidebar

### Test from mobile (on cellular data)
Open `https://plex.starklab.mkroshana.com` — should load the Plex web UI with a valid certificate.

---

## How Plex Through Traefik Works

```
Mobile App / Browser
        │
        ▼ HTTPS
   *.starklab.mkroshana.com (Cloudflare DNS → your public IP)
        │
        ▼ :443
   Router → Traefik (10.10.10.101)
        │
        ▼ sniStrict → CrowdSec check → Rate limit → Security headers
        │
        ▼ HTTP
   Plex (10.10.10.120:32400)
```

- **Auth** is handled by Plex.tv (external), so auth rate limiting targets the proxy-level sign-in endpoint
- **Streaming** goes through Traefik → Plex over the LAN (internal HTTP is fine)
- **SSL termination** happens at Traefik — Plex sees plain HTTP

---

## Troubleshooting

### Plex says "Not available outside your network"
- Ensure Remote Access is **disabled** in Plex
- Ensure Custom server access URLs is set to `https://plex.starklab.mkroshana.com:443`
- Restart Plex after changes

### Plex mobile app can't connect
- In the Plex app, go to **Settings** → **Advanced** → **Custom server URL**
- Enter: `https://plex.starklab.mkroshana.com`
- If the app still can't connect, sign out and sign back into Plex.tv in the app

### Buffering on remote playback
- Check if Plex is transcoding (CPU usage on CTID 120)
- If the Traefik LXC is bottlenecking (512 MiB RAM), consider increasing its resources
- Direct Play reduces load — configure Plex clients to prefer Direct Play

### Port 32400 still accessible externally
- Delete any port 32400 forward from the router
- Verify: `curl http://YOUR_PUBLIC_IP:32400` should timeout (connection refused)
