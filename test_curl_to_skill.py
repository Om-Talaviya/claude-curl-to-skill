#!/usr/bin/env python3
"""Minimal regression test — run before every change: python3 test_curl_to_skill.py"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "skills"


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    failures = []

    # 1. Resend — Bearer + flat JSON body -> should succeed
    r = run([sys.executable, "curl_to_skill.py", "--file", "examples/resend.curl", "--out", str(OUT)])
    if r.returncode != 0 or not (OUT / "resend-create-email" / "SKILL.md").exists():
        failures.append(f"Resend case failed: {r.stderr}")

    # 2. GitHub — Bearer + flat JSON body, extra headers/flags -> should succeed
    r = run([sys.executable, "curl_to_skill.py", "--file", "examples/github.curl", "--out", str(OUT)])
    if r.returncode != 0 or not (OUT / "github-create-issue" / "SKILL.md").exists():
        failures.append(f"GitHub case failed: {r.stderr}")

    # 3. Stripe — Basic auth + form body -> should be REJECTED, not silently mangled
    r = run([sys.executable, "curl_to_skill.py", "--file", "examples/stripe.curl", "--out", str(OUT)])
    if r.returncode == 0:
        failures.append("Stripe case: expected a rejection (Basic auth), but it succeeded")
    if "Basic auth" not in r.stderr:
        failures.append(f"Stripe case: rejection message didn't mention Basic auth: {r.stderr}")

    # 4. Generated runner script: env-var guard actually works
    r = run([sys.executable, str(OUT / "resend-create-email" / "scripts" / "run.py"),
              "--from", "a@b.com", "--to", "c@d.com", "--subject", "hi"])
    if r.returncode == 0 or "RESEND_API_KEY" not in r.stderr:
        failures.append(f"Generated run.py didn't guard on missing API key: {r.stderr}")

    if failures:
        print("FAILED:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print(f"All {4} checks passed.")


if __name__ == "__main__":
    main()
