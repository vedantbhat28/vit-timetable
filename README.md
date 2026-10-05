# VIT Pune - FY Timetable

A clean, mobile-friendly timetable app for **First Year students at Vishwakarma Institute of Technology, Pune** (Academic Year 2026–27).

Instead of digging through ugly PDF timetables every day, pick your **branch, division, and lab batch** once and get a live, easy-to-read view of your schedule — what's happening now, what's next, the full day, and the full week.

> 🤖 **Everything about this project — the design, the code, the copy, and this README — was made entirely by AI.** No hand-written code or design was involved.

---

## Features

- **Branch / division / batch picker** — a simple first-run screen to select your class; the choice is saved on your device so it opens straight to your timetable next time.
- **Live "now / next" hero card** — instantly shows the current or upcoming class, room number, and time remaining, colour-coded by subject.
- **Day view** — a scrollable timeline of the selected day with a live "now" indicator.
- **Week view** — the full week at a glance.
- **Class details** — tap any class to see faculty, room, and batch/group breakdown.
- **12h / 24h clock toggle** and **light / dark theme** (auto-detects system theme, with manual override).
- **Fully responsive** — designed mobile-first, works down to small phone screens, with safe-area support for notches/home indicators.
- **Terms & conditions popup** — a small disclaimer, since the timetable data is AI-extracted from the official PDF.
- **Installable as an app** — on Android/desktop Chrome or Edge, a native "Install" prompt lets you add it to your home screen or app list, so it opens full-screen with no browser bars. On iOS, a banner walks you through the manual "Add to Home Screen" steps (Apple doesn't allow the automatic prompt).

## How it works

- The app's core is a **single self-contained HTML file** (`index.html`, also included here as `timetable.html`) — HTML, CSS, and JavaScript all in one, no build step required.
- Timetable data is fetched live from a **Supabase** backend (the `TimeTable_VIT` project), which stores data extracted from the official department timetable PDF (Form FF957).
- Your selected branch, division, batch, clock format, and theme preference are stored in the browser's `localStorage` — nothing is sent to a server beyond the read-only data fetch.
- A `manifest.json`, a minimal `sw.js` service worker, and a small `icons/` folder make the app installable as a Progressive Web App (PWA).

## Files

| File | Purpose |
|---|---|
| `index.html` | The whole app — must be named exactly `index.html` for GitHub Pages to serve it at the site root. |
| `manifest.json` | App name, icons, and theme colour used for the "Install app" prompt. |
| `sw.js` | Minimal service worker — required for installability and gives a basic offline fallback for the app shell. |
| `icons/` | App icons in the sizes required by Android, desktop, and iOS home screens. |

## Running it

No installation needed to *view* it — just open `index.html` in any modern browser. To actually *install* it as an app, all four items above (the HTML file, `manifest.json`, `sw.js`, and the `icons/` folder) need to be deployed together, in the same folder, since the HTML file links to the others by relative path.

## Disclaimer

Timetable data is extracted with the help of AI from the official college schedule. While effort has been made to keep it accurate, please cross-check with the official department timetable for anything important — see the "terms and conditions" link on the class-picker screen for details.

## Credits

Built entirely by AI (Claude, Anthropic) — design, code, and content.
