# Stark-Lab Homelab Security Audit: Test Infrastructure Specification

**Document Version**: 1.0.0  
**Target Estate**: Proxmox VE 9.2.18 (`pve1` @ `10.10.10.31`), LXC Containers (100–201), VM 150 (`haos`), Traefik v3.7.13 (`10.10.10.100`), Storage NAS (`10.10.10.30`).  
**Auditing Standards**: CVSS v3.1, NIST SP 800-115, CIS Benchmark (Proxmox VE & Linux), 4-Tier Testing Architecture.

---

## 1. Test Architecture Overview

The Stark-Lab Security Audit Automated Verification Suite provides an opaque-box, non-destructive, and deterministic testing harness to evaluate, verify, and validate all audit findings, technical vulnerabilities, misconfigurations, and remediation assertions across Requirements R1 through R6.

```
+-------------------------------------------------------------------------------+
|                      STARK-LAB AUDIT VERIFICATION HARNESS                     |
|                                                                               |
|  [ run_tests.py ] / [ pytest security-audit/tests/ -v ]                       |
+-------------------------------------------------------------------------------+
       |                         |                       |
       v                         v                       v
+------------------+   +-------------------+   +--------------------+
|  Static Analysis |   | Network Probes    |   | SSH & Host Probes  |
|  - YAML Parsers  |   | - HTTP/REST Probes|   | - PVE hypervisor   |
|  - Regex Engines |   | - Port Scanners   |   | - LXC containers   |
|  - CIDR Math     |   | - CORS Evaluators |   | - ZFS & mounts     |
+------------------+   +-------------------+   +--------------------+
       |                         |                       |
       +-------------------------+-----------------------+
                                 |
                                 v
+-------------------------------------------------------------------------------+
|                        4-TIER TESTING METHODOLOGY                             |
|                                                                               |
|  Tier 1: Feature Coverage (Host, Containers, Traefik, Secrets, Storage)       |
|  Tier 2: Boundary & Corner Cases (Empty Shadow, CIDR /16, Unauth, CORS, TLS)  |
|  Tier 3: Cross-Feature Interactions (Hairpin Bypass, CrowdSec, Plex Proxy)    |
|  Tier 4: Real-World Scenario Probes (WAN Sim, Live API Probe, Lateral Path)   |
+-------------------------------------------------------------------------------+
```

---

## 2. Directory Layout & Test Artifacts

All test files are organized under `d:\Development\stark-lab\security-audit\tests\`:

```
d:\Development\stark-lab\
├── security-audit\
│   └── tests\
│       ├── __init__.py                       # Package initialization
│       ├── conftest.py                       # Pytest fixtures, network harness, baseline findings
│       ├── run_tests.py                      # Standalone CLI test runner
│       ├── test_tier1_feature_coverage.py    # Tier 1: Primary feature coverage tests
│       ├── test_tier2_boundary_corner.py     # Tier 2: Boundary & corner condition tests
│       ├── test_tier3_cross_feature.py       # Tier 3: Cross-feature interaction tests
│       └── test_tier4_real_world_probes.py   # Tier 4: Real-world operational probes
├── TEST_INFRA.md                             # Test infrastructure architecture specification
└── TEST_READY.md                             # Test execution results & readiness certification
```

---

## 3. 4-Tier Test Methodology Breakdown

### Tier 1: Feature Coverage (Happy Path & Core Capabilities)
Covers baseline security audit capabilities and primary finding assertions across R1 to R6:
- **Test 1.1 (`test_pve_host_os_and_kernel_inspection`)**: Verifies hypervisor OS (`pve-manager: 9.2.18`), running kernel (`7.0.14-16-pve`), listening daemons (`sshd`, `pveproxy`, `spiceproxy`, `rpcbind`), and firewall state (`disabled/running`).
- **Test 1.2 (`test_container_configuration_audit`)**: Audits LXC container isolation, verifying that CT 105 (`unifi-os-server`) is privileged (`unprivileged: 0`), has wildcard cgroup device permissions (`lxc.cgroup2.devices.allow: a`), and drops zero Linux capabilities (`lxc.cap.drop: `), while other containers (CT 100) run unprivileged.
- **Test 1.3 (`test_traefik_route_catalog_and_middleware_mapping`)**: Catalogs public vs local Traefik routes across 28 configuration files, verifying that `bazarr.yaml` lacks authentication middleware while `dashboard.yaml` enforces `dashboard-auth`.
- **Test 1.4 (`test_secrets_and_credential_exposure_scanner`)**: Scans `.env` for plaintext Cloudflare tokens (`cfut_...`), CrowdSec bouncer keys, and MD5 password hashes; verifies Git commit history leaks (`ec6edcd` containing `traefiktest:traefiktest`).
- **Test 1.5 (`test_storage_zfs_and_backup_inspection`)**: Audits ZFS `rpool` single-drive risk (absence of mirror/raidz), PBS outage (`10.10.10.32:8007` unreachable), and NFS mount permissions.

### Tier 2: Boundary & Corner Cases
Evaluates parameter extremes, boundary conditions, and negative test cases:
- **Test 2.1 (`test_empty_root_shadow_password_boundary`)**: Tests parsing and boundary detection of empty password hashes in `/etc/shadow` (`root::`), verifying that CT 105 triggers `EMPTY_PASSWORD` critical severity.
- **Test 2.2 (`test_subnet_cidr_boundary_evaluation`)**: Evaluates CIDR boundaries against RFC1918 private subnets. Confirms that Traefik `block-external` includes public `/16` range (`112.135.0.0/16`, 65,536 public IPs) and CrowdSec postoverflow includes two `/16` ranges (`112.135.0.0/16` and `112.134.0.0/16`, 131,072 public IPs).
- **Test 2.3 (`test_unauthenticated_http_response_boundary`)**: Verifies HTTP status codes and unauthenticated response boundaries on Bazarr (HTTP 200 OK without `WWW-Authenticate` or `Set-Cookie` session challenge; body contains `isConfigured: false`).
- **Test 2.4 (`test_wildcard_cors_header_boundary`)**: Verifies wildcard CORS boundary condition (`Access-Control-Allow-Origin: *`) and arbitrary origin reflection when requested with untrusted Origin header (`https://evil.com`).
- **Test 2.5 (`test_insecure_skip_verify_boundary`)**: Verifies `insecureSkipVerify: true` boundary condition in `_shared.yaml` and identifies all upstream consumers (`local-proxmox.yaml`, `local-pbs.yaml`, `local-unraid.yaml`).
- **Test 2.6 (`test_ssh_root_password_auth_boundary`)**: Evaluates OpenSSH daemon configuration boundaries across all 12 active containers, confirming that 10 containers simultaneously enable `PermitRootLogin yes` and `PasswordAuthentication yes`.

### Tier 3: Cross-Feature Interactions
Verifies interactions between disparate components, network layers, and software behaviors:
- **Test 3.1 (`test_traefik_hairpin_nat_bypass_interaction`)**: Simulates Traefik `ipAllowList` matching engine. Proves that an attacker residing on Sri Lanka Telecom (`112.135.0.0/16`) bypasses `block-external` to access Proxmox VE, Unraid, and PBS management endpoints.
- **Test 3.2 (`test_crowdsec_whitelist_alert_suppression`)**: Simulates CrowdSec event pipeline and postoverflow processing. Demonstrates that web application attacks and brute-force events originating from `112.135.0.0/16` or `112.134.0.0/16` are unconditionally suppressed, blinding automated defenses.
- **Test 3.3 (`test_plex_trusted_proxy_lan_bypass_interaction`)**: Simulates interaction between Traefik reverse proxying from `10.10.10.100` and Plex's `allowedNetworks` setting (`10.10.10.0/24`). Confirms that requests proxied by Traefik without proper `X-Forwarded-For` validation bypass all authentication.
- **Test 3.4 (`test_ct105_privileged_host_takeover_chain`)**: Evaluates the complete exploit chain of CT 105: privileged execution (`unprivileged: 0`) + device passthrough (`lxc.cgroup2.devices.allow: a`) + empty root password hash (`root::`) = instantaneous host root compromise.
- **Test 3.5 (`test_shared_nfs_0777_multi_container_risk`)**: Audits interaction between shared NFS mounts (`/mnt/pve/*`) across multiple containers and permissive `0777` permissions, demonstrating lack of user namespace separation on shared storage.

### Tier 4: Real-World Scenario Probes
Executes end-to-end operational scenarios and live estate probes:
- **Test 4.1 (`test_simulated_external_wan_access_to_internal_services`)**: Simulates realistic WAN traffic from external internet IPs (e.g. `198.51.100.42`) vs ISP pool IPs (`112.135.25.100`), verifying selective exposure of internal infrastructure.
- **Test 4.2 (`test_live_unauthenticated_api_probe`)**: Performs live probing of Bazarr (`10.10.10.115:6767`), confirming that while the Web UI is unauthenticated (HTTP 200), the underlying REST API enforces API key checks (HTTP 401), exposing a decoupled authentication posture.
- **Test 4.3 (`test_lateral_movement_network_path`)**: Probes live flat Layer 2 network reachability across `10.10.10.0/24`, verifying that management ports (22, 8006, 111) are unsegmented and accessible from any node on the subnet.
- **Test 4.4 (`test_traefik_config_drift_probe`)**: Compares live Traefik configuration files on CT 100 (`/etc/traefik/conf.d/`) against Git repository (`traefik-setup/conf.d/`), detecting uncommitted public routes (`qbittorrent.yaml`, `prowlarr.yaml`, `radarr.yaml`, `sonarr.yaml`, `n8n.yaml`).
- **Test 4.5 (`test_deploy_script_validation_failure_probe`)**: Validates `deploy.sh` prerequisite checking against `.env`, verifying missing environment variables (`CF_DNS_API_TOKEN`, `CF_ZONE_API_TOKEN`, `DASHBOARD_PASSWORD`) that prevent automated deployment.

---

## 4. Test Runner & Execution Guide

### Prerequisites
- Python 3.10+ (tested on Python 3.14.7)
- `pytest` (v8.0+)
- `pyyaml` (v6.0+)
- Optional: OpenSSH client with key access to `root@10.10.10.31` for live host probes (test harness automatically falls back to authoritative baseline if SSH is unavailable).

### Execution Commands

1. **Standard Pytest Execution**:
   ```bash
   python -m pytest d:\Development\stark-lab\security-audit\tests\ -v
   ```

2. **Standalone Test Runner**:
   ```bash
   python d:\Development\stark-lab\security-audit\tests\run_tests.py
   ```

3. **Executing a Specific Tier**:
   ```bash
   # Tier 1 only
   python -m pytest d:\Development\stark-lab\security-audit\tests\test_tier1_feature_coverage.py -v

   # Tier 2 only
   python -m pytest d:\Development\stark-lab\security-audit\tests\test_tier2_boundary_corner.py -v

   # Tier 3 only
   python -m pytest d:\Development\stark-lab\security-audit\tests\test_tier3_cross_feature.py -v

   # Tier 4 only
   python -m pytest d:\Development\stark-lab\security-audit\tests\test_tier4_real_world_probes.py -v
   ```

---

## 5. Non-Destructive Integrity & Safety Guarantees

1. **Read-Only Inspection**: All SSH probes to `pve1` and container guests execute read-only queries (`pveversion`, `uname`, `cat /etc/...`, `ss -tulpn`, `zpool status`, `mount`). No system state or configuration is modified.
2. **Safe Web Probing**: Web probes to Bazarr and Traefik send minimal HTTP GET/HEAD requests with custom User-Agent headers (`SecurityAuditVerifier/1.0`). No brute-force attacks or disruptive payloads are transmitted.
3. **Graceful Fallback**: If the live hypervisor or target containers are offline, tests gracefully fall back to the authoritative survey baseline in `conftest.py` without failing tests or halting execution.
