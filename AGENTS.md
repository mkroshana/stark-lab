<!-- BEGIN:llm-wiki -->
# Personal knowledge wiki

A knowledge base covering my projects, conventions and past decisions
lives at `D:\llm-wiki`.

**This project's page: `D:\llm-wiki\wiki\personal\homelab.md`** — read it before
making non-trivial changes. It records the stack, decisions already made,
and what is still open.

Search the wiki before asking me something it may already answer:

```bash
python D:\llm-wiki\tools\wikisearch.py "<query>"
```

How I expect you to work is recorded in
`D:\llm-wiki\wiki\conventions\` — most importantly: propose a one-line
commit message after substantive changes, plan before large ones, change only
what was asked, and verify rather than assert.

Do **not** write to the wiki from here. File new knowledge by opening a session
in `D:\llm-wiki`.
<!-- END:llm-wiki -->

# Proxmox & LXC Update Pipeline

All LXC containers on `pve1` (`10.10.10.31`) were provisioned via Proxmox VE Community Scripts. When asked to update the homelab or individual containers, work **one guest at a time** and strictly follow this 5-step pipeline:

## 1. Pre-Update Audit
Before modifying any host or container, inspect and report:
- Current application version and active systemd units (`systemctl list-units --type=service --state=running`).
- Pending OS package upgrades (`apt-get update && apt list --upgradable`).
- What `/bin/update` (Community Script entrypoint) will execute, checking for major version jumps or breaking changes.

## 2. Direct ZFS Snapshot
Always create a native ZFS dataset snapshot from the Proxmox host (`root@10.10.10.31`) before running any update:
```bash
# Proxmox Host
ssh root@10.10.10.31 "zfs snapshot rpool/ROOT/pve-1@pre-pve-upgrade"

# LXC Container
ssh root@10.10.10.31 "zfs snapshot rpool/data/subvol-<id>-disk-0@pre-<name>-update"
```
- **Bind-Mount Gotcha:** Do **not** use `pct snapshot <id>`. Proxmox refuses to snapshot containers that have host directory bind mounts (`mp0`, `mp1`, etc., such as NFS media mounts on `111`, `115`, `117`, `118`, `120`, `121`) with `snapshot feature is not available`. Direct ZFS snapshots on `rpool/data/subvol-<id>-disk-0` are instantaneous and bypass this restriction.

## 3. Application Update
Run the Community Scripts update mechanism inside the container:
```bash
ssh root@10.10.10.31 "pct exec <id> -- /bin/update"
```
- **Jellyfin (`CT 121`) Caution:** Major Jellyfin upgrades (e.g., `10.11.x` to `12.0+`) perform irreversible SQLite migrations and can break `File Transformation`, `Media Bar`, `Home Screen Sections`, and custom CSS themes. Always verify plugin/theme compatibility before upgrading Jellyfin, or hold/pin the package version via `apt`.
- **Built-in Updaters:** Some containers (`CT 105` `unifi-os-server`, `CT 117` `radarr`, `CT 118` `sonarr`) use built-in updaters (`uosserver-updater` or internal `.NET` updaters); `/bin/update` will either delegate to them or report that the built-in updater should be used.
- **Home Assistant OS (`VM 150`):** `haos` is a QEMU virtual machine appliance. Its OS, Supervisor, and Core updates are managed exclusively via the Home Assistant Web UI, never via host shell scripts.

## 4. Base OS Upgrade & Cache Cleanup
Community Script `update` often only updates the target application binary. Always follow up with a non-interactive Debian/Ubuntu `dist-upgrade` and cache purge so `dpkg` conffile prompts never hang the session:
```bash
ssh root@10.10.10.31 "pct exec <id> -- apt-get -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold dist-upgrade && pct exec <id> -- apt-get -y autoremove && pct exec <id> -- apt-get clean"
```

## 5. Post-Update Verification
Verify rather than assert:
- Confirm systemd services (`systemctl is-active <service>`) and container runtimes (`docker ps` / `podman ps`) are `active` and `healthy`.
- Check the local HTTP endpoint status code (`curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:<port>`).
- **Stopped Containers:** When updating stopped containers (`105`, `116`, `120`, `140`, `141`, `201`), boot them (`pct start <id>`), run steps 1–5, verify the service responds, and shut them back down (`pct stop <id>`).

---

# Estate Inventory & Baseline (2026-09-13 Audit)

## Hypervisor Host
| Host | IP | OS / PVE Version | ZFS Snapshot | Status |
|---|---|---|---|---|
| `pve1` | `10.10.10.31` | Proxmox VE `8.3.4` (`pve-manager 9.2.18`, kernel `7.0.14-16`) | `rpool/ROOT/pve-1@pre-pve-upgrade` | Active |

## Active LXC Containers
| CT ID | Hostname | OS | Baseline Application Version | Local Port / Check | ZFS Snapshot |
|---|---|---|---|---|---|
| `100` | `traefik` | Debian 12 | Traefik `3.7.13`, CrowdSec `1.8.1` | `80`/`443`, Bouncer `127.0.0.1:6060` | `subvol-100-disk-0@pre-traefik-update` |
| `101` | `duplicati` | Debian 12 | Duplicati `2.4.0.0` | `8200` (`200 OK`) | `subvol-101-disk-0@pre-duplicati-update` |
| `102` | `homelable` | Debian 12 | Homelable `3.4.2` (FastAPI / Uvicorn) | `8000/docs` (`200 OK`) | — |
| `103` | `tailscale` | Debian 12 | Tailscale `1.102.4` | `tailscaled` active | `subvol-103-disk-0@pre-tailscale-update` |
| `111` | `qbittorrent` | Debian 12 | qBittorrent `5.2.3` (`libtorrent 2.0.14`) | `8090` (`200 OK`) | `subvol-111-disk-0@pre-qbit-update` |
| `113` | `flaresolverr` | Debian 12 | FlareSolverr `3.5.0` (Docker) | `8191` (`200 OK`) | `subvol-113-disk-0@pre-flaresolverr-update` |
| `114` | `prowlarr` | Debian 12 | Prowlarr `2.5.2.5491` | `9696` (`200 OK`) | `subvol-114-disk-0@pre-prowlarr-update` |
| `115` | `bazarr` | Debian 12 | Bazarr `1.6.0` (data in `/var/lib/bazarr`) | `6767` (`200 OK`) | `subvol-115-disk-0@pre-bazarr-update` |
| `117` | `radarr` | Debian 12 | Radarr `6.3.0.10514` | `7878` (`200 OK`) | `subvol-117-disk-0@pre-radarr-update` |
| `118` | `sonarr` | Debian 12 | Sonarr `4.0.19.2979` | `8989` (`200 OK`) | `subvol-118-disk-0@pre-sonarr-update` |
| `119` | `seerr` | Debian 12 | Seerr `3.4.1` (Node 22 / pnpm 10) | `5055` (`307 Redirect`) | `subvol-119-disk-0@pre-seerr-update` |
| `121` | `jellyfin` | Ubuntu 24.04 | Jellyfin `12.0.0` | `8096/System/Info/Public` (`200 OK`) | `subvol-121-disk-0@pre-jellyfin-12` |

## Stopped (On-Demand) LXC Containers
| CT ID | Hostname | OS | Baseline Application Version | Local Port / Check | ZFS Snapshot |
|---|---|---|---|---|---|
| `105` | `unifi-os-server` | Debian 13 | UniFi OS Server (rootless Podman `uosserver`) | `11443` / `8080`, `uosserver` active | `subvol-105-disk-0@pre-unifi-os-server-update` |
| `116` | `dispatcharr` | Debian 13 | Dispatcharr `0.30.0` (Node 24, uv 0.12, Comskip V0.83, PG 16.15) | `9191` (`200 OK`) | `subvol-116-disk-0@pre-dispatcharr-update` |
| `120` | `plex` | Ubuntu 24.04 | Plex Media Server `1.42.2.10156` | `32400/identity` (`200 OK`) | `subvol-120-disk-0@pre-plex-update` |
| `140` | `pterodactyl-panel` | Debian 13 | Pterodactyl Panel `1.15.1` (PHP 8.4, MariaDB 11.8, Redis 8.0) | `80` (`200 OK`) | `subvol-140-disk-0@pre-pterodactyl-panel-update` |
| `141` | `pterodactyl-wings` | Debian 13 | Pterodactyl Wings `1.13.3` (Docker CE `29.8.0`) | `wings version` / `docker ps` | `subvol-141-disk-0@pre-pterodactyl-wings-update` |
| `201` | `n8n` | Debian 13 | n8n `2.38.7` (Node 24, npm 12) | `5678/healthz` (`200 OK`) | `subvol-201-disk-0@pre-n8n-update` |

## Virtual Machines
| VM ID | Name | Type | Update Mechanism | Status |
|---|---|---|---|---|
| `150` | `haos` | QEMU VM (`2048 MB`, `32 GB`) | Managed via Home Assistant Web UI | Running |

