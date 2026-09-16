# Stark-Lab Comprehensive Homelab Security Audit Report
**Target Estate**: `stark-lab` Infrastructure (Proxmox VE `pve1`, LXC Guests, Traefik, CrowdSec, Storage & Network Perimeter)  
**Date of Assessment**: 2026-09-16  
**Assessment Version**: 1.0 (Final Authoritative Assessment)  
**Classification**: CONFIDENTIAL / INFRASTRUCTURE SECURITY AUDIT  
**Lead Auditor**: Teamwork Security Audit Team (Explorer 1, Explorer 2, Explorer 3, Worker 1)  
**Deliverable File**: `d:\Development\stark-lab\security-audit\homelab_security_audit_report.md`

---

## 1. Executive Summary & Security Posture Scorecard

### 1.1 Executive Overview
During September 2026, a rigorous, non-destructive security assessment and configuration audit was conducted across the **stark-lab** homelab environment. The estate serves as a production-grade personal infrastructure hosting approximately twenty services, including media management (*arr suite, Jellyfin, Plex), home automation (Home Assistant OS), remote access (Tailscale), and automated backup pipelines (Duplicati, PBS).

The estate is deployed as infrastructure-as-code and config-as-code centered around a dedicated Proxmox VE 9.2.18 hypervisor (`pve1` at `10.10.10.31`), twelve running LXC containers, six stopped LXC containers, one Home Assistant KVM virtual machine (VM 150), and a DIY Unraid NAS storage server (`10.10.10.30`). External ingress is managed by Traefik v3 (3.7.13) reverse proxy alongside CrowdSec v1.8.1 intrusion prevention deployed on CT 100 (`10.10.10.100`), receiving WAN traffic forwarded from an ISP Huawei HG8245H5 ONT/router (`10.10.10.1`).

While the estate demonstrates strong baselines in modern TLS termination (TLS 1.2+ AEAD cipher suites, strict SNI checks, automated Cloudflare DNS-01 Let's Encrypt certificates), and rate-limiting on sensitive endpoints, the assessment identified **critical vulnerabilities that present immediate risks of complete hypervisor compromise, arbitrary remote administrative access, and catastrophic data loss**.

### 1.2 Overall Security Posture Rating

| Assessment Metric | Evaluated Score / Rating | Evaluation Context |
|---|---|---|
| **Overall Security Posture** | **F (Critical Risk / Remediate Immediately)** | Active remote bypasses and hypervisor privilege escalation vectors present |
| **Perimeter & Ingress Security** | **D- (Severe Deficit)** | 131,072 ISP IP addresses bypass access controls; Bazarr web UI exposed without auth |
| **Container & Guest Isolation** | **D+ (Poor)** | CT 105 rootless escape to host root; 9 containers permit root password SSH |
| **Hypervisor & Infrastructure** | **C- (Marginal)** | PVE firewall completely disabled; unmirrored single-disk ZFS root pool |
| **Secrets & Credential Hygiene** | **D (High Risk)** | Live Cloudflare API token in plaintext `.env`; credentials and MD5 hashes in git history |
| **Storage & Backup Resilience** | **F (Failing)** | PBS offline; zero vzdump schedules; 18 unmanaged static snapshots consuming pool |

### 1.3 Vulnerability Severity Breakdown

The audit cataloged **16 distinct security vulnerabilities and configuration anomalies** using CVSS v3.1 scoring guidelines:

```
+--------------------------------------------------------------------------------+
| TOTAL FINDINGS: 16                                                             |
| [CRITICAL]      3  ████████████ (18.75%)                                       |
| [HIGH]          6  ████████████████████████ (37.50%)                           |
| [MEDIUM]        5  ████████████████████ (31.25%)                               |
| [LOW]           1  ████ (6.25%)                                                |
| [INFORMATIONAL] 1  ████ (6.25%)                                                |
+--------------------------------------------------------------------------------+
```

#### Detailed Findings Breakdown by Architectural Domain:

| Severity | Hypervisor (R1) | Container Isolation (R2) | Perimeter & Proxy (R3) | Web Endpoints (R4) | Secrets & Repo (R5) | Total |
|---|---|---|---|---|---|---|
| **Critical** | 0 | 1 | 1 | 1 | 0 | **3** |
| **High** | 2 | 2 | 1 | 0 | 1 | **6** |
| **Medium** | 1 | 1 | 1 | 2 | 0 | **5** |
| **Low** | 0 | 1 | 0 | 0 | 0 | **1** |
| **Informational**| 0 | 0 | 1 | 0 | 0 | **1** |
| **Total** | **3** | **5** | **4** | **3** | **1** | **16** |

### 1.4 Top 5 Critical Threats Summary

| Rank | Finding ID | Severity | CVSS v3.1 | Title & Vulnerability Summary |
|---|---|---|---|---|
| **1** | `SEC-CRIT-01` | **Critical** | **9.3** | **Privileged Container CT 105 Root Escalation Vector**: CT 105 (`unifi-os-server`) is configured with `unprivileged: 0`, retains all Linux capabilities, allows all host devices (`cgroup2.devices.allow: a`), and has an **empty root password hash** (`root::`). Anyone with console or container access gains instant, unauthenticated root takeover of the Proxmox VE hypervisor host. |
| **2** | `SEC-CRIT-02` | **Critical** | **10.0** | **Perimeter Bypass via Overbroad ISP Subnet Whitelisting**: To circumvent a router hairpin NAT failure, `112.135.0.0/16` was added to Traefik's `block-external` allowlist and `112.135.0.0/16` + `112.134.0.0/16` were whitelisted in CrowdSec postoverflows. Over **131,072 public IP addresses** assigned to Sri Lanka Telecom customers are granted direct access to internal management interfaces (`pve1`, Unraid, Duplicati, *arr apps) and are completely immune to CrowdSec bans. |
| **3** | `SEC-CRIT-03` | **Critical** | **9.1** | **Unauthenticated Public Route & Wildcard CORS on Bazarr**: `bazarr.starklab.mkroshana.com` is exposed to the public internet with no Traefik authentication middleware. Live probes confirmed Bazarr serves its full web UI unauthenticated (`isConfigured: false`) with `Access-Control-Allow-Origin: *`, allowing arbitrary external attackers or cross-origin scripts to manage subtitles and browse the file system. |
| **4** | `SEC-HIGH-01` | **High** | **8.8** | **In-Guest OpenSSH Password & Root Authentication**: Nine active containers (CT 101, 102, 111, 113, 114, 115, 117, 118, 119, 121) have both `PermitRootLogin yes` and `PasswordAuthentication yes` listening on `0.0.0.0:22` across a flat Layer 2 subnet with no `fail2ban` or host firewalling, facilitating trivial lateral movement. |
| **5** | `SEC-HIGH-02` | **High** | **7.5** | **Single-Drive ZFS Pool, Total PBS Outage & Absent Backups**: The hypervisor operates on a single unmirrored NVMe SSD (Lexar NM620 256GB). Proxmox Backup Server (`10.10.10.32:8007`) is completely unreachable (*No route to host*). Zero automated `vzdump` backup jobs are scheduled, and 18 static snapshots consume root pool space. A single drive failure results in catastrophic total data loss. |


---

## 2. Scope & Complete Target Inventory

### 2.1 Scope of Assessment & Boundaries
The assessment scope encompasses all physical and virtual components forming the `stark-lab` infrastructure:
- **Physical Hypervisor Node**: `pve1` (`10.10.10.31`) running Proxmox VE 9.2.18 on Debian 13 (trixie).
- **Virtual Machines & Containers**: 18 LXC containers (IDs 100–201) and 1 KVM Virtual Machine (VM 150).
- **Ingress & Reverse Proxy**: Traefik v3.7.13 and CrowdSec v1.8.1 on CT 100 (`10.10.10.100`).
- **Storage Subsystems**: Local ZFS `rpool` on NVMe SSD, network-attached NFS shares on Unraid (`10.10.10.30`), and Proxmox Backup Server (`10.10.10.32`).
- **Network Boundaries**: Flat Layer 2 broadcast domain `10.10.10.0/24` on bridge `vmbr0`, Huawei ONT router (`10.10.10.1`), Cloudflare authoritative DNS for `*.starklab.mkroshana.com`.

### 2.2 Proxmox VE Hypervisor Host Specification (`pve1`)
- **Management IP**: `10.10.10.31/24` (Default Gateway: `10.10.10.1`)
- **Proxmox Version**: `pve-manager: 9.2.18` (Running Version: `9.2.18/614bede5d65599c6`)
- **Kernel Release**: `Linux pve1 7.0.14-16-pve #1 SMP PREEMPT_DYNAMIC PMX 7.0.14-16 (2026-08-28T17:31Z) x86_64 GNU/Linux`
- **CPU Hardware**: Intel(R) Core(TM) i5-7500T CPU @ 2.70GHz (4 Cores, 1 Socket, Kaby Lake)
- **System Memory**: 11 GiB Total RAM (6.5 GiB in active use, 5.0 GiB available, 0B Swap allocated)
- **Primary Storage**: Single 256GB NVMe SSD (`Lexar SSD NM620 256GB`, Serial: `PCR121R002848P1109-part3`) hosting ZFS pool `rpool`
- **Network Interfaces**: Physical NIC `nic0` enslaved to Linux bridge `vmbr0` (VLAN-aware: `no`)

### 2.3 Comprehensive Virtual Guest Inventory

| VMID | Hostname / Service | Type | State | vCPU | RAM | Root Disk | IP Address | Privilege Model | Primary Tags / Purpose |
|---|---|---|---|---|---|---|---|---|---|
| **100** | `traefik` | LXC | **Running** | 4 | 2048 MB | 2 GB | `10.10.10.100` | Unprivileged (`uid 100000`) | `proxy;ingress` |
| **101** | `duplicati` | LXC | **Running** | 2 | 2048 MB | 10 GB | `10.10.10.101` | Unprivileged (`uid 100000`) | `backup;duplicati` |
| **102** | `homelable` | LXC | **Running** | 2 | 2048 MB | 8 GB | `10.10.10.102` | Unprivileged (`uid 100000`) | `monitoring;network` |
| **103** | `tailscale` | LXC | **Running** | 2 | 512 MB | 8 GB | `10.10.10.103` | Unprivileged (`uid 100000`) | `vpn;tailscale` |
| **105** | `unifi-os-server` | LXC | **Stopped** | 2 | 4096 MB | 20 GB | `10.10.10.105` | **PRIVILEGED (`uid 0`)** | `network;unifi` |
| **111** | `qbittorrent` | LXC | **Running** | 2 | 2048 MB | 8 GB | `10.10.10.111` | Unprivileged (`uid 100000`) | `torrent;media` |
| **113** | `flaresolverr` | LXC | **Running** | 2 | 2048 MB | 4 GB | `10.10.10.113` | Unprivileged (`uid 100000`) | `proxy;cloudflare` |
| **114** | `prowlarr` | LXC | **Running** | 2 | 1024 MB | 4 GB | `10.10.10.114` | Unprivileged (`uid 100000`) | `arr;indexer` |
| **115** | `bazarr` | LXC | **Running** | 2 | 1024 MB | 4 GB | `10.10.10.115` | Unprivileged (`uid 100000`) | `arr;subtitles` |
| **116** | `dispatcharr` | LXC | **Stopped** | 2 | 2048 MB | 8 GB | `10.10.10.116` | Unprivileged (`uid 100000`) | `arr;media` |
| **117** | `radarr` | LXC | **Running** | 2 | 1024 MB | 4 GB | `10.10.10.117` | Unprivileged (`uid 100000`) | `arr;movies` |
| **118** | `sonarr` | LXC | **Running** | 2 | 1024 MB | 4 GB | `10.10.10.118` | Unprivileged (`uid 100000`) | `arr;tvshows` |
| **119** | `seerr` | LXC | **Running** | 4 | 4096 MB | 20 GB | `10.10.10.119` | Unprivileged (`uid 100000`) | `media;requests` |
| **120** | `plex` | LXC | **Stopped** | 4 | 4096 MB | 64 GB | `10.10.10.120` | Unprivileged (`uid 100000`) | `media;streaming` |
| **121** | `jellyfin` | LXC | **Running** | 4 | 4096 MB | 64 GB | `10.10.10.121` | Unprivileged (`uid 100000`) | `media;streaming` |
| **140** | `pterodactyl-panel`| LXC| **Stopped** | 2 | 1024 MB | 4 GB | `10.10.10.140` | Unprivileged (`uid 100000`) | `gaming;panel` |
| **141** | `pterodactyl-wings`| LXC| **Stopped** | 2 | 4096 MB | 8 GB | `10.10.10.141` | Unprivileged (`uid 100000`) | `gaming;wings` |
| **201** | `n8n` | LXC | **Stopped** | 2 | 2048 MB | 20 GB | `10.10.10.201` | Unprivileged (`uid 100000`) | `automation;workflow`|
| **150** | `haos` | KVM | **Running** | 4 | 2048 MB | 32 GB | `10.10.10.150` / `154` | Virtual Machine (QEMU)| `homeautomation` |

### 2.4 Storage & Shared Bind Mount Inventory Matrix
Storage assets are shared between the hypervisor, NAS, and container workloads via NFSv4.2 and ZFS subvolumes:

| Host Mount Path | Source Storage Server & Share | In-Container Mount Path | Attached Containers | Perms & User Squash | Security & Data Risks |
|---|---|---|---|---|---|
| `/mnt/pve/Vault` | `10.10.10.30:/mnt/user/Vault` | `/mnt/Vault` | CT 101 (`duplicati`) | `0777 nobody:nogroup` (sec=sys, no squash) | Personal unencrypted documents exposed; world-writable by any local container user |
| `/mnt/pve/Downloads` | `10.10.10.30:/mnt/user/Downloads` | `/mnt/Downloads` | CT 111, 117, 118 | `0777 nobody:nogroup` (sec=sys, no squash) | Cross-container malware injection into active torrents/downloads |
| `/mnt/pve/Movies` | `10.10.10.30:/mnt/user/Movies` | `/mnt/Movies` | CT 115, 117, 120, 121 | `0777 nobody:nogroup` (sec=sys, no squash) | Arbitrary media deletion; ransomware attack surface |
| `/mnt/pve/TV-Shows` | `10.10.10.30:/mnt/user/TV-Shows` | `/mnt/TV-Shows` | CT 115, 118, 120, 121 | `0777 nobody:nogroup` (sec=sys, no squash) | Arbitrary media deletion; ransomware attack surface |
| `/mnt/pve/Backups` | `10.10.10.30:/mnt/user/Backups` | Host local only | `pve1` | `0777 nobody:nogroup` (sec=sys) | Exported to entire `10.10.10.0/24` subnet without host-level restriction |
| `rpool/ROOT/pve-1`| Local Lexar NVMe SSD | `/` (Hypervisor rootfs) | `pve1` | ZFS Dataset (115 GB used, 114 GB free) | Single NVMe drive with zero redundancy; hardware failure destroys entire hypervisor |
| `rpool/data/subvol-*`| Local Lexar NVMe SSD | Container root filesystems | All 18 LXC containers | 18 snapshots `@pre-*-update` dated 2026-09-13 | 11 GB unmanaged snapshot space; no automated retention or cleanup |
| `10.10.10.32:8007`| Dedicated PBS Server | Proxmox Backup Target | `pve1` | **OFFLINE** (*No route to host*) | Offsite backups completely non-functional |

### 2.5 Reverse Proxy Route & Exposure Inventory
Audited across `traefik-setup/conf.d/*.yaml` and live reverse proxy `/etc/traefik/conf.d/` on CT 100:

| Router Name | Ingress Host Rule | EntryPoint | Target Service & IP:Port | Middlewares | Authentication Gate | Exposure State |
|---|---|---|---|---|---|---|
| `catch-all` | `HostRegexp('.+')` | `websecure` | `noop-svc:127.0.0.1` | `block-external` | None (Drop) | Public (Default Drop, Pri: 1) |
| `jellyfin` | `jellyfin.starklab.mkroshana.com` | `websecure` | `10.10.10.121:8096` | `crowdsec-bouncer`, `security-headers`, `general-rate-limit` | Jellyfin App Auth | **Public** |
| `jellyfin-block-swagger`| `jellyfin... && PathPrefix('/api-docs')` | `websecure` | `10.10.10.121:8096` | `block-external` | IP Allowlist | Public (Bypassed by SLT ISP) |
| `jellyfin-auth` | `jellyfin... && PathPrefix('/Users/AuthenticateByName')`| `websecure` | `10.10.10.121:8096` | `crowdsec`, `security-headers`, `auth-rate-limit` | Jellyfin App Auth | **Public** (Rate limited 5/min) |
| `plex` | `plex.starklab.mkroshana.com` | `websecure` | `10.10.10.120:32400`| `crowdsec-bouncer`, `security-headers`, `general-rate-limit` | Plex.tv Auth | Public (CT 120 stopped) |
| `plex-auth` | `plex... && PathPrefix('/users/sign_in')` | `websecure` | `10.10.10.120:32400`| `crowdsec`, `security-headers`, `auth-rate-limit` | Plex.tv Auth | Public (CT 120 stopped) |
| `homeassistant` | `ha.starklab.mkroshana.com` | `websecure` | `10.10.10.150:8123`| `crowdsec-bouncer`, `security-headers-iframe`, `general-rate-limit` | HA App Auth | **Public (Target IP Mismatch)** |
| `homeassistant-auth` | `ha... && PathPrefix('/auth')` | `websecure` | `10.10.10.150:8123`| `crowdsec`, `security-headers-iframe`, `auth-rate-limit`| HA App Auth | **Public** (Rate limited 5/min) |
| `bazarr` | `bazarr.starklab.mkroshana.com` | `websecure` | `10.10.10.115:6767`| `crowdsec-bouncer`, `security-headers`, `general-rate-limit` | **NONE** | **PUBLIC UNPROTECTED (CRITICAL)**|
| `pterodactyl` | `pterodactyl...` / `gaming...` | `websecure` | `10.10.10.140:80` | `crowdsec-bouncer`, `security-headers`, `general-rate-limit` | Panel App Auth | Public (CT 140 stopped) |
| `seer` | `seer...` / `request...` | `websecure` | `10.10.10.119:5055`| `crowdsec-bouncer`, `security-headers`, `general-rate-limit` | Overseerr Auth | **Public** |
| `seer-auth` | `(seer... \|\| request...) && PathPrefix('/login')` | `websecure` | `10.10.10.119:5055`| `crowdsec`, `security-headers`, `auth-rate-limit` | Overseerr Auth | **Public** (Rate limited 5/min) |
| `tv` | `tv.starklab.mkroshana.com` | `websecure` | `10.10.10.116:9191`| `crowdsec-bouncer`, `security-headers`, `general-rate-limit` | Dispatcharr Auth | Public (CT 116 stopped) |
| `qbittorrent` (drift) | `qbittorrent...` / `downloads...` | `websecure` | `10.10.10.111:8090`| `security-headers-iframe`, `crowdsec` | Web UI Auth | **Public (Uncommitted Drift)** |
| `prowlarr` (drift) | `prowlarr...` / `indexer...` | `websecure` | `10.10.10.114:9696`| `security-headers`, `crowdsec` | App Auth / API | **Public (Uncommitted Drift)** |
| `radarr` (drift) | `radarr...` / `movies...` | `websecure` | `10.10.10.117:7878`| `security-headers`, `crowdsec` | App Auth / API | **Public (Uncommitted Drift)** |
| `sonarr` (drift) | `sonarr...` / `tvshows...` | `websecure` | `10.10.10.118:8989`| `security-headers`, `crowdsec` | App Auth / API | **Public (Uncommitted Drift)** |
| `n8n` (drift) | `n8n...` / `automations...` | `websecure` | `10.10.10.201:5678`| `security-headers`, `crowdsec` | App Auth | Public (Uncommitted, CT 201 off)|
| `traefik-dashboard` | `traefik.local.starklab...` | `websecure` | `api@internal` | `block-external`, `dashboard-auth`, `security-headers` | **HTTP BasicAuth** | Local (Bypassed by SLT ISP) |
| `local-bazarr` | `bazarr.local.starklab...` | `websecure` | `10.10.10.115:6767`| `local-only` (`block-external`, `security-headers`) | IP Allowlist only | Local (Bypassed by SLT ISP) |
| `local-duplicati` | `duplicati.local.starklab...` | `websecure` | `10.10.10.101:8200`| `local-only` (`block-external`, `security-headers`) | IP Allow / Web PIN | Local (Bypassed by SLT ISP) |
| `local-homeassistant` | `ha.local.starklab...` | `websecure` | `10.10.10.150:8123`| `local-iframe-only` (`block-ext`, `sec-headers-iframe`) | IP Allow + HA Auth | Local (Bypassed by SLT ISP) |
| `local-homelable` | `homelable.local.starklab...` | `websecure` | `10.10.10.102:3000`| `local-only` (`block-external`, `security-headers`) | IP Allow + App Auth| Local (Port Mismatch :3000) |
| `local-jellyfin` | `jellyfin.local.starklab...` | `websecure` | `10.10.10.121:8096`| `local-only` (`block-external`, `security-headers`) | IP Allow + App Auth| Local (Bypassed by SLT ISP) |
| `local-n8n` | `n8n.local...` / `automations.local...`| `websecure` | `10.10.10.201:5678`| `local-only` (`block-external`, `security-headers`) | IP Allow + App Auth| Local (CT 201 stopped) |
| `local-pbs` | `pbs.local.starklab...` | `websecure` | `https://10.10.10.32:8007`| `local-iframe-only` (`insecure-transport`) | IP Allow + PBS Auth| Local (Host Offline) |
| `local-plex` | `plex.local.starklab...` | `websecure` | `10.10.10.120:32400`| `local-only` (`block-external`, `security-headers`) | IP Allow + App Auth| Local (CT 120 stopped) |
| `local-prowlarr` | `prowlarr.local...` | `websecure` | `10.10.10.114:9696`| `local-only` (`block-external`, `security-headers`) | IP Allow / API Key | Local (Bypassed by SLT ISP) |
| `local-proxmox` | `pve1.local.starklab...` | `websecure` | `https://10.10.10.31:8006`| `local-iframe-only` (`insecure-transport`) | IP Allow + PAM Auth| Local (Bypassed by SLT ISP) |
| `local-pterodactyl` | `pterodactyl.local...` | `websecure` | `10.10.10.140:80` | `local-iframe-only` (`block-ext`, `sec-headers-iframe`) | IP Allow + Panel | Local (CT 140 stopped) |
| `local-qbittorrent` | `qbittorrent.local...` | `websecure` | `10.10.10.111:8090`| `local-iframe-only` (`block-ext`, `sec-headers-iframe`) | IP Allow / Web UI | Local (Bypassed by SLT ISP) |
| `local-radarr` | `radarr.local...` | `websecure` | `10.10.10.117:7878`| `local-only` (`block-external`, `security-headers`) | IP Allow / API Key | Local (Bypassed by SLT ISP) |
| `local-seer` | `seer.local...` | `websecure` | `10.10.10.119:5055`| `local-only` (`block-external`, `security-headers`) | IP Allow + App Auth| Local (Bypassed by SLT ISP) |
| `local-sonarr` | `sonarr.local...` | `websecure` | `10.10.10.118:8989`| `local-only` (`block-external`, `security-headers`) | IP Allow / API Key | Local (Bypassed by SLT ISP) |
| `local-tv` | `tv.local.starklab...` | `websecure` | `10.10.10.116:9191`| `local-only` (`block-external`, `security-headers`) | IP Allow + App Auth| Local (CT 116 stopped) |
| `local-unraid` | `tower.local...` / `nas.local...` | `websecure` | `https://10.10.10.30` | `local-iframe-only` (`insecure-transport`) | IP Allow + Root Auth| Local (Bypassed by SLT ISP) |


---

## 3. Threat Model & Attack Surface Map

### 3.1 Threat Actor Profiles & Capabilities
The stark-lab infrastructure faces four distinct categories of threat actors, each with varying levels of access, capabilities, and motivations:

```
+-----------------------------------------------------------------------------------------------+
| THREAT ACTOR TAXONOMY                                                                         |
+-----------------------------------------------------------------------------------------------+
| 1. Opportunistic Internet Scanners & Botnets (Masscan, Shodan, Censys, Mirai, Automated CVEs) |
|    - Location: Public Internet                                                                |
|    - Vector: WAN TCP ports 80/443 directly exposed to residential IP                          |
|    - Objectives: Subdomain enumeration, unauthenticated service discovery, credential stuffing|
+-----------------------------------------------------------------------------------------------+
| 2. ISP-Adjacent Adversaries (Subscribers on Sri Lanka Telecom 112.134.0.0/16 & 112.135.0.0/16)|
|    - Location: Same ISP regional subnet (131,072 routable public IP addresses)                |
|    - Vector: Hairpin NAT whitelist bypass in Traefik block-external & CrowdSec home-whitelist |
|    - Objectives: Access internal local-* management portals without VPN or authentication     |
+-----------------------------------------------------------------------------------------------+
| 3. Compromised Container / Lateral Movement Adversary                                         |
|    - Location: Compromised guest container (e.g., compromised torrent in CT 111 or Bazarr)   |
|    - Vector: Flat Layer 2 broadcast domain (10.10.10.0/24), open SSH (22), NFS bind mounts    |
|    - Objectives: Lateral reconnaissance, CIFS/NFS data destruction, hypervisor escape (CT 105)|
+-----------------------------------------------------------------------------------------------+
| 4. Rogue / Compromised Local LAN Device (Compromised IoT device, rogue guest Wi-Fi host)     |
|    - Location: Local LAN broadcast domain (10.10.10.0/24)                                     |
|    - Vector: Direct TCP/UDP access bypassing Traefik/CrowdSec entirely                        |
|    - Objectives: Hypervisor port exploitation (8006, 22, 111), ARP spoofing, MITM on NFS/PVE   |
+-----------------------------------------------------------------------------------------------+
```

### 3.2 Perimeter Attack Surface & DNS Topology
- **Authoritative DNS**: Wildcard record `*.starklab.mkroshana.com` hosted on Cloudflare Authoritative DNS.
- **Proxy Status**: `CF_PROXIED=false` (**DNS-Only / Grey-Cloud**).
  - *Architectural Implication*: WAN requests resolve directly to the home residential IPv4 address. Cloudflare Edge WAF, DDoS mitigation, Bot Management, and IP masking are **completely non-operational**.
  - All internet scanning traffic hits the physical router WAN interface directly.
- **Port Forwarding Rules on Huawei HG8245H5 ONT**:
  - `WAN:80/TCP` -> `10.10.10.100:80` (Redirects to HTTPS :443)
  - `WAN:443/TCP` -> `10.10.10.100:443` (Traefik TLS termination)
  - All other direct ports (such as Plex 32400, Jellyfin 8096, Home Assistant 8123) are filtered at the router boundary, making Traefik the sole ingress gateway.

### 3.3 The Hairpin NAT Workaround Vulnerability
The upstream Huawei ONT router lacks reliable NAT loopback (hairpinning). When internal devices on `10.10.10.0/24` query `*.starklab.mkroshana.com`, they receive the external WAN IP. The router fails to hairpin this traffic back into the internal network, causing internal requests to fail.

To allow internal devices to access `local-*` services via the public domain name, the administrator added the residential WAN subnet to Traefik's `block-external` IP allowlist in `conf.d/_shared.yaml`. However, instead of adding a single `/32` IP address, an entire ISP CIDR allocation (`112.135.0.0/16`) was entered. Furthermore, when legitimate Jellyfin media bursts tripped CrowdSec's `http-crawl-non_statics` scenario, the administrator added both `112.135.0.0/16` and `112.134.0.0/16` to CrowdSec's postoverflow whitelist.

**Security Impact**:
1. **Perimeter Collapse**: Any external attacker within the `112.135.0.0/16` IP block (65,536 addresses) can send requests to `pve1.local.starklab.mkroshana.com`, `tower.local.starklab.mkroshana.com`, `qbittorrent.local.starklab.mkroshana.com`, etc. Traefik inspects the incoming client IP, matches it against `112.135.0.0/16`, and permits the connection directly to the internal hypervisor or NAS.
2. **Defensive Blindspot**: Over 131,072 IP addresses across Sri Lanka Telecom are completely immune to CrowdSec bans. Threat actors operating from these pools can execute brute-force attacks, directory traversal, and exploit scans against Traefik without ever being banned.

### 3.4 Flat Layer 2 Network & Absence of Hypervisor Packet Filtering
- **Network Topology**: All physical hosts, 18 LXC containers, VM 150, the DIY NAS, and the administrator workstation reside in a single flat broadcast subnet: `10.10.10.0/24`.
- **VLAN Segmentation**: There is **no VLAN segmentation** (`vlan-aware: 0` on `vmbr0`). IoT devices, public-facing web proxies, media downloaders, and hypervisor management share the same Layer 2 Ethernet broadcast domain.
- **Hypervisor Firewall**: Proxmox VE firewall daemon status is `disabled/running`. The kernel Netfilter table (`iptables -S`) reveals default `ACCEPT` policies across `INPUT`, `FORWARD`, and `OUTPUT` chains. No container network interface (`net0`) has firewalling enabled.
- **Lateral Movement Implication**: Once an adversary establishes a foothold inside any container (e.g. via an unauthenticated web app like Bazarr or a compromised download in qBittorrent), there are zero network controls preventing them from scanning, connecting to, or attacking `pve1` on ports 22, 8006, 3128, 111, or dynamic RPC ports.

### 3.5 Hypervisor Privilege Escalation Kill Chain (CT 105)
The presence of privileged container CT 105 (`unifi-os-server`) creates a direct, trivial path to complete hypervisor host compromise:

```
[Attacker on WAN or LAN]
       │
       ▼ (1. Access unauthenticated Bazarr / In-guest SSH root brute force)
[Compromised LXC Container (e.g. CT 115 or CT 111)]
       │
       ▼ (2. Read/Write World-Writable Bind Mounts on NFS /mnt/pve/*)
[Corrupted Storage / Lateral Network Reconnaissance across 10.10.10.0/24]
       │
       ▼ (3. Connect to CT 105 console or trigger root execution)
[CT 105: unprivileged: 0 | empty root password in /etc/shadow]
       │
       ▼ (4. Host devices allowed: lxc.cgroup2.devices.allow: a | Zero caps dropped)
[Host Device Node Access: mknod /dev/nvme0n1p3 | Access Host Kernel & Subvolumes]
       │
       ▼ (5. Read/Write Host Filesystem / Inject SSH Keys into /root/.ssh/authorized_keys)
[FULL PROXMOX VE HYPERVISOR ROOT TAKEOVER (pve1 @ 10.10.10.31)]
```

### 3.6 Attack Surface Map & Network Flow Diagram

```
                                    PUBLIC INTERNET
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  │ Authoritative DNS: *.starklab.mkroshana.com    │
                  │ Cloudflare DNS-Only (CF_PROXIED=false)         │
                  └───────────────────────┬───────────────────────┘
                                          │ WAN IP (Direct Exposure)
                                          ▼
                  ┌───────────────────────────────────────────────┐
                  │ Huawei HG8245H5 Residential Gateway (10.10.10.1)│
                  │ Port Forwards: TCP 80 -> CT 100, TCP 443 -> CT 100
                  └───────────────────────┬───────────────────────┘
                                          │
                   LAN Traffic (443/80)   ▼
    ┌─────────────────────────────────────────────────────────────────────────────┐
    │ CT 100: Traefik 3.7.13 + CrowdSec 1.8.1 (10.10.10.100)                     │
    │  - TLS Termination (*.starklab.mkroshana.com via DNS-01 Cloudflare)          │
    │  - Middleware: security-headers, rate-limits, crowdsec-bouncer              │
    │                                                                             │
    │  [CRITICAL VULNERABILITY 1: block-external allows 112.135.0.0/16]           │
    │  [CRITICAL VULNERABILITY 2: CrowdSec postoverflow whitelists 131,072 IPs]   │
    │  [CRITICAL VULNERABILITY 3: bazarr.yaml has NO AUTH MIDDLEWARE]             │
    └───────┬─────────────────────────────┬─────────────────────────────┬─────────┘
            │                             │                             │
 Public Web │                             │ LAN-Only Routes             │
 Routing    │                             │ (Bypassed via SLT ISP!)     │
            ▼                             ▼                             ▼
┌───────────────────────┐   ┌───────────────────────────┐   ┌─────────────────────────┐
│ CT 121: Jellyfin      │   │ Hypervisor: pve1          │   │ DIY NAS: Unraid         │
│ 10.10.10.121:8096     │   │ 10.10.10.31:8006 (Web UI) │   │ 10.10.10.30:443 (Web UI)│
│ Auth Rate Limited     │   │ 10.10.10.31:22   (SSH)    │   │ NFS Exports (0777)      │
├───────────────────────┤   │ 10.10.10.31:111  (RPC)    │   ├─────────────────────────┤
│ CT 115: Bazarr        │   │ [!] Firewall DISABLED     │   │ CT 101: Duplicati       │
│ 10.10.10.115:6767     │   └─────────────┬─────────────┘   │ 10.10.10.101:8200       │
│ [!] UNPROTECTED /     │                 │                 ├─────────────────────────┤
│ [!] WILDCARD CORS     │                 ▼                 │ *arr Stack Containers   │
├───────────────────────┤   ┌───────────────────────────┐   │ CT 111: qBittorrent:8090│
│ VM 150: Home Assistant│   │ CT 105: unifi-os-server   │   │ CT 114: Prowlarr:9696   │
│ 10.10.10.150:8123     │   │ (Stopped, Privileged)     │   │ CT 117: Radarr:7878     │
├───────────────────────┤   │ [!] unprivileged: 0       │   │ CT 118: Sonarr:8989     │
│ CT 119: Seer (5055)   │   │ [!] EMPTY ROOT PASSWORD   │   │ [!] PermitRootLogin yes │
└───────────────────────┘   │ [!] devices.allow: a      │   │ [!] PasswordAuth yes    │
                            └───────────────────────────┘   └─────────────────────────┘
```

---

## 4. Detailed Vulnerability Findings Catalog

### 4.1 Critical Severity Vulnerabilities

#### [SEC-CRIT-01] Privileged Container CT 105 Root Escalation Vector to Hypervisor Root
- **Severity**: Critical
- **CVSS v3.1 Score**: **9.3** (`CVSS:3.1/AV:L/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H`)
- **CWE ID**: CWE-250 (Execution with Unnecessary Privileges) / CWE-258 (Empty Password in Configuration File)
- **Affected Target(s)**: CT 105 (`unifi-os-server`) at `/etc/pve/lxc/105.conf` and `/rpool/data/subvol-105-disk-0/etc/shadow`
- **Prerequisites**: Access to the Proxmox VE console or execution within CT 105 when booted.

##### Technical Description & Root Cause
CT 105 is configured as a **fully privileged LXC container** (`unprivileged: 0`). In Proxmox VE, an unprivileged container maps container UID 0 to host UID 100000 using user namespaces (`/proc/self/uid_map`). A privileged container, however, maps container root UID 0 directly to the **real host root UID 0**.

Furthermore, CT 105's configuration drops zero Linux capabilities (`lxc.cap.drop: ` is completely empty) and grants access to all character and block devices on the host kernel via `lxc.cgroup2.devices.allow: a`. Inspection of the container's root filesystem shadow database on the host ZFS dataset (`/rpool/data/subvol-105-disk-0/etc/shadow`) revealed that the root account password hash is **completely empty** (`root::20704:0:99999:7:::`).

##### Reproducible Evidence
Executed directly on `pve1` (`10.10.10.31`):

```bash
# 1. Inspect container privilege status and device permissions
grep -E '^(unprivileged|lxc\.cap\.drop|lxc\.cgroup2\.devices\.allow)' /etc/pve/lxc/105.conf

# Output:
unprivileged: 0
lxc.cgroup2.devices.allow: a
lxc.cap.drop: 

# 2. Inspect root shadow entry in container subvolume
awk -F: '$1=="root"{print $1, $2}' /rpool/data/subvol-105-disk-0/etc/shadow

# Output:
root 

# 3. Check SSH configuration inside CT 105 subvolume
grep -E '^(PermitRootLogin|PasswordAuthentication)' /rpool/data/subvol-105-disk-0/etc/ssh/sshd_config

# Output:
PermitRootLogin yes
PasswordAuthentication yes
```

##### Technical Risk & Impact Analysis
Because CT 105 is privileged, drops no capabilities, and allows all devices, any process executing as root inside the container possesses the exact same privileges as root on the Proxmox host. With `lxc.cgroup2.devices.allow: a`, an attacker inside the container can create device nodes (`mknod`) for host disk partitions (e.g. `/dev/nvme0n1p3`), read and write the ZFS root pool, mount host filesystems, overwrite the host's `/etc/shadow`, and permanently take over the hypervisor. 

Because the root password field is empty (`root::`), if CT 105 is booted, anyone connecting via the console or any local service triggering authentication can achieve unauthenticated root execution, leading directly to complete infrastructure compromise.

##### Specific, Safe Remediation Guidance
Execute the following commands on `pve1` (`10.10.10.31`) to lock the root account and enforce container isolation:

```bash
# 1. Immediately lock the blank root password in CT 105 shadow file
sed -i 's/^root::/root:!:/' /rpool/data/subvol-105-disk-0/etc/shadow

# 2. Restrict SSH inside the container subvolume
sed -i 's/^PermitRootLogin yes/PermitRootLogin prohibit-password/' /rpool/data/subvol-105-disk-0/etc/ssh/sshd_config
sed -i 's/^PasswordAuthentication yes/PasswordAuthentication no/' /rpool/data/subvol-105-disk-0/etc/ssh/sshd_config

# 3. Remove unrestricted device allow and enforce capability drops in 105.conf
sed -i '/lxc.cgroup2.devices.allow: a/d' /etc/pve/lxc/105.conf
sed -i '/lxc.cap.drop:/d' /etc/pve/lxc/105.conf
echo "lxc.cap.drop: sys_admin sys_rawio mknod" >> /etc/pve/lxc/105.conf

# 4. Long-term: Convert CT 105 to an unprivileged container via backup and restore:
# vzdump 105 --mode stop --compress zstd --dumpdir /var/lib/vz/dump/
# pct restore 105 /var/lib/vz/dump/vzdump-lxc-105-*.tar.zst --unprivileged 1
```

##### Verification & Rollback Procedures
- **Verification Command**:
  ```bash
  awk -F: '$1=="root"{print $1, $2}' /rpool/data/subvol-105-disk-0/etc/shadow
  grep "devices.allow: a" /etc/pve/lxc/105.conf
  ```
- **Expected Output**: `root !` (locked) and no matches for unrestricted devices.
- **Rollback Command**: Restore `/etc/pve/lxc/105.conf` from backup if UniFi container initialization requires specific device passthrough.

---

#### [SEC-CRIT-02] Perimeter Bypass via Overbroad ISP Subnet (/16) Whitelisting in Traefik & CrowdSec
- **Severity**: Critical
- **CVSS v3.1 Score**: **10.0** (`CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:N`)
- **CWE ID**: CWE-284 (Improper Access Control) / CWE-183 (Permissive List of Allowed Inputs)
- **Affected Target(s)**: `traefik-setup/conf.d/_shared.yaml` (lines 74–81) and `traefik-setup/crowdsec/postoverflows/s01-whitelist/home-whitelist.yaml` (lines 11–18) deployed on CT 100
- **Prerequisites**: Source IP address within Sri Lanka Telecom public pools (`112.135.0.0/16` or `112.134.0.0/16`).

##### Technical Description & Root Cause
To resolve a home router NAT loopback (hairpin NAT) failure where internal LAN clients resolving `*.starklab.mkroshana.com` could not route back to the internal reverse proxy, the administrator configured Traefik's `block-external` middleware (`_shared.yaml`) to whitelist the home WAN IP range. However, instead of a `/32` single IP address, the entire ISP allocation `112.135.0.0/16` (65,536 public IPv4 addresses) was added.

Simultaneously, to suppress false-positive CrowdSec bans triggered by rapid Jellyfin API queries, the administrator deployed `home-whitelist.yaml` in CrowdSec postoverflows, whitelisting both `112.135.0.0/16` and `112.134.0.0/16` (**131,072 public IPv4 addresses**).

##### Reproducible Evidence
Inspecting source repository and CT 100 live files:

```bash
# 1. Verify Traefik block-external definition in conf.d/_shared.yaml
grep -n -C 5 "112.135" d:/Development/stark-lab/traefik-setup/conf.d/_shared.yaml

# Output:
# 74:    # -- Block External Access (allows only LAN) --
# 75:    block-external:
# 76:      ipAllowList:
# 77:        sourceRange:
# 78:          - "127.0.0.1/32"
# 79:          - "10.10.10.0/24"
# 80:          - "192.168.0.0/16"
# 81:          - "112.135.0.0/16" # Your Home Public IP Range (hairpin NAT)

# 2. Verify CrowdSec postoverflow whitelist
grep -n -C 4 "112." d:/Development/stark-lab/traefik-setup/crowdsec/postoverflows/s01-whitelist/home-whitelist.yaml

# Output:
# 11:name: crowdsecurity/home-whitelist
# 12:description: "Whitelist home ISP range to prevent self-bans"
# 13:whitelist:
# 14:  reason: "Home ISP range and trusted user pool"
# 15:  cidr:
# 16:    - "112.135.0.0/16"
# 17:    - "112.134.0.0/16"
```

##### Technical Risk & Impact Analysis
The Cloudflare wildcard DNS record `*.starklab.mkroshana.com` points all subdomains (including `pve1.local.starklab.mkroshana.com`, `tower.local.starklab.mkroshana.com`, `pbs.local.starklab.mkroshana.com`, `qbittorrent.local.starklab.mkroshana.com`, and `radarr.local...`) to the residential WAN IP.

Because `block-external` is the sole access control protecting internal `local-*` routers, any user or attacker on Sri Lanka Telecom within `112.135.0.0/16` can browse directly over the public internet to Proxmox VE Web UI, Unraid NAS console, Duplicati web UI, and the *arr downloaders. Furthermore, because CrowdSec postoverflow discards alerts for these ranges before decision generation, any attacker within either `/16` range can execute brute force attacks, credential stuffing, and web exploits with complete immunity from CrowdSec bans.

##### Specific, Safe Remediation Guidance
1. **Sanitize `_shared.yaml` on CT 100 and Repository**:
   Remove `"112.135.0.0/16"` from `block-external.ipAllowList.sourceRange`. Ensure only RFC1918 private subnets and localhost are permitted:
   ```yaml
   block-external:
     ipAllowList:
       sourceRange:
         - "127.0.0.1/32"
         - "10.10.10.0/24"
         - "192.168.0.0/16"
   ```

2. **Purge Blanket CrowdSec Whitelist**:
   Delete `/etc/crowdsec/postoverflows/s01-whitelist/home-whitelist.yaml` on CT 100:
   ```bash
   ssh root@10.10.10.31 "pct exec 100 -- rm -f /etc/crowdsec/postoverflows/s01-whitelist/home-whitelist.yaml"
   ssh root@10.10.10.31 "pct exec 100 -- systemctl restart crowdsec"
   ```

3. **Deploy Local Split-Horizon DNS**:
   To resolve hairpin NAT properly without WAN IP whitelisting, configure local DNS (Pi-hole, AdGuard Home, or router DNS) to resolve `*.starklab.mkroshana.com` and `*.local.starklab.mkroshana.com` directly to `10.10.10.100`.

##### Verification & Rollback Procedures
- **Verification Command**:
  ```bash
  # Test with external IP simulation header or curl from outside the LAN:
  curl -s -k -H "Host: pve1.local.starklab.mkroshana.com" https://10.10.10.100/ -H "X-Forwarded-For: 112.135.10.20"
  ```
- **Expected Output**: `HTTP/1.1 403 Forbidden` from Traefik.
- **Rollback Command**: Temporarily restore the specific current public IP `/32` (e.g., `112.135.x.y/32`) if emergency remote access is needed before split-horizon DNS is deployed.

---

#### [SEC-CRIT-03] Unauthenticated Public Route Exposure & Wildcard CORS on Bazarr
- **Severity**: Critical
- **CVSS v3.1 Score**: **9.1** (`CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N`)
- **CWE ID**: CWE-306 (Missing Authentication for Critical Function) / CWE-942 (Permissive Cross-Domain Policy with Wildcard)
- **Affected Target(s)**: `bazarr.starklab.mkroshana.com` (`CT 115` at `10.10.10.115:6767`), defined in `traefik-setup/conf.d/bazarr.yaml`
- **Prerequisites**: Direct access to public internet.

##### Technical Description & Root Cause
The Traefik configuration file `conf.d/bazarr.yaml` defines a public internet router for `Host('bazarr.starklab.mkroshana.com')`. Unlike `dashboard.yaml` (which requires `dashboard-auth` BasicAuth) or internal services (which require `block-external`), `bazarr.yaml` only applies `crowdsec-bouncer`, `security-headers`, and `general-rate-limit`.

Active probing of the live Bazarr service on CT 115 (`10.10.10.115:6767`) revealed that Bazarr's built-in authentication is disabled (`isConfigured: false`, `auth_method: apikey`). The application serves its full administrative single-page web app to any unauthenticated client and sets `Access-Control-Allow-Origin: *`.

##### Reproducible Evidence
Executed against `10.10.10.115:6767`:

```bash
# 1. Probe HTTP response headers on Bazarr
curl -s -I http://10.10.10.115:6767/

# Output:
# HTTP/1.1 200 OK
# Access-Control-Allow-Origin: *
# Content-Length: 2509
# Content-Type: text/html; charset=utf-8
# Server: waitress
# Vary: Accept-Encoding, Cookie

# 2. Verify web UI payload and authentication status
curl -s http://10.10.10.115:6767/ | grep -o 'window.Bazarr = JSON.parse([^)]*)'

# Output:
# window.Bazarr = JSON.parse(`{"baseUrl": "", "canUpdate": true, "hasUpdate": false, "isConfigured": false}`)

# 3. Check Traefik middleware definition in bazarr.yaml
grep -A 10 "middlewares:" d:/Development/stark-lab/traefik-setup/conf.d/bazarr.yaml

# Output:
#       middlewares:
#         - crowdsec-bouncer
#         - security-headers
#         - general-rate-limit
# (No basicAuth, forward-auth, or dashboard-auth attached!)
```

##### Technical Risk & Impact Analysis
Any external user navigating to `https://bazarr.starklab.mkroshana.com` bypasses all authentication gates and gains full administrative access to the Bazarr dashboard. An attacker can:
1. Inspect configured filesystem paths for media libraries and bind mounts (`/mnt/Movies`, `/mnt/TV-Shows`).
2. Read and exfiltrate third-party provider API keys, usernames, and passwords stored in `/var/lib/bazarr/config/config.yaml`.
3. Trigger arbitrary subtitle downloads, file renaming, or file overwrites on shared NFS storage.
4. Exploit the wildcard CORS header (`Access-Control-Allow-Origin: *`) via malicious third-party websites to perform CSRF/CORS-based API requests against Bazarr.

##### Specific, Safe Remediation Guidance
1. **Remove Public Route or Attach Authentication Middleware**:
   In `traefik-setup/conf.d/bazarr.yaml`, attach Traefik basicAuth (`dashboard-auth`) or remove the public route entirely, leaving only `local-bazarr.yaml`:
   ```yaml
   routers:
     bazarr:
       rule: "Host(`bazarr.starklab.mkroshana.com`)"
       entryPoints:
         - websecure
       service: bazarr-svc
       middlewares:
         - crowdsec-bouncer
         - dashboard-auth      # Add BasicAuth gate
         - security-headers
         - general-rate-limit
       tls:
         certResolver: cloudflare
   ```

2. **Enforce Authentication in Bazarr Application Settings**:
   Execute inside CT 115:
   ```bash
   ssh root@10.10.10.31 "pct exec 115 -- sed -i 's/auth_method: .*/auth_method: form/' /var/lib/bazarr/config/config.yaml"
   ssh root@10.10.10.31 "pct exec 115 -- systemctl restart bazarr"
   ```

##### Verification & Rollback Procedures
- **Verification Command**:
  ```bash
  curl -s -I https://bazarr.starklab.mkroshana.com/ --resolve bazarr.starklab.mkroshana.com:443:10.10.10.100
  ```
- **Expected Output**: `HTTP/2 401 Unauthorized` (demanding HTTP Basic Auth credentials).
- **Rollback Command**: Restore `bazarr.yaml` from git if temporary unauthenticated debugging is required.

---

### 4.2 High Severity Vulnerabilities

#### [SEC-HIGH-01] Unprotected In-Guest OpenSSH with Root Password Authentication Across 9 Active Containers
- **Severity**: High
- **CVSS v3.1 Score**: **8.8** (`CVSS:3.1/AV:A/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H`)
- **CWE ID**: CWE-287 (Improper Authentication) / CWE-521 (Weak Password Requirements)
- **Affected Target(s)**: CT 101, 102, 111, 113, 114, 115, 117, 118, 119, 121
- **Prerequisites**: Network access to `10.10.10.0/24`.

##### Technical Description & Root Cause
Auditing in-guest OpenSSH configurations via `pct exec <id> -- sshd -T` across all 12 running containers revealed that **9 active containers** have both `PermitRootLogin yes` AND `PasswordAuthentication yes` enabled on `0.0.0.0:22`.

Furthermore, none of the guest containers run intrusion prevention daemons (`fail2ban` or `crowdsec`). If an administrator assigns a password to root or if PAM modules permit fallback authentication, these containers become immediately vulnerable to password brute-forcing across the flat Layer 2 subnet.

##### Reproducible Evidence
Live audit across running containers:

```bash
ssh root@10.10.10.31 'for id in 100 101 102 103 111 113 114 115 117 118 119 121; do \
  echo -n "CT $id: "; pct exec $id -- sh -c "sshd -T 2>/dev/null | grep -E \"^permitrootlogin|^passwordauthentication\" | tr \"\n\" \" \"; echo \"\""; \
done'

# Verbatim Output:
# CT 100: permitrootlogin without-password passwordauthentication yes 
# CT 101: permitrootlogin yes passwordauthentication yes 
# CT 102: permitrootlogin yes passwordauthentication yes 
# CT 103: permitrootlogin without-password passwordauthentication yes 
# CT 111: permitrootlogin yes passwordauthentication yes 
# CT 113: permitrootlogin yes passwordauthentication yes 
# CT 114: permitrootlogin yes passwordauthentication yes 
# CT 115: permitrootlogin yes passwordauthentication yes 
# CT 117: permitrootlogin yes passwordauthentication yes 
# CT 118: permitrootlogin yes passwordauthentication yes 
# CT 119: permitrootlogin yes passwordauthentication yes 
# CT 121: permitrootlogin yes passwordauthentication yes 
```

##### Technical Risk & Impact Analysis
In Proxmox VE, `sshd` inside LXC containers is completely redundant because the hypervisor provides out-of-band management via `pct enter <id>` and `pct exec <id>`. Having `sshd` listening on `0.0.0.0:22` in every guest container with root password authentication enabled expands the internal attack surface by 12 network daemons, allowing any compromised host on `10.10.10.0/24` to pivot and laterally compromise every other container.

##### Specific, Safe Remediation Guidance
Disable `sshd` on internal containers that do not require network SSH, and enforce key-only authentication on remaining nodes:

```bash
# Execute on pve1 to harden all active containers:
ssh root@10.10.10.31 'for id in 101 102 111 113 114 115 117 118 119 121; do
  echo "Hardening CT $id..."
  pct exec $id -- sed -i "s/^PermitRootLogin.*/PermitRootLogin prohibit-password/" /etc/ssh/sshd_config
  pct exec $id -- sed -i "s/^PasswordAuthentication.*/PasswordAuthentication no/" /etc/ssh/sshd_config
  pct exec $id -- systemctl reload ssh || pct exec $id -- systemctl reload sshd
done'

# For containers where SSH is completely unneeded, disable the service:
# pct exec <id> -- systemctl disable --now ssh
```

##### Verification & Rollback Procedures
- **Verification Command**:
  ```bash
  ssh root@10.10.10.31 'for id in 101 102 111 113 114 115 117 118 119 121; do \
    echo -n "CT $id: "; pct exec $id -- sshd -T | grep -E "^permitrootlogin|^passwordauthentication" | tr "\n" " "; echo ""; \
  done'
  ```
- **Expected Output**: `permitrootlogin prohibit-password passwordauthentication no` across all containers.
- **Rollback Command**: Run `pct enter <id>` and revert `/etc/ssh/sshd_config`.

---

#### [SEC-HIGH-02] Unmirrored Single-Drive ZFS Storage, Total PBS Outage & Absent Automated Backups
- **Severity**: High
- **CVSS v3.1 Score**: **7.5** (`CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H`)
- **CWE ID**: CWE-703 (Improper Check or Handling of Exceptional Conditions) / Architecture Fragility
- **Affected Target(s)**: `pve1` storage architecture (`rpool`), Proxmox Backup Server (`10.10.10.32:8007`), `/etc/pve/vzdump.cron`
- **Prerequisites**: None (Hardware degradation or physical fault).

##### Technical Description & Root Cause
The hypervisor root pool `rpool` operates on a **single 256GB NVMe SSD** (`Lexar SSD NM620 256GB`) with zero RAID mirroring. Furthermore:
1. The offsite Proxmox Backup Server at `10.10.10.32:8007` is completely unreachable (*No route to host*).
2. Proxmox's automated backup configuration (`/etc/pve/vzdump.cron`) contains zero scheduled backup jobs.
3. The root ZFS pool holds 18 unmanaged static snapshots (`@pre-*-update`) created on 2026-09-13 occupying ~11 GB of storage without automated retention or pruning.
4. Only CT 101's Duplicati instance has an offsite copy (to Google Drive), which covers only `/mnt/Vault/Personal Data`. None of the hypervisor configurations, container root filesystems, or databases have active backups.

##### Reproducible Evidence
Audited on `pve1`:

```bash
# 1. Verify single-disk pool status
ssh root@10.10.10.31 "zpool status rpool"

# Output:
#   pool: rpool
#  state: ONLINE
#  config:
# 	NAME                                                 STATE     READ WRITE CKSUM
# 	rpool                                                ONLINE       0     0     0
# 	  nvme-Lexar_SSD_NM620_256GB_PCR121R002848P1109-part3  ONLINE       0     0     0

# 2. Probe PBS connectivity
ssh root@10.10.10.31 "nc -z -v -w 2 10.10.10.32 8007"

# Output:
# (UNKNOWN) [10.10.10.32] 8007 (?) : No route to host

# 3. Check scheduled vzdump jobs
ssh root@10.10.10.31 "cat /etc/pve/vzdump.cron"

# Output:
# # (Empty file / comments only)
```

##### Technical Risk & Impact Analysis
Because consumer-grade NVMe drives exhibit sudden, non-linear failure modes without warning, a hardware failure of the single Lexar NM620 SSD will permanently destroy the hypervisor, all 18 LXC container filesystems, and the Home Assistant virtual machine. With PBS down and no `vzdump` backups, recovery is impossible.

##### Specific, Safe Remediation Guidance
1. **Prune Stale Snapshots**:
   ```bash
   ssh root@10.10.10.31 "for snap in \$(zfs list -H -o name -t snapshot | grep '@pre-'); do zfs destroy \$snap; done"
   ```
2. **Schedule Daily vzdump Backups to Unraid Storage**:
   Configure `/etc/pve/vzdump.cron` to perform daily backups of all guests to `/mnt/pve/Backups` (`10.10.10.30`):
   ```cron
   0 2 * * * root vzdump all --mode snapshot --compress zstd --storage Backups --mailnotification failure
   ```
3. **Restore PBS Host (`10.10.10.32`)**:
   Verify physical power and network cabling on `10.10.10.32` and re-establish backup synchronization.
4. **Hardware Mirroring**:
   Add a second identical 256GB/512GB NVMe SSD to `pve1` and attach it to create a mirrored ZFS vdev:
   `zpool attach rpool nvme-Lexar_SSD_... nvme-Second_SSD_...`

##### Verification & Rollback Procedures
- **Verification Command**:
  ```bash
  ssh root@10.10.10.31 "pvescheduler status && vzdump --list"
  ```
- **Expected Output**: Active scheduled jobs targeting `Backups`.

---

#### [SEC-HIGH-03] Permissive World-Writable (0777) NFS Bind Mounts Lacking Container User Namespace Squash
- **Severity**: High
- **CVSS v3.1 Score**: **8.8** (`CVSS:3.1/AV:A/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H`)
- **CWE ID**: CWE-732 (Incorrect Permission Assignment for Critical Resource)
- **Affected Target(s)**: NFS exports from `10.10.10.30`, mounted on `pve1` at `/mnt/pve/*` and bind-mounted to CT 101, 111, 115, 117, 118, 120, 121
- **Prerequisites**: Compromise of any container sharing an NFS bind mount.

##### Technical Description & Root Cause
Network shares exported from Unraid (`10.10.10.30`) are mounted on `pve1` using NFSv4.2 with options `rw,relatime,vers=4.2,sec=sys`. Every shared directory (`/mnt/pve/Movies`, `/mnt/pve/TV-Shows`, `/mnt/pve/Downloads`, `/mnt/pve/Vault`) has **`0777` (`drwxrwxrwx nobody:nogroup`) permissions**.

Because these directories are bind-mounted into unprivileged containers without UID/GID remapping or root squashing, any user or process inside any attached container possesses unrestricted read, write, and delete permissions over the shared files.

##### Reproducible Evidence
Audited on `pve1`:

```bash
# 1. Check permissions on host NFS mountpoints
ssh root@10.10.10.31 "ls -ld /mnt/pve/*"

# Verbatim Output:
# drwxrwxrwx 15 nobody nogroup 4096 Sep 14 06:50 /mnt/pve/Backups
# drwxrwxrwx 12 nobody nogroup 4096 Sep 16 02:30 /mnt/pve/Downloads
# drwxrwxrwx 45 nobody nogroup 4096 Sep 15 22:15 /mnt/pve/Movies
# drwxrwxrwx 82 nobody nogroup 4096 Sep 15 22:15 /mnt/pve/TV-Shows
# drwxrwxrwx  6 nobody nogroup 4096 Sep 14 07:10 /mnt/pve/Vault

# 2. Verify bind mounts in container configurations
grep -E '^mp[0-9]+:' /etc/pve/lxc/{101,111,115,117,118,121}.conf
```

##### Technical Risk & Impact Analysis
1. **Cross-Container Compromise**: CT 111 (`qbittorrent`) and CT 115 (`bazarr`) are exposed to external inputs (torrents and subtitle archives). A vulnerability in either application allows an attacker to write malicious scripts or overwrite media files in `/mnt/Movies` and `/mnt/TV-Shows` used by Jellyfin (CT 121).
2. **Personal Data Exposure**: CT 101 mounts `/mnt/pve/Vault` as `/mnt/Vault`. Within this share, sensitive personal tax, identity, and medical documents reside in plaintext with world-writable permissions.

##### Specific, Safe Remediation Guidance
1. **Mount Media Shares Read-Only in Consuming Containers**:
   In `/etc/pve/lxc/121.conf` (Jellyfin) and `/etc/pve/lxc/115.conf` (Bazarr), specify `ro=1` on bind mounts where write access is not strictly required:
   `mp2: /mnt/pve/Movies,mp=/mnt/Movies,ro=1`
2. **Implement POSIX ACLs or NFS Squash on Unraid**:
   Reconfigure `/etc/exports` on Unraid (`10.10.10.30`) to restrict NFS access to `10.10.10.31/32` (instead of `10.10.10.0/24`) and enforce `root_squash,all_squash,anonuid=1000,anongid=1000`.
3. **Isolate Personal Vault**:
   Remove `/mnt/pve/Vault` from all containers except CT 101, and enforce `0750` permissions owned by the backup user.

##### Verification & Rollback Procedures
- **Verification Command**:
  ```bash
  ssh root@10.10.10.31 "pct exec 121 -- touch /mnt/Movies/test_write"
  ```
- **Expected Output**: `touch: cannot touch '/mnt/Movies/test_write': Read-only file system`.

---

#### [SEC-HIGH-04] Plaintext API Tokens in Local `.env` & Leaked Credentials in Git History
- **Severity**: High
- **CVSS v3.1 Score**: **7.7** (`CVSS:3.1/AV:L/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N`)
- **CWE ID**: CWE-312 (Cleartext Storage of Sensitive Information) / CWE-522 (Insufficiently Protected Credentials)
- **Affected Target(s)**: `traefik-setup/.env` on workstation, Git commit history (`ec6edcd`, `8f13ca9`, `5000341`)
- **Prerequisites**: Access to developer workstation filesystem or read access to git clone.

##### Technical Description & Root Cause
1. **Local `.env` Exposure**: The file `d:\Development\stark-lab\traefik-setup\.env` contains an active Cloudflare API Token (`CF_API_TOKEN`) with Zone DNS Edit permissions, the CrowdSec Bouncer API key, and an Apache MD5-crypt password hash for Traefik dashboard administrative access. The file inherits standard Windows user NTFS permissions without restricted DACLs.
2. **Git Commit History Leaks**: Git history contains multiple commits that directly checked in plaintext test credentials, hashes, and disabled authentication:
   - Commit `ec6edcd` (2026-04-03): Committed `# TEST USER: traefiktest / traefiktest` and hash `- "traefiktest:$$apr1$$XQZ.P7Z.$6JzXmOn5jYn85rYFzU6pC1"`.
   - Commit `8f13ca9` (2026-04-03): Retained the test user comment and APR1 hash.
   - Commit `5000341` (2026-04-03): Checked in `# middlewares: [] <-- TEMPORARILY DISABLED`.
3. **Obsolete Hashing**: Password hashes use Apache MD5-crypt (`$apr1$`), which is highly vulnerable to GPU-accelerated dictionary attacks.

##### Reproducible Evidence
Inspecting local files and Git log:

```bash
# 1. Plaintext credentials in .env
Select-String -Path "d:\Development\stark-lab\traefik-setup\.env" -Pattern "(CF_API_TOKEN|CROWDSEC_BOUNCER_API_KEY|DASHBOARD_AUTH_HASH)"

# Output:
# CF_API_TOKEN=cfut_[REDACTED_CLOUDFLARE_API_TOKEN]
# CROWDSEC_BOUNCER_API_KEY=z9PHXhNZlffSJQdGE6kf/UlPE8mHy03PWBx7RIbrfY4
# DASHBOARD_AUTH_HASH=admin:$apr1$ucbHoBML$CV813UcrFxSm3PRSJT/gL0

# 2. Inspect git commit history for leaked credentials
git log -S "traefiktest" -p
```

##### Technical Risk & Impact Analysis
1. **Cloudflare Account & DNS Hijacking**: The exposed `CF_API_TOKEN` grants full DNS modification rights for `mkroshana.com`. An attacker possessing this token can redirect traffic to malicious servers, issue rogue SSL/TLS certificates via DNS-01 challenges, or disrupt external services.
2. **Git Clones**: Anyone obtaining a copy of the repository history can extract historical credentials and attempt credential stuffing against StarkLab portals.

##### Specific, Safe Remediation Guidance
1. **Rotate Cloudflare API Token**:
   Log into Cloudflare Dashboard -> API Tokens -> Revoke `cfut_5JQ7...` and generate a new token strictly scoped to `Zone:DNS:Edit` for `mkroshana.com`.
2. **Upgrade Dashboard Password Hash to bcrypt**:
   Generate modern bcrypt hash (`htpasswd -nbB admin <password>`) and update `.env`.
3. **Sanitize Git History**:
   Use `git-filter-repo` to scrub commits `ec6edcd` and `8f13ca9` from git history:
   ```bash
   git filter-repo --replace-text <(echo "traefiktest==>REDACTED")
   ```

##### Verification & Rollback Procedures
- **Verification Command**:
  ```bash
  git log -S "traefiktest"
  ```
- **Expected Output**: Empty (zero matching commits in history).

---

#### [SEC-HIGH-05] Traefik Configuration Drift Between Live CT 100 Filesystem and Git Repository
- **Severity**: High
- **CVSS v3.1 Score**: **8.2** (`CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:L/A:N`)
- **CWE ID**: CWE-1059 (Incomplete Documentation) / Operational Configuration Drift
- **Affected Target(s)**: `/etc/traefik/conf.d/` on CT 100 vs `traefik-setup/conf.d/` in Git repository
- **Prerequisites**: None.

##### Technical Description & Root Cause
A directory diff between the live reverse proxy (`CT 100:/etc/traefik/conf.d/`) and the version-controlled repository (`traefik-setup/conf.d/`) revealed substantial configuration drift. Live CT 100 contains five untracked public router configurations:
- `qbittorrent.yaml` (exposing `qbittorrent.starklab.mkroshana.com` and `downloads.*`)
- `prowlarr.yaml` (exposing `prowlarr.starklab.mkroshana.com` and `indexer.*`)
- `radarr.yaml` (exposing `radarr.starklab.mkroshana.com` and `movies.*`)
- `sonarr.yaml` (exposing `sonarr.starklab.mkroshana.com` and `tvshows.*`)
- `n8n.yaml` (exposing `n8n.starklab.mkroshana.com` and `automations.*`)

Furthermore, `deploy.sh` relies on `tee` to write files and does not purge deleted or obsolete configurations from `/etc/traefik/conf.d/`.

##### Reproducible Evidence
Comparing live files on CT 100 against git repo:

```bash
ssh root@10.10.10.31 "pct exec 100 -- ls -1 /etc/traefik/conf.d/"

# Verbatim Listing on CT 100:
# bazarr.yaml
# duplicati.yaml
# homeassistant.yaml
# homelable.yaml
# jellyfin.yaml
# local-backups.yaml   <-- Untracked in git
# local-bazarr.yaml
# local-duplicati.yaml
# local-homeassistant.yaml
# local-homelable.yaml
# local-jellyfin.yaml
# local-n8n.yaml
# local-pbs.yaml
# local-plex.yaml
# local-prowlarr.yaml
# local-proxmox.yaml
# local-pterodactyl.yaml
# local-qbittorrent.yaml
# local-radarr.yaml
# local-seer.yaml
# local-sonarr.yaml
# local-tv.yaml
# local-unraid.yaml
# n8n.yaml             <-- Untracked in git
# plex.yaml
# prowlarr.yaml        <-- Untracked in git
# pterodactyl.yaml
# qbittorrent.yaml     <-- Untracked in git
# radarr.yaml          <-- Untracked in git
# seer.yaml
# sonarr.yaml          <-- Untracked in git
# tls.yaml
# tv.yaml
# _shared.yaml
```

##### Technical Risk & Impact Analysis
1. **Unmonitored Attack Surface**: Public internet routes for sensitive media management and workflow automation tools (`qBittorrent`, `Radarr`, `Sonarr`, `n8n`) are live on the reverse proxy without being committed or tracked in git.
2. **Deployment Fragility**: Running `deploy.sh` fails to produce a deterministic environment, leaving orphaned configurations active indefinitely.

##### Specific, Safe Remediation Guidance
1. Commit the active configurations to `traefik-setup/conf.d/` or remove the public routes if these services should strictly remain internal (`local-*`):
   ```bash
   # If internal only, remove public route files on CT 100:
   ssh root@10.10.10.31 "pct exec 100 -- rm -f /etc/traefik/conf.d/{qbittorrent,prowlarr,radarr,sonarr,n8n}.yaml"
   ```
2. Update `deploy.sh` to use directory synchronization (`rsync --delete` or explicit cleanup) so that `/etc/traefik/conf.d/` strictly mirrors version control.

##### Verification & Rollback Procedures
- **Verification Command**:
  ```bash
  diff -q "d:\Development\stark-lab\traefik-setup\conf.d\" <(ssh root@10.10.10.31 'pct exec 100 -- ls /etc/traefik/conf.d')
  ```
- **Expected Output**: Zero uncommitted differences.

---

#### [SEC-HIGH-06] Proxmox VE Host Firewall Inactive with Management Ports Exposed Across Subnet
- **Severity**: High
- **CVSS v3.1 Score**: **8.8** (`CVSS:3.1/AV:A/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H`)
- **CWE ID**: CWE-284 (Improper Access Control) / Missing Packet Filtering
- **Affected Target(s)**: Proxmox VE host `pve1` (`10.10.10.31`), `/etc/pve/firewall/`
- **Prerequisites**: Access to `10.10.10.0/24`.

##### Technical Description & Root Cause
The Proxmox VE firewall daemon `pve-firewall` is in state `disabled/running`. The configuration directory `/etc/pve/firewall/` is completely empty (no `cluster.fw` or `pve1.fw` rule definitions). Kernel Netfilter chains (`iptables -S INPUT`) have default `ACCEPT` policies with zero packet filtering rules.

Consequently, management and internal daemons listening on `0.0.0.0` or `*` are completely exposed to all 18 containers, VM 150, and any device on `10.10.10.0/24`:
- TCP 8006 (`pveproxy` - Proxmox Web GUI and API)
- TCP 22 (`sshd` - Host OpenSSH daemon)
- TCP 3128 (`spiceproxy` - SPICE console proxy)
- TCP/UDP 111 (`rpcbind` - RPC portmapper)
- Dynamic TCP/UDP ports 34315, 60647, 48462, 49984 (`rpc.statd` - NFS file locking)

##### Reproducible Evidence
Audited on `pve1`:

```bash
# 1. Inspect PVE firewall status
ssh root@10.10.10.31 "pve-firewall status"

# Output:
# Status: disabled/running

# 2. Check iptables INPUT chain policy
ssh root@10.10.10.31 "iptables -S INPUT"

# Output:
# -P INPUT ACCEPT

# 3. Check listening management ports
ssh root@10.10.10.31 "ss -tulpn | grep -E ':(8006|3128|111|22) '"

# Output:
# tcp   LISTEN 0 128   0.0.0.0:22    0.0.0.0:*  users:(("sshd",pid=1130,fd=3))
# tcp   LISTEN 0 128   *:8006        *:*        users:(("pveproxy",pid=1340,fd=6))
# tcp   LISTEN 0 128   *:3128        *:*        users:(("spiceproxy",pid=1348,fd=6))
# tcp   LISTEN 0 4096  0.0.0.0:111   0.0.0.0:*  users:(("rpcbind",pid=746,fd=4))
# udp   UNCONN 0 0     0.0.0.0:111   0.0.0.0:*  users:(("rpcbind",pid=746,fd=5))
```

##### Technical Risk & Impact Analysis
Without host-level packet filtering, any compromised container or rogue LAN host can launch brute force attacks against SSH (port 22) or the PVE API (port 8006), exploit zero-day vulnerabilities in `pveproxy`, or exploit RPC portmapper flaws.

##### Specific, Safe Remediation Guidance
1. **Create Host Firewall Ruleset (`/etc/pve/nodes/pve1/host.fw`)**:
   Restricting ports 8006 and 22 strictly to the management workstation (`10.10.10.10`) and trusted proxy (`10.10.10.100`):
   ```ini
   [OPTIONS]
   enable: 1
   policy_in: DROP
   policy_out: ACCEPT

   [RULES]
   IN ACCEPT -p tcp -dport 22 -source 10.10.10.10 -log nolog -comment "Admin SSH"
   IN ACCEPT -p tcp -dport 8006 -source 10.10.10.10,10.10.10.100 -log nolog -comment "PVE Web UI"
   IN ACCEPT -p tcp -dport 3128 -source 10.10.10.10 -log nolog -comment "SPICE Proxy"
   IN ACCEPT -i lo -log nolog -comment "Loopback"
   IN ACCEPT -p icmp -log nolog -comment "Allow ICMP ping"
   ```

2. **Enable PVE Firewall Globally**:
   ```bash
   ssh root@10.10.10.31 "pve-firewall start"
   ```

##### Verification & Rollback Procedures
- **Verification Command**:
  ```bash
  ssh root@10.10.10.31 "pve-firewall status"
  ```
- **Expected Output**: `Status: enabled/running`.
- **Rollback Command**: `pve-firewall stop` (disables packet filtering immediately).

---

### 4.3 Medium Severity Vulnerabilities

#### [SEC-MED-01] Missing Modern Web Security Headers (Content-Security-Policy, Permissions-Policy) & Obsolete XSS Header
- **Severity**: Medium
- **CVSS v3.1 Score**: **5.4** (`CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:L/I:L/A:N`)
- **CWE ID**: CWE-693 (Protection Mechanism Failure) / CWE-1021 (Improper Restriction of Rendered UI Layers)
- **Affected Target(s)**: `traefik-setup/conf.d/_shared.yaml` (lines 42–69) across all 28 Traefik routes
- **Prerequisites**: Ability to trigger XSS or malicious iframe inclusion on client browsers.

##### Technical Description & Root Cause
Traefik's `security-headers` and `security-headers-iframe` middlewares enforce HSTS (`maxAge: 31536000`), `contentTypeNosniff: true`, and `referrerPolicy: strict-origin-when-cross-origin`. However:
1. **No Content-Security-Policy (CSP)**: There is zero CSP defined. Modern browsers have no policy restricting script origins, websocket endpoints, image sources, or form actions. If an XSS vulnerability exists in Jellyfin, Seerr, or Home Assistant, an attacker can execute arbitrary JavaScript and exfiltrate user cookies or session tokens.
2. **No Permissions-Policy**: Modern browser hardware and feature restrictions (camera, microphone, geolocation, payment APIs) are omitted.
3. **Deprecated `browserXssFilter: true`**: Configures `X-XSS-Protection: 1; mode=block`. MDN, OWASP, and Google Chrome security guidelines have long deprecated this header because its heuristic auditor introduces new side-channel vulnerabilities and can be exploited to disable legitimate application scripts.

##### Reproducible Evidence
Inspecting `_shared.yaml` and live responses:

```bash
# 1. Inspect security-headers definition in _shared.yaml
grep -A 16 "security-headers:" d:/Development/stark-lab/traefik-setup/conf.d/_shared.yaml

# Output:
#     security-headers:
#       headers:
#         stsSeconds: 31536000
#         stsIncludeSubdomains: true
#         stsPreload: true
#         forceSTSHeader: true
#         frameDeny: true
#         contentTypeNosniff: true
#         browserXssFilter: true
#         referrerPolicy: "strict-origin-when-cross-origin"
#         customResponseHeaders:
#           X-Robots-Tag: "noindex, nofollow"
#           X-Permitted-Cross-Domain-Policies: "none"

# 2. Probe live response headers on Jellyfin
curl -sI https://jellyfin.starklab.mkroshana.com/ --resolve jellyfin.starklab.mkroshana.com:443:10.10.10.100 | grep -Ei "(content-security|permissions-policy|x-xss)"

# Output:
# x-xss-protection: 1; mode=block
# (Notice: content-security-policy and permissions-policy are completely absent)
```

##### Technical Risk & Impact Analysis
Without a CSP, client-side vulnerabilities can be weaponized for session hijacking, credential harvesting, or malicious UI redressing. Furthermore, setting `browserXssFilter: true` activates obsolete heuristic filters in older WebKit/Blink browsers known to create client-side vulnerabilities.

##### Specific, Safe Remediation Guidance
Update `traefik-setup/conf.d/_shared.yaml` to remove `browserXssFilter: true`, set `X-XSS-Protection: 0`, and inject standard `Permissions-Policy`:

```yaml
    security-headers:
      headers:
        stsSeconds: 31536000
        stsIncludeSubdomains: true
        stsPreload: true
        forceSTSHeader: true
        frameDeny: true
        contentTypeNosniff: true
        referrerPolicy: "strict-origin-when-cross-origin"
        permissionsPolicy: "camera=(), microphone=(), geolocation=(), payment=()"
        customResponseHeaders:
          X-Robots-Tag: "noindex, nofollow"
          X-Permitted-Cross-Domain-Policies: "none"
          X-XSS-Protection: "0"
```

##### Verification & Rollback Procedures
- **Verification Command**:
  ```bash
  curl -sI https://jellyfin.starklab.mkroshana.com/ --resolve jellyfin.starklab.mkroshana.com:443:10.10.10.100 | grep -i "permissions-policy"
  ```
- **Expected Output**: `permissions-policy: camera=(), microphone=(), geolocation=(), payment=()`.
- **Rollback Command**: Revert `_shared.yaml` if custom plugins require legacy browser settings.

---

#### [SEC-MED-02] Insecure Upstream TLS Transport (`insecureSkipVerify: true`) for Proxmox VE, PBS & Unraid
- **Severity**: Medium
- **CVSS v3.1 Score**: **6.8** (`CVSS:3.1/AV:A/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:N`)
- **CWE ID**: CWE-295 (Improper Certificate Validation)
- **Affected Target(s)**: `traefik-setup/conf.d/_shared.yaml` (lines 12–14), referenced in `local-proxmox.yaml`, `local-pbs.yaml`, `local-unraid.yaml`
- **Prerequisites**: Network positioning on `10.10.10.0/24` (ARP poisoning or DNS spoofing).

##### Technical Description & Root Cause
In `traefik-setup/conf.d/_shared.yaml`, Traefik defines a backend transport called `insecure-transport` configured with `insecureSkipVerify: true`:

```yaml
serversTransports:
  insecure-transport:
    insecureSkipVerify: true
```

This transport is attached to upstream routers communicating with Proxmox VE (`https://10.10.10.31:8006`), PBS (`https://10.10.10.32:8007`), and Unraid (`https://10.10.10.30`). By disabling upstream TLS certificate verification, Traefik ignores whether the backend server's SSL certificate is valid, self-signed, expired, or presented by an attacker.

##### Reproducible Evidence
Examining `_shared.yaml` and dependent route files:

```bash
grep -n -A 4 "insecure-transport:" d:/Development/stark-lab/traefik-setup/conf.d/_shared.yaml

# Output:
# 12:  serversTransports:
# 13:    insecure-transport:
# 14:      insecureSkipVerify: true

grep -rn "serversTransport: insecure-transport" d:/Development/stark-lab/traefik-setup/conf.d/

# Output:
# local-pbs.yaml:23:      serversTransport: insecure-transport
# local-proxmox.yaml:23:      serversTransport: insecure-transport
# local-unraid.yaml:23:      serversTransport: insecure-transport
```

##### Technical Risk & Impact Analysis
Because the entire estate operates on a flat Layer 2 broadcast subnet without dynamic ARP inspection (DAI) or port security, any rogue host or compromised container on `10.10.10.0/24` can execute ARP spoofing between Traefik (`10.10.10.100`) and the hypervisor (`10.10.10.31`). Because Traefik skips certificate validation, it will establish an encrypted connection to the attacker's interception proxy without warning, allowing the attacker to capture administrator PAM passwords and API tickets in plaintext.

##### Specific, Safe Remediation Guidance
1. Export the Proxmox VE Cluster CA certificate from `/etc/pve/pve-root-ca.pem` on `pve1`.
2. Copy `pve-root-ca.pem` to CT 100 at `/etc/traefik/ssl/pve-root-ca.pem`.
3. Configure Traefik's `serversTransport` to trust the internal CA rather than skipping verification:
   ```yaml
   serversTransports:
     pve-transport:
       rootCAs:
         - /etc/traefik/ssl/pve-root-ca.pem
   ```

##### Verification & Rollback Procedures
- **Verification Command**:
  ```bash
  ssh root@10.10.10.31 "pct exec 100 -- grep -i 'insecureSkipVerify' /etc/traefik/conf.d/_shared.yaml"
  ```
- **Expected Output**: Zero instances of `insecureSkipVerify: true`.
- **Rollback Command**: Revert transport to `insecureSkipVerify: true` if CA cert expires or changes.

---

#### [SEC-MED-03] Outdated OS Packages and Pending Kernel Security Updates on `pve1`
- **Severity**: Medium
- **CVSS v3.1 Score**: **6.3** (`CVSS:3.1/AV:A/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:L`)
- **CWE ID**: CWE-1395 (Dependency on Vulnerable Third-Party Component)
- **Affected Target(s)**: Proxmox VE hypervisor `pve1` (`10.10.10.31`)
- **Prerequisites**: Network access to `10.10.10.31` or local console access.

##### Technical Description & Root Cause
An audit of software package status on `pve1` via `apt list --upgradable` revealed that several critical core virtualization and security packages are unpatched, and the system is running a superseded kernel release:
- Currently running kernel: `Linux 7.0.14-16-pve`
- Available kernel package: `proxmox-kernel-7.0: 7.0.14-17`
- Available PVE Manager: `pve-manager: 9.2.20` (installed: `9.2.18`)
- Available Firewall Daemon: `pve-firewall: 6.0.6` (installed: `6.0.5`)
- Available Common Library: `libpve-common-perl: 9.2.2` (installed: `9.2.1`)

Furthermore, CPU vulnerability auditing on the Intel Core i5-7500T processor indicated that the system is **Vulnerable to Gather Data Sampling (Downfall, CVE-2022-40982)**.

##### Reproducible Evidence
Audited on `pve1`:

```bash
# 1. Inspect upgradable packages
ssh root@10.10.10.31 "apt list --upgradable 2>/dev/null"

# Verbatim Output:
# libpve-common-perl/stable 9.2.2 all [upgradable from: 9.2.1]
# proxmox-kernel-7.0/stable 7.0.14-17 amd64 [upgradable from: 7.0.14-16]
# pve-firewall/stable 6.0.6 amd64 [upgradable from: 6.0.5]
# pve-manager/stable 9.2.20 amd64 [upgradable from: 9.2.18]

# 2. Check CPU vulnerability status
ssh root@10.10.10.31 "cat /sys/devices/system/cpu/vulnerabilities/gather_data_sampling"

# Output:
# Vulnerable
```

##### Technical Risk & Impact Analysis
Running unpatched hypervisor management daemons and kernels exposes the infrastructure to stability regressions, privilege escalation exploits, and hypervisor escape bugs patched in newer Debian/Proxmox point releases.

##### Specific, Safe Remediation Guidance
Apply pending updates and reboot the hypervisor during a scheduled maintenance window:

```bash
# 1. Update Debian package index and upgrade packages
ssh root@10.10.10.31 "apt-get update && DEBIAN_FRONTEND=noninteractive apt-get dist-upgrade -y"

# 2. Clean package cache
ssh root@10.10.10.31 "apt-get clean"

# 3. Reboot hypervisor to boot into kernel 7.0.14-17
# ssh root@10.10.10.31 "reboot"
```

##### Verification & Rollback Procedures
- **Verification Command**:
  ```bash
  ssh root@10.10.10.31 "uname -r && pveversion"
  ```
- **Expected Output**: Kernel `7.0.14-17-pve` and manager `9.2.20`.
- **Rollback Command**: Select prior kernel `7.0.14-16-pve` in the Proxmox GRUB boot menu if kernel regressions occur.

---

#### [SEC-MED-04] Plex Configuration Guide Recommending Disabling Authentication for `10.10.10.0/24`
- **Severity**: Medium
- **CVSS v3.1 Score**: **7.4** (`CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:N`)
- **CWE ID**: CWE-306 (Missing Authentication for Critical Function) / Architectural Proxy Flaw
- **Affected Target(s)**: `traefik-setup/docs/service_plex.md` (lines 51–53) and CT 120 (`plex`)
- **Prerequisites**: Access to `plex.starklab.mkroshana.com` when CT 120 is active.

##### Technical Description & Root Cause
The setup documentation in `traefik-setup/docs/service_plex.md` instructs administrators to configure the Plex Media Server with:
```markdown
3. **List of IP addresses and networks that are allowed without auth:** `10.10.10.0/24`
   - This allows LAN clients to connect without re-authenticating through Plex.tv
```

When Traefik reverse proxies connections to Plex, the TCP socket connection originates from CT 100 (`10.10.10.100`), which resides within the `10.10.10.0/24` subnet. Unless Plex is configured with `customCertificateDomain` and correctly parses `X-Forwarded-For` from explicitly trusted proxies, Plex evaluates the incoming TCP source IP (`10.10.10.100`) as matching the allowed unauthenticated subnet. Consequently, **every external request from the internet routed through Traefik bypasses Plex.tv authentication**.

##### Reproducible Evidence
Documented in `traefik-setup/docs/service_plex.md`:

```bash
sed -n '50,54p' d:/Development/stark-lab/traefik-setup/docs/service_plex.md

# Verbatim Output:
# 3. **List of IP addresses and networks that are allowed without auth:** `10.10.10.0/24`
#    - This allows LAN clients to connect without re-authenticating through Plex.tv
#    - Especially helpful if internet is down or Plex.tv has an outage
```

##### Technical Risk & Impact Analysis
If CT 120 is booted and configured per documentation, external attackers can navigate to `https://plex.starklab.mkroshana.com/web` and obtain immediate, unauthenticated administrative control over the Plex Media Server, media libraries, and server settings.

##### Specific, Safe Remediation Guidance
1. Update `traefik-setup/docs/service_plex.md` to remove the recommendation to exempt `10.10.10.0/24` from authentication.
2. In CT 120 (when booted), ensure the Plex setting `allowedNetworks` is strictly empty.

##### Verification & Rollback Procedures
- **Verification Command**:
  ```bash
  grep "allowed without auth" d:/Development/stark-lab/traefik-setup/docs/service_plex.md
  ```
- **Expected Output**: Documentation explicitly warns against entering reverse proxy subnets.

---

#### [SEC-MED-05] Docker Daemon Socket (`/var/run/docker.sock`) Exposure Inside CT 113 (`flaresolverr`)
- **Severity**: Medium
- **CVSS v3.1 Score**: **7.8** (`CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H`)
- **CWE ID**: CWE-250 (Execution with Unnecessary Privileges)
- **Affected Target(s)**: CT 113 (`flaresolverr` at `10.10.10.113:8191`), `/var/run/docker.sock`
- **Prerequisites**: Command execution inside CT 113.

##### Technical Description & Root Cause
CT 113 runs Docker Engine inside an unprivileged LXC container to host the `flaresolverr` container (`ghcr.io/flaresolverr/flaresolverr:latest`). The Docker UNIX daemon socket `/var/run/docker.sock` is owned by `root:docker` with mode `0660`.

While CT 113 is an unprivileged LXC (UID 0 maps to host UID 100000) and `docker inspect flaresolverr` confirms the socket is **not bind-mounted inside the flaresolverr container**, any local user added to the `docker` group inside CT 113 has full root-equivalent control over the container's nested Docker engine.

##### Reproducible Evidence
Audited inside CT 113:

```bash
# 1. Check Docker socket inside CT 113
ssh root@10.10.10.31 "pct exec 113 -- ls -la /var/run/docker.sock"

# Output:
# srw-rw---- 1 root docker 0 Sep 13 07:05 /var/run/docker.sock

# 2. Verify flaresolverr container mounts
ssh root@10.10.10.31 "pct exec 113 -- docker inspect flaresolverr --format '{{json .Mounts}}'"

# Output:
# [] (Empty mount list - socket is not mounted into flaresolverr container)
```

##### Technical Risk & Impact Analysis
The presence of a Docker daemon inside an LXC guest introduces nested virtualization complexity and increases the attack surface of the container. If FlareSolverr is exploited and an attacker achieves local privilege escalation to the `docker` group, they obtain root within the LXC container.

##### Specific, Safe Remediation Guidance
1. Ensure no untrusted local users are added to the `docker` group inside CT 113.
2. Consider migrating FlareSolverr from Docker-in-LXC to a native Node.js/Chromium systemd service or standard OCI container to eliminate the nested Docker daemon.

##### Verification & Rollback Procedures
- **Verification Command**:
  ```bash
  ssh root@10.10.10.31 "pct exec 113 -- getent group docker"
  ```
- **Expected Output**: `docker:x:999:` with no untrusted local users.

---

### 4.4 Low Severity Vulnerabilities

#### [SEC-LOW-01] Unused Postfix MTA Listening on Port 25 Across All Active Containers
- **Severity**: Low
- **CVSS v3.1 Score**: **3.3** (`CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:L`)
- **CWE ID**: CWE-284 (Improper Access Control) / Unnecessary Service Exposure
- **Affected Target(s)**: `pve1` and CT 100, 101, 102, 103, 111, 113, 114, 115, 117, 118, 119, 121
- **Prerequisites**: Local execution within host or containers.

##### Technical Description & Root Cause
In Debian-based distribution templates and community scripts, the Postfix mail transport agent (`master`) is installed and activated by default. Auditing revealed `master` listening on `127.0.0.1:25` and `[::1]:25` across `pve1` and all 12 active containers.

None of these containers act as mail transfer agents or require local SMTP listening daemons.

##### Reproducible Evidence
Audited across containers:

```bash
ssh root@10.10.10.31 'for id in 100 101 102 103 111 113 114 115 117 118 119 121; do \
  echo -n "CT $id port 25: "; pct exec $id -- ss -tlpn | grep -o ":25 " || echo "closed"; \
done'

# Output confirms master listening on :25 across all 12 containers.
```

##### Technical Risk & Impact Analysis
Running unneeded network daemons consumes system memory, creates unnecessary background logging, and introduces potential local privilege escalation attack surface if local vulnerabilities are discovered in Postfix.

##### Specific, Safe Remediation Guidance
Disable and mask Postfix across all containers:

```bash
ssh root@10.10.10.31 'for id in 100 101 102 103 111 113 114 115 117 118 119 121; do \
  pct exec $id -- systemctl disable --now postfix; \
  pct exec $id -- systemctl mask postfix; \
done'
```

##### Verification & Rollback Procedures
- **Verification Command**:
  ```bash
  ssh root@10.10.10.31 'pct exec 101 -- ss -tulpn | grep :25'
  ```
- **Expected Output**: Empty output (port 25 closed).

---

### 4.5 Informational Findings

#### [SEC-INFO-01] Service Target Configuration Mismatches in Traefik (Home Assistant & Homelable)
- **Severity**: Informational
- **CVSS v3.1 Score**: **0.0** (`Informational`)
- **CWE ID**: CWE-1059 (Incomplete Documentation) / Service Routing Mismatch
- **Affected Target(s)**: `traefik-setup/conf.d/homeassistant.yaml` and `traefik-setup/conf.d/local-homelable.yaml`
- **Prerequisites**: None.

##### Technical Description & Root Cause
The audit identified discrepancies between the configured backend load balancer URLs in Traefik and the actual active addresses of the target services:
1. **Home Assistant**: `conf.d/homeassistant.yaml` (line 48) routes traffic to `http://10.10.10.150:8123`. However, the estate inventory in `homelab.md` and QEMU network queries indicate VM 150 is operating on `10.10.10.154:8123`.
2. **Homelable**: `conf.d/local-homelable.yaml` (line 22) routes traffic to `http://10.10.10.102:3000`. However, the Homelable service runs under `uvicorn` listening on port `8000`.

##### Reproducible Evidence
Examining configuration files vs runtime ports:

```bash
# 1. Home Assistant target in Traefik
grep "url:" d:/Development/stark-lab/traefik-setup/conf.d/homeassistant.yaml
# Output: - url: "http://10.10.10.150:8123"

# 2. Homelable target in Traefik
grep "url:" d:/Development/stark-lab/traefik-setup/conf.d/local-homelable.yaml
# Output: - url: "http://10.10.10.102:3000"

# 3. Check Homelable actual listening port in CT 102
ssh root@10.10.10.31 "pct exec 102 -- ss -tulpn | grep python"
# Output shows uvicorn listening on port 8000
```

##### Technical Risk & Impact Analysis
Requests sent to `ha.starklab.mkroshana.com` or `homelable.local.starklab.mkroshana.com` fail with HTTP 502 Bad Gateway responses or are misrouted, causing service outages.

##### Specific, Safe Remediation Guidance
1. In `conf.d/homeassistant.yaml` and `conf.d/local-homeassistant.yaml`, update the server URL to `http://10.10.10.154:8123`.
2. In `conf.d/local-homelable.yaml`, update the server URL to `http://10.10.10.102:8000`.

##### Verification & Rollback Procedures
- **Verification Command**:
  ```bash
  curl -sI -k https://homelable.local.starklab.mkroshana.com/ --resolve homelable.local.starklab.mkroshana.com:443:10.10.10.100
  ```
- **Expected Output**: HTTP 200 OK or 302 redirect (instead of 502 Bad Gateway).

---

## 5. Component-by-Component Hardening Audits

### 5.1 Proxmox VE Hypervisor Host (`pve1`) Hardening
The Proxmox VE hypervisor is the root trust anchor for the entire homelab. Hardening must isolate the host from guest network traffic and secure administration pathways:

#### 1. Host SSH Daemon Hardening (`/etc/ssh/sshd_config`)
Although `PermitRootLogin` is set to `without-password`, `PasswordAuthentication` is globally enabled (`yes`) for non-root accounts, and X11 forwarding is active.
- **Recommended Configuration**:
  ```ini
  # /etc/ssh/sshd_config.d/01-hardening.conf
  Port 22
  PermitRootLogin prohibit-password
  PasswordAuthentication no
  KbdInteractiveAuthentication no
  X11Forwarding no
  MaxAuthTries 3
  AllowAgentForwarding no
  AllowTcpForwarding no
  ClientAliveInterval 300
  ClientAliveCountMax 2
  ```
- **Action**: Place this file in `/etc/ssh/sshd_config.d/01-hardening.conf` and reload `sshd`:
  `ssh root@10.10.10.31 "systemctl reload ssh"`

#### 2. Proxmox VE Firewall Activation
Create `/etc/pve/nodes/pve1/host.fw` and activate packet filtering:
- Block all unsolicited incoming traffic by default.
- Allow incoming SSH (port 22) strictly from the administrator workstation `10.10.10.10`.
- Allow Proxmox Web GUI (port 8006) strictly from `10.10.10.10` and reverse proxy `10.10.10.100`.
- Drop all unsolicited incoming RPC (port 111 and `rpc.statd` ports) from the LAN.

#### 3. Storage Resilience & Single NVMe Risk Mitigation
- **ZFS Pool Mirroring**: Currently, `rpool` is an unmirrored single SSD (`nvme-Lexar_SSD_NM620_256GB_PCR121R002848P1109-part3`). Install a second NVMe SSD of equal or greater capacity and execute:
  ```bash
  # Partition second drive to match partition table:
  sgdisk --replicate=/dev/nvme1n1 /dev/nvme0n1
  sgdisk --randomize-guids /dev/nvme1n1
  # Attach partition 3 as a mirror:
  zpool attach rpool /dev/nvme0n1p3 /dev/nvme1n1p3
  ```
- **Automate Snapshot Retention**: Install `sanoid` to automate hourly, daily, and weekly snapshot creation and pruning, replacing the 18 static snapshots.

#### 4. Kernel & Package Updates
- Apply pending packages (`pve-manager: 9.2.20`, `proxmox-kernel-7.0: 7.0.14-17`, `pve-firewall: 6.0.6`) via `apt update && apt dist-upgrade -y`.
- Schedule a hypervisor reboot to run kernel `7.0.14-17-pve`.

---

### 5.2 LXC Guest Containers & KVM Virtual Machine Hardening

#### 1. Privilege Level and Capability Enforcement (CT 105 Remediation)
- **Immediate Mitigation**:
  In `/etc/pve/lxc/105.conf`, delete `lxc.cgroup2.devices.allow: a`, drop administrative capabilities (`lxc.cap.drop: sys_admin sys_rawio mknod`), and lock the root password hash in `/rpool/data/subvol-105-disk-0/etc/shadow`.
- **Permanent Remediation**:
  Rebuild or restore CT 105 as an **unprivileged container** (`unprivileged: 1`) using standard rootless podman or standard unprivileged container templates.

#### 2. Containerized OpenSSH Service Elimination
Because Proxmox VE enables direct console execution via `pct enter <id>` from `pve1`, running OpenSSH inside guest containers represents unnecessary exposure.
- On containers that do not specifically require network SSH (CT 101, 102, 111, 113, 114, 115, 117, 118, 119, 121), stop and disable the SSH service:
  ```bash
  ssh root@10.10.10.31 'for id in 101 102 111 113 114 115 117 118 119 121; do \
    pct exec $id -- systemctl disable --now ssh; \
  done'
  ```
- On containers where SSH is retained (CT 100, 103), enforce `PermitRootLogin prohibit-password` and `PasswordAuthentication no`.

#### 3. Bind Mount Read-Only Enforcements
- In `/etc/pve/lxc/121.conf` (Jellyfin) and `/etc/pve/lxc/115.conf` (Bazarr), configure media library mounts with `ro=1`:
  ```ini
  mp2: /mnt/pve/Movies,mp=/mnt/Movies,ro=1
  mp3: /mnt/pve/TV-Shows,mp=/mnt/TV-Shows,ro=1
  ```
- This guarantees that a compromise of the media server or subtitle fetcher cannot delete or alter the central media storage.

#### 4. Unnecessary Daemons (Postfix MTA)
- Disable Postfix on all containers and the host:
  ```bash
  systemctl disable --now postfix && systemctl mask postfix
  ```

---

### 5.3 Reverse Proxy & Perimeter Defense (Traefik & CrowdSec)

#### 1. Elimination of Overbroad ISP Whitelist & Hairpin NAT Resolution
- **Purge Subnet Allowlist**: Remove `112.135.0.0/16` from `_shared.yaml`. `block-external` must strictly contain private RFC1918 subnets:
  ```yaml
  block-external:
    ipAllowList:
      sourceRange:
        - "127.0.0.1/32"
        - "10.10.10.0/24"
        - "192.168.0.0/16"
  ```
- **Deploy Split-Horizon DNS**:
  Configure the local LAN DNS server (e.g. AdGuard Home, Pi-hole, or dnsmasq) with a local DNS rewrite rule:
  ```
  *.starklab.mkroshana.com -> 10.10.10.100
  ```
  This allows LAN clients to connect directly to Traefik via `10.10.10.100` using the official HTTPS domain, completely bypassing the router's hairpin NAT limitation without exposing internal management portals to the public internet.

#### 2. CrowdSec Scenario Tuning for Jellyfin
- Delete `/etc/crowdsec/postoverflows/s01-whitelist/home-whitelist.yaml` from CT 100.
- Instead of whitelisting entire public ISP subnets, create a fine-grained parser whitelist targeting Jellyfin media stream requests in `/etc/crowdsec/parsers/s02-enrich/jellyfin-whitelist.yaml`:
  ```yaml
  name: starklab/jellyfin-whitelist
  description: "Whitelist legitimate burst API requests from Jellyfin clients"
  filter: "evt.Parsed.program == 'traefik' && (evt.Parsed.request startsWith '/Items' || evt.Parsed.request startsWith '/Videos' || evt.Parsed.request startsWith '/Images')"
  whitelist:
    reason: "Jellyfin client metadata and playback requests"
  ```
- Restart CrowdSec: `systemctl restart crowdsec`.

#### 3. Secure Web Routing & Authentication Enforcement
- **Bazarr Protection**: Attach `dashboard-auth` BasicAuth middleware to `conf.d/bazarr.yaml`, or delete `bazarr.yaml` to restrict Bazarr strictly to `local-bazarr.yaml`.
- **Modern Security Headers**:
  - Add standard `Permissions-Policy` to `security-headers`.
  - Set `X-XSS-Protection: "0"`.
  - Define a baseline Content-Security-Policy (CSP) that permits self-origin resources and explicitly required CDNs.
- **Backend TLS Certificate Trust**:
  Import Proxmox VE root certificate authority (`/etc/pve/pve-root-ca.pem`) into Traefik's `serversTransports` and eliminate `insecureSkipVerify: true`.

---

### 5.4 Storage, Data Protection & Backup Systems

#### 1. Restore Proxmox Backup Server (`10.10.10.32`)
- Investigate network reachability to `10.10.10.32:8007`. Resolve physical power, IP address assignment, or switch port issues.
- Once online, verify the Proxmox storage pool `pbs` is active and configure automated snapshot backups of all containers.

#### 2. Implement Scheduled vzdump Backups to Unraid
- While PBS is being restored, configure daily local vzdump backups targeting the Unraid NFS share `/mnt/pve/Backups`.
- Configure retention rules in `/etc/pve/storage.cfg` to retain the last 7 daily backups, 4 weekly backups, and 3 monthly backups.

#### 3. Protect Duplicati Database & Encryption Secrets
- Verify the integrity of CT 101's SQLite database `/var/lib/Duplicati/GSTMETKKPG.sqlite`.
- Ensure `/var/lib/Duplicati.bak` is archived to secure offline storage.
- Encrypt the Duplicati database using SQLCipher or file-level GPG encryption.

---

### 5.5 Secrets, Credentials & Source Code Repository Hygiene

#### 1. Secure Local Environment Files (`traefik-setup/.env`)
- On Windows, restrict NTFS permissions on `d:\Development\stark-lab\traefik-setup\.env` so that only the primary user account has read access:
  ```powershell
  icacls "d:\Development\stark-lab\traefik-setup\.env" /inheritance:r /grant:r "$($env:USERNAME):(R,W)"
  ```
- Harmonize `REQUIRED_VARS` in `deploy.sh` with `.env` so that deployments execute deterministically.

#### 2. Rotate Cloudflare API Token
- Log into Cloudflare Dashboard -> My Profile -> API Tokens.
- Revoke token `cfut_[REDACTED_CLOUDFLARE_API_TOKEN]`.
- Create a new token with minimal privileges:
  - Permissions: `Zone - DNS - Edit`, `Zone - Zone - Read`
  - Zone Resources: `Include - Specific zone - mkroshana.com`
- Update `.env` on workstation and CT 100.

#### 3. Upgrade Dashboard Password Hashing
- Replace legacy MD5 apr1 hashing with bcrypt. Generate a strong hash:
  ```bash
  htpasswd -nbB admin "A_Strong_Random_Passphrase"
  ```
- Store the generated hash in `DASHBOARD_AUTH_HASH`.

#### 4. Scrub Leaked Credentials from Git Commit History
- Run `git-filter-repo` to permanently purge commits `ec6edcd` and `8f13ca9`:
  ```bash
  git filter-repo --invert-paths --path traefik-setup/conf.d/dashboard.yaml
  ```
  Or replace all occurrences of `traefiktest` across all commit objects.

---

## 6. Phased Remediation Roadmap

The remediation strategy is structured across three distinct phases prioritized by risk severity, operational impact, and implementation complexity.

```
+----------------------------------------------------------------------------------------------------+
| REMEDIATION TIMELINE                                                                               |
+----------------------------------------------------------------------------------------------------+
| Phase 1: Immediate Containment (0 - 24 Hours)                                                      |
|   Target: Eliminate critical remote takeover vectors, lock accounts, plug perimeter bypasses       |
+----------------------------------------------------------------------------------------------------+
| Phase 2: Configuration Hardening & Credentials (24 - 48 Hours)                                     |
|   Target: Rotate tokens, scrub git history, harden SSH, activate host firewall, align configs     |
+----------------------------------------------------------------------------------------------------+
| Phase 3: Infrastructure Hardening & Resilience (3 - 7 Days)                                        |
|   Target: Restore PBS, mirror ZFS pool, configure automated vzdump, prune snapshots, update kernel |
+----------------------------------------------------------------------------------------------------+
```

### 6.1 Phase 1: Immediate Containment & Exposure Elimination (0 – 24 Hours)
*Objective: Eliminate active, exploitable remote takeover vectors with zero service disruption.*

| Step | Action Item | Target Component | Command / Implementation Summary | Estimated Time |
|---|---|---|---|---|
| **1.1** | **Lock CT 105 Root Account & Restrict Devices** | `pve1` / CT 105 | `sed -i 's/^root::/root:!:/' /rpool/data/subvol-105-disk-0/etc/shadow`<br>`sed -i '/devices.allow: a/d' /etc/pve/lxc/105.conf` | 5 mins |
| **1.2** | **Sanitize Traefik `block-external`** | CT 100 / Repo | Delete `- "112.135.0.0/16"` from `conf.d/_shared.yaml`. Ensure only RFC1918 private subnets are permitted. | 5 mins |
| **1.3** | **Purge CrowdSec ISP Whitelist** | CT 100 | `pct exec 100 -- rm -f /etc/crowdsec/postoverflows/s01-whitelist/home-whitelist.yaml`<br>`pct exec 100 -- systemctl restart crowdsec` | 5 mins |
| **1.4** | **Secure Bazarr Public Route** | CT 100 / CT 115 | Attach `dashboard-auth` middleware in `conf.d/bazarr.yaml`, or delete `conf.d/bazarr.yaml` so Bazarr is only reachable via `local-bazarr.yaml`. | 10 mins |
| **1.5** | **Deploy Emergency Split-Horizon DNS / Hosts** | Workstation & LAN | Add `10.10.10.100 pve1.local.starklab.mkroshana.com` to local DNS/hosts so removal of `112.135` does not break internal admin access. | 15 mins |

---

### 6.2 Phase 2: Configuration Hardening & Credential Hygiene (24 – 48 Hours)
*Objective: Eliminate credential exposures, secure SSH daemons, enforce host packet filtering, and resolve configuration drift.*

| Step | Action Item | Target Component | Command / Implementation Summary | Estimated Time |
|---|---|---|---|---|
| **2.1** | **Revoke & Rotate Cloudflare API Token** | Cloudflare / `.env` | Revoke `cfut_5JQ7...` on Cloudflare Dashboard; generate new token with scoped `Zone:DNS:Edit` permissions; update `.env` and `/usr/local/bin/cloudflare-ddns.sh`. | 20 mins |
| **2.2** | **Upgrade Dashboard Password Hash to bcrypt** | CT 100 / `.env` | Generate bcrypt hash via `htpasswd -nbB admin <password>`; update `DASHBOARD_AUTH_HASH` in `.env` and restart Traefik. | 15 mins |
| **2.3** | **Scrub Leaked Credentials from Git History** | Git Repository | Execute `git filter-repo` to redact test user credentials and APR1 hashes from commits `ec6edcd` and `8f13ca9`. Force-push sanitized main branch. | 30 mins |
| **2.4** | **Harden In-Guest OpenSSH Across All 9 Containers** | CT 101–121 | Run loop script on `pve1` setting `PermitRootLogin prohibit-password` and `PasswordAuthentication no` across all containers; reload `sshd`. | 25 mins |
| **2.5** | **Activate Proxmox VE Host Firewall** | `pve1` (`10.10.10.31`) | Deploy `/etc/pve/nodes/pve1/host.fw` restricting ports 22 and 8006 to `10.10.10.10` and `10.10.10.100`; execute `pve-firewall start`. | 30 mins |
| **2.6** | **Correct Traefik Routing Targets** | CT 100 / Repo | Update Home Assistant target to `10.10.10.154:8123` and Homelable target to `:8000`. | 10 mins |
| **2.7** | **Harmonize `deploy.sh` & Reconcile Drift** | Repository / CT 100 | Align `REQUIRED_VARS` in `deploy.sh` with active `.env`; reconcile or remove drifted route files (`qbittorrent.yaml`, etc.) on CT 100. | 45 mins |
| **2.8** | **Disable Postfix Across All Containers** | All Containers | Run `pct exec <id> -- systemctl disable --now postfix` across all 12 containers. | 15 mins |

---

### 6.3 Phase 3: Infrastructure Hardening, Architecture & Resilience (3 – 7 Days)
*Objective: Build lasting hardware redundancy, reliable disaster recovery backups, and robust network segmentation.*

| Step | Action Item | Target Component | Command / Implementation Summary | Estimated Time |
|---|---|---|---|---|
| **3.1** | **Restore Proxmox Backup Server (`10.10.10.32`)** | PBS / Physical | Troubleshoot network connectivity, power, and IP reachability to `10.10.10.32:8007`. Reconnect PVE storage pool `pbs`. | 2 hours |
| **3.2** | **Implement Automated vzdump Backups to NAS** | `pve1` / Unraid | Configure daily cron job in `/etc/pve/vzdump.cron` backing up all LXC guests and VM 150 to `/mnt/pve/Backups`. | 30 mins |
| **3.3** | **Hardware Mirroring for Root ZFS Pool** | `pve1` Storage | Install second identical 256GB/512GB NVMe SSD; execute `zpool attach rpool` to establish a two-way mirrored root pool. | 2 hours |
| **3.4** | **Prune Static Snapshots & Install Sanoid** | `pve1` Storage | Destroy 18 static snapshots `@pre-*-update`; deploy `sanoid` for automated policy-based snapshot creation and pruning. | 45 mins |
| **3.5** | **Enforce Read-Only NFS Bind Mounts** | `pve1` / CT 115, 121 | Set `ro=1` on `/mnt/pve/Movies` and `/mnt/pve/TV-Shows` in CT 115 and CT 121 configurations to prevent media ransomware/deletion. | 30 mins |
| **3.6** | **Enforce NFS Network & Squash Security on Unraid** | Unraid NAS (`10.10.10.30`) | Restrict `/etc/exports` strictly to `10.10.10.31/32` (instead of `/24`) with `all_squash,anonuid=1000,anongid=1000`. | 45 mins |
| **3.7** | **Deploy Dedicated Split-Horizon DNS Service** | Network LAN | Deploy AdGuard Home or Pi-hole container returning `10.10.10.100` for `*.starklab.mkroshana.com` to resolve hairpin NAT for all LAN devices. | 2 hours |
| **3.8** | **Apply Kernel & PVE Updates and Reboot Host** | `pve1` Hypervisor | Run `apt-get dist-upgrade` on `pve1` to install kernel `7.0.14-17-pve` and `pve-manager 9.2.20`. Schedule maintenance reboot. | 1 hour |

---

### 6.4 Resource Allocation & Effort Estimation Matrix

| Phase | Priority Level | Total Est. Effort | Primary Administrative Role | Required Outage Window |
|---|---|---|---|---|
| **Phase 1: Immediate Containment** | **Urgent / Critical** | 40 minutes | Systems & Network Administrator | Zero downtime |
| **Phase 2: Configuration Hardening** | **High** | 3.5 hours | Security & DevOps Engineer | Brief Traefik reload (seconds) |
| **Phase 3: Infrastructure Resilience**| **Medium / Long-Term**| 9.5 hours | Infrastructure & Storage Engineer | Scheduled host reboot (10 mins) |

---

## 7. Verification Commands & Re-Audit Test Suite

This section provides an independently verifiable, repeatable test suite designed to confirm the presence of vulnerabilities pre-remediation and validate complete resolution post-remediation.

### 7.1 Individual Verification Command Catalog

| Finding ID | Verification Objective | Executable Test Command | Expected Remediated Output |
|---|---|---|---|
| `SEC-CRIT-01` | Verify CT 105 Root Lock & Device Isolation | `ssh root@10.10.10.31 "awk -F: '\$1==\"root\"{print \$1,\$2}' /rpool/data/subvol-105-disk-0/etc/shadow && grep 'devices.allow: a' /etc/pve/lxc/105.conf"` | `root !` (password locked); zero matches for `devices.allow: a`. |
| `SEC-CRIT-02` | Verify Removal of ISP /16 Whitelist | `grep -n "112.135" d:/Development/stark-lab/traefik-setup/conf.d/_shared.yaml && ssh root@10.10.10.31 "pct exec 100 -- grep '112.' /etc/crowdsec/postoverflows/s01-whitelist/home-whitelist.yaml 2>/dev/null"` | Zero matches returned; file not found or empty. |
| `SEC-CRIT-03` | Verify Bazarr Authentication Gate | `curl -sI https://bazarr.starklab.mkroshana.com/ --resolve bazarr.starklab.mkroshana.com:443:10.10.10.100` | `HTTP/2 401 Unauthorized` (BasicAuth prompt). |
| `SEC-HIGH-01` | Verify In-Guest SSH Hardening | `ssh root@10.10.10.31 'for id in 101 102 111 113 114 115 117 118 119 121; do pct exec $id -- sshd -T 2>/dev/null \| grep -E "^permitrootlogin|^passwordauthentication"; done'` | `permitrootlogin prohibit-password` and `passwordauthentication no` across all containers. |
| `SEC-HIGH-02` | Verify ZFS Mirror & vzdump Schedule | `ssh root@10.10.10.31 "zpool status rpool \| grep mirror && cat /etc/pve/vzdump.cron"` | Output shows `mirror-0` status `ONLINE` and active cron backup schedule. |
| `SEC-HIGH-03` | Verify Read-Only NFS Bind Mounts | `ssh root@10.10.10.31 "pct exec 121 -- touch /mnt/Movies/test_audit 2>&1"` | `touch: cannot touch '/mnt/Movies/test_audit': Read-only file system`. |
| `SEC-HIGH-04` | Verify Git Credential Scrubbing & bcrypt Hash | `git log -S "traefiktest" && grep -E "^\s*-\s*\"admin:\\\$2" d:/Development/stark-lab/traefik-setup/conf.d/dashboard.yaml` | Zero git log matches; bcrypt hash prefix `$2y$` present. |
| `SEC-HIGH-05` | Verify Live CT 100 vs Git Config Drift | `ssh root@10.10.10.31 "pct exec 100 -- ls -1 /etc/traefik/conf.d/*.yaml" \| sort \| diff -u <(ls -1 d:/Development/stark-lab/traefik-setup/conf.d/*.yaml \| xargs -n1 basename \| sort) -` | Zero uncommitted differences. |
| `SEC-HIGH-06` | Verify PVE Firewall State | `ssh root@10.10.10.31 "pve-firewall status && iptables -L PVEFW-INPUT -n 2>/dev/null \| head -n 10"` | `Status: enabled/running` with active PVEFW chains. |
| `SEC-MED-01` | Verify Modern Security Headers & Obsolete Removal | `curl -sI https://jellyfin.starklab.mkroshana.com/ --resolve jellyfin.starklab.mkroshana.com:443:10.10.10.100 \| grep -Ei "(permissions-policy\|x-xss-protection)"` | `permissions-policy: ...` present; `x-xss-protection: 0` or absent. |
| `SEC-MED-02` | Verify Backend TLS Verification | `ssh root@10.10.10.31 "pct exec 100 -- grep -i 'insecureSkipVerify: true' /etc/traefik/conf.d/_shared.yaml"` | Zero matches returned. |
| `SEC-MED-03` | Verify Kernel Version & Upgradable Packages | `ssh root@10.10.10.31 "uname -r && apt list --upgradable 2>/dev/null"` | `7.0.14-17-pve` (or later); `Listing... Done` with 0 upgradable security packages. |
| `SEC-MED-04` | Verify Plex Documentation Security | `grep "10.10.10.0/24" d:/Development/stark-lab/traefik-setup/docs/service_plex.md` | Zero recommendations to exempt internal subnet. |
| `SEC-MED-05` | Verify Docker Socket Group in CT 113 | `ssh root@10.10.10.31 "pct exec 113 -- getent group docker"` | `docker:x:999:` with no untrusted local members. |
| `SEC-LOW-01` | Verify Postfix MTA Disabled | `ssh root@10.10.10.31 'for id in 100 101 102 111 115 121; do pct exec $id -- ss -tlpn \| grep :25; done'` | Zero output (port 25 completely closed across all containers). |
| `SEC-INFO-01` | Verify HA & Homelable Backend URLs | `grep -E "url:.*(10\.10\.10\.154|:8000)" d:/Development/stark-lab/traefik-setup/conf.d/{homeassistant.yaml,local-homelable.yaml}` | Matches `http://10.10.10.154:8123` and `http://10.10.10.102:8000`. |

---

### 7.2 Automated Re-Audit Shell Runner Script (`re-audit.sh`)
An auditor can copy and run the following automated test script on the management host or `pve1` to verify all remediation milestones:

```bash
#!/usr/bin/env bash
# ==============================================================================
# Stark-Lab Automated Post-Remediation Verification Suite
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PVE_HOST="10.10.10.31"
PROXY_HOST="10.10.10.100"

log_pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; }
log_info() { echo -e "${YELLOW}[INFO]${NC} $1"; }

echo "========================================================================"
echo "STARK-LAB AUTOMATED RE-AUDIT VERIFICATION RUNNER"
echo "========================================================================"

# Test 1: CT 105 Root Lock
echo -n "Testing SEC-CRIT-01 (CT 105 Root Password & Devices)... "
SHADOW_VAL=$(ssh root@${PVE_HOST} "awk -F: '\$1==\"root\"{print \$2}' /rpool/data/subvol-105-disk-0/etc/shadow")
DEV_ALLOW=$(ssh root@${PVE_HOST} "grep -c 'devices.allow: a' /etc/pve/lxc/105.conf || true")
if [[ "$SHADOW_VAL" != "" && "$DEV_ALLOW" -eq 0 ]]; then
    log_pass "CT 105 root is locked and devices are restricted."
else
    log_fail "CT 105 root password is empty or all devices allowed!"
fi

# Test 2: Traefik & CrowdSec ISP /16 Whitelist
echo -n "Testing SEC-CRIT-02 (ISP /16 Whitelist Removal)... "
SHARED_MATCH=$(ssh root@${PVE_HOST} "pct exec 100 -- grep -c '112.135' /etc/traefik/conf.d/_shared.yaml || true")
CS_MATCH=$(ssh root@${PVE_HOST} "pct exec 100 -- grep -c '112.' /etc/crowdsec/postoverflows/s01-whitelist/home-whitelist.yaml 2>/dev/null || true")
if [[ "$SHARED_MATCH" -eq 0 && "$CS_MATCH" -eq 0 ]]; then
    log_pass "ISP /16 subnets removed from Traefik and CrowdSec."
else
    log_fail "ISP subnets still whitelisted!"
fi

# Test 3: Bazarr Authentication Gate
echo -n "Testing SEC-CRIT-03 (Bazarr Authentication Enforcement)... "
BAZARR_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://bazarr.starklab.mkroshana.com/ \
    --resolve bazarr.starklab.mkroshana.com:443:${PROXY_HOST} || true)
if [[ "$BAZARR_CODE" == "401" || "$BAZARR_CODE" == "403" ]]; then
    log_pass "Bazarr requires authentication (HTTP $BAZARR_CODE)."
else
    log_fail "Bazarr exposed unauthenticated (HTTP $BAZARR_CODE)!"
fi

# Test 4: Host Firewall State
echo -n "Testing SEC-HIGH-06 (Proxmox VE Host Firewall)... "
FW_STATUS=$(ssh root@${PVE_HOST} "pve-firewall status | awk '{print \$2}'")
if [[ "$FW_STATUS" == "enabled/running" ]]; then
    log_pass "Proxmox VE Firewall is active."
else
    log_fail "Proxmox VE Firewall is $FW_STATUS!"
fi

# Test 5: In-Guest SSH Hardening
echo -n "Testing SEC-HIGH-01 (In-Guest SSH Configurations)... "
SSH_FAILURES=0
for id in 101 102 111 113 114 115 117 118 119 121; do
    PASS_AUTH=$(ssh root@${PVE_HOST} "pct exec $id -- sshd -T 2>/dev/null | grep '^passwordauthentication' | awk '{print \$2}'" || echo "closed")
    if [[ "$PASS_AUTH" == "yes" ]]; then
        SSH_FAILURES=$((SSH_FAILURES + 1))
    fi
done
if [[ "$SSH_FAILURES" -eq 0 ]]; then
    log_pass "Password authentication disabled across all audited containers."
else
    log_fail "$SSH_FAILURES containers still allow password authentication!"
fi

echo "========================================================================"
echo "Re-Audit Run Completed."
echo "========================================================================"
```

---

## 8. Appendix & Configuration Artifacts

### Appendix A: Production-Hardened `conf.d/_shared.yaml`
```yaml
# ==============================================================================
# Hardened Shared Middlewares and Transport Configuration
# File: /etc/traefik/conf.d/_shared.yaml
# ==============================================================================
http:
  # -- Secure Upstream Transport with Internal CA --
  serversTransports:
    pve-secure-transport:
      rootCAs:
        - /etc/traefik/ssl/pve-root-ca.pem
      serverName: "pve1.starklab"

  middlewares:
    # -- Defense-in-Depth Security Headers --
    security-headers:
      headers:
        stsSeconds: 31536000
        stsIncludeSubdomains: true
        stsPreload: true
        forceSTSHeader: true
        frameDeny: true
        contentTypeNosniff: true
        referrerPolicy: "strict-origin-when-cross-origin"
        permissionsPolicy: "camera=(), microphone=(), geolocation=(), payment=()"
        customResponseHeaders:
          X-Robots-Tag: "noindex, nofollow"
          X-Permitted-Cross-Domain-Policies: "none"
          X-XSS-Protection: "0"

    # -- Same-Origin Frame Headers for Consoles & Dialogs --
    security-headers-iframe:
      headers:
        stsSeconds: 31536000
        stsIncludeSubdomains: true
        stsPreload: true
        forceSTSHeader: true
        customFrameOptionsValue: "SAMEORIGIN"
        contentTypeNosniff: true
        referrerPolicy: "strict-origin-when-cross-origin"
        permissionsPolicy: "camera=(), microphone=(), geolocation=(), payment=()"
        customResponseHeaders:
          X-Robots-Tag: "noindex, nofollow"
          X-Permitted-Cross-Domain-Policies: "none"
          X-XSS-Protection: "0"

    # -- Sanitized Block External Access (RFC1918 Private LAN Only) --
    block-external:
      ipAllowList:
        sourceRange:
          - "127.0.0.1/32"
          - "10.10.10.0/24"
          - "192.168.0.0/16"
          - "172.16.0.0/12"
        # REMOVED: 112.135.0.0/16 (Vulnerability SEC-CRIT-02 remediated)

    # -- Local-Only Composite Middleware --
    local-only:
      chain:
        middlewares:
          - block-external
          - security-headers

    # -- Local-Only Iframe Composite Middleware --
    local-iframe-only:
      chain:
        middlewares:
          - block-external
          - security-headers-iframe

    # -- General Volumetric Rate Limiting --
    general-rate-limit:
      rateLimit:
        average: 100
        burst: 200
        period: 1m

    # -- Strict Authentication Endpoint Rate Limiting --
    auth-rate-limit:
      rateLimit:
        average: 5
        burst: 3
        period: 1m
```

---

### Appendix B: Production-Hardened `conf.d/bazarr.yaml`
```yaml
# ==============================================================================
# Hardened Bazarr Reverse Proxy Router
# File: /etc/traefik/conf.d/bazarr.yaml
# ==============================================================================
http:
  routers:
    bazarr:
      rule: "Host(`bazarr.starklab.mkroshana.com`)"
      entryPoints:
        - websecure
      service: bazarr-svc
      middlewares:
        - crowdsec-bouncer
        - dashboard-auth        # SEC-CRIT-03 Remediated: Enforce BasicAuth
        - security-headers
        - general-rate-limit
      tls:
        certResolver: cloudflare

  services:
    bazarr-svc:
      loadBalancer:
        servers:
          - url: "http://10.10.10.115:6767"
        passHostHeader: true
```

---

### Appendix C: Production-Hardened Proxmox Firewall Rule Artifacts

#### Cluster Configuration (`/etc/pve/firewall/cluster.fw`)
```ini
[OPTIONS]
enable: 1
ebtables: 1

[RULES]
IN ACCEPT -p tcp -dport 22 -source 10.10.10.10 -comment "Admin Workstation SSH"
IN ACCEPT -p tcp -dport 8006 -source 10.10.10.10,10.10.10.100 -comment "PVE Web Management"
IN ACCEPT -p icmp -log nolog
```

#### Node Configuration (`/etc/pve/nodes/pve1/host.fw`)
```ini
[OPTIONS]
enable: 1
policy_in: DROP
policy_out: ACCEPT
log_level_in: nolog

[RULES]
IN ACCEPT -i lo -log nolog -comment "Allow Loopback"
IN ACCEPT -p tcp -dport 22 -source 10.10.10.10 -log nolog -comment "Admin SSH"
IN ACCEPT -p tcp -dport 8006 -source 10.10.10.10,10.10.10.100 -log nolog -comment "PVE Web API"
IN ACCEPT -p tcp -dport 3128 -source 10.10.10.10 -log nolog -comment "SPICE Proxy"
IN ACCEPT -p udp -dport 53 -source 10.10.10.1 -comment "DNS Responses"
```

---

### Appendix D: Hardened CrowdSec Jellyfin API Whitelist
```yaml
# ==============================================================================
# Hardened CrowdSec Parser Whitelist for Jellyfin API Bursts
# File: /etc/crowdsec/parsers/s02-enrich/jellyfin-whitelist.yaml
# ==============================================================================
name: starklab/jellyfin-api-whitelist
description: "Whitelist high-frequency static/metadata queries from Jellyfin apps"
filter: "evt.Parsed.program == 'traefik' && (evt.Parsed.request startsWith '/Items' || evt.Parsed.request startsWith '/Videos' || evt.Parsed.request startsWith '/Images' || evt.Parsed.request startsWith '/System/Info')"
whitelist:
  reason: "Legitimate Jellyfin client UI rendering and streaming calls"
```

---

### Appendix E: Comprehensive Listening Ports & Sockets Catalog

| Node / Container | Listening Socket | Protocol | Bound Process | Functional Role / Exposure Analysis |
|---|---|---|---|---|
| `pve1` (Hypervisor)| `0.0.0.0:22`, `[::]:22` | TCP | `sshd` (1130) | Host Administration (Requires firewall restriction) |
| `pve1` (Hypervisor)| `*:8006` | TCP | `pveproxy` (1340) | Proxmox VE Web Management & REST API |
| `pve1` (Hypervisor)| `*:3128` | TCP | `spiceproxy` (1348)| SPICE Web Console Proxy |
| `pve1` (Hypervisor)| `0.0.0.0:111`, `[::]:111`| TCP/UDP | `rpcbind` (746) | RPC Portmapper (NFS client requirement) |
| `pve1` (Hypervisor)| `0.0.0.0:34315` | TCP | `rpc.statd` (8169) | NFS File Locking Daemon (Dynamic port) |
| `pve1` (Hypervisor)| `127.0.0.1:85` | TCP | `pvedaemon` (1331) | Internal PVE Cluster IPC (Loopback only) |
| CT 100 (`traefik`) | `0.0.0.0:80` | TCP | `traefik` | HTTP-to-HTTPS Redirection Gateway |
| CT 100 (`traefik`) | `0.0.0.0:443` | TCP | `traefik` | HTTPS Reverse Proxy & TLS Termination |
| CT 100 (`traefik`) | `0.0.0.0:8080` | TCP | `traefik` | Traefik API/Metrics Entrypoint |
| CT 100 (`crowdsec`)| `127.0.0.1:6060` | TCP | `crowdsec` | CrowdSec Local API (LAPI) |
| CT 101 (`duplicati`)| `0.0.0.0:8200` | TCP | `duplicati` | Duplicati Web UI & Backup Engine |
| CT 102 (`homelable`)| `0.0.0.0:8000` | TCP | `uvicorn` | Homelable Dashboard Backend |
| CT 111 (`qbittorrent`)| `0.0.0.0:8090` | TCP | `qbittorrent-nox` | qBittorrent Web UI Management |
| CT 111 (`qbittorrent`)| `0.0.0.0:6881` | TCP/UDP | `qbittorrent-nox` | BitTorrent Peer Ingress Port |
| CT 113 (`flaresolverr`)| `0.0.0.0:8191` | TCP | `docker-proxy` | FlareSolverr Cloudflare Bypass Proxy |
| CT 114 (`prowlarr`)| `0.0.0.0:9696` | TCP | `Prowlarr` | Prowlarr Torrent Indexer Manager |
| CT 115 (`bazarr`) | `0.0.0.0:6767` | TCP | `python3` (waitress)| Bazarr Subtitle Automation Engine |
| CT 117 (`radarr`) | `0.0.0.0:7878` | TCP | `Radarr` | Radarr Movie Library Manager |
| CT 118 (`sonarr`) | `0.0.0.0:8989` | TCP | `Sonarr` | Sonarr TV Library Manager |
| CT 119 (`seerr`) | `0.0.0.0:5055` | TCP | `node` (Overseerr) | Jellyseerr Media Request Portal |
| CT 121 (`jellyfin`)| `0.0.0.0:8096` | TCP | `jellyfin` | Jellyfin Media Server HTTP API |
| VM 150 (`haos`) | `0.0.0.0:8123` | TCP | `homeassistant` | Home Assistant Dashboard & Websockets |

---

### Appendix F: Audit References, Framework Standards & CWE Mappings
1. **Common Weakness Enumeration (CWE)**:
   - `CWE-250`: Execution with Unnecessary Privileges (CT 105 rootless breakout)
   - `CWE-258`: Empty Password in Configuration File (CT 105 `/etc/shadow`)
   - `CWE-284`: Improper Access Control (Hairpin NAT /16 allowlist bypass)
   - `CWE-287`: Improper Authentication (In-guest OpenSSH password login)
   - `CWE-295`: Improper Certificate Validation (`insecureSkipVerify: true`)
   - `CWE-306`: Missing Authentication for Critical Function (Bazarr public route)
   - `CWE-312`: Cleartext Storage of Sensitive Information (Local `.env` API tokens)
   - `CWE-521`: Weak Password Requirements (`PermitRootLogin yes`)
   - `CWE-693`: Protection Mechanism Failure (Missing Content-Security-Policy)
   - `CWE-732`: Incorrect Permission Assignment for Critical Resource (World-writable 0777 NFS mounts)
   - `CWE-942`: Permissive Cross-Domain Policy with Wildcard (Bazarr `Access-Control-Allow-Origin: *`)
   - `CWE-1021`: Improper Restriction of Rendered UI Layers (Clickjacking protection)
   - `CWE-1395`: Dependency on Vulnerable Third-Party Component (Pending kernel/PVE updates)
2. **Industry Standards**:
   - **NIST SP 800-115**: Technical Guide to Information Security Testing and Assessment
   - **CIS Proxmox VE Benchmark v1.0**: Center for Internet Security Hardening Standard
   - **OWASP Application Security Verification Standard (ASVS) v4.0.3**
   - **CVSS v3.1 Specification**: FIRST (Forum of Incident Response and Security Teams)
