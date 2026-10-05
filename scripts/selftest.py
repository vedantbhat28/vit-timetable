#!/usr/bin/env python3
"""Offline checks for the validator and diff (no network, no API key). Run: python scripts/selftest.py"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import import_timetables as it  # noqa: E402

# (weekday, hour, code, type, batch, room, initials) - CSSE-C grid, W.E.F. 15-09-2026
G = [
    (1, 11, "ES26108A", "Theory", None, "E215", "SB"), (1, 12, "ES26101", "Theory", None, "E215", "MBD"),
    (1, 14, "ES26105", "Lab", "B1", "D306", "PSA"), (1, 14, "ES26104", "Lab", "B2", "E102", "AJS"),
    (1, 14, "ES26104", "Lab", "B3", "E112", "OBW"), (1, 15, "ES26105", "Lab", "B1", "D306", "PSA"),
    (1, 15, "ES26104", "Lab", "B2", "E102", "AJS"), (1, 15, "ES26104", "Lab", "B3", "E112", "OBW"),
    (1, 16, "ES26101", "Tutorial", "B1", "D115", "MBD"),
    (2, 13, "ES26101", "Theory", None, "E303", "MBD"), (2, 14, "ES26109", "Theory", None, "E303", "APK"),
    (2, 16, "ES26105", "Theory", None, "E303", "KLP"), (2, 17, "ES26106", "Theory", None, "E303", "DSP"),
    (3, 10, "ES26105", "Lab", "B2", "D307", "KLP"), (3, 10, "ES26104", "Lab", "B3", "D107", "OBW"),
    (3, 11, "ES26105", "Lab", "B2", "D307", "KLP"), (3, 11, "ES26104", "Lab", "B3", "D107", "OBW"),
    (3, 13, "ES26101", "Theory", None, "E311", "MBD"), (3, 14, "ES26103", "Theory", None, "E311", "NbK"),
    (3, 15, "ES26103", "Theory", None, "E311", "NbK"), (3, 16, "ES26109", "Theory", None, "E311", "APK"),
    (4, 10, "ES26104", "Lab", "B2", "E402", "AJS"), (4, 10, "ES26104", "Lab", "B1", "E112", "VsS"),
    (4, 11, "ES26104", "Lab", "B2", "E402", "AJS"), (4, 11, "ES26104", "Lab", "B1", "E112", "VsS"),
    (4, 12, "ES26104", "Theory", None, "E216", "MMU"), (4, 14, "ES26106", "Theory", None, "E311", "DSP"),
    (4, 15, "ES26107", "Theory", None, "E311", "SLG"), (4, 16, "ES26105", "Theory", None, "E311", "KLP"),
    (4, 17, "ES26101", "Tutorial", "B3", "E310", "HVD"),
    (5, 13, "ES26108A", "Theory", None, "E310", "SB"), (5, 14, "ES26105", "Lab", "B3", "D307", "KLP"),
    (5, 14, "ES26104", "Lab", "B1", "E112", "JSK"), (5, 15, "ES26101", "Tutorial", "B2", "E302", "ABR"),
    (5, 15, "ES26105", "Lab", "B3", "D307", "KLP"), (5, 15, "ES26104", "Lab", "B1", "E112", "JSK"),
    (5, 16, "ES26104", "Theory", None, "E215", "MMU"),
]
LEG = [
    ("Visiting_06", "SB", "SIYA BOKIL", "ES26108A", "Language-English"),
    ("12390", "MBD", "Machindranath Bansilal Diwate", "ES26101", "Linear Algebra"),
    ("12418", "PSA", "PRIYANKA SWAPNIL AGNIHOTRI", "ES26105", "Basics of Engineering"),
    ("12403", "AJS", "ASHWINI JAGMOHAN SHINDE", "ES26104", "Programming for Engineers"),
    ("12409", "OBW", "ONKAR BHAUSAHEB WANVE", "ES26104", "Programming for Engineers"),
    ("20006", "APK", "MRS. APARNA PARAG KULKARNI", "ES26109", "Student Activity"),
    ("20470", "KLP", "KALPANA LAXMIKANT PARDESHI", "ES26105", "Basics of Engineering"),
    ("20338", "DSP", "MR. DHANANJAY SHANTARAM PAWAR", "ES26106", "Universal Human Values"),
    ("2001", "NbK", "NAVNATH B KALE", "ES26103", "Logic and Quantitative Aptitude 1"),
    ("3333", "VsS", "V1 SPB SPB", "ES26104", "Programming for Engineers"),
    ("11055", "MMU", "MAKARAND MADHUKAR UPKARE", "ES26104", "Programming for Engineers"),
    ("20422", "SLG", "MRS. SHRUTI LAXMIKANT GORE", "ES26107", "Indian Knowledge System"),
    ("20011", "HVD", "MS. HIMANI VENKATESH DESHPANDE", "ES26101", "Linear Algebra"),
    ("12392", "JSK", "Jyoti Sachin Kulkarni", "ES26104", "Programming for Engineers"),
    ("20465", "ABR", "DR. AVINASH BHANUDAS RAUT", "ES26101", "Linear Algebra"),
]


def fixture():
    return {
        "header": {"division_label": "CSSE-C", "year_label": "First Year", "program": "DESH-DESH",
                   "academic_year": "2026-27", "semester": 1, "version": "V1", "wef": "15-09-2026",
                   "to_date": "10-01-2027", "total_theory": 16, "total_lab": 18, "total_tutorial": 3,
                   "total_all": 37},
        "legend": [{"faculty_id": a, "initials": b, "faculty_name": c, "subject_code": d, "subject_name": e}
                   for a, b, c, d, e in sorted(LEG)],
        "sessions": [{"weekday": w, "start_time": f"{h:02d}:00", "end_time": f"{h + 1:02d}:00", "subject_code": c,
                      "session_type": t, "batch": b, "room": r, "faculty_initials": i}
                     for w, h, c, t, b, r, i in G],
    }


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        check.failed = True


check.failed = False

# 1. good extraction validates, names come from the legend
err, warn, rows, hdr = it.build_rows(fixture(), {}, {})
check("valid extraction has no errors", not err)
check("37 rows", len(rows) == 37)
psa = next(r for r in rows if r["faculty_initials"] == "PSA")
check("faculty id/name resolved from legend", (psa["faculty_id"], psa["faculty_name"]) == ("12418", "PRIYANKA SWAPNIL AGNIHOTRI"))
check("subject name from legend, not truncated grid text", psa["subject_name"] == "Basics of Engineering")
check("dates parsed", (hdr["effective_from"], hdr["effective_to"]) == ("2026-09-15", "2027-01-10"))
check("theory has no batch", all(r["batch"] is None for r in rows if r["session_type"] == "Theory"))

# 2. a dropped session is caught by the footer totals
d = fixture(); d["sessions"].pop(5)
err, *_ = it.build_rows(d, {}, {})
check("missing session -> totals error", any("totals" in e for e in err))

# 3. unknown initials are rejected unless the DB already knows them
d = fixture(); d["sessions"][0]["faculty_initials"] = "ZZZ"
err, *_ = it.build_rows(d, {}, {})
check("unknown initials rejected", any("ZZZ" in e for e in err))
err, *_ = it.build_rows(d, {"ZZZ": ("1", "SOME ONE")}, {})
check("DB fallback resolves them", not any("ZZZ" in e for e in err))

# 4. clash and bad-slot detection
d = fixture(); d["sessions"][1]["start_time"] = "11:00"; d["sessions"][1]["end_time"] = "12:00"
err, *_ = it.build_rows(d, {}, {})
check("clash detected", any("clash" in e for e in err))
d = fixture(); d["sessions"][0]["end_time"] = "13:00"
err, *_ = it.build_rows(d, {}, {})
check("2-hour block rejected (must be split per hour)", any("one hour" in e for e in err))

# 5. initials case-insensitive match keeps legend casing
d = fixture()
for s in d["sessions"]:
    if s["faculty_initials"] == "NbK":
        s["faculty_initials"] = "NBK"
err, _, rows, _ = it.build_rows(d, {}, {})
check("case-insensitive initials keep legend casing", not err and any(r["faculty_initials"] == "NbK" for r in rows))

# 6. diff: the Mon B1 lab teacher change is exactly two changed rows
_, _, new, _ = it.build_rows(fixture(), {}, {})
old = copy.deepcopy(new)
for r in old:
    if r["faculty_initials"] == "PSA":
        r["faculty_initials"], r["faculty_id"] = "SVK", "10503"
a, rm, ch = it.diff_rows(old, new)
check("diff = 0 added, 0 removed, 2 changed", (len(a), len(rm), len(ch)) == (0, 0, 2))

# 7. rendering + rotation on the real sample PDF, if present
pdf = Path(__file__).parent.parent / "pdfs" / "CSSE_C.pdf"
if pdf.exists():
    pages = it.render_pages(pdf, dpi=80)
    check("sample renders 2 pages", len(pages) == 2)
    up = it.rotate_cw(pages[0], 90)
    check("rotating page 1 90 deg clockwise makes it landscape", up.width > up.height and pages[0].height > pages[0].width)

# ---------------------------------------------------------------- layout B (CSAI-A: days as rows, dates like 15-Sep-2026)
B = [  # weekday, hour, code, type, batch, room, initials
    (1, 8, "ES26104", "Lab", "B1", "1226", "ASG"), (1, 8, "ES26104", "Lab", "B3", "1225", "PMB"), (1, 8, "ES26205", "Lab", "B2", "1201", "SHB"),
    (1, 9, "ES26104", "Lab", "B1", "1226", "ASG"), (1, 9, "ES26104", "Lab", "B3", "1225", "PMB"), (1, 9, "ES26205", "Lab", "B2", "1201", "SHB"),
    (1, 10, "ES26205", "Theory", None, "1116", "SHB"), (1, 12, "ES26103", "Theory", None, "1125", "vss"),
    (1, 13, "ES26103", "Theory", None, "1125", "vss"), (1, 14, "ES26206", "Theory", None, "1116", "RJD"),
    (2, 8, "ES26104", "Lab", "B2", "1225", "ASG"), (2, 8, "ES26104", "Lab", "B3", "1226", "SRD"), (2, 8, "ES26205", "Lab", "B1", "1201", "SHB"),
    (2, 9, "ES26104", "Lab", "B2", "1225", "ASG"), (2, 9, "ES26104", "Lab", "B3", "1226", "SRD"), (2, 9, "ES26205", "Lab", "B1", "1201", "SHB"),
    (2, 10, "ES26207", "Theory", None, "1116", "SMP"), (2, 11, "ES26108A", "Theory", None, "1116", "VW"),
    (3, 8, "ES26104", "Lab", "B1", "1225", "ASG"), (3, 8, "ES26205", "Lab", "B3", "1201", "SHB"),
    (3, 9, "ES26104", "Lab", "B1", "1225", "ASG/ASG"), (3, 9, "ES26201", "Tutorial", "B2", "1115", "SCB"), (3, 9, "ES26205", "Lab", "B3", "1201", "SHB"),
    (3, 10, "ES26201", "Theory", None, "1116", "SCB"), (3, 11, "ES26108A", "Theory", None, "1116", "VW"),
    (3, 12, "ES26104", "Theory", None, "1116", "ASG"), (3, 14, "ES26206", "Theory", None, "1122", "RJD"),
    (4, 8, "ES26104", "Lab", "B2", "1225", "ASG"), (4, 8, "ES26201", "Tutorial", "B1", "1115", "SCB"),
    (4, 9, "ES26104", "Lab", "B2", "1225", "ASG"), (4, 9, "ES26201", "Tutorial", "B3", "1409", "SCB"),
    (4, 10, "ES26201", "Theory", None, "1116", "SCB"), (4, 11, "ES26104", "Theory", None, "1116", "ASG"),
    (4, 12, "ES26207", "Theory", None, "1116", "SMP"),
    (5, 8, "ES26206", "Theory", None, "1116", "RJD"), (5, 9, "ES26205", "Theory", None, "1116", "SHB"),
    (5, 10, "ES26201", "Theory", None, "1116", "SCB"),
]
LEG_B = [
    ("20231", "SHB", "SMITA HANMANT BHAGWAT", "ES26205", "Engineering Robotics", "Theory"),
    ("20231", "SHB", "SMITA HANMANT BHAGWAT", "ES26205", "Engineering Robotics", "Lab"),
    ("10463", "RJD", "DR. RAJESH JAGDISH DHAKE", "ES26206", "Environment Studies", "Theory"),
    ("12402", "SCB", "SACHIN CHANDRAKANT BIDWAI", "ES26201", "Calculus", "Theory"),
    ("12402", "SCB", "SACHIN CHANDRAKANT BIDWAI", "ES26201", "Calculus", "Tutorial"),
    ("12382", "ASG", "ANUJA SHAHAJI GARANDE", "ES26104", "Programming for Engineers", "Lab"),
    ("12382", "ASG", "ANUJA SHAHAJI GARANDE", "ES26104", "Programming for Engineers", "Theory"),
    ("2025_264", "vss", "V4_COMP S S", "ES26103", "Logic and Quantitative Aptitude 1", "Theory"),
    ("Visiting_02", "VW", "VINAY WAGHMARE", "ES26108A", "Language-English", "Theory"),
    ("12393", "SMP", "SWATI MOHAN PATIL", "ES26207", "Design Thinking & Ideation", "Theory"),
    ("12394", "PMB", "PALLAVI MOHAN BHUJBAL", "ES26104", "Programming for Engineers", "Lab"),
    ("12397", "SRD", "SWAMINI RAJENDRA DESHMANE", "ES26104", "Programming for Engineers", "Lab"),
]


def fixture_b():
    return {
        "header": {"division_label": "FY CSAI-A", "year_label": "", "program": "DESH-DESH", "academic_year": "2026-27",
                   "semester": 1, "version": "V1", "wef": "15-Sep-2026", "to_date": "10-Jan-2027",
                   "total_theory": 16, "total_lab": 18, "total_tutorial": 3, "total_all": 37},
        "legend": [{"faculty_id": a, "initials": b, "faculty_name": c, "subject_code": d, "subject_name": e, "load_type": f}
                   for a, b, c, d, e, f in LEG_B],
        "sessions": [{"weekday": w, "start_time": f"{h:02d}:00", "end_time": f"{h + 1:02d}:00", "subject_code": c,
                      "session_type": t, "batch": b, "room": r, "faculty_initials": i} for w, h, c, t, b, r, i in B],
    }


err, warn, rows_b, hdr_b = it.build_rows(fixture_b(), {}, {})
check("layout B: validates (37 sessions, footer 16/18/3/37)", not err and len(rows_b) == 37)
check("layout B: 15-Sep-2026 dates parsed", (hdr_b["effective_from"], hdr_b["effective_to"]) == ("2026-09-15", "2027-01-10"))
check("layout B: 'FY CSAI-A' -> CSAI-A, year FY", (hdr_b["division_label"], hdr_b["year_label"]) == ("CSAI-A", "FY"))
check("layout B: ASG/ASG (same teacher twice) is stored as plain ASG, no warning needed",
      any(r["faculty_initials"] == "ASG" and r["weekday"] == 3 and r["start_time"] == "09:00" for r in rows_b)
      and not any("several teachers" in w for w in warn))
d = fixture_b()
for s_ in d["sessions"]:
    if s_["weekday"] == 3 and s_["start_time"] == "09:00" and s_["faculty_initials"] == "ASG/ASG":
        s_["faculty_initials"] = "ASG/SCB"
e2, w2, r2, _ = it.build_rows(d, {}, {})
check("two different teachers: first one stored, warning raised",
      not e2 and any("several teachers ASG/SCB" in w for w in w2))
check("layout B: lowercase 'vss' keeps legend id", any(r["faculty_initials"] == "vss" and r["faculty_id"] == "2025_264" for r in rows_b))

# date formats and label variants
for raw, want in (("15-Sep-2026", "2026-09-15"), ("15 September 2026", "2026-09-15"), ("15/09/2026", "2026-09-15"),
                  ("10-01-2027", "2027-01-10"), ("31-Feb-2026", None), ("garbage", None)):
    check(f"date {raw!r}", it.norm_date(raw) == want)
for raw, want in (("FY CSAI-A", "CSAI-A"), ("First Year - CSSE-C", "CSSE-C"), ("CSAI-A", "CSAI-A"), ("FY AIML-B", "AIML-B")):
    check(f"label {raw!r}", it.split_division_label(raw)[0] == want)

# division matching against tt_divisions rows (pdf_label differs from the printed name for AIML)
DIVS = [{"slug": "fy-csai-a-2026-27", "branch": "CSAI", "division": "FY CSAI-A", "pdf_label": "CSAI-A"},
        {"slug": "fy-csaiml-a-2026-27", "branch": "CSAIML", "division": "FY CSAIML-A", "pdf_label": "AIML-A"},
        {"slug": "fy-csse-c-2026-27", "branch": "CSSE", "division": "FY CSSE-C", "pdf_label": "CSSE-C"}]
check("match CSAI-A", it.find_division(DIVS, "CSAI-A")[0]["slug"] == "fy-csai-a-2026-27")
check("match AIML-A via pdf_label", it.find_division(DIVS, "AIML-A")[0]["slug"] == "fy-csaiml-a-2026-27")
check("match CSAIML-A via division name", it.find_division(DIVS, "CSAIML-A")[0]["slug"] == "fy-csaiml-a-2026-27")
check("CSAI-A is not confused with CSAIML-A", it.find_division(DIVS, "CSAI-A")[0]["slug"] != "fy-csaiml-a-2026-27")
check("unknown division -> no match", it.find_division(DIVS, "MECH-A") == [])

# discovery: any file name, any subfolder, any case
import tempfile
with tempfile.TemporaryDirectory() as td:
    for n in ("CSAI-A_rotated.pdf", "Final (1).PDF", "sub/x y z.pdf", "notes.txt"):
        f = Path(td) / n
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"%PDF-1.4")
    found = sorted(p.name for p in Path(td).rglob("*") if p.is_file() and p.suffix.lower() == ".pdf")
    check("pdf discovery ignores names/case/subfolders", found == ["CSAI-A_rotated.pdf", "Final (1).PDF", "x y z.pdf"])

# 8. Gemini wiring with a mocked HTTP layer (no key, no network)
import json as _json
import os
import requests
from PIL import Image


class FakeResp:
    def __init__(self, code, payload):
        self.status_code, self._p, self.ok, self.text = code, payload, code < 400, _json.dumps(payload)

    def json(self):
        return self._p


calls = []


def fake_post(url, headers=None, data=None, timeout=None):
    calls.append((url, _json.loads(data)))
    if len(calls) == 1:  # first call is rate limited, second succeeds with fenced JSON
        return FakeResp(429, {})
    txt = "```json\n" + _json.dumps(fixture()) + "\n```"
    return FakeResp(200, {"candidates": [{"content": {"parts": [{"text": txt}]}}]})


real_post, real_sleep = requests.post, __import__("time").sleep
requests.post = fake_post
__import__("time").sleep = lambda s: None
try:
    out = it.call_gemini("KEY", [Image.new("RGB", (50, 50), "white")])
finally:
    requests.post, __import__("time").sleep = real_post, real_sleep
check("gemini: retries on 429 then parses fenced JSON", len(calls) == 2 and out["header"]["division_label"] == "CSSE-C")
body = calls[-1][1]
check("gemini: image + schema sent, JSON mode on",
      body["generationConfig"]["responseMimeType"] == "application/json"
      and any("inline_data" in p for p in body["contents"][0]["parts"]))
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ["GEMINI_API_KEY"] = "x"
check("provider: gemini chosen when its key is set", it.make_extractor()[0].startswith("gemini"))
os.environ.pop("GEMINI_API_KEY")
check("provider: none when no key", it.make_extractor() is None)

sys.exit(1 if check.failed else 0)
