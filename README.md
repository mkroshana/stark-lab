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
   git clone https://github.com/mkroshana/stark-lab.git
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
   Navigate to the Traefik dashboard (e.g., `https://traefik.yourdomain.com`). Log in using the `admin` username and the plain-text password you defined in your `.env` file.

---

## 🏠 Local-Only Service Access

In addition to external access, this setup provides a secure local-only routing for specific subdomains using the `*.local.starklab.mkroshana.com` pattern. Services routed here use Traefik's `block-external` middleware, restricting access strictly to your home LAN. 

**Exposed Local Services:**
- Jellyfin, Plex, Home Assistant (Reusing external backends)
- Proxmox PVE1 (`https://10.10.10.31:8006` via `insecure-transport` SkipVerify)
- Unraid Tower (`https://10.10.10.30` via `insecure-transport` SkipVerify)

### DNS Setup (Hybrid Strategy)
For best performance and reliability, we employ both local DNS rewrites and a public DNS fallback:
1. **Local DNS (Pi-hole/AdGuard Router)**:
   Add a wildcard DNS rewrite for `*.local.starklab.mkroshana.com` pointing to the Traefik LXC IP (`10.10.10.100`). This ensures instant connection without leaving your local network.
2. **Cloudflare Fallback**:
   Create an A Record for `*.local.starklab` pointing to `10.10.10.100` (Proxy **OFF** / DNS-only). While returning a local/private IP via a public DNS resolver, it acts as a reliable fallback for devices without local DNS set up, and is safely protected against internet exploitation by the `block-external` restriction rules.

---

## 🛠️ Adding a New Service

To expose a new homelab service:
1. Create a new file in `traefik-setup/conf.d/` (e.g., `myservice.yaml`).
2. Copy the structure from an existing file like `plex.yaml`.
3. Update the `rule` matching (e.g., `Host('myservice.yourdomain.com')`) and point the `loadBalancer` to your internal IP and port.
4. Rely on Traefik's native rule-length sorting (avoid setting a hard `priority` unless strictly necessary) and attach the `_shared.yaml` middlewares to instantly secure the route.
5. Re-run `sudo ./deploy.sh`.

---

## 🔒 Security Best Practices

- **Zero-Trust LAN:** Even internal setups use strict routing. Services like the Traefik Dashboard and internal APIs use the `block-external` middleware to reject traffic originating outside the local subnets (`10.x.x.x`, `192.168.x.x`).
- **Hairpin NAT:** Ensure your home router supports Hairpin NAT (NAT Loopback) so internal requests to your public domain dynamically loop back to Traefik.
- **Port Forwarding:** Only forward Port `443` to your Traefik server. Port `80` is not required due to the DNS-01 verification method used by Let's Encrypt.
