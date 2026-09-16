"""Tier 4: Real-World Scenario Probes Test Suite.
Verifies real-world operational scenarios, end-to-end exploit vectors, and live estate telemetry:
- Simulated external WAN access to internal services via Traefik.
- Live unauthenticated Web UI & API probing (Bazarr).
- Lateral movement network path evaluation across flat L2 subnet.
- Live Traefik configuration drift probe between CT 100 and git repository.
- Deployment script environment validation probe.
"""

import re
import socket
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Set

import pytest
import yaml


class TestTier4RealWorldProbes:
    """Tier 4 Real-World Scenario Probes Tests."""

    def test_simulated_external_wan_access_to_internal_services(
        self, conf_d_dir: Path
    ):
        """Scenario Probe 4.1: Simulate WAN access to internal services via block-external allowlist (SEC-CRIT-02).
        Evaluates requests originating from untrusted WAN IPs vs whitelisted ISP IPs.
        Authoritative source: ORIGINAL_REQUEST.md R3, Explorer 2 survey report.
        """
        shared_yaml = conf_d_dir / "_shared.yaml"
        with open(shared_yaml, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        source_ranges = (
            data.get("http", {})
            .get("middlewares", {})
            .get("block-external", {})
            .get("ipAllowList", {})
            .get("sourceRange", [])
        )

        import ipaddress
        networks = [ipaddress.ip_network(r, strict=False) for r in source_ranges]

        def evaluate_ip(client_ip: str) -> bool:
            ip = ipaddress.ip_address(client_ip)
            return any(ip in net for net in networks)

        # Scenario A: External attacker on random internet IP (e.g., DigitalOcean 198.51.100.42)
        # Expected: Access denied (False -> 403 Forbidden)
        assert evaluate_ip("198.51.100.42") is False
        assert evaluate_ip("8.8.8.8") is False
        assert evaluate_ip("1.1.1.1") is False

        # Scenario B: Attacker residing on Sri Lanka Telecom (SLT) subscriber pool (112.135.x.x)
        # Expected vulnerability: Access GRANTED (True -> proxies to Proxmox VE Web UI)
        assert evaluate_ip("112.135.25.100") is True
        assert evaluate_ip("112.135.1.1") is True
        assert evaluate_ip("112.135.254.254") is True

        # Confirm that 65,536 external IPs in 112.135.0.0/16 are improperly granted access
        slt_net = ipaddress.ip_network("112.135.0.0/16")
        assert slt_net.num_addresses == 65536

    def test_live_unauthenticated_api_probe(
        self, live_bazarr_reachable: bool
    ):
        """Scenario Probe 4.2: Probe live web endpoint for unauthenticated UI and decoupled API auth (SEC-CRIT-03).
        Authoritative source: ORIGINAL_REQUEST.md R4, Explorer 3 survey report.
        """
        if not live_bazarr_reachable:
            pytest.skip("Bazarr endpoint 10.10.10.115:6767 not reachable from test environment")

        # 1. Probe Web UI root: returns 200 OK without authentication
        req_root = urllib.request.Request(
            "http://10.10.10.115:6767/",
            headers={"User-Agent": "SecurityAuditVerifier/1.0"},
        )
        with urllib.request.urlopen(req_root, timeout=3.0) as resp:
            assert resp.status == 200
            headers = dict(resp.getheaders())
            body = resp.read().decode("utf-8", errors="ignore")

        # Wildcard CORS must be present
        cors = [v for k, v in headers.items() if k.lower() == "access-control-allow-origin"]
        assert cors and cors[0] == "*", "Expected Access-Control-Allow-Origin: *"

        # Web UI contains unauthenticated status
        assert "window.Bazarr" in body
        assert "isConfigured" in body

        # 2. Probe API endpoint /api/badges without API key
        # In Bazarr, the API enforces apikey auth (401), while the web UI has NO auth
        req_api = urllib.request.Request(
            "http://10.10.10.115:6767/api/badges",
            headers={"User-Agent": "SecurityAuditVerifier/1.0"},
        )
        api_status = None
        try:
            with urllib.request.urlopen(req_api, timeout=3.0) as api_resp:
                api_status = api_resp.status
        except urllib.error.HTTPError as e:
            api_status = e.code

        assert api_status == 401, (
            f"Expected API endpoint to return 401 Unauthorized when missing API key, got {api_status}"
        )

    def test_lateral_movement_network_path(
        self, live_pve_reachable: bool, pve_ssh, authoritative_audit_baseline: Dict[str, Any]
    ):
        """Scenario Probe 4.3: Probe flat L2 network reachability and unsegmented management ports (SEC-HIGH-06).
        Authoritative source: ORIGINAL_REQUEST.md R1 & R2, Explorer 1 survey report.
        """
        baseline = authoritative_audit_baseline["pve1"]

        # 1. Management port socket test from current LAN position (10.10.10.10)
        pve_ip = baseline["ip"]
        open_ports = []
        for port in [22, 8006, 3128, 111]:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.5)
            try:
                s.connect((pve_ip, port))
                open_ports.append(port)
            except (socket.timeout, OSError):
                pass
            finally:
                s.close()

        assert 22 in open_ports, "SSH port 22 must be reachable on hypervisor"
        assert 8006 in open_ports, "PVE Web Management port 8006 must be reachable on hypervisor"
        assert 111 in open_ports, "RPCbind port 111 must be reachable on hypervisor"

        # 2. If PVE is live, check that pve-firewall is disabled and iptables policy is ACCEPT
        if live_pve_reachable:
            fw_res = pve_ssh("pve-firewall status; iptables -S INPUT")
            assert fw_res.returncode == 0
            out = fw_res.stdout
            assert "disabled" in out.lower(), "pve-firewall is disabled"
            assert "-P INPUT ACCEPT" in out, "iptables INPUT chain default policy is ACCEPT"

    def test_traefik_config_drift_probe(
        self, live_pve_reachable: bool, pve_ssh, conf_d_dir: Path
    ):
        """Scenario Probe 4.4: Probe live CT 100 filesystem vs git repository for configuration drift (SEC-HIGH-05).
        Authoritative source: ORIGINAL_REQUEST.md R3, Explorer 1 & 2 survey reports.
        """
        git_files: Set[str] = {f.name for f in conf_d_dir.glob("*.yaml")}

        if live_pve_reachable:
            res = pve_ssh("pct exec 100 -- ls -1 /etc/traefik/conf.d/")
            assert res.returncode == 0
            live_files = {line.strip() for line in res.stdout.splitlines() if line.strip().endswith(".yaml")}

            # Identify untracked files on live CT 100
            untracked = live_files - git_files

            # Expected untracked public route files
            expected_untracked = {
                "qbittorrent.yaml",
                "prowlarr.yaml",
                "radarr.yaml",
                "sonarr.yaml",
                "n8n.yaml",
            }
            found_untracked = untracked.intersection(expected_untracked)
            assert len(found_untracked) >= 4, (
                f"Expected untracked public routes in live Traefik, found: {found_untracked}"
            )
        else:
            pytest.skip("PVE host 10.10.10.31 not reachable from test environment")

    def test_deploy_script_validation_failure_probe(
        self, repo_root: Path, env_path: Path
    ):
        """Scenario Probe 4.5: Validate deploy.sh environment requirements against current .env (SEC-INFO-01).
        Verifies that required variables defined in deploy.sh are missing from .env.
        Authoritative source: ORIGINAL_REQUEST.md R3, Explorer 2 & 3 survey reports.
        """
        deploy_sh = repo_root / "traefik-setup" / "deploy.sh"
        assert deploy_sh.exists()

        # Parse REQUIRED_VARS from deploy.sh
        deploy_content = deploy_sh.read_text(encoding="utf-8")
        req_vars_match = re.search(r"REQUIRED_VARS=\(([^)]+)\)", deploy_content)
        assert req_vars_match, "REQUIRED_VARS array not found in deploy.sh"

        required_vars = [
            v.strip().strip('"').strip("'")
            for v in req_vars_match.group(1).split()
            if v.strip()
        ]
        assert "CF_API_TOKEN" in required_vars
        assert "CF_DNS_API_TOKEN" in required_vars
        assert "DASHBOARD_PASSWORD" in required_vars

        # Parse variables defined in .env
        env_content = env_path.read_text(encoding="utf-8")
        defined_vars = set()
        for line in env_content.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key = line.split("=", 1)[0].strip()
                defined_vars.add(key)

        # Check missing variables
        missing_vars = [var for var in required_vars if var not in defined_vars]
        assert "CF_DNS_API_TOKEN" in missing_vars, (
            "CF_DNS_API_TOKEN is required by deploy.sh but missing from .env"
        )
        assert "CF_ZONE_API_TOKEN" in missing_vars, (
            "CF_ZONE_API_TOKEN is required by deploy.sh but missing from .env"
        )
        assert "DASHBOARD_PASSWORD" in missing_vars, (
            "DASHBOARD_PASSWORD is required by deploy.sh but missing from .env"
        )
