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
  - **Theme after any Jellyfin update:** the NeutralFin theme lives in `jellyfin-web`'s own `themes/dark/theme.css`, which a package update resets to stock. After updating `CT 121`, run `jellyfin/themes/ship.sh` from this repo (it detects the stock file, asks once and redeploys), or `jellyfin/themes/deploy.sh --live`, and check that `dpkg -V jellyfin-web` lists only that file. See `jellyfin/themes/README.md`.
- **Built-in Updaters:** Some containers (`CT 117` `radarr`, `CT 118` `sonarr`) use built-in `.NET` updaters; `/bin/update` will either delegate to them or report that the built-in updater should be used.
- **Home Assistant OS (`VM 150`):** `haos` is a QEMU virtual machine appliance. Its OS, Supervisor, and Core updates are managed exclusively via the Home Assistant Web UI, never via host shell scripts.
- **jpm-n8n (`CT 210`, Work — JobProMax):** Migrated from Azure VM (`n8n`, `20.171.25.77`) on 2026-11-19. Runs n8n natively with `/opt/n8n.env` (`N8N_USER_FOLDER=/root`, `N8N_PROXY_HOPS=1`, `N8N_SECURE_COOKIE=true`, `n8n.jobpromax.it.com`). `/bin/update` preserves `/opt/n8n.env`. Publicly routed through CT 100 Traefik via `letsencrypt-http` (HTTP-01, `/etc/traefik/ssl/acme-http.json`) and CNAME → `ddns.starklab.mkroshana.com` (DNS-only). Pre-migration Azure archive saved on `pve1` at `/root/backups/azure-n8n-2026-11-19.tar.gz`.
- **jpm-mail / ArcReach (`CT 211`, Work — TheJobsHelpers / JobProMax):** Migrated from Azure App Service (`arcreach-app`) + Azure PostgreSQL (`arcreach-db`) on 2026-11-19. No Community Script `/bin/update`; runs Next.js `15.5.26` (`azure` branch in `/opt/arcreach`) + PostgreSQL `16.16` (PGDG, UTF-8, `127.0.0.1:5432`) as unprivileged user `arcreach` with `/etc/arcreach/arcreach.env` (`0640 root:arcreach`). Deploy updates with `/usr/local/bin/arcreach-deploy` (checks `prisma migrate diff` before building; pass `--push-schema` when schema changes), or automatically via GitHub Actions on push to `azure` (after `test` + `build` pass, CI posts an HMAC-SHA256 signed request with 5-min replay check to `https://arcreach.thejobshelpers.com/_hooks/deploy` → `arcreach-deploy-hook.service` on CT 211 `:9000`, secret in `/etc/arcreach/deploy-hook.env`). Publicly routed through CT 100 Traefik via independent `letsencrypt-http` certs for `arcreach.thejobshelpers.com` and `mail.jobpromax.com` (split middlewares: tracking/unsubscribe and Event Grid `/api/webhook` bypass CrowdSec with `1000/min` burst `500`). Nightly `pg_dump -Fc` runs from `pve1` via `arcreach-pg-backup.timer` (`03:15`) to `/mnt/pve/Backups/ArcReach/` (14-day retention, no NFS bind mount inside CT 211). Pre-migration Azure dump saved at `/root/backups/azure-arcreach-2026-11-19.dump` and `/mnt/pve/Backups/ArcReach/azure-pre-migration-2026-11-19.dump`.
- **job-extractor (`CT 212`, Work — JobProMax / TheJobsHelpers):** Migrated from Azure VM (`new-job-extraction`, `20.150.143.151`) on 2026-11-20. No Community Script `/bin/update`; Ubuntu 24.04 with Python `3.12.3` venv (`spacy 3.7.2`, `en_core_web_sm 3.7.1`, `pydantic 2.5.3`, `pymongo 4.6.1`, `opensearch-py 2.4.2`) in `/opt/job-extractor` (`main` branch of `TheJobHelpers/job-extraction` via read-only deploy key `/home/jobextractor/.ssh/id_ed25519`), owned by unprivileged user `jobextractor` with `/opt/job-extractor/.env` (`0600`, `MEMORY_LIMIT_MB=3000`) and `geocoding_cache.json` (120,531 entries). Deploy updates with `/usr/local/bin/job-extractor-deploy`, or automatically via GitHub Actions on push to `main` (after `verify` passes, CI posts an HMAC-SHA256 signed request with 5-min replay check to `https://ddns.starklab.mkroshana.com/_hooks/job-extractor-deploy` → `job-extractor-deploy-hook.service` on CT 212 `:9000`, secret in `/etc/job-extractor-deploy-hook.env`). Runs outbound daily cron at `0 2 * * *` UTC (`07:30 Asia/Colombo`) via `cron_runner.sh` → `runner.py` → `main.py` (`greenhouse,ashby,smartrecruiters,workday`), logging to `/opt/job-extractor/logs/cron.log` (rotated daily via `/etc/logrotate.d/job-extractor`) and Better Stack / Logtail. Dynamic home WAN IP is auto-synced every 5 minutes (`azure-fw-sync.timer` + pre-cron hook `/usr/local/sbin/azure-fw-sync.sh` using scoped SP credentials in `/etc/job-extractor-fw.env` `0600`) to `jpm-main-mongodb` (`starklab-homelab-temp-2026-11-20`) and `jpm-search-prod-nsg` (`allow-opensearch-homelab-temp`, prio 320, port 9200). Pre-migration Azure archive saved on `pve1` at `/root/backups/azure-job-extraction-2026-11-20.tar.gz`.
- **thejobhelpers-vps (`CT 213`, Work — TheJobHelpers lead extraction):** Migrated from Azure VM `THEJOBHELPERS-VPS` (`TJH_IT`, `172.172.195.192`) on 2026-11-20. No Community Script `/bin/update`; update with plain `apt`. A reproduction of the VM, not a fresh install:
  - **OS:** Ubuntu `22.04.5` from the linuxcontainers.org rootfs (`pveam` no longer lists 22.04), `UTC`, `LANG=C.UTF-8`. Every package the VM had, except kernel, boot, Azure, snap and hardware ones.
  - **Accounts:** same UIDs, groups, password hashes and sudo as the VM — `tjhvps` `1000` (`NOPASSWD`), `chamaru` `1001`, `rusiru` `1002` (home `/mnt/nvme3/home/rusiru`), `pipline` `1003`; `postgres` `114:124`, `docker` gid `125`. `sshd` settings and host keys copied (password and key login, X11).
  - **PostgreSQL `14.24`:** cluster `main` `127.0.0.1:5432` (`leadgen_api`), cluster `contacts` `*:5433` (`contacts`, 72M `profiles`, data in `/mnt/nvme1/postgres-db/pgdata`).
  - **Docker `29.1.3`:** classic `overlay2` store (`/etc/docker/daemon.json` `containerd-snapshotter: false`) so image IDs match the VM. `qdrant` (`:6333`); `recruiting-app` (created, never started, as on the VM); `4166e2519bbb_recruiting-app` (restart-loops on a missing `bs4`, as on the VM).
  - **Data disks:** raw images on Unraid NFS storage `LeadData` (`spinning-disks/LeadData`: zstd, `recordsize=64K`, `quota=600G`, export `sync`, `pve1` only) — `mp0` 350G at `/home`, `mp1` 200G at `/mnt/nvme1`, both `backup=0`. Daily snapshots `@auto-daily-*`, 7 kept (Unraid User Scripts `leaddata-snapshots`, `02:30`). `ct213-fstrim.timer` on `pve1` (Sunday 04:30) runs `pct fstrim 213`, which returns deleted space to Unraid.
  - **Network:** isolated bridge `vmbr1`, `10.99.0.213/24` — internet only, no LAN, `pve1`, Unraid or Tailscale range (`pve1/vmbr1/`). SSH from the LAN: `ssh -J root@10.10.10.31 <user>@10.99.0.213`.
  - **Remote SSH (2026-11-24):** `leads-mkssh.thejobhelpers.com` (zone `thejobhelpers.com`, TJH's main domain; `thejobshelpers.com` with an "s" is a bought alternative; proxied CNAME) → Cloudflare Tunnel `tjh-ssh` (`810b76ca-7a6e-4f70-8038-e4a511f793fc`, remotely managed, account `Thejobhelperscom`) → `ssh://localhost:22`. `cloudflared` runs inside CT 213 (`cloudflared.service`, Cloudflare apt repo; outbound only, so no router port and `vmbr1` is unchanged). Gated by Access app **TJH SSH (CT 213)** (team `tjh-jpm`): allow-list of 4 emails, one-time email PIN or Google Workspace, 24 h session. Add or remove people in that app's policy. The tunnel token lives in the systemd unit, readable by CT 213's sudo users; it can only run the connector, not change who is allowed. Client setup: `pve1/ct213/REMOTE-SSH.md`. Tailscale was dropped for this.
  - **Start:** `onboot: 0`; `ct213-wait-start.service` on `pve1` starts it once `LeadData` is active, waiting up to 30 min for Unraid (`pve1/ct213/`).
  - **Cautions:** `pct snapshot` does not work (NFS raw images) — snapshot `rpool/data/subvol-213-disk-0` for the system disk and `spinning-disks/LeadData` on Unraid for the data. Stop CT 213 before any Unraid or NFS maintenance.
  - **Azure VM:** kept running for rollback with Docker and PostgreSQL stopped and disabled; temporary user `migrate` still on it. Do not deallocate it before deleting — that wipes `/mnt/nvme1`.

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

### Work / Commercial LXC Containers (JobProMax & TheJobsHelpers)
Non-personal work workloads hosted on `pve1`. Numbering convention: **`210+`** (`10.10.10.21x` on `vmbr0`, CT ID == last IP octet) for self-managed work services behind Traefik. Exception: `CT 213` is isolated on `vmbr1` at `10.99.0.213`, because other people have sudo inside it.

| CT ID | Hostname | OS | Baseline Application Version | Local Port / Check | ZFS Snapshot |
|---|---|---|---|---|---|
| `210` | `jpm-n8n` | Debian 13 | JobProMax n8n `2.45.7` (Node 24, npm `12.2.1`, public `n8n.jobpromax.it.com`, LAN `jpm-n8n.local.starklab.mkroshana.com`) | `5678/healthz` (`200 OK`) | `subvol-210-disk-0@pre-jpm-n8n-migrate` |
| `211` | `jpm-mail` | Debian 13 | ArcReach `Next.js 15.5.26` / Prisma `6.19.3` (Node `22.23.5`, PG `16.16`, public `arcreach.thejobshelpers.com` & `mail.jobpromax.com`, LAN `jpm-mail.local.starklab.mkroshana.com` / `arcreach.local.starklab.mkroshana.com`) | `3000/login` (`200 OK`) | `subvol-211-disk-0@pre-arcreach-migrate` |
| `212` | `job-extractor` | Ubuntu 24.04 | Job Extractor (`Python 3.12.3`, `spacy 3.7.2`; outbound worker, cron `0 2 * * *` UTC) | `cron` & `job-extractor-deploy-hook` (`:9000`) active | `subvol-212-disk-0@pre-job-extractor-migrate` |
| `213` | `thejobhelpers-vps` | Ubuntu 22.04 | TheJobHelpers lead extraction (PG `14.24` `:5432`/`:5433`, Docker `29.1.3` Qdrant; isolated `vmbr1` `10.99.0.213`; data on Unraid `LeadData`) | `pg_lsclusters` online, `6333/collections` (`200 OK`) | `subvol-213-disk-0@post-tjh-migrate` |

- **External / Work Domain TLS (`CT 100` Traefik):** Domains outside `mkroshana.com` (e.g., `n8n.jobpromax.it.com`) use the `letsencrypt-http` ACME HTTP-01 resolver on port 80 (stored separately in `/etc/traefik/ssl/acme-http.json`) with a DNS-only `CNAME` to `ddns.starklab.mkroshana.com`.

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

## NFS and Power Safety (Changed 2026-11-14)
Two NFS-related outages led to these changes. On 2026-11-11 the host wedged: a lazy unmount of Drive and Vault on 2026-11-05 had left a kernel flush worker stuck for six days, and an 18 GB download then could not be written out; soft reboots hung and it needed the power button. On 2026-11-13 a power cut put the UPS on battery at 13:00; Unraid shut itself down at 13:07, but `pve1` kept running against its now-dead NFS mounts until the battery ran out at about 13:47.

- **Never lazy-unmount (`umount -l`) an NFS share on `pve1`.** To recover a stale or hung share, stop the containers that bind-mount it first, then unmount normally and run `pvesm activate-storage <name>`, or reboot. If writes are stuck, a reboot may still need the power button.

| Where | Change | Reason | Undo |
|---|---|---|---|
| `pve1` | `pve-nfs-watchdog` timer disabled; script removed | It could only lazy-unmount shares, and its variables had been stripped so it never worked | Copies in `/root/disabled-2026-11-14/` |
| `pve1` | `vm.dirty_background_bytes=64 MB`, `vm.dirty_bytes=256 MB` in `/etc/sysctl.d/90-nfs-writeback.conf` (was 10% / 20% of RAM, about 2.3 / 4.6 GB) | Stops GBs of unwritten NFS data piling up in RAM | Delete the file and reboot |
| `111` `qbittorrent` | Disk IO type **POSIX-compliant** (`Session\DiskIOType=Posix`, API value `2`; was Default, memory-mapped) | Memory-mapped writes are not recommended on network storage | `qBittorrent.conf.bak-2026-11-14` |
| `pve1` | NUT client **active** (`MODE=netclient`): `slaveups` secondary of `apc-ups@10.10.10.30`; `upssched` runs `upsmon -c fsd` 180 s after the UPS goes on battery (60 s until 2026-11-20), cancelled if mains returns first. Touch `/etc/nut/upssched-dryrun` to test without shutting down | So `pve1` is off before Unraid stops NFS, while riding out short cuts | `nut.conf.bak-2026-11-14`, `upsmon.conf.bak-2026-11-14`, `upssched.conf.bak-2026-11-14` (60 s) and `upssched.conf.bak-2026-11-20`, `upssched-cmd.bak-2026-11-20` in `/etc/nut/` |
| Unraid | NUT plugin shutdown timer `TIMEOUT="480"` in `/boot/config/plugins/nut-dw/nut-dw.cfg` (was `360`); `nut-notify` reads it at each on-battery event | Keeps about 3 min between `pve1` being off (about 5 min) and Unraid stopping NFS | `nut-dw.cfg.bak-2026-11-20` |

- **NUT verified 2026-11-14 (dry run):** Unraid lists `10.10.10.31` as a logged-in client; a simulated on-battery event fired the trigger after 61 s; on-battery followed by mains-back after 5 s fired nothing.
- **First real power cut, 2026-11-20:** on battery at 09:11:59; `pve1` started its shutdown about 60 s later, stopped all guests cleanly by 09:14:11 and was off by 09:14:57. Mains returned at 09:13:44, so Unraid cancelled its own shutdown and `pve1` stayed off until powered on by hand at 10:17 (Wake-on-LAN from the LAN did not wake it). On boot every guest, including `CT 213` via `ct213-wait-start`, came back with no filesystem repair.
- **Second power cut, 2026-11-20:** on battery 16:58:49 to 17:00:14 (about 1.5 min); `pve1` again shut down cleanly after 60 s and stayed off until powered on by hand. Both cuts that day were shorter than 2 min, so the `pve1` delay was raised to 180 s and Unraid's to 480 s. The UPS (Smart-UPS 750, about 30% load) reported about 17 min runtime. Dry run the same day: a simulated on-battery event at 17:09:52 fired the trigger at 17:12:52 (180 s).
- **Short outages:** cuts shorter than 3 min now pass with nothing shutting down. If mains returns after `pve1` has shut down but before the UPS battery runs out, the UPS never drops power, so `pve1` stays off until powered on by hand. Unraid's "Turn off UPS after shutdown" (currently off) would make both machines boot themselves when mains returns.
- **Unraid pool:** `spinning-disks` (2-disk raidz1) is 94% full, 889 GB free of 14.5 TB. Downloads and Movies live on it, and ZFS writes slow down sharply above about 90%. qBittorrent removes a torrent and its files at ratio 1, with no seeding-time limit.

## Health-Check Fixes (Changed 2026-11-22)
Found in the 2026-11-21 health check after the Azure migrations. Keep them through updates.

| Where | Change | Reason | Undo |
|---|---|---|---|
| `113` `flaresolverr` | Memory `3072` MB (was `2048`; swap `512` unchanged) | Each request opens its own Chromium, held for the full 60 s while a Cloudflare challenge fails. Overlapping `uindex.org` requests hit the 2 GiB limit 1,383 times from 2026-11-20, and Chromium was OOM-killed on 2026-11-21 at 21:57 | `pct set 113 -memory 2048` |
| `pve1` | `/etc/zfs/zpool.cache` rebuilt from the live pool (`zpool set cachefile=/etc/zfs/zpool.cache rpool`); lists only `rpool` | It still listed `localshare`, a pool on a HGST 500 GB laptop drive (`ata-HGST_HTS725050A7E630`) removed without `zpool export`, so `zfs-import-cache.service` failed at every boot | `/etc/zfs/zpool.cache.bak-2026-11-22`; snapshot `rpool/ROOT/pve-1@pre-zpool-cache-fix` |
| `210` `jpm-n8n`, `211` `jpm-mail` | `systemd-networkd.socket` and `systemd-networkd.service` disabled (`systemd-network-generator` with them) | ifupdown (`/etc/network/interfaces`) runs `eth0`. networkd managed no links, so `apt-daily` waited 30 s on `systemd-networkd-wait-online` and logged a timeout about 3 times a day | `pct exec <id> -- systemctl enable --now systemd-networkd.socket systemd-networkd.service systemd-network-generator.service`; snapshot `subvol-<id>-disk-0@pre-networkd-disable` |

- **Initramfs:** the boot image still holds the old cache file. This is harmless, because it imports only `rpool`, by name (`root=ZFS=rpool/ROOT/pve-1`). It was not rebuilt by hand, so the ESP is untouched; the next kernel or ZFS update rebuilds it with the clean file.
- **If the HGST drive comes back:** `localshare` no longer imports at boot. Run `zpool import localshare` once to add it back to the cache.
- **Other Debian 13 CTs:** `100`–`119`, `130`, `200` and `201` have the same networkd/ifupdown overlap and apt timeouts, and are unchanged. `121`, `212` and `213` are run by networkd and are fine. `103` and `130` have extra interfaces; check them before applying the change there.
- **Not yet verified:** a reboot of `pve1` (expect `systemctl --failed` to be empty) and of `210`/`211` (expect networkd to stay inactive). For CT 113, `memory.events` `max` was 1,383 at the change; if it stops climbing, the fix held.

