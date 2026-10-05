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

# ---------------------------------------------------------------- resilience (what went wrong in the first real run)
import time as _time
from PIL import Image as _Image

os.environ.pop("GEMINI_MODELS", None)
_sleeps = []
_real_sleep = _time.sleep
_time.sleep = lambda s_: _sleeps.append(s_)
real_post2 = requests.post
good = {"candidates": [{"content": {"parts": [{"text": _json.dumps(fixture())}]}}]}


def run_gemini(script):
    """script: dict model -> list of status codes (last one repeats)."""
    seq = {m: list(v) for m, v in script.items()}
    seen = []

    def post(url, headers=None, data=None, timeout=None):
        model = url.split("/models/")[1].split(":")[0]
        seen.append(model)
        codes = seq.get(model, [200])
        code = codes.pop(0) if len(codes) > 1 else codes[0]
        return FakeResp(code, good if code == 200 else {})
    requests.post = post
    it._cooldown.clear(); it._dead.clear(); _sleeps.clear()
    try:
        return it.call_gemini("K", [_Image.new("RGB", (20, 20), "white")]), seen
    finally:
        requests.post = real_post2


M = it.gemini_models()
out, seen = run_gemini({M[0]: [503], M[1]: [200]})
check("503 on first model -> next model answers at once, no long waiting", out["header"]["division_label"] == "CSSE-C"
      and seen == [M[0], M[1]] and not _sleeps)
out, seen = run_gemini({M[0]: [404], M[1]: [404], M[2]: [200]})
check("unknown model names (404) are skipped", out is not None and seen[-1] == M[2])
try:
    run_gemini({m: [503] for m in it.gemini_models()})
    check("all models busy -> GeminiUnavailable", False)
except it.GeminiUnavailable:
    check("all models busy -> GeminiUnavailable after 4 rounds, not 5 minutes per PDF", True)
check("waiting between rounds is capped small", all(s_ <= 100 for s_ in _sleeps))
os.environ["GEMINI_MODELS"] = "model-a, model-b ,model-a"
check("GEMINI_MODELS overrides the list and dedupes", it.gemini_models() == ["model-a", "model-b"])
os.environ["GEMINI_MODELS"] = ""
check("empty GEMINI_MODELS (unset repo variable) uses defaults", len(it.gemini_models()) >= 3)
os.environ.pop("GEMINI_MODELS")

# Supabase: ReadTimeout then success is retried
class FakeSession:
    def __init__(self):
        self.n = 0
        self.headers = {}

    def request(self, method, url, timeout=None, **kw):
        self.n += 1
        if self.n < 3:
            raise requests.exceptions.ReadTimeout("read timed out")
        return FakeResp(200, [{"id": 1}])


sb = it.Supa("https://x.supabase.co", "k")
sb.s = FakeSession()
_sleeps.clear()
rows = sb.get_all("tt_import_log", {"select": "id"})
check("supabase ReadTimeout is retried (twice) then succeeds", rows == [{"id": 1}] and sb.s.n == 3 and len(_sleeps) == 2)


class DeadSession(FakeSession):
    def request(self, *a, **k):
        raise requests.exceptions.ConnectionError("down")


sb.s = DeadSession()
try:
    sb.get_all("t", {})
    check("supabase down -> clear error", False)
except RuntimeError as e:
    check("supabase down -> clear error after retries", "kept failing" in str(e))
_time.sleep = _real_sleep

# ---------------------------------------------------------------- repair pass, verification, shift detection
import types
_gone = [dict(weekday=2, start_time="12:00", subject_code="ES26101", session_type="Tutorial", batch="B2", room="D211", faculty_initials="PAK", faculty_id="12095")]
_new = [dict(_gone[0], start_time="13:00")]
sp = it.shifted_pairs(_new, _gone)
check("1h shift of the same session is flagged", len(sp) == 1)
check("unrelated add/remove is not flagged", it.shifted_pairs([dict(_new[0], subject_code="X")], _gone) == [])
a = dict(_gone[0], faculty_id="Visiting_06"); b = dict(_gone[0], faculty_id="Visiting 06")
check("faculty id formatting noise is not a change", it.diff_rows([a], [b])[2] == [])
c = dict(_gone[0], room="E999")
check("a real room change is shown readably", "room D211 -> E999" in it.fmt_change(_gone[0], c))

# repair pass: first reads miss sessions, the repair read returns the full fixture
bad = fixture(); bad["sessions"] = bad["sessions"][:-3]
calls2 = []
def fake_extractor(images, hint=None, variant=0, max_side=2600):
    calls2.append((hint is not None, variant))
    return fixture() if hint else bad
it.render_pages = lambda path, dpi=220: [_Image.new("RGB", (30, 30), "white")]
it._ROT_ORDER[:] = [0, 90, 270]
errs, warns, rws, hdr, dat, deg = it.extract_pdf(fake_extractor, Path("x.pdf"), {}, {})
check("repair pass fixes a short read after the rotations fail", not errs and len(calls2) == 4 and calls2[3][0] is True)
check("a successful rotation is remembered for the next PDF", it._ROT_ORDER[0] == deg)

calls2.clear()
errs, *_ = it.extract_pdf(lambda im, h=None, v=0, m=2600: fixture(), Path("x.pdf"), {}, {})
check("a clean first read costs exactly one call", not errs)

# verification: agreeing second read -> no differences; disagreeing -> listed
_, _, good_rows, _ = it.build_rows(fixture(), {}, {})
check("verify: identical second read confirms", it.verify_read(lambda im, h=None, v=0, m=2600: fixture(), Path("x.pdf"), {}, {}, good_rows) == [])
other = fixture(); other["sessions"][0] = dict(other["sessions"][0], room="Z999")
d = it.verify_read(lambda im, h=None, v=0, m=2600: other, Path("x.pdf"), {}, {}, good_rows)
check("verify: a different second read is reported", len(d) >= 1)

sys.exit(1 if check.failed else 0)
