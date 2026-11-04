#!/usr/bin/env python3
"""Fetch the public contribution calendar. No token, no third-party stats service.

Reads the same HTML fragment the profile page loads and writes
data/contributions.json with every day's count and GitHub's 0-4 level.
"""
from __future__ import annotations

import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USER = json.loads((ROOT / "profile.json").read_text())["user"]


class Calendar(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.days: dict[str, dict] = {}
        self.tips: dict[str, str] = {}
        self._tip: str | None = None

    def handle_starttag(self, tag: str, attrs: list) -> None:
        attr = dict(attrs)
        if tag == "td" and "ContributionCalendar-day" in (attr.get("class") or "") and attr.get("data-date"):
            self.days[attr.get("id", "")] = {"date": attr["data-date"], "level": int(attr.get("data-level") or 0)}
        elif tag == "tool-tip":
            self._tip = attr.get("for")

    def handle_data(self, data: str) -> None:
        if self._tip:
            self.tips[self._tip] = self.tips.get(self._tip, "") + data

    def handle_endtag(self, tag: str) -> None:
        if tag == "tool-tip":
            self._tip = None


def parse(html: str) -> list[dict]:
    calendar = Calendar()
    calendar.feed(html)
    days = []
    for cell, day in calendar.days.items():
        count = re.match(r"\s*([\d,]+) contribution", calendar.tips.get(cell, ""))
        days.append({**day, "count": int(count[1].replace(",", "")) if count else 0})
    return sorted(days, key=lambda d: d["date"])


def longest_streak(days: list[dict]) -> int:
    best = run = 0
    for day in days:
        run = run + 1 if day["count"] else 0
        best = max(best, run)
    return best


def main() -> None:
    request = urllib.request.Request(f"https://github.com/users/{USER}/contributions", headers={"User-Agent": "profile-printout"})
    with urllib.request.urlopen(request, timeout=30) as response:
        days = parse(response.read().decode())
    if not days:
        raise SystemExit("no calendar cells found; GitHub's markup may have changed")
    # GitHub's grid starts on a Sunday; keep whole weeks so columns stay aligned.
    report = {"total": sum(d["count"] for d in days), "longest_streak": longest_streak(days), "days": days}
    (ROOT / "data/contributions.json").write_text(json.dumps(report, separators=(",", ":")) + "\n")
    print(f'{report["total"]} contributions over {len(days)} days')


if __name__ == "__main__":
    main()
