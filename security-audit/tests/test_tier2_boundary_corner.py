"""Tier 2: Boundary & Corner Cases Test Suite.
Verifies boundary conditions, parameter extremes, and security edge cases:
- Empty root shadow password detection (root:: boundary).
- Subnet CIDR evaluation (/16 public ISP vs private RFC1918 /32 boundaries).
- Unauthenticated HTTP status code & payload boundaries (200 OK vs 401/403).
- Wildcard CORS header evaluation (Access-Control-Allow-Origin: *).
- Insecure backend transport flag (insecureSkipVerify: true).
- OpenSSH daemon authentication combinations (PermitRootLogin + PasswordAuthentication).
"""

import ipaddress
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml


class ShadowPasswordParser:
    """Parser and evaluator for Linux /etc/shadow password fields."""

    @staticmethod
    def evaluate_shadow_line(line: str) -> Dict[str, Any]:
        parts = line.strip().split(":")
        if len(parts) < 2:
            return {"valid": False, "username": "", "status": "malformed"}
        username = parts[0]
        passwd_field = parts[1]

        if passwd_field == "":
            return {"valid": True, "username": username, "status": "EMPTY_PASSWORD", "severity": "CRITICAL"}
        elif passwd_field in ["*", "!", "!!"]:
            return {"valid": True, "username": username, "status": "LOCKED", "severity": "SAFE"}
        elif passwd_field.startswith("!"):
            return {"valid": True, "username": username, "status": "LOCKED_HASH", "severity": "SAFE"}
        elif passwd_field.startswith(("$1$", "$5$", "$6$", "$y$", "$2a$", "$2b$")):
            return {"valid": True, "username": username, "status": "HASHED", "severity": "NORMAL"}
        else:
            return {"valid": True, "username": username, "status": "PLAINTEXT_OR_UNKNOWN", "severity": "HIGH"}


class SubnetCidrEvaluator:
    """Evaluates IP CIDRs against RFC1918 private ranges and prefix boundaries."""

    PRIVATE_NETWORKS = [
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("100.64.0.0/10"),  # CGNAT RFC 6598
    ]

    @classmethod
    def is_private(cls, cidr_str: str) -> bool:
        net = ipaddress.ip_network(cidr_str, strict=False)
        return any(net.subnet_of(priv) for priv in cls.PRIVATE_NETWORKS)

    @classmethod
    def evaluate_cidr(cls, cidr_str: str) -> Dict[str, Any]:
        net = ipaddress.ip_network(cidr_str, strict=False)
        is_priv = cls.is_private(cidr_str)
        num_hosts = net.num_addresses
        prefix_len = net.prefixlen
        is_overbroad_public = (not is_priv) and (prefix_len <= 16)
        return {
            "cidr": cidr_str,
            "prefixlen": prefix_len,
            "num_addresses": num_hosts,
            "is_private": is_priv,
            "is_overbroad_public": is_overbroad_public,
        }


class TestTier2BoundaryCorner:
    """Tier 2 Boundary & Corner Cases Tests."""

    def test_empty_root_shadow_password_boundary(
        self, live_pve_reachable: bool, pve_ssh, authoritative_audit_baseline: Dict[str, Any]
    ):
        """Corner Test 2.1: Verify boundary condition for empty root shadow password (SEC-CRIT-01).
        Authoritative source: ORIGINAL_REQUEST.md R2, Explorer 1 survey report.
        """
        # 1. Unit boundary validation
        assert ShadowPasswordParser.evaluate_shadow_line("root::20704:0:99999:7:::")[
            "status"
        ] == "EMPTY_PASSWORD"
        assert ShadowPasswordParser.evaluate_shadow_line("root:*:20704:0:99999:7:::")[
            "status"
        ] == "LOCKED"
        assert ShadowPasswordParser.evaluate_shadow_line("root:!:20704:0:99999:7:::")[
            "status"
        ] == "LOCKED"
        assert ShadowPasswordParser.evaluate_shadow_line(
            "root:$6$salt$hash:20704:0:99999:7:::"
        )["status"] == "HASHED"

        # 2. Live / Baseline validation for CT 105
        if live_pve_reachable:
            shadow_res = pve_ssh("grep '^root:' /rpool/data/subvol-105-disk-0/etc/shadow")
            assert shadow_res.returncode == 0
            eval_res = ShadowPasswordParser.evaluate_shadow_line(shadow_res.stdout)
            assert eval_res["status"] == "EMPTY_PASSWORD", (
                f"Expected CT 105 root shadow to have empty password, got: {shadow_res.stdout}"
            )
            assert eval_res["severity"] == "CRITICAL"
        else:
            # Baseline check
            assert authoritative_audit_baseline["containers"]["ct_105"]["shadow_root_password"] == ""

    def test_subnet_cidr_boundary_evaluation(
        self, conf_d_dir: Path, crowdsec_whitelist_path: Path
    ):
        """Corner Test 2.2: Evaluate CIDR boundaries and detect /16 public subnet whitelisting (SEC-CRIT-02).
        Authoritative source: ORIGINAL_REQUEST.md R3, Explorer 2 survey report.
        """
        shared_yaml = conf_d_dir / "_shared.yaml"
        assert shared_yaml.exists()
        with open(shared_yaml, "r", encoding="utf-8") as f:
            shared_data = yaml.safe_load(f)

        block_external = (
            shared_data.get("http", {})
            .get("middlewares", {})
            .get("block-external", {})
        )
        source_ranges = block_external.get("ipAllowList", {}).get("sourceRange", [])

        # Evaluate all CIDRs in block-external
        evaluations = [SubnetCidrEvaluator.evaluate_cidr(cidr) for cidr in source_ranges]

        # Verify private ranges are recognized
        privates = [e for e in evaluations if e["is_private"]]
        assert any(e["cidr"] == "127.0.0.1/32" for e in privates)
        assert any(e["cidr"] == "10.10.10.0/24" for e in privates)
        assert any(e["cidr"] == "192.168.0.0/16" for e in privates)

        # Boundary violation: 112.135.0.0/16 is public and encompasses 65,536 IPs
        public_ranges = [e for e in evaluations if not e["is_private"]]
        assert len(public_ranges) >= 1
        slt_range = next((e for e in public_ranges if "112.135" in e["cidr"]), None)
        assert slt_range is not None, "Expected 112.135.0.0/16 to be detected in block-external"
        assert slt_range["num_addresses"] == 65536
        assert slt_range["is_overbroad_public"] is True

        # Check CrowdSec whitelist boundary
        assert crowdsec_whitelist_path.exists()
        with open(crowdsec_whitelist_path, "r", encoding="utf-8") as f:
            cs_data = yaml.safe_load(f)

        cs_cidrs = cs_data.get("whitelist", {}).get("cidr", [])
        assert len(cs_cidrs) >= 2
        cs_evals = [SubnetCidrEvaluator.evaluate_cidr(cidr) for cidr in cs_cidrs]
        total_exposed_ips = sum(e["num_addresses"] for e in cs_evals)
        assert total_exposed_ips == 131072, (
            f"Expected exactly 131,072 IP addresses whitelisted in CrowdSec, got {total_exposed_ips}"
        )
        assert all(e["is_overbroad_public"] for e in cs_evals)

    def test_unauthenticated_http_response_boundary(
        self, live_bazarr_reachable: bool
    ):
        """Corner Test 2.3: Verify HTTP status codes and unauthenticated response boundaries (SEC-CRIT-03).
        Authoritative source: ORIGINAL_REQUEST.md R4, Explorer 3 survey report.
        """
        if live_bazarr_reachable:
            import urllib.request

            req = urllib.request.Request(
                "http://10.10.10.115:6767/",
                headers={"User-Agent": "SecurityAuditVerifier/1.0"},
            )
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                status_code = resp.status
                headers = dict(resp.getheaders())
                body = resp.read().decode("utf-8", errors="ignore")

            # Boundary: HTTP 200 OK without authentication requirement
            assert status_code == 200
            assert "www-authenticate" not in [k.lower() for k in headers.keys()]
            assert "set-cookie" not in [k.lower() for k in headers.keys()]
            assert "window.Bazarr" in body
            assert '"isConfigured": false' in body or '"isConfigured":false' in body
        else:
            pytest.skip("Bazarr endpoint 10.10.10.115:6767 not reachable from test environment")

    def test_wildcard_cors_header_boundary(
        self, live_bazarr_reachable: bool
    ):
        """Corner Test 2.4: Verify wildcard Access-Control-Allow-Origin header boundary (SEC-CRIT-03).
        Authoritative source: ORIGINAL_REQUEST.md R4, Explorer 3 survey report.
        """
        if live_bazarr_reachable:
            import urllib.request

            # 1. Request with untrusted Origin: Bazarr reflects the arbitrary origin
            req_origin = urllib.request.Request(
                "http://10.10.10.115:6767/",
                headers={"User-Agent": "SecurityAuditVerifier/1.0", "Origin": "https://evil.com"},
            )
            with urllib.request.urlopen(req_origin, timeout=3.0) as resp:
                headers_origin = {k.lower(): v for k, v in resp.getheaders()}
            cors_reflected = headers_origin.get("access-control-allow-origin")
            assert cors_reflected in ["*", "https://evil.com"], (
                f"Expected wildcard or arbitrary reflected origin, got: {cors_reflected}"
            )

            # 2. Request without Origin: Bazarr returns wildcard *
            req_wildcard = urllib.request.Request(
                "http://10.10.10.115:6767/",
                headers={"User-Agent": "SecurityAuditVerifier/1.0"},
            )
            with urllib.request.urlopen(req_wildcard, timeout=3.0) as resp:
                headers_wildcard = {k.lower(): v for k, v in resp.getheaders()}
            cors_wildcard = headers_wildcard.get("access-control-allow-origin")
            assert cors_wildcard == "*", (
                f"Expected wildcard CORS 'Access-Control-Allow-Origin: *', got: {cors_wildcard}"
            )
        else:
            pytest.skip("Bazarr endpoint 10.10.10.115:6767 not reachable from test environment")

    def test_insecure_skip_verify_boundary(
        self, conf_d_dir: Path
    ):
        """Corner Test 2.5: Verify insecureSkipVerify transport configuration boundary (SEC-MED-02).
        Authoritative source: ORIGINAL_REQUEST.md R3, Explorer 3 survey report.
        """
        shared_yaml = conf_d_dir / "_shared.yaml"
        with open(shared_yaml, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        transports = data.get("http", {}).get("serversTransports", {})
        assert "insecure-transport" in transports
        insecure_transport = transports["insecure-transport"]
        assert insecure_transport.get("insecureSkipVerify") is True, (
            "insecureSkipVerify should be True in insecure-transport definition"
        )

        # Confirm services using this insecure transport
        insecure_services = []
        for yaml_file in conf_d_dir.glob("*.yaml"):
            with open(yaml_file, "r", encoding="utf-8") as f:
                content = f.read()
                if "insecure-transport" in content:
                    insecure_services.append(yaml_file.name)

        expected_users = {"local-proxmox.yaml", "local-pbs.yaml", "local-unraid.yaml"}
        assert expected_users.issubset(set(insecure_services)), (
            f"Expected {expected_users} to use insecure-transport, found: {insecure_services}"
        )

    def test_ssh_root_password_auth_boundary(
        self, live_pve_reachable: bool, pve_ssh, authoritative_audit_baseline: Dict[str, Any]
    ):
        """Corner Test 2.6: Audit dangerous PermitRootLogin yes + PasswordAuthentication yes combinations (SEC-HIGH-01).
        Authoritative source: ORIGINAL_REQUEST.md R2, Explorer 1 survey report.
        """
        if live_pve_reachable:
            # Query active container SSH configs from PVE
            check_script = (
                'for id in 101 102 111 113 114 115 117 118 119 121; do '
                'pct exec $id -- sh -c "sshd -T 2>/dev/null | grep -E \\"^(permitrootlogin|passwordauthentication)\\"" '
                '| tr "\\n" " "; echo ""; done'
            )
            ssh_res = pve_ssh(check_script, timeout=30)
            assert ssh_res.returncode == 0
            lines = [l.strip() for l in ssh_res.stdout.splitlines() if l.strip()]
            for line in lines:
                assert "permitrootlogin yes" in line.lower()
                assert "passwordauthentication yes" in line.lower()
        else:
            baseline_containers = authoritative_audit_baseline["containers"]["ssh_root_password_auth_containers"]
            assert len(baseline_containers) == 10
