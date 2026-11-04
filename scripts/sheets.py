"""The printed sheets on the profile page. Each returns one complete SVG string.

Every sheet has a wide layout and a phone layout, and every number comes from
data/verification.json or data/contributions.json. Nothing is typed in here that
a job could measure instead.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime

from printer import BAR, LINE, base_css, banner, document, layer, paper, text

WIDE, PHONE = 860, 400
INK_PITCH = 0.6  # Plex Mono advances 0.6em per character


def baseline(row: int) -> int:
    """Baseline of a printed line, so text sits on the bars like real output."""
    return row * LINE + 13


def job_of(verification: dict) -> str:
    ran = datetime.fromisoformat(verification["ran_at"].replace("Z", "+00:00"))
    return f"{ran:%y%j}"


def stamp(verification: dict) -> str:
    return verification["ran_at"][:16].replace("T", " ") + " UTC"


def grouped(number: int) -> str:
    return f"{number:,}"


def checks_failed(verification: dict) -> int:
    return sum(1 for check in verification["checks"].values() if check["status"] == "fail")


def checks_ran(verification: dict) -> int:
    return sum(1 for check in verification["checks"].values() if check["status"] in ("pass", "fail"))


def report_lines(verification: dict) -> list[tuple[str, str, str, bool]]:
    """(repo, claim, result, in_red) for the hero. Red marks a loss on the ledger."""
    checks = verification["checks"]
    rounds = verification["rounds"]
    killed = sum(1 for r in rounds if r["result"].startswith("FAIL"))

    def measured(key: str, render) -> tuple[str, bool]:
        check = checks.get(key, {"status": "skipped"})
        if check["status"] == "fail":
            return "FAILED", True
        return (render(check), False) if check["status"] == "pass" else ("pending", False)

    tests = lambda check: f"{grouped(check['tests'])} ok"  # noqa: E731
    t_stat = lambda check: f"t = {check['t']:+.2f}"  # noqa: E731
    return [
        ("careos", "compliance suite, insider test", *measured("careos_pgtap", tests)),
        ("hft", "zero-edge strategy loses", *measured("hft_falsification", t_stat)),
        ("hft", "planted edge is found", *measured("hft_power", t_stat)),
        ("hft", "my strategies it has killed", f"{killed} of {len(rounds)}", True),
        ("visionaid", "fail-closed AI boundary", *measured("visionaid_tests", tests)),
    ]


def header(verification: dict, page: int, x: float, right: float, y: float) -> str:
    job = job_of(verification)
    return text(x, y, f"JOB {job}   USER SMSABEIDI", "s strong") + text(right, y, f"{stamp(verification)}   PAGE {page}", "s end")


TYPE_CSS = ".s{font-size:10px}.end{text-anchor:end}.ar text{font-size:var(--art)}.ar.b text{font-weight:600}.banner text{font-weight:600}"


def feed(height: int, seconds: float = 4.2) -> str:
    """The one big motion on the page: the sheet advances out of the printer a line at a time."""
    return (
        f"@keyframes feed{{from{{transform:translateY({height}px)}}to{{transform:none}}}}"
        f".sheet{{animation:feed {seconds}s steps({height // 8},end) both}}"
    )


CALM = "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"


def portrait_layers(portrait: dict, x: float, y: float, advance: float, line: float) -> str:
    light = layer(portrait["regular"], x, y, advance, line)
    heavy = layer(portrait["bold"], x, y, advance, line) + layer(portrait["over"], x, y, advance, line)
    return f'<g class="ar">{light}</g><g class="ar b">{heavy}</g>'


def hero(wide: bool, theme: dict, profile: dict, verification: dict, portrait: dict) -> str:
    lines = report_lines(verification)
    failed = checks_failed(verification)
    summary = f"{checks_ran(verification)} checks ran. {failed} failed."
    job = job_of(verification)
    title = f'{profile["name"]}: {profile["thesis"]}'
    desc = (
        f'ASCII portrait of {profile["name"]} printed on green-bar paper beside his name and a make verify report. '
        + " ".join(f"{repo}: {claim}, {result}." for repo, claim, result, _ in lines)
        + f" {summary}"
    )

    if wide:
        width, height = WIDE, 540
        left, right, column = 40, 820, 432
        art = portrait_layers(portrait, left, 48, 2.4, 4)
        body = [
            header(verification, 1, left, right, baseline(1)),
            art,
            banner("MUHAMMED", column, 62, 8.2, 10),
            banner("SALIM", column, 142, 8.2, 10),
        ]
        body += [text(column, baseline(12 + i), line, "t") for i, line in enumerate(profile["about"])]
        body += [text(column, 320, profile["thesis_lines"][0], "h"), text(column, 346, profile["thesis_lines"][1], "h")]
        first = 20
        body.append(text(column, baseline(first), "$ make verify", "t strong"))
        for i, (repo, claim, result, red) in enumerate(lines, first + 1):
            cls = "t red" if red else "t"
            body += [text(column, baseline(i), f"{repo:<10}{claim}", cls), text(right, baseline(i), result, cls + " end")]
        body.append(text(column, baseline(first + 6), summary, "t strong red" if failed else "t strong"))
        body.append(text(left, baseline(28), f"*** END OF JOB {job} ***", "s strong"))
        css = "--art:4px;--t:12.2px;--h:22px;--b:13.67px"
        margin = 28
    else:
        width, left, right = PHONE, 26, 374
        cell = (right - left) / 47
        advance = (right - left) / portrait["cols"]
        art_y = 216
        art_h = portrait["rows"] * advance / 0.6
        y = art_y + art_h + 8
        body = [
            header(verification, 1, left, right, baseline(1)),
            banner("MUHAMMED", left, 64, cell, 9.2),
            banner("SALIM", left, 138, cell, 9.2),
            portrait_layers(portrait, left, art_y, advance, advance / 0.6),
        ]
        for line in profile["about"]:
            body.append(text(left, y, line, "t"))
            y += LINE
        y += 16
        for line in profile["thesis_lines"]:
            body.append(text(left, y, line, "h"))
            y += 26
        y += 14
        body.append(text(left, y, "$ make verify", "t strong"))
        for repo, claim, result, red in lines:
            y += LINE
            cls = "t red" if red else "t"
            body += [text(left, y, f"{repo:<10}{claim}", cls), text(right, y, result, cls + " end")]
        y += LINE
        body.append(text(left, y, summary, "t strong red" if failed else "t strong"))
        y += LINE * 2
        body.append(text(left, y, f"*** END OF JOB {job} ***", "s strong"))
        height = (int(y + LINE) // BAR + 1) * BAR
        css = f"--art:{advance / INK_PITCH:.3f}px;--t:11.1px;--h:21px;--b:{cell / INK_PITCH:.2f}px"
        margin = 16

    style = (
        base_css(theme) + TYPE_CSS + f"svg{{{css}}}.t{{font-size:var(--t)}}.h{{font-size:var(--h);font-weight:600}}"
        ".banner text{font-size:var(--b)}" + feed(height) + CALM
    )
    sheet = f'<g class="sheet">{paper(width, height, theme, margin)}{"".join(body)}</g>'
    return document(width, height, style, sheet, title, desc)


# The ledger sheet. A worked example of audit.compute_chain with real SHA-256,
# so anyone can recompute these digests from the migration.
TENANT = "aaaaaaaa-0000-0000-0000-000000000001"
EVENTS = (
    (41, "2026-11-02T14:03:11.000000Z", "form.signed", "form", '{"form": 17}'),
    (42, "2026-11-02T14:09:40.000000Z", "visit.clock_in", "visit", '{"visit": 8}'),
    (43, "2026-11-02T15:21:05.000000Z", "plan.amended", "plan", '{"visits": 2}'),
    (44, "2026-11-02T16:47:52.000000Z", "form.signed", "form", '{"form": 18}'),
    (45, "2026-11-02T17:30:18.000000Z", "visit.clock_out", "visit", '{"visit": 8}'),
)
TAMPERED_ID, TAMPERED_PAYLOAD = 43, '{"visits": 4}'


def event_digest(previous: bytes | None, event: tuple, payload: str | None = None) -> bytes:
    event_id, occurred, action, entity, stored = event
    fields = (TENANT, str(event_id), occurred, "", "system", action, entity, "", payload or stored)
    return hashlib.sha256((previous or b"\x00") + "|".join(fields).encode()).digest()


def chain() -> list[dict]:
    rows, previous = [], None
    for event in EVENTS:
        digest = event_digest(previous, event)
        rows.append({"id": event[0], "action": event[2], "payload": event[4], "prev": previous, "hash": digest})
        previous = digest
    return rows


def hex8(value: bytes | None) -> str:
    return value.hex()[:8] if value else "00"


def timed(name: str, start: float, end: float = 99.0) -> str:
    """Keyframes that show an element between two points of the loop, in percent."""
    return f"@keyframes {name}{{0%,{start}%{{opacity:0}}{start + 0.1}%,{end}%{{opacity:1}}{end + 0.1}%,100%{{opacity:0}}}}.{name}{{animation:{name} 15s infinite}}"


def ledger(wide: bool, theme: dict, verification: dict) -> str:
    rows = chain()
    tampered = next(i for i, row in enumerate(rows) if row["id"] == TAMPERED_ID)
    recomputed = event_digest(rows[tampered]["prev"], EVENTS[tampered], TAMPERED_PAYLOAD)
    width = WIDE if wide else PHONE
    left, right, margin = (40, 820, 28) if wide else (26, 374, 16)
    pitch = (12.2 if wide else 11.1) * INK_PITCH

    columns = (
        {"id": 0, "action": 6, "payload": 24, "prev": 41, "hash": 52, "again": 63, "verify": 74}
        if wide
        else {"id": 0, "payload": 4, "hash": 19, "again": 29, "verify": 40}
    )
    at = lambda name: left + columns[name] * pitch  # noqa: E731
    names = {"id": "ID", "action": "ACTION", "payload": "PAYLOAD", "prev": "PREV_HASH", "hash": "HASH", "again": "RECOMPUTED", "verify": "VERIFY"}

    body = [header(verification, 2, left, right, baseline(1))]
    insider = "-- as superuser: disable the trigger, edit one row, enable the trigger" if wide else "-- as superuser: trigger off, edit one row, trigger on"
    body.append(text(left, baseline(3), insider, "t red note"))
    head = 5
    body += [text(at(name), baseline(head), names[name], "t strong") for name in columns]
    css = timed("note", 7)

    sweep = {}  # row index -> animation class, so the walk reveals one row at a time
    for i, row in enumerate(rows):
        y = baseline(head + 1 + i)
        body.append(text(at("id"), y, str(row["id"]), "t"))
        if wide:
            body.append(text(at("action"), y, row["action"], "t"))
            body.append(text(at("prev"), y, hex8(row["prev"]), "t"))
        if i == tampered:
            body.append(text(at("payload"), y, row["payload"], "t was"))
            body.append(text(at("payload"), y, TAMPERED_PAYLOAD, "t red now"))
        else:
            body.append(text(at("payload"), y, row["payload"], "t"))
        body.append(text(at("hash"), y, hex8(row["hash"]), "t"))
        if i <= tampered:
            name = f"w{i}"
            sweep[i] = name
            css += timed(name, 32 + i * 9)
            again = recomputed if i == tampered else row["hash"]
            verdict, cls = ("FAIL", "t red strong") if i == tampered else ("ok", "t")
            body.append(text(at("again"), y, hex8(again), f"{cls} {name}"))
            body.append(text(at("verify"), y, verdict, f"{cls} {name}"))

    query = head + 7
    done = 32 + (tampered + 1) * 9
    body.append(text(left, baseline(query), "SQL> select ok, first_bad_id from audit.verify_chain(:tenant);" if wide else "SQL> select * from audit.verify_chain(:tenant);", "t strong"))
    body.append(text(left, baseline(query + 1), " ok | first_bad_id", "t res"))
    body.append(text(left, baseline(query + 2), f" f  | {TAMPERED_ID:>12}", "t red strong res"))
    body.append(text(left, baseline(query + 4), "stored hash covers the old payload, so the row can't pass as original." if wide else "the stored hash covers the old payload.", "t res"))

    css += timed("res", done)
    css += "@keyframes was{0%,13.9%{opacity:1}14%,100%{opacity:0}}.was{animation:was 15s infinite;opacity:0}"
    css += "@keyframes now{0%,13.9%{opacity:0}14%,99%{opacity:1}99.1%,100%{opacity:0}}.now{animation:now 15s infinite}"
    height = (query + 6) * LINE
    height = (height // BAR + (1 if height % BAR else 0)) * BAR
    style = base_css(theme) + TYPE_CSS + f".t{{font-size:{12.2 if wide else 11.1}px}}" + css + CALM
    title = "Hash-chained audit ledger catches an insider edit"
    desc = (
        f"An audit table of five events. A superuser edits the payload of event {TAMPERED_ID}. "
        f"audit.verify_chain walks the chain, recomputes each SHA-256 hash, and reports ok false at first_bad_id {TAMPERED_ID}."
    )
    return document(width, height, style, paper(width, height, theme, margin) + "".join(body), title, desc)


def plot_axis(cols: int, low: float, high: float, labels: tuple[int, ...]) -> str:
    axis = [" "] * cols
    for value in labels:
        tag = f"{value:+d}" if value else "0"
        spot = round((value - low) / (high - low) * (cols - 1)) - len(tag) // 2
        for offset, ch in enumerate(tag):
            if 0 <= spot + offset < cols:
                axis[spot + offset] = ch
    return "".join(axis)


def plot_row(t: float | None, cols: int, low: float, high: float) -> tuple[str, str]:
    """A line-printer dot plot: '.' for the track, ':' at zero, '|' at the t = 2 gate."""
    track = ["."] * cols
    track[round((0 - low) / (high - low) * (cols - 1))] = ":"
    track[round((2 - low) / (high - low) * (cols - 1))] = "|"
    if t is None:
        return "".join(track), ""
    if t < low:
        mark, spot = "<", 0
    else:
        mark, spot = "#", round((min(t, high) - low) / (high - low) * (cols - 1))
    marks = [" "] * cols
    track[spot] = " "
    marks[spot] = mark
    return "".join(track), "".join(marks).rstrip()


def verdict_of(result: str) -> str:
    return "PASS" if result == "PASS" else "PASS?" if result.startswith("PASS") else "FAIL"


def gauntlet(wide: bool, theme: dict, verification: dict) -> str:
    checks = verification["checks"]
    rounds = sorted(verification["rounds"], key=lambda r: (r["t"] is None, r["t"] if r["t"] is not None else 0))
    width = WIDE if wide else PHONE
    left, right, margin = (40, 820, 28) if wide else (26, 374, 16)
    size = 12.2 if wide else 10.6
    pitch = size * INK_PITCH
    name_cols, cols = (30, 48) if wide else (28, 18)
    plot_x = left + name_cols * pitch
    t_x = plot_x + (cols + 8) * pitch
    low, high = (-8.0, 18.0)

    def row(y: int, name: str, t: float | None, stability: float | None, verdict: str, red: bool) -> str:
        track, marks = plot_row(t, cols, low, high)
        cls = "t red" if red else "t"
        y_px = baseline(y)
        out = [text(left, y_px, name[: name_cols - 1], cls), text(plot_x, y_px, track, "t pre")]
        if marks:
            out.append(text(plot_x, y_px, marks, "t strong red" if red else "t strong"))
        if wide:
            out.append(text(t_x, y_px, "n/a" if t is None else f"{t:+.2f}", cls + " end"))
            out.append(text(t_x + 7 * pitch, y_px, "" if stability is None else f"{stability:.0%}", cls + " end"))
        out.append(text(right, y_px, verdict, cls + " strong end" if not red else cls + " end"))
        return "".join(out)

    body = [header(verification, 3, left, right, baseline(1))]
    body.append(text(left, baseline(3), "SELF-TESTS", "t strong"))
    body.append(text(plot_x, baseline(3), plot_axis(cols, low, high, (-8, -4, 0, 4, 8, 12, 16) if wide else (-4, 4, 12)), "t pre"))
    if wide:
        body.append(text(t_x, baseline(3), "t", "t strong end"))
        body.append(text(t_x + 7 * pitch, baseline(3), "stab", "t strong end"))
    body.append(text(right, baseline(3), "VERDICT", "t strong end"))
    body.append(row(4, "zero edge must lose", checks["hft_falsification"].get("t"), None, "PASS", False))
    body.append(row(5, "planted edge must be found", checks["hft_power"].get("t"), None, "PASS", False))
    body.append(row(6, "noise must find nothing", None, None, "PASS", False))
    body.append(text(left, baseline(8), "STRATEGIES ON REAL DATA, FROM reports/rounds.log" if wide else "REAL DATA, reports/rounds.log", "t strong"))
    y = 9
    for entry in rounds:
        verdict = verdict_of(entry["result"])
        body.append(row(y, entry["family"], entry["t"], entry["stability"], verdict, verdict == "FAIL"))
        y += 1
    y += 1
    rule = (
        ("To pass: t >= 2 after costs, out of sample, >= 60% window stability, enough trades.", "A variant must also beat the strategy it came from.")
        if wide
        else ("To pass: t >= 2 after costs, out of sample,", ">= 60% stability, enough trades. A variant", "must also beat the strategy it came from.")
    )
    for line in rule:
        body.append(text(left, baseline(y), line, "t"))
        y += 1
    height = (y + 2) * LINE
    height = (height // BAR + (1 if height % BAR else 0)) * BAR
    style = base_css(theme) + TYPE_CSS + f".t{{font-size:{size}px}}"
    killed = sum(1 for r in rounds if r["result"].startswith("FAIL"))
    title = f"Research gauntlet: {killed} of {len(rounds)} strategies rejected"
    desc = "Line-printer dot plot of out-of-sample t-statistics. " + " ".join(
        f'{r["family"]}: t {r["t"]}, {r["result"]}.' for r in rounds
    )
    return document(width, height, style, paper(width, height, theme, margin) + "".join(body), title, desc)


LEVELS = (".", ":", "+", "#", "@")


def contributions(wide: bool, theme: dict, verification: dict, data: dict) -> str:
    """The year as print density: each day one character, heavier for busier days."""
    width = WIDE if wide else PHONE
    left, right, margin = (40, 820, 28) if wide else (26, 374, 16)
    days = data["days"]
    weeks = [days[i : i + 7] for i in range(0, len(days), 7)]
    weeks = weeks[-53:] if wide else weeks[-27:]
    pitch = (right - left) / len(weeks)
    line = 15 if wide else 13

    body = [header(verification, 4, left, right, baseline(1))]
    months, last = [], None
    for column, week in enumerate(weeks):
        month = date.fromisoformat(week[0]["date"]).strftime("%b")
        if month != last and column < len(weeks) - 2:
            months.append(text(left + column * pitch, baseline(3), month, "s pre"))
        last = month
    body += months
    rows = {level: [[" "] * len(weeks) for _ in range(7)] for level in range(5)}
    for column, week in enumerate(weeks):
        for row, day in enumerate(week):
            rows[day["level"]][row][column] = LEVELS[day["level"]]
    top = baseline(4)
    for level, grid in rows.items():
        cls = "pre" if level == 0 else "heavy" if level >= 3 else ""
        cells = "".join(
            f'<text x="{left + column * pitch:.1f}" y="{top + row * line}">{grid[row][column]}</text>'
            for row in range(7)
            for column in range(len(weeks))
            if grid[row][column] != " "
        )
        body.append(f'<g class="grid {cls}">{cells}</g>')
    y = top + 7 * line + 14
    total = f'{grouped(data["total"])} contributions in the last year. Longest streak {data["longest_streak"]} days.'
    body.append(text(left, y, total if wide else f'{grouped(data["total"])} contributions in the last year.', "t strong"))
    if wide:
        body.append(text(right, y, "less . : + # @ more", "s pre end"))
    height = ((y + 22) // BAR + 1) * BAR
    style = base_css(theme) + TYPE_CSS + ".t{font-size:12.2px}.grid text{font-size:13px}.grid.heavy text{font-weight:600}.grid.pre text{fill:" + theme["preprint"] + "}"
    return document(width, height, style, paper(width, height, theme, margin) + "".join(body), "Contribution graph", f'{data["total"]} contributions in the last year, printed as a density grid.')
