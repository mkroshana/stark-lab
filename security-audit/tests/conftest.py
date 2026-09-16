"""Pytest configuration, shared fixtures, and audit test harness.
Provides fixtures for repository paths, YAML parsers, live network probes,
and authoritative baseline audit datasets for Stark-Lab homelab verification.
"""

import os
import socket
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TRAEFIK_SETUP_DIR = REPO_ROOT / "traefik-setup"
CONF_D_DIR = TRAEFIK_SETUP_DIR / "conf.d"
ENV_FILE = TRAEFIK_SETUP_DIR / ".env"
CROWDSEC_DIR = TRAEFIK_SETUP_DIR / "crowdsec"
CROWDSEC_WHITELIST = CROWDSEC_DIR / "postoverflows" / "s01-whitelist" / "home-whitelist.yaml"

PVE_HOST = "10.10.10.31"
TRAEFIK_HOST = "10.10.10.100"
BAZARR_HOST = "10.10.10.115"
PBS_HOST = "10.10.10.32"
HA_HOST = "10.10.10.154"
HOMELABLE_HOST = "10.10.10.102"
NAS_HOST = "10.10.10.30"


def check_socket(host: str, port: int, timeout: float = 1.0) -> bool:
    """Check if a TCP socket is open and reachable."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def conf_d_dir() -> Path:
    return CONF_D_DIR


@pytest.fixture(scope="session")
def env_path() -> Path:
    return ENV_FILE


@pytest.fixture(scope="session")
def crowdsec_whitelist_path() -> Path:
    return CROWDSEC_WHITELIST


@pytest.fixture(scope="session")
def live_pve_reachable() -> bool:
    return check_socket(PVE_HOST, 22, timeout=1.5)


@pytest.fixture(scope="session")
def live_traefik_reachable() -> bool:
    return check_socket(TRAEFIK_HOST, 80, timeout=1.5)


@pytest.fixture(scope="session")
def live_bazarr_reachable() -> bool:
    return check_socket(BAZARR_HOST, 6767, timeout=1.5)


@pytest.fixture(scope="session")
def pve_ssh():
    """Helper to run non-destructive commands on pve1 via SSH if reachable."""
    def _run(cmd: str, timeout: int = 25) -> subprocess.CompletedProcess:
        full_cmd = [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=4",
            "-o", "StrictHostKeyChecking=accept-new",
            f"root@{PVE_HOST}",
            cmd,
        ]
        return subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
    return _run


@pytest.fixture(scope="session")
def traefik_yaml_configs() -> Dict[str, Dict[str, Any]]:
    """Loads and parses all YAML files in traefik-setup/conf.d."""
    configs: Dict[str, Dict[str, Any]] = {}
    for yaml_file in CONF_D_DIR.glob("*.yaml"):
        with open(yaml_file, "r", encoding="utf-8") as f:
            try:
                data = yaml.safe_load(f)
                if data:
                    configs[yaml_file.name] = data
            except Exception as e:
                configs[yaml_file.name] = {"__parse_error__": str(e)}
    return configs


@pytest.fixture(scope="session")
def authoritative_audit_baseline() -> Dict[str, Any]:
    """Authoritative baseline findings derived from Explorer 1, 2, and 3 surveys.
    Provides ground truth specifications for audit verification.
    """
    return {
        "pve1": {
            "ip": "10.10.10.31",
            "kernel": "7.0.14-16-pve",
            "pve_version": "9.2.18",
            "firewall_status": "disabled/running",
            "iptables_input_policy": "ACCEPT",
            "listening_ports": [22, 111, 3128, 8006],
            "single_disk_rpool": "nvme-Lexar_SSD_NM620_256GB_PCR121R002848P1109-part3",
            "pbs_ip": "10.10.10.32",
            "pbs_port": 8007,
            "pbs_reachable": False,
            "static_snapshots_count": 18,
            "vzdump_cron_jobs": 0,
            "nfs_permissions": "0777",
        },
        "containers": {
            "total": 18,
            "active": [100, 101, 102, 103, 111, 113, 114, 115, 117, 118, 119, 121],
            "stopped": [105, 116, 120, 140, 141, 201],
            "privileged_containers": [105],
            "ct_105": {
                "name": "unifi-os-server",
                "unprivileged": 0,
                "shadow_root_password": "",  # root:: (empty password)
                "device_allow": "a",
                "capabilities_dropped": [],
            },
            "ssh_root_password_auth_containers": [
                101, 102, 111, 113, 114, 115, 117, 118, 119, 121
            ],
            "docker_in_lxc": [113],
        },
        "traefik": {
            "whitelisted_subnets": ["112.135.0.0/16"],
            "crowdsec_whitelisted_subnets": ["112.135.0.0/16", "112.134.0.0/16"],
            "unauthenticated_public_routes": ["bazarr.yaml"],
            "insecure_skip_verify_services": [
                "local-proxmox.yaml", "local-pbs.yaml", "local-unraid.yaml"
            ],
            "config_drift_untracked_public_files": [
                "qbittorrent.yaml", "prowlarr.yaml", "radarr.yaml", "sonarr.yaml", "n8n.yaml"
            ],
        },
        "secrets": {
            "env_keys": [
                "CF_API_TOKEN", "CROWDSEC_BOUNCER_API_KEY", "DASHBOARD_AUTH_HASH"
            ],
            "git_leak_commits": ["ec6edcd", "8f13ca9"],
            "leaked_test_user": "traefiktest",
        },
    }
