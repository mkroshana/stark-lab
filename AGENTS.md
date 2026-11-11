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
Always refresh the native ZFS dataset snapshot from the Proxmox host (`root@10.10.10.31`) before running any update:
```bash
# Proxmox Host
ssh root@10.10.10.31 "zfs destroy rpool/ROOT/pve-1@pre-pve-upgrade 2>/dev/null; zfs snapshot rpool/ROOT/pve-1@pre-pve-upgrade"

# LXC Container
ssh root@10.10.10.31 "zfs destroy rpool/data/subvol-<id>-disk-0@pre-<name>-update 2>/dev/null; zfs snapshot rpool/data/subvol-<id>-disk-0@pre-<name>-update"
```
- **Bind-Mount Gotcha:** Do **not** use `pct snapshot <id>`. Proxmox refuses to snapshot containers that have host directory bind mounts (`mp0`, `mp1`, etc., such as NFS media/drive mounts on `110`, `111`, `115`, `117`, `118`, `120`, `121`) with `snapshot feature is not available`. Direct ZFS snapshots on `rpool/data/subvol-<id>-disk-0` are instantaneous and bypass this restriction.

## 3. Application Update
Run the Community Scripts update mechanism inside the container:
```bash
ssh root@10.10.10.31 "pct exec <id> -- /bin/update"
```
- **Hermes Agent (`CT 200`) Caution:** Do **not** run `/bin/update` on `CT 200`. Upstream `PR #18203` in the Community Script blocks on an interactive `confirm_external_installer` prompt and rewrites `hermes-dashboard.service` from `--host 0.0.0.0 --port 9119` to `--host 127.0.0.1 --port 9119`, which breaks LAN/Traefik routing. Update Hermes directly as user `hermes` and restart the system unit:
  ```bash
  ssh root@10.10.10.31 "pct exec 200 -- runuser -l hermes -c 'set -a; source /etc/default/hermes; set +a; /home/hermes/.local/bin/hermes update --yes' && pct exec 200 -- systemctl restart hermes-dashboard"
  ```
- **Jellyfin (`CT 121`) Caution:** Major Jellyfin upgrades (e.g., `10.11.x` to `12.0+`) perform irreversible SQLite migrations and can break `File Transformation`, `Media Bar`, `Home Screen Sections`, and custom CSS themes. Always verify plugin/theme compatibility before upgrading Jellyfin, or hold/pin the package version via `apt`.
- **Built-in Updaters:** Some containers (`CT 117` `radarr`, `CT 118` `sonarr`) use built-in `.NET` updaters; `/bin/update` will either delegate to them or report that the built-in updater should be used.
- **Home Assistant OS (`VM 150`):** `haos` is a QEMU virtual machine appliance. Its OS, Supervisor, and Core updates are managed exclusively via the Home Assistant Web UI, never via host shell scripts.

## 4. Base OS Upgrade & Cache Cleanup
Community Script `update` often only updates the target application binary. Always follow up with a non-interactive Debian/Ubuntu `dist-upgrade` and cache purge so `dpkg` conffile prompts never hang the session:
```bash
ssh root@10.10.10.31 "pct exec <id> -- env DEBIAN_FRONTEND=noninteractive apt-get -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold dist-upgrade && pct exec <id> -- apt-get -y autoremove && pct exec <id> -- apt-get clean"
```

## 5. Post-Update Verification
Verify rather than assert:
- Confirm systemd services (`systemctl is-active <service>`) and container runtimes (`docker ps` / `podman ps`) are `active` and `healthy`.
- Check the local HTTP endpoint status code (`curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:<port>`).
- **Stopped Containers:** When updating stopped containers (`120`, `140`, `141`, `202`), boot them (`pct start <id>`), run steps 1–5, verify the service responds, and shut them back down (`pct stop <id>`).

---

# Estate Inventory & Baseline (2026-10-30 Audit)

## Hypervisor Host
| Host | IP | OS / PVE Version | ZFS Snapshot | Status |
|---|---|---|---|---|
| `pve1` | `10.10.10.31` | Proxmox VE `9.2.0` (`pve-manager 9.2.24`, kernel `7.0.14-26-pve`) | `rpool/ROOT/pve-1@pre-pve-upgrade` | Active |

## Active LXC Containers
| CT ID | Hostname | OS | Baseline Application Version | Local Port / Check | ZFS Snapshot |
|---|---|---|---|---|---|
| `100` | `traefik` | Debian 13 | Traefik `3.7.17`, CrowdSec `1.8.2` | `80`/`443`, Prometheus `8080`, CrowdSec `6060` | `subvol-100-disk-0@pre-traefik-update` |
| `101` | `duplicati` | Debian 13 | Duplicati `2.4.1.0` | `8200` (`200 OK`) | `subvol-101-disk-0@pre-duplicati-update` |
| `102` | `homelable` | Debian 13 | Homelable `3.6.0` (FastAPI / Uvicorn) | `8000/docs` (`200 OK`) | `subvol-102-disk-0@pre-homelable-update` |
| `103` | `tailscale` | Debian 13 | Tailscale `1.104.4` | `tailscaled` active | `subvol-103-disk-0@pre-tailscale-update` |
| `110` | `cloudreve` | Debian 13 | Cloudreve `4.19.1` | `5212` (`200 OK`) | `subvol-110-disk-0@pre-cloudreve-update` |
| `111` | `qbittorrent` | Debian 13 | qBittorrent `5.3.0` (`libtorrent 2.1.2`) | `8090` (`200 OK`) | `subvol-111-disk-0@pre-qbit-update` |
| `113` | `flaresolverr` | Debian 13 | FlareSolverr `3.5.2` (Docker `29.9.2`, Chrome 156) | `8191` (`200 OK`) | `subvol-113-disk-0@pre-flaresolverr-update` |
| `114` | `prowlarr` | Debian 13 | Prowlarr `2.7.0.5723` | `9696` (`200 OK`) | `subvol-114-disk-0@pre-prowlarr-update` |
| `115` | `bazarr` | Debian 13 | Bazarr `1.6.2` (`uv 0.13.6`, Python 3.12) | `6767` (`200 OK`) | `subvol-115-disk-0@pre-bazarr-update` |
| `116` | `dispatcharr` | Debian 13 | Dispatcharr `0.33.0` (Node 24, `uv 0.13.6`, Comskip V0.83) | `9191` (`200 OK`) | `subvol-116-disk-0@pre-dispatcharr-update` |
| `117` | `radarr` | Debian 13 | Radarr `6.4.4.10685` | `7878` (`200 OK`) | `subvol-117-disk-0@pre-radarr-update` |
| `118` | `sonarr` | Debian 13 | Sonarr `4.0.20.3014` | `8989` (`200 OK`) | `subvol-118-disk-0@pre-sonarr-update` |
| `119` | `seerr` | Debian 13 | Seerr `3.5.1` (Node 22 / pnpm 10) | `5055` (`307 Redirect`) | `subvol-119-disk-0@pre-seerr-update` |
| `121` | `jellyfin` | Ubuntu 24.04 | Jellyfin `12.4.0` | `8096/System/Info/Public` (`200 OK`) | `subvol-121-disk-0@pre-jellyfin-update` |
| `130` | `traefik-manager` | Debian 13 | Traefik Manager `1.15.5` (Docker `29.9.3`) | `5000` (`302 Redirect`) | `subvol-130-disk-0@pre-traefik-manager-update` |
| `200` | `hermesagent` | Debian 13 | Hermes Agent `v0.22.5+3003.gef35e8b` | `9119` (`302 Found`), Gateway `8642` | `subvol-200-disk-0@pre-hermesagent-update` |
| `201` | `n8n` | Debian 13 | n8n `2.45.7` (Node 24, npm `12.2.1`) | `5678/healthz` (`200 OK`) | `subvol-201-disk-0@pre-n8n-update` |

## Stopped (On-Demand) LXC Containers
| CT ID | Hostname | OS | Baseline Application Version | Local Port / Check | ZFS Snapshot |
|---|---|---|---|---|---|
| `120` | `plex` | Ubuntu 24.04 | Plex Media Server `1.43.5.11079-b3b13e506` | `32400/identity` (`200 OK`) | `subvol-120-disk-0@pre-plex-update` |
| `140` | `pterodactyl-panel` | Debian 13 | Pterodactyl Panel `1.15.2` (PHP `8.4.27`, MariaDB `11.8.6`, Redis `8.0.2`) | `80` (`200 OK`) | `subvol-140-disk-0@pre-pterodactyl-panel-update` |
| `141` | `pterodactyl-wings` | Debian 13 | Pterodactyl Wings `1.13.4` (Docker CE `29.9.2`, containerd `2.4.2`) | `wings version` / `docker ps` | `subvol-141-disk-0@pre-pterodactyl-wings-update` |
| `202` | `firecrawl` | Debian 13 | Firecrawl `2.11.0` (Node `22.23.4`, PG 17, RabbitMQ, Redis 8.0) | `3000` (`200 OK`), Playwright `3002` | `subvol-202-disk-0@pre-firecrawl-update` |

## Virtual Machines
| VM ID | Name | Type | Update Mechanism | Status |
|---|---|---|---|---|
| `150` | `haos` | QEMU VM (`6144 MB`, `32 GB`) | Managed via Home Assistant Web UI | Running |

## Media Pipeline Settings (Changed 2026-11-11)
Deliberate non-default settings. Keep them through updates. Changed after Intro Skipper's CPU-only scan of a 4K episode pegged all four `pve1` cores, and a new episode failed to play while Sonarr was still copying it into the library. The original files are saved next to each edited file as `*.bak-2026-11-11`.

| Guest | Setting | Value | Reason |
|---|---|---|---|
| `121` `jellyfin` | Intro Skipper `ProcessThreads` | `2` (was `0` = all cores) | The plugin has no GPU decoding, so this caps its CPU use |
| `121` `jellyfin` | Intro Skipper `MaxParallelism` | `1` (was `4`) | Scans one episode at a time instead of four |
| `121` `jellyfin` | Intro Skipper `ScanTimeoutSeconds` | `900` (was `300`) | 4K credits scans were being killed at 300 s with nothing saved |
| `121` `jellyfin` | Intro Skipper `AutoDetectIntros` | `false` (was `true`) | No scan the moment a file arrives; the nightly *Detect and Analyze Media Segments* task (about 00:00) does it instead |
| `121` `jellyfin` | `EnableRealtimeMonitor` on TV Shows and Movies | `false` (was `true`) | Jellyfin was listing files Sonarr was still copying |
| `118` `sonarr`, `117` `radarr` | Connect → Emby / Jellyfin | `10.10.10.121:8096`, Update Library on, notifications off | Tells Jellyfin to scan only after an import has finished |

- **Files:** `/var/lib/jellyfin/plugins/configurations/IntroSkipper.xml` and `/var/lib/jellyfin/root/default/{TV Shows,Movies}/options.xml` in `CT 121`.
- **Why imports copy:** `Downloads`, `TV-Shows` and `Movies` are separate Unraid NFS exports (`10.10.10.30`). A hardlink can't cross between them, so every import is a full network copy, about 2 minutes for a 4 GB file.
- **Side effect:** Files added outside Sonarr and Radarr appear only after Jellyfin's scheduled library scan, or a manual scan.
- **Not yet verified:** The first new episode or movie to appear through the Sonarr/Radarr connection.

