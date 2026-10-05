#!/usr/bin/env python3
"""
Import VIT Pune timetable PDFs from ./pdfs into the TimeTable_VIT Supabase project.

Flow per PDF
  1. hash it; skip if this exact file was already imported (tt_import_log)
  2. render pages and send them to a vision model once -> structured JSON
     (free: Google Gemini API free tier; optional: Claude). The JSON is cached in tt_import_log.
  3. validate hard: footer totals (Theory/Lab/Tutorial/Total), legend lookups,
     no clashes, hourly slots. Anything doubtful -> nothing is written.
  4. diff against the rows currently in Supabase and print it
  5. atomically replace that division via the tt_replace_division() RPC

If ./pdfs is missing or has no PDFs, the script exits 0 and changes nothing:
the app simply keeps serving whatever is already in Supabase.

Env
  SUPABASE_SERVICE_KEY  required  (service_role key, never put it in the app)
  GEMINI_API_KEY        free key from aistudio.google.com (no card)  -> default reader
  ANTHROPIC_API_KEY     optional paid alternative
  EXTRACT_PROVIDER      optional: gemini | anthropic (default: gemini if its key is set, else anthropic)
  GEMINI_MODEL          optional (default gemini-flash-latest)
  EXTRACT_MODEL         optional Claude model (default claude-sonnet-5-5)
  SUPABASE_URL          optional  (defaults to the TimeTable_VIT project)
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_SUPABASE_URL = "https://fqfzygubyjqkimsphmdn.supabase.co"
EXTRACT_MODEL = os.environ.get("EXTRACT_MODEL", "claude-sonnet-5-5")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
MAX_PAGES = 4
LARGE_DIFF_RATIO = 0.5

SESSION_TYPES = {"theory": "Theory", "lab": "Lab", "tutorial": "Tutorial"}
YEARS = {"first": ("fy", 1), "second": ("sy", 2), "third": ("ty", 3), "final": ("ly", 4), "fourth": ("ly", 4)}

SYSTEM_PROMPT = """You transcribe weekly division timetables of Vishwakarma Institute of Technology (VIT), Pune from page images into structured data. Call submit_timetable exactly once.

Pages
- Page 1 is the timetable grid. Header row: "Division : First Year - CSSE-C", Program, Academic Year, Semester, Version, W.E.F. date, To_Date. Footer: "Theory = 16  Lab = 18  Tutorial = 3  Total : 37". Report the footer totals exactly as printed; never compute them yourself.
- Page 2 (if present) is a legend table: Sr No, Teacher ("12390 MBD( Machindranath Bansilal Diwate)" = faculty id, initials, full name), Load Type, Subject ("LA - ES26101 - Linear Algebra" = abbreviation, code, name).
- Pages may be rotated or scanned. Read them in whatever orientation makes the text upright.

Grid rules
- Columns are days Sunday..Saturday. Rows are one-hour slots such as "14:00 : 15:00". Many rows are empty.
- Each class block shows: faculty initials | "CODE - subject name:Bn" | session type (Theory/Lab/Tutorial) | room.
- Several blocks stacked inside one slot are parallel batches (B1, B2, B3). Emit one session per block.
- A block that spans several hourly rows (for example a lab drawn across 14:00-16:00) must be emitted as one session per hour (14:00-15:00 and 15:00-16:00).
- batch is the Bn suffix after the subject name (it may wrap, e.g. ":B" then "2"). Theory blocks have no batch (null).
- weekday: Monday=1 ... Saturday=6, Sunday=7. Times are 24h "HH:MM".
- Copy codes, initials (keep exact capitalisation such as NbK, VsS) and rooms exactly as printed. The subject name inside the grid is truncated; the code is what matters.
- Never invent anything. If something is hard to read, give your best reading and add a short note to "uncertain".

Legend rules
- Transcribe every row. faculty_name is exactly what is printed inside the brackets. subject_name is the text after the code."""

TOOL = {
    "name": "submit_timetable",
    "description": "Submit the transcribed timetable.",
    "input_schema": {
        "type": "object",
        "properties": {
            "header": {
                "type": "object",
                "properties": {
                    "division_label": {"type": "string", "description": "e.g. CSSE-C"},
                    "year_label": {"type": "string", "description": "e.g. First Year"},
                    "program": {"type": "string"},
                    "academic_year": {"type": "string", "description": "e.g. 2026-27"},
                    "semester": {"type": "integer"},
                    "version": {"type": "string", "description": "e.g. V1"},
                    "wef": {"type": "string", "description": "W.E.F. date, dd-mm-yyyy"},
                    "to_date": {"type": "string", "description": "To_Date, dd-mm-yyyy"},
                    "total_theory": {"type": "integer"},
                    "total_lab": {"type": "integer"},
                    "total_tutorial": {"type": "integer"},
                    "total_all": {"type": "integer"},
                },
                "required": ["division_label", "academic_year", "semester", "wef", "to_date",
                             "total_theory", "total_lab", "total_tutorial", "total_all"],
            },
            "legend": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "faculty_id": {"type": "string"},
                        "initials": {"type": "string"},
                        "faculty_name": {"type": "string"},
                        "load_type": {"type": "string"},
                        "subject_code": {"type": "string"},
                        "subject_name": {"type": "string"},
                    },
                    "required": ["faculty_id", "initials", "faculty_name", "subject_code", "subject_name"],
                },
            },
            "sessions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "weekday": {"type": "integer", "minimum": 1, "maximum": 7},
                        "start_time": {"type": "string"},
                        "end_time": {"type": "string"},
                        "subject_code": {"type": "string"},
                        "session_type": {"type": "string", "enum": ["Theory", "Lab", "Tutorial"]},
                        "batch": {"type": ["string", "null"], "enum": ["B1", "B2", "B3", None]},
                        "room": {"type": "string"},
                        "faculty_initials": {"type": "string"},
                    },
                    "required": ["weekday", "start_time", "end_time", "subject_code", "session_type",
                                 "batch", "room", "faculty_initials"],
                },
            },
            "uncertain": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["header", "legend", "sessions"],
    },
}


def log(msg: str = "") -> None:
    print(msg, flush=True)


# --------------------------------------------------------------------------- Supabase

class Supa:
    def __init__(self, url: str, key: str):
        import requests
        self.base = url.rstrip("/") + "/rest/v1/"
        self.s = requests.Session()
        self.s.headers.update({"apikey": key, "Authorization": f"Bearer {key}",
                               "Content-Type": "application/json"})

    def _check(self, r, what):
        if not r.ok:
            raise RuntimeError(f"Supabase {what} failed: {r.status_code} {r.text[:400]}")
        return r

    def get_all(self, table: str, params: dict) -> list[dict]:
        out, offset = [], 0
        while True:  # PostgREST caps responses at 1000 rows by default
            p = dict(params, limit=1000, offset=offset)
            rows = self._check(self.s.get(self.base + table, params=p, timeout=60), f"GET {table}").json()
            out += rows
            if len(rows) < 1000:
                return out
            offset += 1000

    def insert(self, table: str, row: dict) -> None:
        self._check(self.s.post(self.base + table, data=json.dumps(row),
                                headers={"Prefer": "return=minimal"}, timeout=60), f"INSERT {table}")

    def rpc(self, fn: str, payload: dict) -> dict:
        r = self._check(self.s.post(self.base + "rpc/" + fn, data=json.dumps(payload), timeout=120), f"RPC {fn}")
        return r.json()


# --------------------------------------------------------------------------- rendering

def render_pages(path: Path, dpi: int = 220):
    import pymupdf
    from PIL import Image
    pages = []
    with pymupdf.open(path) as doc:
        for page in list(doc)[:MAX_PAGES]:
            pix = page.get_pixmap(dpi=dpi)  # honours the PDF's /Rotate flag
            pages.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    return pages


def rotate_cw(im, deg: int):
    from PIL import Image
    deg %= 360
    if deg == 90:
        return im.transpose(Image.Transpose.ROTATE_270)
    if deg == 180:
        return im.transpose(Image.Transpose.ROTATE_180)
    if deg == 270:
        return im.transpose(Image.Transpose.ROTATE_90)
    return im


def png_block(im, max_side: int = 2600) -> dict:
    im = im.copy()
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    data = buf.getvalue()
    media = "image/png"
    if len(data) > 4_500_000:
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=88)
        data, media = buf.getvalue(), "image/jpeg"
    return {"type": "image", "source": {"type": "base64", "media_type": media,
                                        "data": base64.b64encode(data).decode()}}


def call_claude(client, images) -> dict:
    content = []
    for i, im in enumerate(images, 1):
        content += [{"type": "text", "text": f"Page {i}:"}, png_block(im)]
    content.append({"type": "text", "text": "Transcribe this timetable by calling submit_timetable."})
    r = client.messages.create(model=EXTRACT_MODEL, max_tokens=12000, system=SYSTEM_PROMPT, tools=[TOOL],
                               tool_choice={"type": "tool", "name": "submit_timetable"},
                               messages=[{"role": "user", "content": content}])
    for b in r.content:
        if b.type == "tool_use":
            return b.input
    raise RuntimeError("model returned no structured result")


def call_gemini(api_key: str, images) -> dict:
    """Google AI Studio free tier. Retries on 429 (free-tier rate limit)."""
    import requests
    import time
    parts = []
    for i, im in enumerate(images, 1):
        blk = png_block(im)["source"]
        parts += [{"text": f"Page {i}:"}, {"inline_data": {"mime_type": blk["media_type"], "data": blk["data"]}}]
    parts.append({"text": "Transcribe this timetable. Reply with ONE JSON object that follows this JSON schema "
                          "exactly, and nothing else:\n" + json.dumps(TOOL["input_schema"])})
    body = {"systemInstruction": {"parts": [{"text": SYSTEM_PROMPT.replace(
                "Call submit_timetable exactly once.", "Reply with a single JSON object only.")}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    for attempt in range(5):
        r = requests.post(url, headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                          data=json.dumps(body), timeout=300)
        if r.status_code in (429, 500, 503):
            wait = 20 * (attempt + 1)
            log(f"   Gemini busy/rate-limited ({r.status_code}); waiting {wait}s")
            time.sleep(wait)
            continue
        if not r.ok:
            raise RuntimeError(f"Gemini error {r.status_code}: {r.text[:300]}")
        try:
            text = "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError):
            raise RuntimeError(f"Gemini returned no answer: {r.text[:300]}")
        text = re.sub(r"^```(?:json)?|```$", "", text.strip()).strip()
        return json.loads(text)
    raise RuntimeError("Gemini kept rate-limiting; try again later (free tier quota)")


def make_extractor():
    """Returns (name, fn(images)->dict) or None when no key is configured."""
    want = os.environ.get("EXTRACT_PROVIDER", "").lower()
    gk, ak = os.environ.get("GEMINI_API_KEY"), os.environ.get("ANTHROPIC_API_KEY")
    if want == "gemini" or (not want and gk):
        if not gk:
            return None
        return f"gemini:{GEMINI_MODEL}", lambda imgs: call_gemini(gk, imgs)
    if ak:
        import anthropic
        client = anthropic.Anthropic()
        return f"claude:{EXTRACT_MODEL}", lambda imgs: call_claude(client, imgs)
    return None


# --------------------------------------------------------------------------- validation

def norm_time(t: str) -> str | None:
    m = re.fullmatch(r"\s*(\d{1,2})[:.](\d{2})(?::\d{2})?\s*", str(t))
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    return f"{h:02d}:{mi:02d}" if h < 24 and mi < 60 else None


def mins(t: str) -> int:
    return int(t[:2]) * 60 + int(t[3:5])


def norm_date(s: str) -> str | None:
    m = re.fullmatch(r"\s*(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\s*", str(s))
    if not m:
        return None
    d, mo, y = map(int, m.groups())
    try:
        from datetime import date
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def build_rows(data: dict, known_fac: dict, known_sub: dict):
    """Validate the extraction. Returns (errors, warnings, rows, header). Pure function."""
    errors, warnings = [], []
    h = data.get("header") or {}

    for k in ("division_label", "academic_year", "semester", "total_theory", "total_lab",
              "total_tutorial", "total_all"):
        if h.get(k) in (None, ""):
            errors.append(f"header: missing {k}")
    eff_from, eff_to = norm_date(h.get("wef", "")), norm_date(h.get("to_date", ""))
    if not eff_from or not eff_to:
        errors.append(f"header: bad dates wef={h.get('wef')!r} to_date={h.get('to_date')!r}")
    elif eff_from >= eff_to:
        errors.append(f"header: W.E.F. {eff_from} is not before To_Date {eff_to}")

    # legend lookups (this PDF first, existing Supabase data as fallback)
    fac, sub = {}, {}
    for r in data.get("legend") or []:
        ini = (r.get("initials") or "").strip()
        if ini:
            entry = (str(r.get("faculty_id", "")).strip(), (r.get("faculty_name") or "").strip())
            if ini.lower() in fac and fac[ini.lower()][1:] != (entry[0], entry[1]):
                errors.append(f"legend: initials {ini} appear twice with different id/name")
            fac[ini.lower()] = (ini,) + entry
        code = (r.get("subject_code") or "").strip()
        if code:
            sub[code.upper()] = (r.get("subject_name") or "").strip()
    for k, v in known_fac.items():
        fac.setdefault(k.lower(), (k,) + v)
    for k, v in known_sub.items():
        sub.setdefault(k.upper(), v)

    rows, seen = [], set()
    for i, s in enumerate(data.get("sessions") or [], 1):
        tag = f"session {i}"
        wd = s.get("weekday")
        st, en = norm_time(s.get("start_time", "")), norm_time(s.get("end_time", ""))
        typ = SESSION_TYPES.get(str(s.get("session_type", "")).strip().lower())
        batch = s.get("batch") or None
        code = (s.get("subject_code") or "").strip().upper()
        room = (s.get("room") or "").strip()
        ini = (s.get("faculty_initials") or "").strip()

        if wd not in range(1, 8):
            errors.append(f"{tag}: bad weekday {wd!r}"); continue
        if not st or not en or mins(en) - mins(st) != 60:
            errors.append(f"{tag}: slot {s.get('start_time')}-{s.get('end_time')} is not one hour"); continue
        if not typ:
            errors.append(f"{tag}: bad session_type {s.get('session_type')!r}"); continue
        if typ == "Theory" and batch:
            errors.append(f"{tag}: theory with batch {batch}")
        if typ != "Theory" and not batch:
            errors.append(f"{tag}: {typ} without a batch ({code} wd{wd} {st})")
        if not room:
            errors.append(f"{tag}: no room ({code} wd{wd} {st})")
        if code not in sub:
            errors.append(f"{tag}: subject code {code!r} not in legend or database"); continue
        if ini.lower() not in fac:
            errors.append(f"{tag}: faculty initials {ini!r} not in legend or database"); continue

        f_ini, f_id, f_name = fac[ini.lower()]
        row = {"weekday": wd, "start_time": st, "end_time": en, "subject_code": code,
               "subject_name": sub[code], "session_type": typ, "batch": batch, "room": room,
               "faculty_initials": f_ini, "faculty_name": f_name, "faculty_id": f_id}
        key = (wd, st, code, typ, batch)
        if key in seen:
            warnings.append(f"{tag}: duplicate of an earlier session, dropped")
            continue
        seen.add(key)
        rows.append(row)

    # clashes: a whole-class slot overlapping anything else, or one batch twice
    by_slot: dict = {}
    for r in rows:
        by_slot.setdefault((r["weekday"], r["start_time"]), []).append(r)
    for (wd, st), grp in by_slot.items():
        whole = [r for r in grp if r["batch"] is None]
        if whole and len(grp) > 1:
            errors.append(f"clash: wd{wd} {st} has a whole-class session plus other sessions")
        batches = [r["batch"] for r in grp if r["batch"]]
        dup = {b for b in batches if batches.count(b) > 1}
        if dup:
            errors.append(f"clash: wd{wd} {st} batch {sorted(dup)} has more than one session")

    # footer totals are the ground truth for completeness
    got = {"theory": 0, "lab": 0, "tutorial": 0}
    for r in rows:
        got[r["session_type"].lower()] += 1
    want = {k: h.get("total_" + k) for k in got}
    for k in got:
        if want[k] is not None and got[k] != want[k]:
            errors.append(f"totals: {k} extracted {got[k]} but footer says {want[k]}")
    if h.get("total_all") is not None and len(rows) != h["total_all"]:
        errors.append(f"totals: extracted {len(rows)} sessions but footer total is {h['total_all']}")
    for u in data.get("uncertain") or []:
        warnings.append(f"model unsure: {u}")

    header = {"division_label": (h.get("division_label") or "").strip(),
              "year_label": (h.get("year_label") or "First Year").strip(),
              "program": (h.get("program") or "").strip() or None,
              "academic_year": (h.get("academic_year") or "").strip(),
              "semester": h.get("semester"), "version": (h.get("version") or "V1").strip(),
              "effective_from": eff_from, "effective_to": eff_to,
              "total_theory": h.get("total_theory"), "total_lab": h.get("total_lab"),
              "total_tutorial": h.get("total_tutorial"), "total_all": h.get("total_all")}
    return errors, warnings, rows, header


def row_key(r: dict):
    return (r["weekday"], r["start_time"][:5], r["subject_code"], r["session_type"], r.get("batch"))


def diff_rows(old: list[dict], new: list[dict]):
    o = {row_key(r): r for r in old}
    n = {row_key(r): r for r in new}
    added = [n[k] for k in n if k not in o]
    removed = [o[k] for k in o if k not in n]
    changed = []
    for k in n.keys() & o.keys():
        a, b = o[k], n[k]
        if (a["room"], a["faculty_initials"], str(a.get("faculty_id"))) != \
           (b["room"], b["faculty_initials"], str(b.get("faculty_id"))):
            changed.append((a, b))
    return added, removed, changed


DAYS = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}


def fmt(r):
    return (f"{DAYS[r['weekday']]} {r['start_time'][:5]} {r['subject_code']} {r['session_type']}"
            f"{' ' + r['batch'] if r.get('batch') else ''} {r['room']} {r['faculty_initials']}")


def resolve_division(header: dict, existing: list[dict], allow_new: bool):
    if existing:
        d = existing[0]
        return {"slug": d["slug"], "branch": d["branch"], "year": d["year"], "division": d["division"],
                "pdf_label": d["pdf_label"]}, False
    if not allow_new:
        return None, True
    label = header["division_label"]
    yk = header["year_label"].split()[0].lower() if header["year_label"] else "first"
    prefix, year = YEARS.get(yk, ("fy", 1))
    m = re.fullmatch(r"([A-Za-z]+)-([A-Za-z0-9]+)", label)
    if not m:
        raise ValueError(f"cannot derive a slug from division label {label!r}")
    branch, letter = m.group(1).upper(), m.group(2)
    return {"slug": f"{prefix}-{branch.lower()}-{letter.lower()}-{header['academic_year']}",
            "branch": branch, "year": year, "division": f"{prefix.upper()} {label}",
            "pdf_label": label}, True


# --------------------------------------------------------------------------- main flow

def load_known(sb: Supa):
    fac, sub = {}, {}
    for r in sb.get_all("tt_sessions", {"select": "subject_code,subject_name,faculty_initials,faculty_name,faculty_id"}):
        if r["faculty_initials"]:
            fac.setdefault(r["faculty_initials"], (r["faculty_id"] or "", r["faculty_name"] or ""))
        if r["subject_code"]:
            sub.setdefault(r["subject_code"], r["subject_name"] or "")
    return fac, sub


def extract_pdf(extractor, path: Path, known_fac, known_sub):
    """Render and extract. PDFs should be uploaded upright; if the first read fails validation the pages
    are retried rotated 90 and 270 degrees (the common sideways 'print to PDF' orientation)."""
    pages = render_pages(path)
    log(f"   {len(pages)} page(s)")
    best = None
    for n, deg in enumerate((0, 90, 270), 1):
        data = extractor([rotate_cw(im, deg) for im in pages])
        errors, warnings, rows, header = build_rows(data, known_fac, known_sub)
        if best is None or len(errors) < len(best[0]):
            best = (errors, warnings, rows, header, data)
        if not errors:
            break
        if n < 3:
            log(f"   read at {deg} deg had {len(errors)} problem(s); retrying rotated")
    return best


def process_pdf(path: Path, sb: Supa, extractor, known, args, done_slugs: set) -> bool:
    log(f"\n== {path.name}")
    model_name = extractor[0] if extractor else "none"
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    prior = sb.get_all("tt_import_log", {"pdf_sha256": f"eq.{sha}", "select": "id,status,extracted,division_slug",
                                         "order": "id.desc"})
    if any(p["status"] == "imported" for p in prior) and not args.force:
        log("   unchanged since last import - skipped")
        return True

    cached = next((p["extracted"] for p in prior if p["extracted"] and p["status"] in ("dry_run",)), None)
    known_fac, known_sub = known
    if args.from_json:
        data = json.loads(Path(args.from_json).read_text())
        errors, warnings, rows, header = build_rows(data, known_fac, known_sub)
    elif cached:
        log("   reusing cached extraction")
        data = cached
        errors, warnings, rows, header = build_rows(data, known_fac, known_sub)
    else:
        if extractor is None:
            log("   ERROR: no GEMINI_API_KEY (or ANTHROPIC_API_KEY) set - cannot read this PDF; Supabase left as is")
            return False
        errors, warnings, rows, header, data = extract_pdf(extractor[1], path, known_fac, known_sub)

    for w in warnings:
        log(f"   warn: {w}")
    if errors:
        for e in errors:
            log(f"   ERROR: {e}")
        sb.insert("tt_import_log", {"pdf_sha256": sha, "filename": path.name, "status": "failed",
                                    "extracted": data, "notes": "; ".join(errors)[:1500], "model": model_name})
        log("   NOT imported - Supabase left as is")
        return False

    existing_div = sb.get_all("tt_divisions", {"pdf_label": f"eq.{header['division_label']}",
                                               "academic_year": f"eq.{header['academic_year']}", "select": "*"})
    div, is_new = resolve_division(header, existing_div, args.allow_new)
    if div is None:
        msg = f"division {header['division_label']} ({header['academic_year']}) is not in tt_divisions; rerun with --allow-new"
        log(f"   ERROR: {msg}")
        sb.insert("tt_import_log", {"pdf_sha256": sha, "filename": path.name, "status": "failed",
                                    "extracted": data, "notes": msg, "model": model_name})
        return False
    if div["slug"] in done_slugs:
        log(f"   ERROR: another PDF in this run already updates {div['slug']}; keep only one PDF per division")
        return False

    old = sb.get_all("tt_sessions", {"division": f"eq.{div['slug']}", "select": "*",
                                     "order": "weekday,start_time,batch,subject_code"})
    for r in old:
        r["start_time"], r["end_time"] = r["start_time"][:5], r["end_time"][:5]
    added, removed, changed = diff_rows(old, rows)
    log(f"   {div['slug']}: {len(rows)} sessions (was {len(old)})  +{len(added)} -{len(removed)} ~{len(changed)}")
    for r in added:
        log(f"     + {fmt(r)}")
    for r in removed:
        log(f"     - {fmt(r)}")
    for a, b in changed:
        log(f"     ~ {fmt(a)}  ->  {b['room']} {b['faculty_initials']}")

    churn = (len(added) + len(removed) + len(changed)) / max(len(old), len(rows), 1)
    if old and churn > LARGE_DIFF_RATIO and not args.accept_large_diff:
        msg = f"{churn:.0%} of the timetable changed - looks like a bad read; rerun with --accept-large-diff if real"
        log(f"   ERROR: {msg}")
        sb.insert("tt_import_log", {"pdf_sha256": sha, "filename": path.name, "division_slug": div["slug"],
                                    "status": "failed", "extracted": data, "notes": msg, "model": model_name})
        return False

    if args.dry_run:
        sb.insert("tt_import_log", {"pdf_sha256": sha, "filename": path.name, "division_slug": div["slug"],
                                    "status": "dry_run", "session_count": len(rows), "extracted": data,
                                    "model": model_name, "notes": "dry run"})
        log("   dry run - nothing written (extraction cached for the real run)")
        return True

    p_div = dict(div, program=header["program"], academic_year=header["academic_year"],
                 semester=header["semester"], version=header["version"],
                 effective_from=header["effective_from"], effective_to=header["effective_to"],
                 total_theory=header["total_theory"], total_lab=header["total_lab"],
                 total_tutorial=header["total_tutorial"], total_all=header["total_all"])
    payload_rows = [{k: r[k] for k in ("weekday", "start_time", "end_time", "subject_code", "subject_name",
                                       "session_type", "batch", "room", "faculty_initials", "faculty_name",
                                       "faculty_id")} for r in rows]
    res = sb.rpc("tt_replace_division", {"p_div": p_div, "p_sessions": payload_rows})
    previous = [{k: r[k] for k in payload_rows[0]} for r in old] if old else None
    sb.insert("tt_import_log", {"pdf_sha256": sha, "filename": path.name, "division_slug": div["slug"],
                                "status": "imported", "session_count": res.get("new"), "extracted": payload_rows,
                                "previous": previous, "model": model_name,
                                "notes": f"+{len(added)} -{len(removed)} ~{len(changed)}"})
    done_slugs.add(div["slug"])
    log(f"   imported: {res}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf-dir", default="pdfs")
    ap.add_argument("--only", help="process just this PDF filename")
    ap.add_argument("--dry-run", action="store_true", help="extract + diff, write nothing to the timetable")
    ap.add_argument("--force", action="store_true", help="re-import even if this exact PDF was imported before")
    ap.add_argument("--allow-new", action="store_true", help="allow creating a division not in tt_divisions")
    ap.add_argument("--accept-large-diff", action="store_true", help="accept >50%% change to a division")
    ap.add_argument("--from-json", help="debug: use this extraction JSON instead of calling the model")
    args = ap.parse_args()

    pdf_dir = Path(args.pdf_dir)
    pdfs = sorted(p for p in pdf_dir.iterdir() if p.suffix.lower() == ".pdf") if pdf_dir.is_dir() else []
    if args.only:
        pdfs = [p for p in pdfs if p.name == args.only]
    if not pdfs:
        log(f"No PDFs found in {pdf_dir}/ - nothing to import. The app keeps using the data already in Supabase.")
        return 0

    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not key:
        log("SUPABASE_SERVICE_KEY is not set")
        return 1
    sb = Supa(os.environ.get("SUPABASE_URL", DEFAULT_SUPABASE_URL), key)

    extractor = make_extractor()
    if extractor:
        log(f"Reader: {extractor[0]}")

    try:
        known = load_known(sb)
    except Exception as e:
        log(f"Cannot reach Supabase ({e}); leaving everything as is")
        return 1

    ok, done = True, set()
    for p in pdfs:
        try:
            ok &= process_pdf(p, sb, extractor, known, args, done)
            if extractor and extractor[0].startswith("gemini") and p is not pdfs[-1]:
                import time
                time.sleep(8)  # stay under the free-tier requests-per-minute limit
        except Exception as e:
            log(f"   ERROR: {type(e).__name__}: {e}")
            ok = False
    log("\nAll done." if ok else "\nFinished with errors (see above). Failed PDFs left the database untouched.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
