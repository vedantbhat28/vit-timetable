# VIT Pune – FY Timetable

A clean, mobile-first timetable app for **First Year students at Vishwakarma Institute of Technology, Pune** (Academic Year 2026–27, Semester I).

Instead of digging through PDF timetables every day, pick your **branch, division and lab batch** once and get a live, easy-to-read view of your schedule: what's on now, what's next, the full day and the full week. Since launch it has grown into a small campus toolkit with room finders, teacher lookup, a friend-schedule matcher, a study planner and a student forum.

![Visits](https://img.shields.io/badge/visits-80k%2B-1B2340)
![Unique users](https://img.shields.io/badge/unique%20users-3.6k%2B-2F5BD6)
![Daily visits](https://img.shields.io/badge/daily%20visits-2.5k%2B-E5383B)
![Hosting](https://img.shields.io/badge/hosted%20on-GitHub%20Pages-181717)
![PWA](https://img.shields.io/badge/PWA-installable-5A0FC8)

> 🤖 **The design, code, copy and this README were all made with AI (Claude, by Anthropic).** The project is student-built and unofficial.

---

## Why it exists

Official timetables come as dense PDFs that are painful to read on a phone. This app turns them into a live dashboard that answers the only questions that matter on a given day: *Where do I need to be? When? How long do I have?*

## Impact

| Metric | Number |
|---|---|
| Total visits | **80,000+** |
| Unique users | **3,600+** |
| Visits per day | **2,500+** |

Visits are counted from the app's own anonymous traffic log (see [Privacy](#privacy--data)).

---

## Features

### Core timetable
- **Class picker**: choose branch, division and lab batch once; it's remembered on your device and opens straight to your timetable next time.
- **Live "now / next" hero card**: the current or upcoming class, room, time remaining and a progress bar, colour-coded by subject.
- **Day view**: a scrollable timeline with a live "now" indicator. Overlapping sessions (like lab batches) sit side by side.
- **Week view**: the whole week at a glance, including six-day weeks with Saturday classes.
- **Class details**: tap any class for faculty, room, session type and batch/group breakdown.
- **Lab batch awareness**: B1/B2/B3 filtering so you only see your own labs.
- **German and Japanese support**: enter your roll number (optional) and the app adds your foreign-language slot and dims English. The roll-number check runs entirely on your device. Bibwewadi German groups are supported too.
- **Holidays, exam windows and notices**: pulled from the FY Academic Calendar 2026–27, with one-day change banners (room changes, cancellations, extra lectures) and festive greetings.
- **12h / 24h clock** and **light / dark theme** (follows your system, with manual override).

### Extra tools (Beta)
| Tool | What it does |
|---|---|
| **Empty classrooms** | Pick a campus (Bibwewadi or Kondhwa), a date and a time window to see which rooms have no timetabled class, handy for group study or events. |
| **Bro connect** | Compare the weekly timetables of two or more people (with or without yours), find the slots when everyone is free, and save the result as a PDF. Friends' details stay on your device. |
| **Find a teacher** | Browse faculty by subject or search by name, see which room a teacher is in right now and their next four periods. |
| **Study Planner** | An AI-assisted daily and week-by-week study plan for the mid-sems, built around your timetable, your own activities and your sleep. Stored on your device only. |
| **Forum** | A place for students to ask questions, share updates and reply to each other. |

### App experience
- **Installable PWA**: on Android and desktop Chrome/Edge, a native Install prompt adds it to your home screen. On iOS, a banner walks you through "Add to Home Screen".
- **Fully responsive**: mobile-first, works down to small phones, with safe-area support for notches and home indicators.
- **Fast returning visits**: a light loading screen while data loads, and a basic offline fallback for the app shell via the service worker.
- **Quick, anonymous survey** to collect student feedback.

---

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | Single self-contained `index.html` (HTML + CSS + vanilla JS, no framework, no build step) |
| Data | [Supabase](https://supabase.com) (Postgres + REST). Timetable tables are read-only to the public through Row Level Security |
| Source data | Official department timetable PDFs (Form FF957), extracted with AI assistance, plus the FY Academic Calendar 2026–27 |
| Hosting | GitHub Pages |
| Offline / install | Web App Manifest + minimal service worker |
| Fonts | Big Shoulders Display and Instrument Sans (Google Fonts) |

### How it works
1. On load, the app fetches the list of divisions from Supabase (metadata only).
2. When you open a class, that division's sessions and faculty are fetched once and cached for the visit.
3. Everything else, such as the now/next logic, week grid, free-slot maths and room availability, is computed in your browser.
4. Your class, clock format, theme and other preferences live in `localStorage`.

---

## Project structure

| File | Purpose |
|---|---|
| `index.html` | The main app. Must be named exactly `index.html` so GitHub Pages serves it at the site root. |
| `forum.html` | The student forum page. |
| `studyPlanner.html` | The Study Planner page. |
| `rouge.html` | Landing page for visitors arriving from an unofficial mirror of the site. |
| `manifest.json` | App name, icons and theme colour for the install prompt. |
| `sw.js` | Minimal service worker (installability + basic offline shell). |
| `icons/` | App icons for Android, desktop and iOS. |

All files must be deployed together in the same folder, since pages link to each other by relative path.

## Running locally

No install needed to view it: open `index.html` in a modern browser. For the full experience (service worker, install prompt), serve the folder over HTTP, for example:

```bash
npx serve .
# or
python3 -m http.server 8000
```

Note: some features, such as traffic logging, are intentionally skipped when the page is opened from `file://`.

---

## Privacy & data

- **Stored on your device only:** selected class, clock format, theme, optional roll number, Study Planner data, and any friends you add in Bro connect.
- **Roll numbers are never sent to any server.** The German/Japanese lookup runs locally against a list embedded in the page. The only thing recorded is an anonymous count of how many visitors have a foreign-language course, never the roll number, name or language.
- **Anonymous usage statistics:** each visit logs a random visitor ID, the page, referrer, your selected class, and basic device info (device type, OS, browser, screen size, language, timezone). No names, logins or roll numbers are collected.
- **Survey answers** are anonymous: only your answers and your class are saved.
- **Supabase keys in the page** are the public "anon" keys. Security relies on Row Level Security: timetable tables are read-only, and the traffic and survey tables are insert-only.

To clear everything, clear the site's data in your browser.

## Known limitations

- Timetable data was extracted with AI from official PDFs, so errors in rooms, times or faculty can happen.
- Bro connect and Empty classrooms use the regular weekly timetable only. They don't account for holidays, exams, club or event bookings, makeup lectures or one-off changes.
- Empty classrooms only knows about FY sessions, so rooms used by SY, TY or BTech classes may show as free.
- Teacher campus labels are inferred from the branch (CS, CS-AIML, CS-AI and IT are at Bibwewadi; the rest at Kondhwa).
- Preferences don't sync across devices.

## Disclaimer

This is an **unofficial, student-made tool**, not affiliated with or endorsed by VIT Pune. Timetable data is extracted with the help of AI from the official college schedule. Please cross-check with the official department timetable for anything important. See the "Terms & conditions" link on the class-picker screen.

## Contributing & feedback

Spotted a wrong room, a missing class or a bug? Open an issue or send a pull request. Corrections to timetable data are especially welcome. You can also use the in-app Forum or survey.

## Credits

Made by [Vedant Bhat](https://github.com/vedantbhat28) (VIT Pune '30), built entirely with AI (Claude, Anthropic): design, code and content. Other projects: [CETkit](https://cetkit.github.io/cetkit) and [CPPkit](https://vedantbhat28.github.io/cppkit).
