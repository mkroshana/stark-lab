"""Tier 3: Cross-Feature Interactions Test Suite.
Verifies interactions between multiple architectural components, security controls, and protocols:
- Traefik hairpin NAT workaround & block-external bypass interaction.
- CrowdSec detection engine & postoverflow whitelist suppression interaction.
- Plex reverse proxying & trusted LAN subnet unauthenticated bypass interaction.
- CT 105 privileged containment & capability/cgroup/shadow escalation chain.
- Shared NFS bind mounts & cross-container file tampering interaction.
"""

import ipaddress
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml


class TraefikAllowListSimulator:
    """Simulates Traefik ipAllowList middleware matching logic."""

    def __init__(self, source_ranges: List[str]):
        self.networks = [ipaddress.ip_network(r.strip(), strict=False) for r in source_ranges]

    def is_allowed(self, client_ip: str) -> bool:
        ip = ipaddress.ip_address(client_ip.strip())
        return any(ip in net for net in self.networks)


class CrowdSecDecisionSimulator:
    """Simulates CrowdSec alert processing and postoverflow whitelist suppression."""

    def __init__(self, whitelisted_cidrs: List[str]):
        self.whitelist_nets = [ipaddress.ip_network(c.strip(), strict=False) for c in whitelisted_cidrs]

    def process_alert(self, attacker_ip: str, scenario: str) -> Dict[str, Any]:
        ip = ipaddress.ip_address(attacker_ip.strip())
        is_whitelisted = any(ip in net for net in self.whitelist_nets)
        if is_whitelisted:
            return {
                "attacker_ip": attacker_ip,
                "scenario": scenario,
                "action": "SUPPRESSED",
                "ban_created": False,
                "reason": "Matched postoverflow home-whitelist CIDR",
            }
        else:
            return {
                "attacker_ip": attacker_ip,
                "scenario": scenario,
                "action": "BANNED",
                "ban_created": True,
                "duration": "4h",
            }


class PlexAuthPolicySimulator:
    """Simulates Plex media server allowedNetworks IP authorization check."""

    def __init__(self, allowed_networks: List[str]):
        self.networks = [ipaddress.ip_network(n.strip(), strict=False) for n in allowed_networks]

    def check_request(
        self, tcp_peer_ip: str, forwarded_for_ip: str, respects_x_forwarded_for: bool
    ) -> Dict[str, Any]:
        evaluated_ip = (
            forwarded_for_ip
            if respects_x_forwarded_for and forwarded_for_ip
            else tcp_peer_ip
        )
        ip = ipaddress.ip_address(evaluated_ip.strip())
        is_lan = any(ip in net for net in self.networks)
        return {
            "evaluated_ip": evaluated_ip,
            "is_lan": is_lan,
            "auth_required": not is_lan,
        }


class TestTier3CrossFeature:
    """Tier 3 Cross-Feature Interaction Tests."""

    def test_traefik_hairpin_nat_bypass_interaction(self, conf_d_dir: Path):
        """Cross-Feature Test 3.1: Test interaction between Hairpin NAT allowlisting and LAN route protection (SEC-CRIT-02).
        Verifies that an external IP in 112.135.0.0/16 bypasses block-external to access internal management routes.
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
        simulator = TraefikAllowListSimulator(source_ranges)

        # 1. Standard LAN client must be allowed
        assert simulator.is_allowed("10.10.10.10") is True
        assert simulator.is_allowed("127.0.0.1") is True

        # 2. Arbitrary external client must be blocked
        assert simulator.is_allowed("198.51.100.25") is False
        assert simulator.is_allowed("203.0.113.88") is False

        # 3. CRITICAL FLAW: External ISP client in 112.135.0.0/16 is admitted!
        assert simulator.is_allowed("112.135.1.1") is True
        assert simulator.is_allowed("112.135.250.99") is True

        # Cross-feature check: Verify which local management routes are exposed
        local_routes = ["local-proxmox.yaml", "local-unraid.yaml", "local-pbs.yaml"]
        for lr in local_routes:
            lr_path = conf_d_dir / lr
            with open(lr_path, "r", encoding="utf-8") as f:
                lr_data = yaml.safe_load(f)
            routers = lr_data.get("http", {}).get("routers", {})
            for r_name, r_info in routers.items():
                mws = r_info.get("middlewares", [])
                assert any(
                    m in ["block-external", "local-only", "local-iframe-only"]
                    for m in mws
                ), f"Route {r_name} in {lr} should reference block-external"

    def test_crowdsec_whitelist_alert_suppression(self, crowdsec_whitelist_path: Path):
        """Cross-Feature Test 3.2: Test interaction between CrowdSec IDS and postoverflow ISP whitelist (SEC-CRIT-02).
        Verifies that attack scenarios triggered by IPs in 112.135.0.0/16 or 112.134.0.0/16 are suppressed.
        Authoritative source: ORIGINAL_REQUEST.md R3, Explorer 2 survey report.
        """
        with open(crowdsec_whitelist_path, "r", encoding="utf-8") as f:
            cs_data = yaml.safe_load(f)

        cidrs = cs_data.get("whitelist", {}).get("cidr", [])
        simulator = CrowdSecDecisionSimulator(cidrs)

        # 1. Normal external attacker gets banned
        decision_external = simulator.process_alert("198.51.100.99", "crowdsecurity/http-crawl-non_statics")
        assert decision_external["action"] == "BANNED"
        assert decision_external["ban_created"] is True

        # 2. Attacker on Sri Lanka Telecom pool is suppressed and never banned!
        decision_isp_1 = simulator.process_alert("112.135.50.12", "crowdsecurity/http-crawl-non_statics")
        assert decision_isp_1["action"] == "SUPPRESSED"
        assert decision_isp_1["ban_created"] is False

        decision_isp_2 = simulator.process_alert("112.134.100.5", "crowdsecurity/ssh-bf")
        assert decision_isp_2["action"] == "SUPPRESSED"
        assert decision_isp_2["ban_created"] is False

    def test_plex_trusted_proxy_lan_bypass_interaction(self, repo_root: Path):
        """Cross-Feature Test 3.3: Test interaction between Traefik reverse proxy and Plex allowedNetworks (SEC-MED-04).
        Authoritative source: ORIGINAL_REQUEST.md R3, Explorer 2 survey report, traefik-setup/docs/service_plex.md.
        """
        plex_doc = repo_root / "traefik-setup" / "docs" / "service_plex.md"
        assert plex_doc.exists()
        doc_content = plex_doc.read_text(encoding="utf-8")

        # Verify documentation contains flawed guidance: allowed without auth = 10.10.10.0/24
        assert "10.10.10.0/24" in doc_content
        assert "allowed without auth" in doc_content.lower()

        # Simulate Plex receiving proxied requests from Traefik CT 100 (10.10.10.100)
        traefik_ip = "10.10.10.100"
        simulator = PlexAuthPolicySimulator(allowed_networks=["10.10.10.0/24"])

        # When Plex treats TCP peer IP as client IP (standard default when not parsing trusted proxies):
        result_without_forward = simulator.check_request(
            tcp_peer_ip=traefik_ip, forwarded_for_ip="203.0.113.5", respects_x_forwarded_for=False
        )
        # Auth is bypassed for the external attacker!
        assert result_without_forward["auth_required"] is False, (
            "Vulnerability confirmed: Incoming proxied connection from Traefik bypasses Plex authentication!"
        )

        # When Plex is properly configured to parse X-Forwarded-For from trusted proxies:
        result_with_forward = simulator.check_request(
            tcp_peer_ip=traefik_ip, forwarded_for_ip="203.0.113.5", respects_x_forwarded_for=True
        )
        assert result_with_forward["auth_required"] is True, (
            "Safe state: When X-Forwarded-For is evaluated, external client requires authentication"
        )

    def test_ct105_privileged_host_takeover_chain(
        self, live_pve_reachable: bool, pve_ssh, authoritative_audit_baseline: Dict[str, Any]
    ):
        """Cross-Feature Test 3.4: Test privileged container CT 105 host takeover escalation chain (SEC-CRIT-01).
        Authoritative source: ORIGINAL_REQUEST.md R2, Explorer 1 survey report.
        """
        if live_pve_reachable:
            # 1. CT 105 config contains dangerous combinations
            res_conf = pve_ssh("cat /etc/pve/lxc/105.conf")
            assert res_conf.returncode == 0
            conf = res_conf.stdout

            has_no_drop = "lxc.cap.drop:" in conf
            has_all_devices = "lxc.cgroup2.devices.allow: a" in conf
            is_privileged = "unprivileged: 1" not in conf

            assert is_privileged and has_no_drop and has_all_devices, (
                "CT 105 escalation chain elements confirmed on hypervisor configuration"
            )

            # 2. Shadow file contains empty password
            res_shadow = pve_ssh("cat /rpool/data/subvol-105-disk-0/etc/shadow")
            assert res_shadow.returncode == 0
            root_shadow = [l for l in res_shadow.stdout.splitlines() if l.startswith("root:")]
            assert len(root_shadow) > 0
            assert root_shadow[0].split(":")[1] == "", "Empty root password confirmed on CT 105 filesystem"
        else:
            ct = authoritative_audit_baseline["containers"]["ct_105"]
            assert ct["unprivileged"] == 0
            assert ct["device_allow"] == "a"
            assert ct["shadow_root_password"] == ""

    def test_shared_nfs_0777_multi_container_risk(
        self, live_pve_reachable: bool, pve_ssh, authoritative_audit_baseline: Dict[str, Any]
    ):
        """Cross-Feature Test 3.5: Test shared world-writable NFS bind mount risks across containers (SEC-HIGH-03).
        Authoritative source: ORIGINAL_REQUEST.md R1 & R2, Explorer 1 survey report.
        """
        if live_pve_reachable:
            # Verify permissions on /mnt/pve mounts
            ls_res = pve_ssh("ls -ld /mnt/pve/*")
            assert ls_res.returncode == 0
            for line in ls_res.stdout.splitlines():
                if any(m in line for m in ["Movies", "TV-Shows", "Downloads", "Vault", "Backups"]):
                    # Permissions should start with rwxrwxrwx (0777)
                    perms = line.split()[0]
                    assert "rwxrwxrwx" in perms or perms.endswith("rwx"), (
                        f"Expected world-writable permissions on NFS mount: {line}"
                    )
        else:
            assert authoritative_audit_baseline["pve1"]["nfs_permissions"] == "0777"
