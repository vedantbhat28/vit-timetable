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
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
STATS = {"read": 0}  # PDFs that actually needed a model call in this run (for --limit)
MAX_PAGES = 10
LARGE_DIFF_RATIO = 0.5

SESSION_TYPES = {"theory": "Theory", "lab": "Lab", "tutorial": "Tutorial"}
YEARS = {"first": ("fy", 1), "fy": ("fy", 1), "second": ("sy", 2), "sy": ("sy", 2), "third": ("ty", 3),
         "ty": ("ty", 3), "final": ("ly", 4), "fourth": ("ly", 4), "ly": ("ly", 4)}

SYSTEM_PROMPT = """You transcribe weekly division timetables of Vishwakarma Institute of Technology (VIT), Pune from page images into structured data. Call submit_timetable exactly once.

The PDFs come in two layouts (and may have any file name). Work out which one you are looking at.
Layout A: the first page is a grid with DAYS as columns (Sunday..Saturday) and one-hour slots as rows ("14:00 : 15:00"). Header: "Division : First Year - CSSE-C". Each block shows: faculty initials | "CODE - subject name:Bn" | session type | room. A teacher legend table is on a later page.
Layout B: the grid has DAYS as rows (Monday, Tuesday...) and one-hour slots as columns ("08:00-09:00"). Header: "Division : FY CSAI-A". Each block is a small text stack: "FY CSAI-A", faculty initials, "CODE - subject name:Bn" (the name wraps over lines), session type, room. The table continues over several pages; the column header row repeats on every page and a day's row can continue on the next page without a new day label (continue the previous day). The legend table is at the end.

Rules for both layouts
- Header fields: division_label is the division only, e.g. "CSAI-A" or "CSSE-C" (drop FY / First Year). Copy dates (W.E.F. and To Date) exactly as printed, e.g. "15-Sep-2026" or "15-09-2026".
- Footer: "Theory = 16 Lab = 18 Tutorial = 3 ... Total : 37". Report the printed totals; never compute them yourself. Ignore Seminar / Project / General if blank.
- Legend rows: faculty id, initials, full name, load type, subject abbreviation, code, subject name. "12402 SCB (SACHIN CHANDRAKANT BIDWAI)" = id 12402, initials SCB, name SACHIN CHANDRAKANT BIDWAI. Transcribe every row. Subject name is the text after the code.
- Several blocks in one slot are parallel batches (B1, B2, B3): up to three blocks can sit side by side or stacked in ONE hourly slot. Emit one session per block per one-hour slot and never skip one; a lab hour normally has all three batches.
- Before answering, count your sessions per type and compare with the printed footer totals. If a count is short, look again for missed blocks (usually parallel lab batches or hours of a block that spans several slots).
- A block drawn across several hourly slots (layout A) must be emitted once per hour. In layout B each hourly cell already holds its own copy; emit one session per cell.
- batch is the Bn suffix after the subject name (it may wrap, e.g. ":B" then "2"). Blocks without a Bn tag (theory) have batch null.
- Copy subject codes, rooms and initials exactly as printed, keeping capitalisation (NbK, vss). If a cell shows two initials such as "ASG/ASG", copy them exactly as printed.
- weekday: Monday=1 ... Saturday=6, Sunday=7. Times are 24h "HH:MM".
- Never invent anything. If something is hard to read, give your best reading and add a short note to "uncertain"."""

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

    def _req(self, method: str, url: str, what: str, **kw):
        """Retries timeouts, dropped connections and 5xx (Supabase free projects stall now and then)."""
        import requests
        import time
        last = None
        for attempt in range(5):
            try:
                r = self.s.request(method, url, timeout=120, **kw)
                if r.status_code in (502, 503, 504, 522, 524):
                    last = f"HTTP {r.status_code}"
                else:
                    if not r.ok:
                        raise RuntimeError(f"Supabase {what} failed: {r.status_code} {r.text[:400]}")
                    return r
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last = type(e).__name__
            wait = (3, 8, 20, 45)[min(attempt, 3)]
            log(f"   Supabase {what}: {last}; retrying in {wait}s")
            time.sleep(wait)
        raise RuntimeError(f"Supabase {what} kept failing ({last})")

    def get_all(self, table: str, params: dict) -> list[dict]:
        out, offset = [], 0
        while True:  # PostgREST caps responses at 1000 rows by default
            p = dict(params, limit=1000, offset=offset)
            rows = self._req("GET", self.base + table, f"GET {table}", params=p).json()
            out += rows
            if len(rows) < 1000:
                return out
            offset += 1000

    def insert(self, table: str, row: dict) -> None:
        self._req("POST", self.base + table, f"INSERT {table}", data=json.dumps(row),
                  headers={"Prefer": "return=minimal"})

    def rpc(self, fn: str, payload: dict) -> dict:
        return self._req("POST", self.base + "rpc/" + fn, f"RPC {fn}", data=json.dumps(payload)).json()


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


def call_claude(client, images, hint=None, variant=0, max_side=2600) -> dict:
    content = []
    for i, im in enumerate(images, 1):
        content += [{"type": "text", "text": f"Page {i}:"}, png_block(im, max_side)]
    content.append({"type": "text", "text": "Transcribe this timetable by calling submit_timetable." + (("\n\n" + hint) if hint else "")})
    r = client.messages.create(model=EXTRACT_MODEL, max_tokens=12000, system=SYSTEM_PROMPT, tools=[TOOL],
                               tool_choice={"type": "tool", "name": "submit_timetable"},
                               messages=[{"role": "user", "content": content}])
    for b in r.content:
        if b.type == "tool_use":
            return b.input
    raise RuntimeError("model returned no structured result")


class GeminiUnavailable(RuntimeError):
    """Every configured Gemini model is overloaded / rate-limited right now."""


_cooldown: dict = {}   # model -> monotonic time until which we leave it alone
_dead: set = set()     # models that do not exist for this key (404)


def gemini_models() -> list[str]:
    raw = os.environ.get("GEMINI_MODELS", "").strip() or \
        f"{GEMINI_MODEL},gemini-flash-latest,gemini-3.1-flash-lite,gemini-2.5-flash,gemini-2.5-flash-lite"
    out = []
    for m in (x.strip() for x in raw.split(",")):
        if m and m not in out:
            out.append(m)
    return out


def call_gemini(api_key: str, images, hint=None, variant=0, max_side=2600) -> dict:
    """Google AI Studio free tier. 503/429 on one model -> immediately try the next model; if all are busy,
    wait for the earliest cooldown and go round again (4 rounds), then give up with GeminiUnavailable."""
    import requests
    import time
    parts = []
    for i, im in enumerate(images, 1):
        blk = png_block(im, max_side)["source"]
        parts += [{"text": f"Page {i}:"}, {"inline_data": {"mime_type": blk["media_type"], "data": blk["data"]}}]
    parts.append({"text": "Transcribe this timetable. Reply with ONE JSON object that follows this JSON schema "
                          "exactly, and nothing else:\n" + json.dumps(TOOL["input_schema"])
                          + (("\n\n" + hint) if hint else "")})
    body = {"systemInstruction": {"parts": [{"text": SYSTEM_PROMPT.replace(
                "Call submit_timetable exactly once.", "Reply with a single JSON object only.")}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    models = gemini_models()
    if models and variant:  # a different model goes first on repair / verification reads
        k = variant % len(models)
        models = models[k:] + models[:k]
    for rnd in range(4):
        tried = False
        for model in models:
            if model in _dead or _cooldown.get(model, 0) > time.monotonic():
                continue
            tried = True
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            try:
                r = requests.post(url, headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                                  data=json.dumps(body), timeout=300)
            except requests.exceptions.RequestException as e:
                log(f"   {model}: network error ({type(e).__name__}); trying next model")
                _cooldown[model] = time.monotonic() + 30
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                log(f"   {model}: busy ({r.status_code}); trying next model")
                _cooldown[model] = time.monotonic() + 90
                continue
            if r.status_code == 404:
                log(f"   {model}: model not available for this key; skipping it")
                _dead.add(model)
                continue
            if not r.ok:
                raise RuntimeError(f"Gemini error {r.status_code} on {model}: {r.text[:300]}")
            try:
                text = "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"])
            except (KeyError, IndexError, ValueError):
                log(f"   {model}: empty answer ({r.text[:120]!r}); trying next model")
                _cooldown[model] = time.monotonic() + 30
                continue
            text = re.sub(r"^```(?:json)?|```$", "", text.strip()).strip()
            try:
                return json.loads(text)
            except ValueError:
                log(f"   {model}: answer was not valid JSON; trying next model")
                continue
        if not tried:
            live = [m for m in models if m not in _dead]
            if not live:
                raise RuntimeError("none of the configured Gemini models exist for this key; set GEMINI_MODELS")
            wait = max(10, min(_cooldown.get(m, 0) for m in live) - time.monotonic())
            log(f"   all Gemini models are busy; waiting {int(wait)}s (round {rnd + 1}/4)")
            time.sleep(wait)
    raise GeminiUnavailable("Gemini is overloaded or out of free quota on every model")


def make_extractor():
    """Returns (name, fn(images)->dict) or None when no key is configured."""
    want = os.environ.get("EXTRACT_PROVIDER", "").lower()
    gk, ak = os.environ.get("GEMINI_API_KEY"), os.environ.get("ANTHROPIC_API_KEY")
    if want == "gemini" or (not want and gk):
        if not gk:
            return None
        return f"gemini:{GEMINI_MODEL}", lambda imgs, hint=None, variant=0, max_side=2600: call_gemini(gk, imgs, hint, variant, max_side)
    if ak:
        import anthropic
        client = anthropic.Anthropic()
        return f"claude:{EXTRACT_MODEL}", lambda imgs, hint=None, variant=0, max_side=2600: call_claude(client, imgs, hint, variant, max_side)
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


MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def norm_date(s: str) -> str | None:
    """15-09-2026, 15/09/2026, 15-Sep-2026, 15 September 2026 -> 2026-09-15"""
    from datetime import date
    t = str(s).strip()
    m = re.fullmatch(r"(\d{1,2})[-/. ](\d{1,2})[-/. ](\d{4})", t)
    if m:
        d, mo, y = map(int, m.groups())
    else:
        m = re.fullmatch(r"(\d{1,2})[-/. ]([A-Za-z]{3,9})[-/. ,]*(\d{4})", t)
        if not m or m.group(2)[:3].lower() not in MONTHS:
            return None
        d, mo, y = int(m.group(1)), MONTHS[m.group(2)[:3].lower()], int(m.group(3))
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


YEAR_PREFIX = re.compile(r"^\s*(FY|SY|TY|LY|First\s+Year|Second\s+Year|Third\s+Year|Final\s+Year|Fourth\s+Year)\s*[-:]?\s*(.+?)\s*$", re.I)


def split_division_label(raw: str, year_label: str = ""):
    """'FY CSAI-A' / 'First Year - CSSE-C' / 'CSAI-A' -> ('CSAI-A', 'FY' or 'First Year')"""
    raw = (raw or "").strip()
    m = YEAR_PREFIX.match(raw)
    if m:
        return m.group(2).strip(), (year_label or m.group(1)).strip()
    return raw, (year_label or "").strip()


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
    legend_ini, warned_db = set(), set()
    for r in data.get("legend") or []:
        ini = (r.get("initials") or "").strip()
        if ini:
            entry = (str(r.get("faculty_id", "")).strip(), (r.get("faculty_name") or "").strip())
            if ini.lower() in fac and fac[ini.lower()][1:] != (entry[0], entry[1]):
                errors.append(f"legend: initials {ini} appear twice with different id/name")
            fac[ini.lower()] = (ini,) + entry
            legend_ini.add(ini.lower())
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
        parts = []
        for part in re.split(r"\s*[/,&]\s*", ini):
            if part and part.lower() not in [x.lower() for x in parts]:
                parts.append(part)
        if len(parts) > 1:
            warnings.append(f"{tag}: several teachers {'/'.join(parts)} (wd{wd} {st}); stored under {parts[0]}")
        ini = parts[0] if parts else ini

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
        if ini.lower() not in legend_ini and ini.lower() not in warned_db:
            warned_db.add(ini.lower())
            warnings.append(f"faculty {ini} is not in this PDF's legend; used the stored record {f_id} {f_name}")
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

    label, ylabel = split_division_label(h.get("division_label") or "", h.get("year_label") or "")
    header = {"division_label": label,
              "year_label": ylabel or "First Year",
              "program": (h.get("program") or "").strip() or None,
              "academic_year": (h.get("academic_year") or "").strip(),
              "semester": h.get("semester"), "version": (h.get("version") or "V1").strip(),
              "effective_from": eff_from, "effective_to": eff_to,
              "total_theory": h.get("total_theory"), "total_lab": h.get("total_lab"),
              "total_tutorial": h.get("total_tutorial"), "total_all": h.get("total_all")}
    return errors, warnings, rows, header


def fmt_change(a: dict, b: dict) -> str:
    bits = []
    if a["room"] != b["room"]:
        bits.append(f"room {a['room']} -> {b['room']}")
    if a["faculty_initials"] != b["faculty_initials"]:
        bits.append(f"teacher {a['faculty_initials']} -> {b['faculty_initials']}")
    if _key(a.get("faculty_id")) != _key(b.get("faculty_id")):
        bits.append(f"teacher id {a.get('faculty_id')} -> {b.get('faculty_id')}")
    return f"{DAYS[a['weekday']]} {a['start_time'][:5]} {a['subject_code']} {a['session_type']}" \
           f"{' ' + a['batch'] if a.get('batch') else ''}: " + ", ".join(bits)


def shifted_pairs(added: list, removed: list):
    """A session that vanished at one time and appeared 1-2 h away is more often a misread column than a real move."""
    out = []
    for r in removed:
        for a in added:
            same = (r["weekday"], r["subject_code"], r["session_type"], r.get("batch")) == \
                   (a["weekday"], a["subject_code"], a["session_type"], a.get("batch"))
            if same and 60 <= abs(mins(a["start_time"][:5]) - mins(r["start_time"][:5])) <= 120:
                out.append((r, a))
                break
    return out


def _key(x) -> str:
    return re.sub(r"[^a-z0-9]", "", str(x if x is not None else "").lower())


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
        if (a["room"], a["faculty_initials"], _key(a.get("faculty_id"))) != \
           (b["room"], b["faculty_initials"], _key(b.get("faculty_id"))):
            changed.append((a, b))
    return added, removed, changed


DAYS = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}


def fmt(r):
    return (f"{DAYS[r['weekday']]} {r['start_time'][:5]} {r['subject_code']} {r['session_type']}"
            f"{' ' + r['batch'] if r.get('batch') else ''} {r['room']} {r['faculty_initials']}")


def find_division(divs: list[dict], label: str):
    """Match the printed division (CSAI-A, AIML-A, FY CSAIML-A ...) to a tt_divisions row."""
    k = _key(label)
    for d in divs:
        letter = (d["division"] or "").split("-")[-1]
        cands = {_key(d["pdf_label"]), _key(split_division_label(d["division"])[0]), _key(f"{d['branch']}-{letter}")}
        if k in cands:
            return [d]
    return []


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


_ROT_ORDER = [0, 90, 270]   # the rotation that worked last time is tried first (saves calls on a batch of sideways PDFs)


def repair_hint(errors: list, data: dict) -> str:
    prev = json.dumps({"header": data.get("header"), "sessions": data.get("sessions")})
    return ("Your previous answer failed these checks against the printed footer / legend:\n- "
            + "\n- ".join(errors[:12])
            + "\n\nYour previous answer was:\n" + prev
            + "\n\nLook at the images again. Find every block you missed or put in the wrong day or hour "
              "(especially parallel lab batches B1/B2/B3 in the same slot, and blocks that span several hours) "
              "and return the COMPLETE corrected JSON object, including the legend.")


def extract_pdf(extractor, path: Path, known_fac, known_sub, hi_res: bool = False, variant: int = 0):
    """Render and extract. Tries the remembered rotation first, then the others. If every read still fails
    validation, up to two repair passes feed the failed checks back to the model together with its own answer.
    Returns (errors, warnings, rows, header, data, rotation)."""
    pages = render_pages(path, dpi=300 if hi_res else 220)
    side = 3600 if hi_res else 2600
    log(f"   {len(pages)} page(s)")
    best = None

    def attempt(deg, hint=None, var=variant):
        nonlocal best
        data = extractor([rotate_cw(im, deg) for im in pages], hint, var, side)
        errors, warnings, rows, header = build_rows(data, known_fac, known_sub)
        if best is None or len(errors) < len(best[0]):
            best = (errors, warnings, rows, header, data, deg)
        return errors

    for n, deg in enumerate(list(_ROT_ORDER), 1):
        if not attempt(deg):
            _ROT_ORDER.remove(deg)
            _ROT_ORDER.insert(0, deg)
            return best
        if n < 3:
            log(f"   read at {deg} deg had {len(best[0])} problem(s); retrying rotated")
    for k in (1, 2):
        log(f"   repair pass {k}: sending the failed checks back to the model ({len(best[0])} problem(s))")
        if not attempt(best[5], repair_hint(best[0], best[4]), variant + k):
            _ROT_ORDER.remove(best[5])
            _ROT_ORDER.insert(0, best[5])
            break
    return best


def verify_read(extractor, path: Path, known_fac, known_sub, first_rows: list):
    """A second, independent read (higher resolution, a different model first). The changes a PDF would make are only
    trusted when both reads agree on every session. Returns a list of disagreements (empty = confirmed)."""
    errors, _w, rows2, _h, _d, _deg = extract_pdf(extractor, path, known_fac, known_sub, hi_res=True, variant=1)
    if errors:
        return [f"second read could not be validated: {errors[0]}"]
    a = {row_key(r): (r["room"], r["faculty_initials"]) for r in first_rows}
    b = {row_key(r): (r["room"], r["faculty_initials"]) for r in rows2}
    out = [f"only in 1st read: {fmt(r)}" for r in first_rows if row_key(r) not in b]
    out += [f"only in 2nd read: {fmt(r)}" for r in rows2 if row_key(r) not in a]
    out += [f"room/teacher differ: {fmt(r)}" for r in first_rows if row_key(r) in b and a[row_key(r)] != b[row_key(r)]]
    return out


def process_pdf(path: Path, sb: Supa, extractor, known, args, done_slugs: set) -> bool:
    log(f"\n== {path}")
    model_name = extractor[0] if extractor else "none"
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    prior = sb.get_all("tt_import_log", {"pdf_sha256": f"eq.{sha}", "select": "id,status", "order": "id.desc"})
    if any(p["status"] == "imported" for p in prior) and not args.force:
        log("   unchanged since last import - skipped")
        return True

    cached = None
    if any(p["status"] == "dry_run" for p in prior):
        rows = sb.get_all("tt_import_log", {"pdf_sha256": f"eq.{sha}", "status": "eq.dry_run",
                                            "select": "extracted", "order": "id.desc", "limit": 1})
        cached = next((r["extracted"] for r in rows if r["extracted"]), None)
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
        STATS["read"] += 1
        errors, warnings, rows, header, data, _deg = extract_pdf(extractor[1], path, known_fac, known_sub)

    for w in warnings:
        log(f"   warn: {w}")
    if errors:
        for e in errors:
            log(f"   ERROR: {e}")
        sb.insert("tt_import_log", {"pdf_sha256": sha, "filename": path.name, "status": "failed",
                                    "extracted": data, "notes": "; ".join(errors)[:1500], "model": model_name})
        log("   NOT imported - Supabase left as is")
        return False

    year_divs = sb.get_all("tt_divisions", {"academic_year": f"eq.{header['academic_year']}", "select": "*"})
    existing_div = find_division(year_divs, header["division_label"])
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
        log(f"     ~ {fmt_change(a, b)}")
    for r, a in shifted_pairs(added, removed):
        log(f"   warn: {fmt(r)} seems to have moved to {a['start_time'][:5]} (a 1-2 h shift can be a misread column)")

    churn = (len(added) + len(removed) + len(changed)) / max(len(old), len(rows), 1)
    if old and churn > LARGE_DIFF_RATIO and not args.accept_large_diff:
        msg = f"{churn:.0%} of the timetable changed - looks like a bad read; rerun with --accept-large-diff if real"
        log(f"   ERROR: {msg}")
        sb.insert("tt_import_log", {"pdf_sha256": sha, "filename": path.name, "division_slug": div["slug"],
                                    "status": "failed", "extracted": data, "notes": msg, "model": model_name})
        return False

    if (added or removed or changed) and extractor and not args.no_verify and not args.from_json \
            and not data.get("_verified"):
        log("   changes found - confirming with a second independent read")
        diffs = verify_read(extractor[1], path, known_fac, known_sub, rows)
        if diffs:
            for d in diffs[:15]:
                log(f"   ERROR: {d}")
            msg = f"two reads of the PDF disagree ({len(diffs)} difference(s)); check the PDF by hand or rerun"
            log(f"   {msg}. NOT imported - Supabase left as is")
            sb.insert("tt_import_log", {"pdf_sha256": sha, "filename": path.name, "division_slug": div["slug"],
                                        "status": "failed", "extracted": data, "notes": msg + "; " + "; ".join(diffs)[:1200],
                                        "model": model_name})
            return False
        data["_verified"] = True
        log("   second read agrees - changes confirmed")

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
    ap.add_argument("--only", help="process just PDFs whose file name contains this text (case-insensitive)")
    ap.add_argument("--no-verify", action="store_true", help="skip the second confirming read of changed divisions")
    ap.add_argument("--limit", type=int, help="process at most this many PDFs that still need reading")
    ap.add_argument("--dry-run", action="store_true", help="extract + diff, write nothing to the timetable")
    ap.add_argument("--force", action="store_true", help="re-import even if this exact PDF was imported before")
    ap.add_argument("--allow-new", action="store_true", help="allow creating a division not in tt_divisions")
    ap.add_argument("--accept-large-diff", action="store_true", help="accept >50%% change to a division")
    ap.add_argument("--from-json", help="debug: use this extraction JSON instead of calling the model")
    args = ap.parse_args()

    pdf_dir = Path(args.pdf_dir)
    pdfs = sorted(p for p in pdf_dir.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf") if pdf_dir.is_dir() else []  # any name, any subfolder
    if args.only:
        pdfs = [p for p in pdfs if args.only.lower() in p.name.lower()]
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

    ok, done, down = True, set(), 0
    for p in pdfs:
        if args.limit is not None and STATS["read"] >= args.limit:
            log(f"\nReached --limit {args.limit}; remaining PDFs are left for the next run.")
            break
        try:
            ok &= process_pdf(p, sb, extractor, known, args, done)
            if extractor and extractor[0].startswith("gemini") and p is not pdfs[-1]:
                import time
                time.sleep(8)  # stay under the free-tier requests-per-minute limit
        except GeminiUnavailable as e:
            log(f"   ERROR: {e}")
            ok, down = False, down + 1
            if down >= 2:
                log("\nGemini is unavailable right now, so I am stopping instead of burning the whole run. "
                    "Re-run later: PDFs that were already read are cached and will not be read again.")
                break
        except Exception as e:
            log(f"   ERROR: {type(e).__name__}: {e}")
            ok = False
    log("\nAll done." if ok else "\nFinished with errors (see above). Failed PDFs left the database untouched.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
