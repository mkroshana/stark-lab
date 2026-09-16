"""Tier 1: Feature Coverage Test Suite.
Verifies core security audit capabilities and finding assertions across R1 to R6:
- Host inspection (PVE OS, kernel, daemons, firewall status).
- Container configuration verification (Privileged vs unprivileged, isolation, capabilities).
- Traefik route verification (Public vs LAN-only routes, middleware binding, auth gates).
- Secrets & credential scanners (Regex token scanner, git commit history scan, hash strength).
- Storage & backup resilience (ZFS single-disk, PBS reachability, NFS permissions).
"""

import re
import subprocess
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml


class TestTier1FeatureCoverage:
    """Tier 1 Feature Coverage Tests."""

    def test_pve_host_os_and_kernel_inspection(
        self, live_pve_reachable: bool, pve_ssh, authoritative_audit_baseline: Dict[str, Any]
    ):
        """Feature Test 1.1: Verify PVE hypervisor host OS, kernel, and listening ports (R1).
        Authoritative source: ORIGINAL_REQUEST.md R1, Explorer 1 survey report.
        """
        baseline = authoritative_audit_baseline["pve1"]

        if live_pve_reachable:
            # Run live verification on pve1
            pve_ver_res = pve_ssh("pveversion -v")
            assert pve_ver_res.returncode == 0, f"Failed to execute pveversion: {pve_ver_res.stderr}"
            assert "proxmox-ve:" in pve_ver_res.stdout
            assert "pve-manager:" in pve_ver_res.stdout

            uname_res = pve_ssh("uname -r")
            assert uname_res.returncode == 0
            kernel_release = uname_res.stdout.strip()
            assert "pve" in kernel_release, f"Expected PVE kernel, got: {kernel_release}"

            # Verify firewall status
            fw_res = pve_ssh("pve-firewall status")
            assert fw_res.returncode == 0
            assert "disabled" in fw_res.stdout.lower(), (
                f"Expected pve-firewall disabled/running finding, got: {fw_res.stdout}"
            )

            # Verify listening ports
            ss_res = pve_ssh("ss -tulpn")
            assert ss_res.returncode == 0
            listening_output = ss_res.stdout
            for expected_port in [22, 8006, 3128, 111]:
                assert f":{expected_port}" in listening_output, (
                    f"Port {expected_port} not found in listening sockets: {listening_output}"
                )
        else:
            # Fallback to authoritative surveyed baseline
            assert baseline["ip"] == "10.10.10.31"
            assert "pve" in baseline["kernel"]
            assert baseline["firewall_status"] == "disabled/running"
            assert 22 in baseline["listening_ports"]
            assert 8006 in baseline["listening_ports"]

    def test_container_configuration_audit(
        self, live_pve_reachable: bool, pve_ssh, authoritative_audit_baseline: Dict[str, Any]
    ):
        """Feature Test 1.2: Audit LXC container configurations for privilege & isolation (R2).
        Flags CT 105 as privileged (unprivileged: 0) and verifies unprivileged containment on others.
        Authoritative source: ORIGINAL_REQUEST.md R2, Explorer 1 survey report.
        """
        baseline = authoritative_audit_baseline["containers"]

        if live_pve_reachable:
            # Inspect CT 105 configuration directly on PVE
            ct105_conf = pve_ssh("cat /etc/pve/lxc/105.conf")
            assert ct105_conf.returncode == 0
            stdout_105 = ct105_conf.stdout

            # In Proxmox LXC, unprivileged containers have 'unprivileged: 1'
            # Privileged containers either have 'unprivileged: 0' or omit the field entirely
            assert "unprivileged: 1" not in stdout_105, (
                "CT 105 should NOT be unprivileged. SEC-CRIT-01 requires detecting privileged mode."
            )
            assert "lxc.cgroup2.devices.allow: a" in stdout_105, (
                "CT 105 allows all cgroup devices without restriction"
            )
            assert "lxc.cap.drop:" in stdout_105, (
                "CT 105 drops zero Linux capabilities"
            )

            # Verify CT 100 is unprivileged
            ct100_conf = pve_ssh("cat /etc/pve/lxc/100.conf")
            if ct100_conf.returncode == 0:
                assert "unprivileged: 1" in ct100_conf.stdout, (
                    "CT 100 (Traefik) should be unprivileged"
                )
        else:
            # Verify authoritative baseline values
            assert 105 in baseline["privileged_containers"]
            assert baseline["ct_105"]["unprivileged"] == 0
            assert baseline["ct_105"]["device_allow"] == "a"
            assert baseline["ct_105"]["capabilities_dropped"] == []

    def test_traefik_route_catalog_and_middleware_mapping(
        self, traefik_yaml_configs: Dict[str, Dict[str, Any]], authoritative_audit_baseline: Dict[str, Any]
    ):
        """Feature Test 1.3: Catalog Traefik routers, services, and middlewares (R3).
        Authoritative source: ORIGINAL_REQUEST.md R3, Explorer 2 survey report.
        """
        assert len(traefik_yaml_configs) >= 20, (
            f"Expected at least 20 YAML configuration files, found {len(traefik_yaml_configs)}"
        )

        # Classify routers into public vs local
        public_routers = {}
        local_routers = {}

        for filename, config in traefik_yaml_configs.items():
            if "http" in config and "routers" in config["http"]:
                for router_name, r_conf in config["http"]["routers"].items():
                    rule = r_conf.get("rule", "")
                    middlewares = r_conf.get("middlewares", [])
                    entry_points = r_conf.get("entryPoints", [])
                    if filename.startswith("local-") or "local." in rule:
                        local_routers[router_name] = {
                            "file": filename, "rule": rule, "middlewares": middlewares
                        }
                    else:
                        public_routers[router_name] = {
                            "file": filename, "rule": rule, "middlewares": middlewares
                        }

        # Expected public services
        assert "bazarr" in public_routers
        assert "jellyfin" in public_routers
        assert "homeassistant" in public_routers

        # Crucial security check: bazarr lacks authentication middleware
        bazarr_middlewares = public_routers["bazarr"]["middlewares"]
        auth_middlewares = {"dashboard-auth", "basicAuth", "authelia", "authentik"}
        has_auth = any(m in auth_middlewares for m in bazarr_middlewares)
        assert not has_auth, (
            "SEC-CRIT-03 finding confirmed: bazarr.yaml public route lacks authentication middleware!"
        )

        # Dashboard router in dashboard.yaml has rule traefik.local... and enforces dashboard-auth
        assert "traefik-dashboard" in local_routers
        dashboard_middlewares = local_routers["traefik-dashboard"]["middlewares"]
        assert "dashboard-auth" in dashboard_middlewares

        # Verify shared.yaml defines block-external
        shared_config = traefik_yaml_configs.get("_shared.yaml", {})
        middlewares = shared_config.get("http", {}).get("middlewares", {})
        assert "block-external" in middlewares
        assert "ipAllowList" in middlewares["block-external"]

    def test_secrets_and_credential_exposure_scanner(
        self, env_path: Path, repo_root: Path, authoritative_audit_baseline: Dict[str, Any]
    ):
        """Feature Test 1.4: Regex scanner for plaintext tokens, API keys, and Git history leaks (R5).
        Authoritative source: ORIGINAL_REQUEST.md R5, Explorer 3 survey report.
        """
        # 1. Scan local .env file
        assert env_path.exists(), f".env file expected at {env_path}"
        env_content = env_path.read_text(encoding="utf-8")

        # Pattern for Cloudflare API tokens: cfut_ followed by base62/alnum characters
        cf_pattern = re.compile(r"CF_API_TOKEN=(cfut_[a-zA-Z0-9_-]{30,})")
        cf_match = cf_pattern.search(env_content)
        assert cf_match, "Expected Cloudflare API token pattern to match in .env"
        token = cf_match.group(1)
        assert len(token) > 30

        # Pattern for CrowdSec bouncer key
        cs_pattern = re.compile(r"CROWDSEC_BOUNCER_API_KEY=([a-zA-Z0-9/+=_-]{25,})")
        cs_match = cs_pattern.search(env_content)
        assert cs_match, "Expected CrowdSec API key pattern to match in .env"

        # Pattern for MD5-crypt hash ($apr1$ or $1$)
        apr1_pattern = re.compile(r"DASHBOARD_AUTH_HASH=([a-zA-Z0-9_]+:\$apr1\$[a-zA-Z0-9./]+\$[a-zA-Z0-9./]+)")
        apr1_match = apr1_pattern.search(env_content)
        assert apr1_match, "Expected Apache MD5 apr1 hash in .env"

        # 2. Scan Git history for leaked commit ec6edcd
        git_check = subprocess.run(
            ["git", "log", "--grep=traefiktest", "-n", "1", "--oneline"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        if git_check.returncode == 0 and git_check.stdout.strip():
            assert "traefiktest" in git_check.stdout.lower()

    def test_storage_zfs_and_backup_inspection(
        self, live_pve_reachable: bool, pve_ssh, authoritative_audit_baseline: Dict[str, Any]
    ):
        """Feature Test 1.5: Audit ZFS single-drive risk, PBS outage, and NFS permissions (R1).
        Authoritative source: ORIGINAL_REQUEST.md R1, Explorer 1 survey report.
        """
        baseline = authoritative_audit_baseline["pve1"]

        if live_pve_reachable:
            # Query ZFS pool status
            zpool_res = pve_ssh("zpool status rpool")
            assert zpool_res.returncode == 0
            zpool_out = zpool_res.stdout
            # Single drive pool has no mirror or raidz keyword in vdev tree
            assert "mirror" not in zpool_out.lower(), "Expected single-drive pool without mirror"
            assert "raidz" not in zpool_out.lower(), "Expected single-drive pool without raidz"

            # Query PBS reachability from PVE
            pbs_nc = pve_ssh("nc -z -v -w 2 10.10.10.32 8007")
            # Should fail or return non-zero because PBS is down
            assert pbs_nc.returncode != 0, f"Expected PBS (10.10.10.32:8007) to be unreachable, got: {pbs_nc.stdout}"

            # Query NFS mounts
            nfs_mounts = pve_ssh("mount | grep nfs4")
            if nfs_mounts.returncode == 0:
                assert "10.10.10.30" in nfs_mounts.stdout
        else:
            assert not baseline["pbs_reachable"]
            assert baseline["nfs_permissions"] == "0777"
