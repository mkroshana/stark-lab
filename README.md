# 🛡️ Stark-Lab: Highly Secure Traefik Infrastructure for your Homelab
(Disclosure: AI helped me with this and I'm new to Traefik and this is a work in progress. Open to any suggestions.)

![Traefik](https://img.shields.io/badge/Traefik-v3-blue?style=for-the-badge&logo=traefik)
![Cloudflare](https://img.shields.io/badge/Cloudflare-DNS--01-orange?style=for-the-badge&logo=cloudflare)
![CrowdSec](https://img.shields.io/badge/CrowdSec-Secured-red?style=for-the-badge&logo=crowdsec)
![Bash](https://img.shields.io/badge/Deploy-Automated-brightgreen?style=for-the-badge&logo=gnu-bash)

A highly secure reverse proxy architecture built with **Traefik v3**. Designed to securely expose internal homelab services (Plex, Jellyfin, Home Assistant) to the internet while maintaining strict access controls, automated SSL, and real-time threat protection.

---

## ✨ Key Features

- **Traefik v3 (Native Install):** High-performance routing using the robust File Provider architecture.
- **Automated Wildcard SSL:** Utilizes Let's Encrypt and the Cloudflare DNS-01 challenge to automatically provision and renew wildcard certificates (`*.yourdomain.com`) without exposing Port 80 to the internet.
- **CrowdSec Integration:** Built-in CrowdSec bouncer middleware to actively block malicious IPs and known threats in real-time.
- **Defense-in-Depth Security:**
  - Strict security headers (HSTS, XSS protection, Frame Deny).
  - Rate limiting on global routes and aggressive rate limiting on authentication endpoints.
  - "Catch-All" router to drop unrecognized host requests.
  - Internal dashboard access strictly protected by automated Basic Auth and LAN-only IP allowlisting.
- **Modular & Scalable:** Individual `.yaml` configuration files for each service, allowing you to seamlessly plug in new applications without touching core routing logic.
- **Automated Deployment:** A smart `deploy.sh` engine that natively handles password hashing, secure credential injection via `.env`, and configuration deployment.

---

## 📂 Repository Structure

```text
stark-lab/
├── traefik-setup/
│   ├── .env.example       # Template for required secrets
│   ├── deploy.sh          # Automated deployment and hashing script
│   ├── traefik.yaml       # Core static Traefik configuration
│   └── conf.d/            # Dynamic service routing configurations
│       ├── _shared.yaml      # Global middlewares (Crowdsec, Headers, Rate limits)
│       ├── catch-all.yaml    # Drops invalid traffic
│       ├── dashboard.yaml    # Secure Traefik dashboard
│       ├── homeassistant.yaml# HA Routing
│       ├── jellyfin.yaml     # Jellyfin Routing
│       ├── local-*.yaml      # Local-only routing configurations (PVE, Unraid, etc.)
│       ├── plex.yaml         # Plex Routing
│       └── tls.yaml          # Strict TLS/SNI enforcement
```

---

## 🚀 Getting Started

### Prerequisites
1. A Linux server (e.g., Proxmox LXC running Ubuntu).
2. Traefik v3 installed locally.
3. A Cloudflare account managing your domain's DNS.
4. CrowdSec installed with the Traefik Bouncer plugin.

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/stark-lab.git
   cd stark-lab/traefik-setup
   ```

2. **Configure your Environment:**
   Copy the example environment file and fill in your secure credentials.
   ```bash
   cp .env.example .env
   nano .env
   ```
   > ⚠️ **SECURITY WARNING:** Never commit your `.env` file to version control. It must remain in your `.gitignore`.

3. **Deploy:**
   Run the deployment engine. The script will dynamically generate your Basic Auth hashes, securely inject your Cloudflare API tokens, and restart Traefik.
   ```bash
   sudo chmod +x deploy.sh
   sudo ./deploy.sh
   ```

4. **Verify:**
   Navigate to the Traefik dashboard (e.g., `https://traefik.local.yourdomain.com`). Log in using the `admin` username and the plain-text password you defined in your `.env` file.

---

## 🏠 Local-Only Service Access

In addition to external access, this setup provides a secure local-only routing for specific subdomains using the `*.local.yourdomain.com` pattern. Services routed here use Traefik's `block-external` middleware, restricting access strictly to your home LAN. 

**Exposed Local Services:**
- Traefik Dashboard (`https://traefik.local.yourdomain.com` via Basic Auth)
- Jellyfin, Plex, Home Assistant, Seerr, Pterodactyl Panel (Reusing external backends)
- Duplicati (`https://10.x.x.x:8200`)
- Proxmox PVE1 (`https://10.x.x.x:8006` via `insecure-transport` SkipVerify)
- Proxmox Backup Server PBS (`https://10.x.x.x:8007` via `insecure-transport` SkipVerify)
- Unraid Tower (`https://10.x.x.x` via `insecure-transport` SkipVerify)
- Pterodactyl Wings (`10.x.x.x:8080` / `:2022` - Backend daemon/SFTP only)

### DNS Setup (Hybrid Strategy)
For best performance and reliability, we employ both local DNS rewrites and a public DNS fallback:
1. **Local DNS (Pi-hole/AdGuard Router)**:
   Add a wildcard DNS rewrite for `*.local.yourdomain.com` pointing to the Traefik LXC IP (`10.x.x.x`). This ensures instant connection without leaving your local network.
2. **Cloudflare Fallback**:
   Create an A Record for `*.local.yourdomain.com` pointing to `10.x.x.x` (Proxy **OFF** / DNS-only). While returning a local/private IP via a public DNS resolver, it acts as a reliable fallback for devices without local DNS set up, and is safely protected against internet exploitation by the `block-external` restriction rules.

---

## 🛠️ Adding a New Service

To expose a new homelab service:
1. Create a new file in `traefik-setup/conf.d/` (e.g., `myservice.yaml`).
2. Copy the structure from an existing file like `plex.yaml`.
3. Update the `rule` matching (e.g., `Host('myservice.yourdomain.com')`) and point the `loadBalancer` to your internal IP and port.
4. Rely on Traefik's native rule-length sorting (avoid setting a hard `priority` unless strictly necessary) and attach the `_shared.yaml` middlewares to instantly secure the route.
5. **CRITICAL STEP**: Update `D:\Development\service_links.md` to track the new service's public/local URLs, VM ID, IP address, and port.
6. Re-run `sudo ./deploy.sh`.

---

## 🔒 Security Best Practices

- **Zero-Trust LAN:** Even internal setups use strict routing. Services like the Traefik Dashboard and internal APIs use the `block-external` middleware to reject traffic originating outside the local subnets (`10.x.x.x`, `192.168.x.x`).
- **Hairpin NAT:** Ensure your home router supports Hairpin NAT (NAT Loopback) so internal requests to your public domain dynamically loop back to Traefik.
- **Port Forwarding:** Only forward Port `443` to your Traefik server. Port `80` is not required due to the DNS-01 verification method used by Let's Encrypt.


---

## Proxmox Estate & Maintenance Pipeline

All LXC containers on the Proxmox VE hypervisor (`pve1` / `10.10.10.31`) are provisioned via Proxmox VE Community Scripts and backed by ZFS storage (`rpool`). Updates across the estate follow a standardized, zero-downtime 5-step pipeline.

### 5-Step Update Pipeline

Each container and host update is executed sequentially (one guest at a time):

1. **Pre-Update Audit**
   Inspect active systemd services, current application versions, and pending APT upgrades before making changes:
   ```bash
   ssh root@10.10.10.31 "pct exec <id> -- apt-get update && pct exec <id> -- apt list --upgradable"
   ```

2. **Direct ZFS Snapshot**
   Take an atomic ZFS dataset snapshot on the Proxmox host before applying updates:
   ```bash
   # Proxmox Host Root Pool
   ssh root@10.10.10.31 "zfs snapshot rpool/ROOT/pve-1@pre-pve-upgrade"

   # LXC Container Subvolume
   ssh root@10.10.10.31 "zfs snapshot rpool/data/subvol-<id>-disk-0@pre-<name>-update"
   ```
   > **Why Direct ZFS Snapshots Instead of `pct snapshot`:** Proxmox's `pct snapshot` aborts with `snapshot feature is not available` whenever an LXC container has host directory bind mounts attached (such as NFS media shares on `111`, `115`, `117`, `118`, `120`, `121`). Snapshotting `rpool/data/subvol-<id>-disk-0` directly at the ZFS layer is instantaneous and bypasses the bind-mount restriction.

3. **Community Script Application Update**
   Run the Community Script entrypoint inside the container to upgrade the application binary, runtime dependencies (Node.js, Python `uv`, PHP, Composer), and database migrations:
   ```bash
   ssh root@10.10.10.31 "pct exec <id> -- /bin/update"
   ```
   - **Jellyfin (`CT 121`) Note:** Major Jellyfin upgrades (such as `10.11.x` to `12.0+`) perform irreversible SQLite schema migrations and alter the web client DOM, which can impact `File Transformation`, `Media Bar`, and custom CSS themes. Verify plugin compatibility prior to major upgrades or pin the package version via `apt`.
   - **Home Assistant OS (`VM 150`):** Runs as a QEMU virtual machine appliance; updates are managed directly from the Home Assistant Web UI rather than host shell scripts.

4. **Base OS Package Upgrade & Cache Cleanup**
   Upgrade underlying Debian/Ubuntu packages non-interactively so configuration file prompts never block execution, then purge APT caches:
   ```bash
   ssh root@10.10.10.31 "pct exec <id> -- apt-get -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold dist-upgrade && pct exec <id> -- apt-get -y autoremove && pct exec <id> -- apt-get clean"
   ```

5. **Post-Update Health Verification**
   Verify systemd daemon states, container runtimes (`docker ps` / `podman ps`), and local HTTP response codes:
   ```bash
   ssh root@10.10.10.31 'pct exec <id> -- systemctl is-active <service> && pct exec <id> -- curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:<port>'
   ```
   For stopped/on-demand containers (`105`, `116`, `120`, `140`, `141`, `201`), boot the container (`pct start <id>`), execute steps 1–5, verify service readiness, and power it back off (`pct stop <id>`).

### Estate Inventory & Verified Baseline

#### Hypervisor Host

| Target | Hostname | IP Address | Version Baseline | ZFS Rollback Snapshot |
|---|---|---|---|---|
| **Host** | `pve1` | `10.10.10.31` | Proxmox VE `8.3.4` (`pve-manager 9.2.18`, kernel `7.0.14-16`) | `rpool/ROOT/pve-1@pre-pve-upgrade` |

#### Active LXC Containers

| CT ID | Hostname | OS | Application Version | Verification Port & Status | ZFS Rollback Snapshot |
|---|---|---|---|---|---|
| **100** | `traefik` | Debian 12 | Traefik `3.7.13`, CrowdSec `1.8.1` | Ports `80`/`443`, Bouncer `:6060` (`active`) | `subvol-100-disk-0@pre-traefik-update` |
| **101** | `duplicati` | Debian 12 | Duplicati `2.4.0.0` | Port `8200` (`200 OK`) | `subvol-101-disk-0@pre-duplicati-update` |
| **102** | `homelable` | Debian 12 | Homelable `3.4.2` | Port `8000/docs` (`200 OK`) | — |
| **103** | `tailscale` | Debian 12 | Tailscale `1.102.4` | `tailscaled` (`active`) | `subvol-103-disk-0@pre-tailscale-update` |
| **111** | `qbittorrent` | Debian 12 | qBittorrent `5.2.3` (`libtorrent 2.0.14`) | Port `8090` (`200 OK`) | `subvol-111-disk-0@pre-qbit-update` |
| **113** | `flaresolverr` | Debian 12 | FlareSolverr `3.5.0` (Docker) | Port `8191` (`200 OK`) | `subvol-113-disk-0@pre-flaresolverr-update` |
| **114** | `prowlarr` | Debian 12 | Prowlarr `2.5.2.5491` | Port `9696` (`200 OK`) | `subvol-114-disk-0@pre-prowlarr-update` |
| **115** | `bazarr` | Debian 12 | Bazarr `1.6.0` | Port `6767` (`200 OK`) | `subvol-115-disk-0@pre-bazarr-update` |
| **117** | `radarr` | Debian 12 | Radarr `6.3.0.10514` | Port `7878` (`200 OK`) | `subvol-117-disk-0@pre-radarr-update` |
| **118** | `sonarr` | Debian 12 | Sonarr `4.0.19.2979` | Port `8989` (`200 OK`) | `subvol-118-disk-0@pre-sonarr-update` |
| **119** | `seerr` | Debian 12 | Seerr `3.4.1` (Node 22, pnpm 10) | Port `5055` (`307 Redirect`) | `subvol-119-disk-0@pre-seerr-update` |
| **121** | `jellyfin` | Ubuntu 24.04 | Jellyfin `12.0.0` | Port `8096` (`200 OK`) | `subvol-121-disk-0@pre-jellyfin-12` |

#### Stopped (On-Demand) LXC Containers

| CT ID | Hostname | OS | Application Version | Verification Port & Status | ZFS Rollback Snapshot |
|---|---|---|---|---|---|
| **105** | `unifi-os-server` | Debian 13 | UniFi OS Server (Podman `uosserver`) | Port `11443` (`healthy`, powered off) | `subvol-105-disk-0@pre-unifi-os-server-update` |
| **116** | `dispatcharr` | Debian 13 | Dispatcharr `0.30.0` (PG 16.15, Comskip V0.83) | Port `9191` (`200 OK`, powered off) | `subvol-116-disk-0@pre-dispatcharr-update` |
| **120** | `plex` | Ubuntu 24.04 | Plex Media Server `1.42.2.10156` | Port `32400/identity` (`200 OK`, powered off) | `subvol-120-disk-0@pre-plex-update` |
| **140** | `pterodactyl-panel` | Debian 13 | Pterodactyl Panel `1.15.1` (PHP 8.4, MariaDB 11.8) | Port `80` (`200 OK`, powered off) | `subvol-140-disk-0@pre-pterodactyl-panel-update` |
| **141** | `pterodactyl-wings` | Debian 13 | Pterodactyl Wings `1.13.3` (Docker CE `29.8.0`) | `wings version` (`v1.13.3`, powered off) | `subvol-141-disk-0@pre-pterodactyl-wings-update` |
| **201** | `n8n` | Debian 13 | n8n `2.38.7` (Node 24, npm 12) | Port `5678/healthz` (`200 OK`, powered off) | `subvol-201-disk-0@pre-n8n-update` |

#### Virtual Machines

| VM ID | Name | Type | Update Mechanism | Status |
|---|---|---|---|---|
| **150** | `haos` | QEMU VM (`2048 MB` RAM, `32 GB` Disk) | Home Assistant Supervisor Web UI | Running |
