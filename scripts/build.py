#!/usr/bin/env python3
"""Print the page: profile.json + measurements + README.template.md -> README.md + assets/.

Standard library only, so the weekly job has nothing to install. SVG names carry a
content hash because GitHub caches images hard; a changed sheet gets a new URL.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import sheets
from printer import THEMES

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


def load(name: str) -> dict | None:
    path = ROOT / name
    return json.loads(path.read_text()) if path.exists() else None


def picture(files: dict[str, str], alt: str, href: str, base: str) -> str:
    """Theme- and width-aware image, opening the sheet's evidence when clicked.

    The <p> keeps this one HTML block; left bare, Markdown splits the <picture> apart.
    Raw URLs because the profile page lives at github.com/<user>, where a relative
    srcset would resolve against the wrong path.
    """
    return (
        f'<p><a href="{href}"><picture>\n'
        f'  <source media="(max-width: 767px) and (prefers-color-scheme: dark)" srcset="{base}/{files["phone-dark"]}">\n'
        f'  <source media="(max-width: 767px)" srcset="{base}/{files["phone-light"]}">\n'
        f'  <source media="(prefers-color-scheme: dark)" srcset="{base}/{files["wide-dark"]}">\n'
        f'  <img src="{base}/{files["wide-light"]}" alt="{alt}" width="100%">\n'
        "</picture></a></p>"
    )


def write_sheet(name: str, render) -> dict[str, str]:
    """Render a sheet in all four variants and return their hashed file names."""
    files = {}
    for size in ("wide", "phone"):
        for theme_name, theme in THEMES.items():
            svg = render(size == "wide", theme)
            digest = hashlib.sha256(svg.encode()).hexdigest()[:8]
            file_name = f"{name}-{size}-{theme_name}-{digest}.svg"
            (ASSETS / file_name).write_text(svg)
            files[f"{size}-{theme_name}"] = file_name
    return files


def lookup(context: dict, dotted: str) -> str:
    value = context
    for key in dotted.split("."):
        if key not in value:
            return "n/a"  # measured on the next CI run
        value = value[key]
    return f"{value:,}" if isinstance(value, int) else str(value)


def main() -> None:
    profile = load("profile.json")
    verification = load("data/verification.json")
    portrait = load("data/portrait.json")
    calendar = load("data/contributions.json")

    ASSETS.mkdir(exist_ok=True)
    for stale in ASSETS.glob("*.svg"):
        stale.unlink()

    user = profile["user"]
    rounds = verification["rounds"]
    killed = sum(1 for r in rounds if r["result"].startswith("FAIL"))
    alive = [r for r in rounds if not r["result"].startswith("FAIL")]
    summary = {"rounds": {"total": len(rounds), "killed": killed, "alive": len(alive)}, "date": verification["ran_at"][:10]}

    pages = {
        "hero": (
            lambda wide, theme: sheets.hero(wide, theme, profile, verification, portrait),
            f'{profile["name"]}: {profile["thesis"]} ASCII portrait on green-bar printer paper beside a make verify report measured by CI.',
            f'https://github.com/{user}/{user}/blob/main/data/verification.json',
        ),
        "ledger": (
            lambda wide, theme: sheets.ledger(wide, theme, verification),
            "Animated audit table. A superuser edits row 43; verify_chain recomputes each SHA-256 hash and reports first_bad_id 43.",
            f"https://github.com/{user}/careOS/blob/main/supabase/tests/database/004_audit_chain.sql",
        ),
        "gauntlet": (
            lambda wide, theme: sheets.gauntlet(wide, theme, verification),
            f"Printed dot plot of out-of-sample t-statistics: {killed} of {len(rounds)} strategy variants rejected. Data: reports/rounds.log.",
            f"https://github.com/{user}/hft/blob/main/reports/rounds.log",
        ),
    }
    if calendar:
        pages["contributions"] = (
            lambda wide, theme: sheets.contributions(wide, theme, verification, calendar),
            f'Contribution graph printed as character density: {calendar["total"]:,} contributions in the last year.',
            f"https://github.com/{user}",
        )

    branch = os.environ.get("GITHUB_REF_NAME") or subprocess.run(
        ("git", "branch", "--show-current"), cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    base = f"https://raw.githubusercontent.com/{user}/{user}/{branch or 'main'}/assets"
    blocks = {name: picture(write_sheet(name, render), alt, href, base) for name, (render, alt, href) in pages.items()}

    context = {**verification, "summary": summary, "profile": profile}

    def fill(match: re.Match) -> str:
        token = match[1]
        if token.startswith("sheet:"):
            return blocks.get(token[6:], "")
        return lookup(context, token)

    template = (ROOT / "README.template.md").read_text()
    (ROOT / "README.md").write_text(re.sub(r"\{\{([\w.:]+)\}\}", fill, template))
    print(f"printed {len(list(ASSETS.glob('*.svg')))} sheets")


if __name__ == "__main__":
    main()
