#!/usr/bin/env python3
"""Automated Test Runner for Stark-Lab Homelab Security Audit Verification Suite.
Executes Tier 1 through Tier 4 test suites and outputs structured audit telemetry.
"""

import sys
from pathlib import Path
import pytest

TESTS_DIR = Path(__file__).resolve().parent


def main():
    print("=" * 80)
    print("STARK-LAB HOMELAB SECURITY AUDIT: E2E AUTOMATED VERIFICATION SUITE")
    print("=" * 80)
    print("Executing 4-Tier Test Architecture:")
    print("  - Tier 1: Feature Coverage (Host, Containers, Traefik, Secrets, Storage)")
    print("  - Tier 2: Boundary & Corner Cases (Empty Shadow, CIDR /16, Unauth, CORS, TLS)")
    print("  - Tier 3: Cross-Feature Interactions (Hairpin Bypass, CrowdSec, Plex Proxy)")
    print("  - Tier 4: Real-World Scenario Probes (WAN Simulation, Live API, Lateral Path)")
    print("=" * 80)

    args = [
        str(TESTS_DIR),
        "-v",
        "--tb=short",
        "-rA",
    ]

    retcode = pytest.main(args)
    if retcode == 0:
        print("\n" + "=" * 80)
        print("ALL SECURITY AUDIT VERIFICATION TESTS PASSED SUCCESSFULLY.")
        print("Findings and security assertions across R1 to R6 are verified.")
        print("=" * 80)
    else:
        print(f"\n[!] Test suite completed with exit code: {retcode}", file=sys.stderr)

    sys.exit(retcode)


if __name__ == "__main__":
    main()
