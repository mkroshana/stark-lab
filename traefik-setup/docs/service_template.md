# Service Template — Adding Any New Service

> **Prerequisites:** Complete [traefik_core_setup.md](traefik_core_setup.md) first.

## Zero-Touch Onboarding

After the core setup is done, adding a new service requires:

| What | Needed? |
|------|---------|
| DNS record | ❌ No — wildcard `*.starklab` covers it |
| SSL certificate | ❌ No — wildcard cert covers it |
| Traefik restart | ❌ No — file watcher auto-reloads |
| DDNS changes | ❌ No — wildcard is already updated |
| Router changes | ❌ No — ports 80/443 are already forwarded |
| Secret management | ❌ No — secrets are in `.env`, shared across all configs |
| **Config file** | ✅ **Yes — add a YAML in `conf.d/` and run `deploy.sh`** |

---

## Template

Create a new file at `conf.d/<service-name>.yaml` in the repo:

```yaml
# conf.d/<service-name>.yaml
http:
  routers:
    <service-name>:
      rule: "Host(`<subdomain>.starklab.mkroshana.com`)"
      entryPoints:
        - websecure
      service: <service-name>-svc
      middlewares:
        - crowdsec-bouncer
        - security-headers
        - general-rate-limit
      tls:
        certResolver: cloudflare
      priority: 1

  services:
    <service-name>-svc:
      loadBalancer:
        servers:
          - url: "http://<LXC_IP>:<PORT>"
        passHostHeader: true
```

### Placeholders

| Placeholder | Example | Description |
|-------------|---------|-------------|
| `<service-name>` | `immich` | Unique name (used in router/service IDs) |
| `<subdomain>` | `photos` | The subdomain prefix |
| `<LXC_IP>` | `10.10.10.130` | LXC container IP |
| `<PORT>` | `2283` | Service port |

---

## Deploy

```bash
cd /opt/stark-lab/traefik-setup
# Add your new config file to conf.d/
sudo ./deploy.sh
```

`deploy.sh` processes all `conf.d/*.yaml` files, substitutes any `${ENV_VAR}` references, and deploys to `/etc/traefik/conf.d/`. Traefik auto-reloads — no restart needed.

### Verify

```bash
curl -sk -o /dev/null -w "%{http_code}" https://<subdomain>.starklab.mkroshana.com
```

---

## Optional: Add Endpoint Blocking

If the service has admin or API endpoints to hide externally:

```yaml
    # Block admin panel from external access
    <service-name>-block-admin:
      rule: "Host(`<subdomain>.starklab.mkroshana.com`) && PathPrefix(`/admin`)"
      entryPoints:
        - websecure
      service: <service-name>-svc
      middlewares:
        - block-external
      tls:
        certResolver: cloudflare
      priority: 100
```

The `block-external` middleware (from `_shared.yaml`) allows only LAN IPs (`10.10.10.0/24`, `192.168.0.0/16`).

---

## Optional: Add Auth Rate Limiting

If the service has a login endpoint:

```yaml
    <service-name>-auth:
      rule: "Host(`<subdomain>.starklab.mkroshana.com`) && PathPrefix(`/api/auth`)"
      entryPoints:
        - websecure
      service: <service-name>-svc
      middlewares:
        - crowdsec-bouncer
        - security-headers
        - auth-rate-limit
      tls:
        certResolver: cloudflare
      priority: 50
```

---

## Removing a Service

```bash
# Remove from repo
rm conf.d/<service-name>.yaml

# Re-deploy (removes from /etc/traefik/conf.d/ too)
cd /opt/stark-lab/traefik-setup
sudo ./deploy.sh
```

Traefik removes the routes automatically.

> [!NOTE]
> `deploy.sh` copies all `conf.d/*.yaml` files from the repo. If you remove a file from the repo but don't remove it from `/etc/traefik/conf.d/`, it will persist until manually deleted. Run `sudo rm /etc/traefik/conf.d/<service-name>.yaml` if needed.

---

## Available Shared Middlewares

Defined in `_shared.yaml` — use any of these in your router's `middlewares` list:

| Middleware | Purpose |
|-----------|---------|
| `crowdsec-bouncer` | Block malicious IPs via CrowdSec |
| `security-headers` | HSTS, X-Frame-Options, nosniff, etc. |
| `general-rate-limit` | 100 req/min, burst 200 |
| `auth-rate-limit` | 5 req/min, burst 3 (for login endpoints) |
| `block-external` | Allow only LAN IPs (10.10.10.0/24) |

---

## Service Checklist

When adding a new service, verify:

- [ ] Config file added to `conf.d/` in the repo
- [ ] Router name is unique across all configs
- [ ] Service name is unique across all configs
- [ ] Backend URL is reachable from Traefik LXC (`curl http://<IP>:<PORT>`)
- [ ] `deploy.sh` ran successfully
- [ ] App-side settings updated (trusted proxies, base URL, etc.)
- [ ] Test HTTPS access: `curl -sk https://<subdomain>.starklab.mkroshana.com`
- [ ] Test from mobile data (not home WiFi)
