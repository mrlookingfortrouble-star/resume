# resume-as-code

> One YAML file. Three renderings. Zero manual formatting, ever again.

**Live:** [arnav-mahadeshwar.github.io](https://arnav-mahadeshwar.github.io/resume) · **Author:** Arnav Mahadeshwar · [LinkedIn](www.linkedin.com/in/arnav-bala)

[![build](https://github.com/arnav-mahadeshwar/resume/actions/workflows/deploy.yml/badge.svg)](https://github.com/arnav-mahadeshwar/resume/actions)
![python](https://img.shields.io/badge/python-3.12-blue)
![deps](https://img.shields.io/badge/deps-pyyaml%20%2B%20jinja2-lightgrey)
![js](https://img.shields.io/badge/runtime%20JS-~1%20line-brightgreen)

---

If you're reading this because it was listed as a project *on the resume it builds* — yes, that's intentional. This repository is the pipeline that generates that document. The resume references the project; the project produces the resume. Updating my resume is now:

```bash
vim resume.yaml && git push
```

That's the entire workflow. CI does the rest.

---

## Why this exists

A resume in 2026 has to satisfy three very different readers, with conflicting requirements:

| Reader | Wants | Punishes |
|---|---|---|
| **ATS parsers** (~97% of large employers) | Linear text, standard headers, complete dates | Columns, graphics, clipped text, icon fonts |
| **Human recruiters** (~7 seconds of attention) | Visual hierarchy, scannability, polish | Walls of plain text |
| **Engineers** (interviews, referrals) | Evidence you can actually build things | Claims without artifacts |

Most people solve this by maintaining multiple documents that drift out of sync. This repo solves it with **one source of truth and per-audience compilation** — the same way you'd never hand-maintain three copies of a config for dev/staging/prod.

```
                        ┌──────────────────────────────┐
                        │         resume.yaml          │
                        │   (JSON Resume schema + 2    │
                        │    extensions, see below)    │
                        └──────────────┬───────────────┘
                                       │  python build.py
                        ┌──────────────┴───────────────┐
                        ▼                              ▼
              ┌───────────────────┐        ┌───────────────────┐
              │   dist/index.html │        │   dist/ats.html   │
              │  "the shapeshifter"│        │  "the guarantee"  │
              └─────┬────────┬────┘        └─────────┬─────────┘
                    │        │                       │
             screen │        │ Ctrl+P               │ Ctrl+P
                    ▼        ▼                       ▼
             terminal UI   two-column          single-column
             (portfolio)   "macchiato" PDF     ATS-safe PDF
                           (for humans)        (for portals)
```

---

## The interesting part: one DOM, two faces

`dist/index.html` contains **no duplicated content and ~1 line of JavaScript** (`window.print()`), yet renders as two completely different documents:

- **On screen:** a dark, terminal-themed interactive page — window chrome, blinking cursor, syntax-colored skill chips, hover-lifting cards.
- **On print:** a two-column serif document with a teal accent bar, sidebar skills, and dashed entry separators.

The mechanism is two CSS features doing a job usually reserved for a templating engine:

1. **`display: contents`** — on screen, the print layout's column containers (`.side`, `.main`) are dissolved from the layout tree, so all sections become siblings in a single flex column.
2. **Flexbox `order`** — those siblings are then re-sequenced (`.o1`–`.o7`) into a narrative order for scrolling: summary → skills → experience → projects → education.
3. **At `@media print`**, both tricks are reverted: the containers reappear as a 29/71 grid of real columns, and DOM order takes over inside each.

No framework, no build-time duplication, no hydration. View source — it's all there.

---

## The engineering problem: PDF text extraction order

This is the part of the project I'd actually defend in an interview.

When an ATS extracts text from a PDF, it uses one of two strategies — and the applicant never knows which:

- **Content-stream order:** text runs are read in the order they were written to the file. Browser print-to-PDF writes them in approximately **DOM order**.
- **Geometric reconstruction:** coordinates are used to rebuild reading order. Good implementations detect columns and read each whole; crude ones interleave lines by y-position — the classic two-column failure mode.

A multi-column layout can therefore never be *provably* safe for all parsers. This repo's response is defense in depth:

1. **DOM order is a valid resume on its own.** The markup is sequenced `header → summary → experience → projects → skills → education → publications → languages`, and the sidebar is moved to the *left visually* via `order: -1` at print time. Stream-order extractors get a textbook linear resume.
2. **Geometry is kept trivially clean.** Full-width identity header (name/contact always parse first and intact), non-overlapping column x-ranges, `min-width: 0` everywhere so no text can ever clip out of the page box, complete written dates (`April 2026 – Present`) with `white-space: nowrap`.
3. **A zero-risk fallback exists.** `ats.html` is strictly single-column — under *any* extraction strategy it produces identical, perfect output. That version goes to application portals; the styled version goes to humans.

This design was informed by a real failure: an earlier template silently **clipped text past the page edge**, so words were missing from the PDF's text layer entirely — dates truncated to `04/2026 - P`, sentences ending mid-word. No visual inspection caught it. Which motivates:

### The 10-second verification test

Open any resume PDF → `Ctrl+A` → copy → paste into a plain-text editor. If the result reads top-to-bottom as complete sentences with complete dates, parsers can handle it. Both outputs of this pipeline pass; the template it replaced did not. *(Try it on your own resume. Seriously.)*

---

## Schema

[JSON Resume](https://jsonresume.org/schema/) in YAML, with two extensions:

```yaml
work:
  - name: "Employer"
    position: "Role"
    subsections:            # EXTENSION 1: multiple projects under one employer,
      - name: "Project A"   # so parsers see one job, not three
        keywords: [ ... ]
        highlights: [ ... ]

volunteer: [ ... ]          # EXTENSION 2: rendered inside Experience,
                            # tagged "(Volunteer, Part-Time)" — no orphan sections
```

Content rules enforced by convention (the pipeline renders whatever the YAML says — garbage in, garbage out):

- Every metric must be defensible in an interview
- Acronyms expanded on first use — `Continuous Integration/Continuous Deployment (CI/CD)` — because keyword matchers are literal
- No self-assigned skill levels
- Outcomes over outputs (time saved, not lines of code written)

---

## Usage

```bash
pip install pyyaml jinja2
python build.py                 # → dist/index.html + dist/ats.html
python build.py --only ats      # single target
```

**Export to PDF** (Chrome/Edge): `Ctrl+P` → Save as PDF → uncheck *Headers and footers* → Margins: *None* → **Background graphics: ON** (the styled version carries its own margins and colors).

**Deploy:** push to `main`. The [workflow](.github/workflows/deploy.yml) rebuilds both targets and publishes `dist/` to GitHub Pages. The badge at the top of this README is the pipeline's live status.

```
.
├── resume.yaml              # the single source of truth
├── build.py                 # ~200 lines: YAML → Jinja2 → HTML × 2
├── .github/workflows/
│   └── deploy.yml           # push = build = deploy
└── dist/                    # generated — never edited by hand
    ├── index.html           # terminal (screen) ⇄ macchiato (print)
    └── ats.html             # linear, parser-guaranteed
```

---

## FAQ

**Why not just use a resume builder / LaTeX / one of the many resume-as-code tools?**
I started with one (resumed/JSON-Resume themes). Its two-column template silently clipped text out of the PDF's text layer — undetectable visually, fatal to parsers. Owning the render pipeline means owning the failure modes. Also, the tool teaching you the most is usually the one you built.

**Isn't the styled PDF still risky for ATS?**
Marginally, yes — see [the extraction-order section](#the-engineering-problem-pdf-text-extraction-order). That residual risk is why `ats.html` exists and why portal submissions always use it. Right tool, right audience.

**Is listing this repo on the resume it generates a bit much?**
It's a working demonstration of YAML schema design, templating, CSS layout internals, CI/CD, and applied knowledge of how hiring systems parse documents — with a live build badge as proof. The self-reference is just the honest shape of the dependency graph.

---

*If you're a recruiter or hiring manager: the [live version](https://arnav-mahadeshwar.github.io) has a `⎙ print` button — press it and watch the page reshape itself. That transformation, and everything above, is the work sample.*