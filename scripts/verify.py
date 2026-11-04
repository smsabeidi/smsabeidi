#!/usr/bin/env python3
"""Clone my public repositories, run their checks, and record what happened.

Nothing in this file writes to the page. build.py prints whatever this measures,
including failures, so the only way to change a number on the profile is to change
the code it came from.

    python3 scripts/verify.py                    run everything
    python3 scripts/verify.py --only hft mslc    run some of it
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/verification.json"
OWNER = "smsabeidi"
PLAIN = {**os.environ, "NO_COLOR": "1", "FORCE_COLOR": "0", "CI": "1"}

# Files the README deep-links to. If one moves, the link check fails here first.
EVIDENCE = {
    "careOS": (
        "supabase/migrations/0003_audit_chain.sql",
        "supabase/tests/database/003_append_only.sql",
        "supabase/tests/database/004_audit_chain.sql",
        "supabase/tests/database/002_rls_matrix.sql",
        "scripts/gen-policies.sh",
    ),
    "hft": (
        "scripts/run_falsification.py",
        "scripts/run_synthetic_check.py",
        "scripts/run_power_check.py",
        "reports/rounds.log",
    ),
    "vision-aid": ("tests/api-route.test.ts", "tests/model-analysis.test.ts", "tests/safety.test.ts", "tests/resilience.test.ts"),
    "mslc": ("src/lib/domain.ts",),
}


def run(command: str, cwd: Path, timeout: int = 900) -> tuple[int, str]:
    try:
        done = subprocess.run(command, cwd=cwd, shell=True, env=PLAIN, timeout=timeout, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    return done.returncode, done.stdout


def clone(repo: str, workdir: Path) -> Path:
    target = workdir / repo
    code, output = run(f"git clone --quiet --depth 1 https://github.com/{OWNER}/{repo}.git {target}", workdir, 300)
    if code:
        raise RuntimeError(output)
    return target


def commit_of(repo: Path) -> str:
    return run("git rev-parse --short HEAD", repo)[1].strip()


def careos_pgtap(repo: Path) -> dict:
    """The real compliance suite on a real Postgres, including the insider test."""
    code, output = run("supabase --version", repo)
    if code:
        return {"status": "skipped", "why": "supabase CLI not installed"}
    code, output = run("supabase db start", repo, 900)
    if code:
        return {"status": "error", "why": output[-400:]}
    code, output = run("supabase test db", repo, 900)
    run("supabase stop --no-backup", repo, 120)
    found = re.search(r"Files=(\d+),\s*Tests=(\d+)", output)
    if not found:
        return {"status": "error", "why": output[-400:]}
    passed = code == 0 and "Result: PASS" in output
    migrations = len(list((repo / "supabase/migrations").glob("*.sql")))
    return {"status": "pass" if passed else "fail", "files": int(found[1]), "tests": int(found[2]), "migrations": migrations, "commit": commit_of(repo)}


def hft_tests(repo: Path) -> dict:
    code, output = run("python3 -m pytest -q -o addopts= --tb=line -p no:cacheprovider", repo, 300)
    passed = re.search(r"(\d+) passed", output)
    failed = re.search(r"(\d+) failed", output)
    if not passed and not failed:
        return {"status": "error", "why": output[-400:]}
    return {"status": "fail" if code else "pass", "tests": int(passed[1]) if passed else 0, "failed": int(failed[1]) if failed else 0, "commit": commit_of(repo)}


def t_from(output: str) -> float | None:
    found = re.findall(r"t=(-?\d+\.\d+)", output)
    return float(found[-1]) if found else None


def hft_falsification(repo: Path) -> dict:
    """A strategy with no edge has to lose money after costs."""
    code, output = run("python3 scripts/run_falsification.py", repo, 300)
    return {"status": "pass" if code == 0 and "GATE PASSED" in output else "fail", "t": t_from(output)}


def hft_noise(repo: Path) -> dict:
    """Real strategy families have to fail on random walks."""
    code, output = run("python3 scripts/run_synthetic_check.py", repo, 600)
    return {"status": "pass" if code == 0 and "FALSIFICATION PASSED" in output else "fail"}


def hft_power(repo: Path) -> dict:
    """A planted edge has to be found, or the gates are just rejecting everything."""
    code, output = run("python3 scripts/run_power_check.py", repo, 300)
    return {"status": "pass" if code == 0 and "POWER CHECK PASSED" in output else "fail", "t": t_from(output)}


def hft_rounds(repo: Path) -> list[dict]:
    """Latest result for every strategy in the append-only research log."""
    latest: dict[str, dict] = {}
    for line in (repo / "reports/rounds.log").read_text().splitlines():
        fields = dict(re.findall(r"(\w+)=(\S+)", line))
        if "family" not in fields:
            continue
        latest[fields["family"]] = {
            "family": fields["family"],
            "date": line[:10],
            "t": float(fields["t"]) if "t" in fields else None,
            "stability": float(fields["stability"]) if "stability" in fields else None,
            "result": fields["result"],
        }
    return list(latest.values())


def visionaid_tests(repo: Path) -> dict:
    code, output = run("npm ci --ignore-scripts --no-audit --no-fund", repo, 600)
    if code:
        return {"status": "error", "why": output[-400:]}
    code, output = run("npm test", repo, 300)
    passed, failed = re.search(r"# pass (\d+)", output), re.search(r"# fail (\d+)", output)
    if not passed:
        return {"status": "error", "why": output[-400:]}
    return {"status": "fail" if code else "pass", "tests": int(passed[1]), "failed": int(failed[1]) if failed else 0, "commit": commit_of(repo)}


def mslc_tests(repo: Path) -> dict:
    code, output = run("npm ci --ignore-scripts --no-audit --no-fund", repo, 600)
    if code:
        return {"status": "error", "why": output[-400:]}
    code, output = run("npx vitest run", repo, 300)
    passed = re.search(r"Tests\s+(?:\d+ failed \| )?(\d+) passed", output)
    if not passed:
        return {"status": "error", "why": output[-400:]}
    return {"status": "fail" if code else "pass", "tests": int(passed[1]), "commit": commit_of(repo)}


CHECKS = {
    "careos_pgtap": ("careOS", careos_pgtap),
    "hft_tests": ("hft", hft_tests),
    "hft_falsification": ("hft", hft_falsification),
    "hft_noise": ("hft", hft_noise),
    "hft_power": ("hft", hft_power),
    "visionaid_tests": ("vision-aid", visionaid_tests),
    "mslc_tests": ("mslc", mslc_tests),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", choices=sorted(EVIDENCE), help="repositories to check")
    args = parser.parse_args()
    wanted = set(args.only or EVIDENCE)

    previous = json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {"checks": {}, "rounds": []}
    checks, rounds, missing = dict(previous["checks"]), previous["rounds"], []

    with tempfile.TemporaryDirectory() as scratch:
        workdir = Path(scratch)
        repos = {name: clone(name, workdir) for name in wanted}
        for name, repo in repos.items():
            missing += [f"{name}/{path}" for path in EVIDENCE[name] if not (repo / path).exists()]
        if "hft" in repos:
            rounds = hft_rounds(repos["hft"])
        for key, (name, check) in CHECKS.items():
            if name not in repos:
                continue
            result = check(repos[name])
            print(f"{key}: {result}", flush=True)
            # A check that couldn't run keeps its old numbers for the record but loses its pass.
            checks[key] = result if result["status"] in ("pass", "fail") else {**checks.get(key, {}), **result}

    checks["evidence_links"] = {"status": "fail" if missing else "pass", "links": sum(len(v) for v in EVIDENCE.values()), "missing": missing}
    report = {"ran_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "checks": checks, "rounds": rounds}
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
