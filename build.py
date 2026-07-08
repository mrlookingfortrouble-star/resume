
#!/usr/bin/env python3
"""
resume build pipeline v3 — resume.yaml -> dist/index.html + dist/ats.html
===========================================================================
Usage:
    pip install pyyaml jinja2
    python build.py                # build both targets into ./dist
    python build.py --only ats     # single target (ats | hybrid)
    python build.py --check        # build + lint; exit 1 on placeholders
                                   #   (use this in CI)

v3 changes (full audit):
  BUGS FIXED
  - Country name derived from basics.location.countryCode (was hardcoded)
  - Both targets print A4 (was A4/Letter mismatch)
  - Bullets can no longer split across page breaks (li break-inside)
  - Nav includes Volunteer; anchor targets get scroll-margin-top
  - Removed .wrap bottom padding that fought @page bottom margin
  PRINT FRAGMENTATION (consolidated)
  - .keep wrappers bind section headings to their first card
  - Sidebar sections are atomic units; h2 break-after belt-and-braces
  - @page vertical margins give continuation pages breathing room
  - orphans/widows control on flowing text
  ROBUSTNESS
  - Content linter: flags [bracketed placeholders] and TODOs in output;
    --check makes it a CI gate
  - Schema validation with human-readable errors
  - Date parsing errors report the offending value and context
  POLISH
  - Dual-span skill titles (snake_case screen / proper-case print)
  - Lato italic 300/700 faces restored (theme fidelity)
  - prefers-reduced-motion support on the screen face
  - Meta description + generator comment in output

Schema: JSON Resume (https://jsonresume.org/schema/) + extensions:
  work[].subsections: [{name, keywords, highlights}]  # projects per employer
  volunteer[]: rendered as its own section in both targets

CI (GitHub Actions), .github/workflows/deploy.yml:
  ---------------------------------------------------------------
  name: build-resume
  on: { push: { branches: [main] } }
  jobs:
    build:
      runs-on: ubuntu-latest
      permissions: { contents: write }
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with: { python-version: '3.12' }
        - run: pip install pyyaml jinja2
        - run: python build.py --check     # fails on leftover placeholders
        - uses: peaceiris/actions-gh-pages@v4
          with:
            github_token: ${{ secrets.GITHUB_TOKEN }}
            publish_dir: ./dist
  ---------------------------------------------------------------
"""
import argparse
import datetime
import pathlib
import re
import sys

try:
    import yaml
    from jinja2 import Environment, BaseLoader
except ImportError:
    sys.exit("Missing deps. Run: pip install pyyaml jinja2")

GENERATOR = "resume-as-code v3 (build.py)"

COUNTRY_NAMES = {
    "IN": "India", "US": "United States", "GB": "United Kingdom",
    "DE": "Germany", "JP": "Japan", "SG": "Singapore", "AE": "UAE",
    "CA": "Canada", "AU": "Australia", "NL": "Netherlands",
}

# ---------------------------------------------------------------- helpers

def fmt_date(iso, default="Present"):
    if not iso:
        return default
    try:
        d = datetime.date.fromisoformat(str(iso)[:10])
    except ValueError:
        sys.exit(f"resume.yaml: unparseable date {iso!r} — expected YYYY-MM-DD")
    return d.strftime("%B %Y")

def daterange(item):
    return f"{fmt_date(item.get('startDate'))} – {fmt_date(item.get('endDate'))}"

def country_name(code):
    return COUNTRY_NAMES.get(str(code).upper(), str(code))

def env():
    e = Environment(loader=BaseLoader(), autoescape=True,
                    trim_blocks=True, lstrip_blocks=True)
    e.filters["daterange"] = daterange
    e.filters["fmtdate"] = fmt_date
    e.filters["country"] = country_name
    return e

# ---------------------------------------------------------------- validation

def validate(r):
    """Fail fast with readable errors instead of Jinja stack traces."""
    errors = []
    b = r.get("basics") or {}
    for key in ("name", "label", "email", "phone", "summary", "location"):
        if not b.get(key):
            errors.append(f"basics.{key} is missing")
    if b.get("location") and not b["location"].get("countryCode"):
        errors.append("basics.location.countryCode is missing")
    for i, w in enumerate(r.get("work") or []):
        for key in ("name", "position", "startDate"):
            if not w.get(key):
                errors.append(f"work[{i}] ({w.get('name','?')}): {key} missing")
        if not w.get("highlights") and not w.get("subsections"):
            errors.append(f"work[{i}] ({w.get('name','?')}): no highlights or subsections")
    if not r.get("skills"):
        errors.append("skills section is empty")
    if not r.get("education"):
        errors.append("education section is empty")
    if errors:
        sys.exit("Schema validation failed:\n  - " + "\n  - ".join(errors))

# ---------------------------------------------------------------- linting

PLACEHOLDER_RX = re.compile(r"\[(?:[A-Z][^\]\n]{0,40})\]")
TODO_RX = re.compile(r"\bTODO\b|\bFIXME\b|\bXXX\b")

def lint(rendered: dict) -> list:
    """Scan rendered text for content that should never reach a recruiter."""
    findings = []
    tag_rx = re.compile(r"<[^>]+>")
    for target, html in rendered.items():
        text = tag_rx.sub(" ", html)
        for m in PLACEHOLDER_RX.finditer(text):
            findings.append(f"{target}: unresolved placeholder {m.group(0)!r}")
        for m in TODO_RX.finditer(text):
            findings.append(f"{target}: leftover marker {m.group(0)!r}")
    return findings

# ---------------------------------------------------------------- macros

MACRO_HEAD = """
{% set b = r.basics %}
{% set gh = (r.basics.profiles | selectattr('network','equalto','GitHub') | list | first) %}
{% set li = (r.basics.profiles | selectattr('network','equalto','LinkedIn') | list | first) %}
{% set loc = b.location.city ~ ", " ~ b.location.region ~ ", " ~ (b.location.countryCode | country) %}
"""

# ---------------------------------------------------------------- ATS (linear)

TPL_ATS = MACRO_HEAD + """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<!-- generated by {{ generator }} — do not edit; edit resume.yaml -->
<title>{{ b.name }} — Resume</title>
<style>
@page{margin:10mm 0;size:A4}
body{font-family:Georgia,"Times New Roman",serif;color:#1a1a1a;font-size:10pt;
line-height:1.25;max-width:8.27in;margin:0 auto;padding:.4in;background:#fff}
h1{font-size:18pt;margin:0 0 1px}
.role{color:#1a4d8f;font-family:Arial,sans-serif;font-size:11pt;font-weight:700;margin:0 0 3px}
.contact{color:#444;font-family:Arial,sans-serif;font-size:9pt;margin:0}
h2{font-family:Arial,sans-serif;font-size:10pt;color:#1a4d8f;text-transform:uppercase;
letter-spacing:1.2px;border-bottom:1.25px solid #c9c9c9;padding-bottom:2px;margin:10px 0 4px}
h3{font-size:10.5pt;margin:6px 0 0}
.when{color:#444;font-family:Arial,sans-serif;font-style:italic;font-size:9pt;margin:0 0 2px}
.blurb{color:#444;font-size:9.5pt;margin:0 0 3px}
h4{font-family:Arial,sans-serif;font-size:9pt;margin:4px 0 1px}
ul{margin:1px 0 3px;padding-left:16px}
li{font-size:10pt;margin-bottom:1.5px}
.sk{font-size:9.5pt;margin:1px 0}
.sk b{font-family:Arial,sans-serif;font-size:9pt}
p,li{orphans:3;widows:3}
@media print{
.card{page-break-inside:avoid}
.allow-break{page-break-inside:auto}
li{break-inside:avoid}
h2{break-after:avoid-page}
.keep{break-inside:avoid;page-break-inside:avoid}
}
</style></head><body>

<h1>{{ b.name | upper }}</h1>
<p class="role">{{ b.label }}</p>
<p class="contact">{{ loc }} | {{ b.phone }} | {{ b.email }}</p>
<p class="contact">{% if li %}LinkedIn: {{ li.url | replace('https://www.','') }}{% endif %}
{% if gh %} | GitHub: {{ gh.url | replace('https://','') }}{% endif %}</p>

<h2>Professional Summary</h2>
<p>{{ b.summary }}</p>

<h2>Core Competencies</h2>
{% for s in r.skills %}<p class="sk"><b>{{ s.name }}:</b> {{ s.keywords | join(', ') }}</p>
{% endfor %}

<h2>Work Experience</h2>
{% for w in r.work %}
<div class="card{% if w.subsections %} allow-break{% endif %}">
<h3>{{ w.position }} — {{ w.name }}</h3>
<p class="when">{{ w | daterange }}{% if w.location %} | {{ w.location }}{% endif %}</p>
{% if w.summary %}<p class="blurb">{{ w.summary }}</p>{% endif %}
{% if w.highlights %}<ul>{% for h in w.highlights %}<li>{{ h }}</li>{% endfor %}</ul>{% endif %}
{% for sub in w.subsections or [] %}
<h4>{{ sub.name }}</h4>
<ul>{% for h in sub.highlights %}<li>{{ h }}</li>{% endfor %}</ul>
{% endfor %}
</div>
{% endfor %}

{% if r.volunteer %}
{% for v in r.volunteer %}
{% if loop.first %}<div class="keep"><h2>Volunteer Experience</h2>{% endif %}
<div class="card">
<h3>{{ v.position }} (Volunteer) — {{ v.organization }}</h3>
<p class="when">{{ v | daterange }}</p>
<ul>{% for h in v.highlights %}<li>{{ h }}</li>{% endfor %}</ul>
</div>
{% if loop.first %}</div>{% endif %}
{% endfor %}
{% endif %}

{% for p in r.projects %}
{% if loop.first %}<div class="keep"><h2>Projects</h2>{% endif %}
<div class="card">
<h3>{{ p.name }}</h3>
<p class="when">{{ p | daterange }}{% if p.keywords %} | {{ p.keywords | join(', ') }}{% endif %}</p>
<ul>{% for h in p.highlights %}<li>{{ h }}</li>{% endfor %}</ul>
</div>
{% if loop.first %}</div>{% endif %}
{% endfor %}

<div class="keep">
<h2>Education</h2>
{% for e in r.education %}
<h3>{{ e.studyType }}, {{ e.area }}</h3>
<p class="when">{{ e | daterange }} | {{ e.institution }} | CGPA: {{ e.score }}</p>
{% endfor %}
</div>

{% if r.publications %}
<div class="keep">
<h2>Publications</h2>
{% for p in r.publications %}
<p>"{{ p.name }}" — {{ p.publisher }}, {{ p.releaseDate | fmtdate }}. {{ p.summary }}</p>
{% endfor %}
</div>
{% endif %}

<div class="keep">
<h2>Languages</h2>
<p>{% for l in r.languages %}{{ l.language }} ({{ l.fluency }}){% if not loop.last %} | {% endif %}{% endfor %}</p>
</div>

</body></html>
"""

# ---------------------------------------------------------------- hybrid
# Screen: terminal. Print: original macchiato (Josefin Sans / Lato,
# #56817A, keylines, ghostwhite chips, dotted separators, A4).
# DOM order is ATS-linear (main content first); print swaps columns
# visually via display:table + direction:rtl, which also keeps the
# columns attached across page breaks (flex fragments unreliably).

TPL_HYBRID = MACRO_HEAD + """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<!-- generated by {{ generator }} — do not edit; edit resume.yaml -->
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="description" content="{{ b.name }} — {{ b.label }}. Interactive resume: terminal-themed on screen, print for the document version.">
<title>{{ b.name }} — {{ b.label }}</title>
<style>
/* ── macchiato-original fonts (print face) ── */
@font-face{font-family:'Josefin Sans';font-style:normal;font-weight:300;
src:local('Josefin Sans Light'),local('JosefinSans-Light'),
url(https://fonts.gstatic.com/s/josefinsans/v14/Qw3FZQNVED7rKGKxtqIqX5Ecpl5te10k.ttf) format('truetype')}
@font-face{font-family:'Josefin Sans';font-style:normal;font-weight:700;
src:local('Josefin Sans Bold'),local('JosefinSans-Bold'),
url(https://fonts.gstatic.com/s/josefinsans/v14/Qw3FZQNVED7rKGKxtqIqX5Ectllte10k.ttf) format('truetype')}
@font-face{font-family:'Lato';font-style:normal;font-weight:300;
src:local('Lato Light'),local('Lato-Light'),
url(https://fonts.gstatic.com/s/lato/v16/S6u9w4BMUTPHh7USSwiPHA.ttf) format('truetype')}
@font-face{font-family:'Lato';font-style:normal;font-weight:400;
src:local('Lato Regular'),local('Lato-Regular'),
url(https://fonts.gstatic.com/s/lato/v16/S6uyw4BMUTPHjx4wWw.ttf) format('truetype')}
@font-face{font-family:'Lato';font-style:normal;font-weight:700;
src:local('Lato Bold'),local('Lato-Bold'),
url(https://fonts.gstatic.com/s/lato/v16/S6u9w4BMUTPHh6UVSwiPHA.ttf) format('truetype')}
@font-face{font-family:'Lato';font-style:italic;font-weight:300;
src:local('Lato Light Italic'),local('Lato-LightItalic'),
url(https://fonts.gstatic.com/s/lato/v16/S6u_w4BMUTPHjxsI9w2_Gwfo.ttf) format('truetype')}
@font-face{font-family:'Lato';font-style:italic;font-weight:400;
src:local('Lato Italic'),local('Lato-Italic'),
url(https://fonts.gstatic.com/s/lato/v16/S6u8w4BMUTPHjxsAXC-v.ttf) format('truetype')}
@font-face{font-family:'Lato';font-style:italic;font-weight:700;
src:local('Lato Bold Italic'),local('Lato-BoldItalic'),
url(https://fonts.gstatic.com/s/lato/v16/S6u_w4BMUTPHjxsI5wq_Gwfo.ttf) format('truetype')}

:root{--bg:#0a0e14;--panel:#11161f;--panel2:#161d29;--ink:#d6dde8;--dim:#7d8799;
--green:#7ee787;--cyan:#79c0ff;--amber:#ffbe5c;--pink:#ff7b9c;--purple:#c497ff;--rule:#232c3b;
--mono:"SF Mono","Cascadia Code",Consolas,monospace;--sans:"Segoe UI",system-ui,sans-serif;
--m-green:#56817A;--m-ink:#39424B;--m-em:#999;--m-dotted:#e0e0e0;
--m-head:"Josefin Sans",Helvetica,Arial,sans-serif;
--m-body:"Lato",Helvetica,Arial,sans-serif}
*{box-sizing:border-box;margin:0}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);line-height:1.55}
.wrap{max-width:880px;margin:0 auto;padding:40px 24px 80px}
.print-topbar{display:none}
.print-name{display:none}
.term{background:var(--panel);border:1px solid var(--rule);border-radius:12px;overflow:hidden;
box-shadow:0 18px 50px rgba(0,0,0,.5)}
.term-bar{display:flex;align-items:center;gap:8px;padding:10px 14px;background:var(--panel2);
border-bottom:1px solid var(--rule);font-family:var(--mono);font-size:12px;color:var(--dim)}
.dot{width:11px;height:11px;border-radius:50%}
.dot.r{background:#ff5f57}.dot.y{background:#febc2e}.dot.g{background:#28c840}
.term-body{padding:26px 28px;font-family:var(--mono);font-size:14px}
.prompt{color:var(--green)}
.cursor{display:inline-block;width:8px;height:16px;background:var(--green);
vertical-align:text-bottom;animation:blink 1.1s steps(1) infinite}
@keyframes blink{50%{opacity:0}}
.name{font-size:clamp(28px,5vw,44px);font-weight:800;letter-spacing:1px;color:#fff;
margin:14px 0 2px;font-family:var(--mono)}
.name .accent{color:var(--green)}
.role{color:var(--cyan);font-family:var(--mono);font-size:15px;margin-bottom:14px}
.contactline{font-family:var(--mono);font-size:12.5px;color:var(--dim)}
.contactline a{color:var(--cyan);text-decoration:none;border-bottom:1px dashed #2c3a52}
nav.pills{display:flex;flex-wrap:wrap;gap:8px;margin:22px 0 6px}
nav.pills a{font-family:var(--mono);font-size:12px;color:var(--dim);border:1px solid var(--rule);
border-radius:999px;padding:5px 13px;text-decoration:none}
nav.pills a:hover{color:var(--green);border-color:var(--green)}
.btn-print{font-family:var(--mono);font-size:12px;cursor:pointer;background:var(--green);
color:#08210e;border:none;border-radius:999px;padding:6px 14px;font-weight:700}

.cols{display:flex;flex-direction:column}
.side,.main,.keep{display:contents}
{% for i in range(1,9) %}.o{{ i }}{order:{{ i }}}{% endfor %}

section{margin-top:44px;scroll-margin-top:20px}
h2.sec{font-family:var(--mono);font-size:14px;color:var(--pink);letter-spacing:1px;margin-bottom:16px}
h2.sec::before{content:"## ";color:var(--dim)}
h2.sec::after{content:"";display:block;height:1px;margin-top:8px;
background:linear-gradient(90deg,var(--rule),transparent)}
.card{background:var(--panel);border:1px solid var(--rule);border-radius:10px;
padding:20px 22px;margin-bottom:14px;transition:transform .2s,border-color .2s}
.card:hover{transform:translateY(-3px);border-color:#33507a}
.erow{display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap}
.card h3{font-size:16px;color:#fff}
.card h3 .at{color:var(--dim);font-weight:400}
.dates{font-family:var(--mono);font-size:11.5px;color:var(--amber)}
.blurb{color:var(--dim);font-size:13.5px;margin:4px 0 10px}
.sub{font-family:var(--mono);font-size:12px;color:var(--purple);margin:12px 0 5px}
.card ul{padding-left:18px}
.card li{font-size:13.5px;margin-bottom:5px}
.card li::marker{color:var(--green)}
.chips{display:flex;flex-wrap:wrap;gap:7px;margin:6px 0 4px}
.chip{font-family:var(--mono);font-size:11.5px;color:var(--cyan);background:#0d2138;
border:1px solid #1d3d5f;border-radius:6px;padding:3px 9px}
.group{margin-bottom:12px}
.group h3{font-family:var(--mono);font-size:12px;color:var(--amber);font-weight:400;margin-bottom:4px}
.plainlist{font-size:13.5px}
.plainlist i{color:var(--dim)}
footer{margin-top:60px;text-align:center;font-family:var(--mono);font-size:11.5px;color:var(--dim)}
footer .hint{color:var(--amber)}

@media (prefers-reduced-motion: reduce){
.cursor{animation:none}
.card{transition:none}
.card:hover{transform:none}
}

/* ════════════════════════════════════════════════════════════
   PRINT — original macchiato.
   ════════════════════════════════════════════════════════════ */
@media print{
@page{margin:10mm 0;size:A4}
body{background:#fff;color:var(--m-ink);font-family:var(--m-body);
font-weight:400;letter-spacing:.3px;line-height:1.45}
.wrap{max-width:100%;padding:0}
.screen-only,.term-bar,nav.pills,.btn-print,.cursor,.prompt-line,footer .hint{display:none!important}
.print-name{display:inline}
.print-topbar{display:block;height:10px;background:var(--m-green);
-webkit-print-color-adjust:exact;print-color-adjust:exact}
.term{background:none;border:none;box-shadow:none;border-radius:0}
.term-body{padding:22px 22px 6px 34px;font-family:var(--m-body)}
.name{font-family:var(--m-head);font-weight:700;font-size:40px;letter-spacing:1px;
color:var(--m-ink);margin:0}
.name .accent{color:var(--m-ink)}
.role{font-family:var(--m-head);font-weight:300;font-size:16px;letter-spacing:.5px;
color:var(--m-ink);margin:2px 0 8px}
.contactline{font-family:var(--m-body);font-size:11px;color:var(--m-ink);overflow-wrap:anywhere}
.contactline a{color:var(--m-ink);border:none;text-decoration:none}

/* columns: table + rtl = ATS-linear DOM, sidebar visually left,
   cells stay attached across page breaks */
.cols{display:table;width:100%;direction:rtl;padding:0 22px 0 34px}
.main{display:table-cell;direction:ltr;vertical-align:top;width:auto}
.side{display:table-cell;direction:ltr;vertical-align:top;width:160px;padding-right:20px}
{% for i in range(1,9) %}.o{{ i }}{order:0}{% endfor %}

section{margin-top:0;margin-bottom:12px}
.side section{break-inside:avoid;page-break-inside:avoid}
.keep{display:block;break-inside:avoid;page-break-inside:avoid}
h2.sec{font-family:var(--m-head);font-weight:300;font-size:16px;letter-spacing:.5px;
color:var(--m-ink);margin:0 0 2px;break-after:avoid-page}
h2.sec::before{content:""}
h2.sec::after{content:"";display:block;width:45px;height:0;
border-top:1px solid var(--m-green);margin:8px 0 10px;background:none;
-webkit-print-color-adjust:exact;print-color-adjust:exact}
.card{background:none;border:none;border-radius:0;padding:0;margin:0 0 10px;
page-break-inside:avoid;transform:none}
.card.allow-break{page-break-inside:auto}
.main .card + .card,.main .keep + .card{padding-top:8px;border-top:1px dotted var(--m-dotted)}
.card h3{font-family:var(--m-body);font-weight:700;font-size:13px;color:var(--m-ink)}
.card h3 .at{color:var(--m-ink);font-weight:300;font-size:12px}
.dates{font-family:var(--m-body);font-style:italic;font-size:10px;color:var(--m-em);white-space:nowrap}
.blurb{font-family:var(--m-body);font-style:italic;font-size:10.5px;color:var(--m-em);margin:1px 0 4px}
.sub{font-family:var(--m-body);font-weight:700;font-size:11px;color:var(--m-ink);margin:7px 0 1px}
.card ul{margin:3px 0 0;padding-left:18px}
.card li{font-size:11px;line-height:1.4;margin-bottom:2px;padding-left:4px;color:var(--m-ink);
break-inside:avoid;orphans:3;widows:3}
.card li::marker{color:var(--m-green);-webkit-print-color-adjust:exact;print-color-adjust:exact}
.chips{gap:0;margin:2px 0 3px}
.chip{font-family:var(--m-body);font-size:9px;color:var(--m-ink);background:ghostwhite;
border:none;border-radius:5px;margin:.15em;padding:.15em .4em;
-webkit-print-color-adjust:exact;print-color-adjust:exact}
.group{margin-bottom:9px}
.group h3{font-family:var(--m-body);font-size:10px;font-weight:700;color:var(--m-ink);margin:0 0 2px}
.plainlist{font-size:10px;line-height:1.6;color:var(--m-ink)}
.plainlist i{color:var(--m-em);font-size:9.5px}
footer{margin:8px 22px 0 34px;text-align:left;font-size:9px;color:var(--m-em);font-family:var(--m-body)}
}
</style></head><body>
<div class="wrap">
<div class="print-topbar"></div>

<div class="term">
<div class="term-bar screen-only"><span class="dot r"></span><span class="dot y"></span>
<span class="dot g"></span><span style="margin-left:8px">arnav@pune:~/resume — zsh</span></div>
<div class="term-body">
<div class="prompt-line screen-only"><span class="prompt">➜ ~/resume</span>
 cat resume.yaml | render --target=$MEDIUM<span class="cursor"></span></div>
<div class="name">{{ b.name.split(' ')[0] | upper }} <span class="accent">{{ b.name.split(' ')[1:] | join(' ') | upper }}</span></div>
<div class="role">{{ b.label }}</div>
<p class="contactline">{{ loc }} · {{ b.phone }} · {{ b.email }}</p>
<p class="contactline">{% if li %}LinkedIn: <a href="{{ li.url }}">{{ li.url | replace('https://www.','') }}</a>{% endif %}
{% if gh %} · GitHub: <a href="{{ gh.url }}">{{ gh.url | replace('https://','') }}</a>{% endif %}</p>
<nav class="pills screen-only"><a href="#exp">experience</a><a href="#skills">skills</a>
{% if r.volunteer %}<a href="#volunteer">volunteer</a>{% endif %}<a href="#projects">projects</a>
<a href="#edu">education</a>
<button class="btn-print" onclick="window.print()" aria-label="Print resume as PDF">⎙ print → macchiato PDF</button></nav>
</div></div>

<!-- DOM ORDER = ATS EXTRACTION ORDER. Print swaps columns visually
     via direction:rtl, never in the content stream. -->
<div class="cols">

<main class="main">

<section class="o1" id="summary"><h2 class="sec">Summary</h2>
<div class="card"><ul style="list-style:none;padding:0"><li>{{ b.summary }}</li></ul></div></section>

<section class="o3" id="exp"><h2 class="sec">Experience</h2>
{% for w in r.work %}
<div class="card{% if w.subsections %} allow-break{% endif %}">
<div class="erow"><h3>{{ w.position }} <span class="at">· {{ w.name }}</span></h3>
<span class="dates">{{ w | daterange }}</span></div>
{% if w.summary %}<p class="blurb">{{ w.summary }}</p>{% endif %}
{% if w.highlights %}<ul>{% for h in w.highlights %}<li>{{ h }}</li>{% endfor %}</ul>{% endif %}
{% for sub in w.subsections or [] %}
<div class="sub">{{ sub.name }}</div>
{% if sub.keywords %}<div class="chips">{% for k in sub.keywords %}<span class="chip">{{ k }}</span>{% endfor %}</div>{% endif %}
<ul>{% for h in sub.highlights %}<li>{{ h }}</li>{% endfor %}</ul>
{% endfor %}
</div>
{% endfor %}
</section>

{% if r.volunteer %}
<section class="o4" id="volunteer">
{% for v in r.volunteer %}
{% if loop.first %}<div class="keep"><h2 class="sec">Volunteer</h2>{% endif %}
<div class="card">
<div class="erow"><h3>{{ v.position }} <span class="at">· {{ v.organization }}</span></h3>
<span class="dates">{{ v | daterange }}</span></div>
<ul>{% for h in v.highlights %}<li>{{ h }}</li>{% endfor %}</ul>
</div>
{% if loop.first %}</div>{% endif %}
{% endfor %}
</section>
{% endif %}

<section class="o5" id="projects">
{% for p in r.projects %}
{% if loop.first %}<div class="keep"><h2 class="sec">Open Source Projects</h2>{% endif %}
<div class="card">
<div class="erow"><h3>{{ p.name }}</h3><span class="dates">{{ p | daterange }}</span></div>
{% if p.keywords %}<div class="chips">{% for k in p.keywords %}<span class="chip">{{ k }}</span>{% endfor %}</div>{% endif %}
<ul>{% for h in p.highlights %}<li>{{ h }}</li>{% endfor %}</ul>
</div>
{% if loop.first %}</div>{% endif %}
{% endfor %}
</section>

</main>

<aside class="side">

<section class="o2" id="skills"><h2 class="sec">Skills</h2><div class="card">
{% for s in r.skills %}
<div class="group"><h3><span class="screen-only">{{ s.name | lower | replace(' & ','_') | replace(' ','_') }}:</span><span class="print-name">{{ s.name }}</span></h3>
<div class="chips">{% for k in s.keywords %}<span class="chip">{{ k }}</span>{% endfor %}</div></div>
{% endfor %}
</div></section>

<section class="o6" id="edu"><h2 class="sec">Education</h2>
{% for e in r.education %}<div class="card">
<div class="erow"><h3>{{ e.studyType }} <span class="at">— {{ e.area }}</span></h3></div>
<div class="plainlist">{{ e.institution }}<br>
<i>{{ e | daterange }}</i> · CGPA: {{ e.score }}</div>
</div>{% endfor %}</section>

{% if r.publications %}
<section class="o7"><h2 class="sec">Publication</h2>
{% for p in r.publications %}<div class="card"><div class="plainlist">
"{{ p.name }}" — {{ p.publisher }}, {{ p.releaseDate | fmtdate }}</div></div>{% endfor %}
</section>{% endif %}

<section class="o8"><h2 class="sec">Languages</h2><div class="card"><div class="plainlist">
{% for l in r.languages %}{{ l.language }} <i>({{ l.fluency }})</i>{% if not loop.last %}<br>{% endif %}{% endfor %}
</div></div></section>

</aside>

</div>

<footer><span class="hint">// hint: Ctrl+P re-renders this page as a macchiato document.
view-source is welcome.</span><br>{{ b.name }} — {{ b.email }}</footer>
</div></body></html>
"""

# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="resume.yaml -> HTML")
    ap.add_argument("--src", default="resume.yaml")
    ap.add_argument("--out", default="dist")
    ap.add_argument("--only", choices=["hybrid", "ats"])
    ap.add_argument("--check", action="store_true",
                    help="lint rendered output; exit 1 on placeholders (CI gate)")
    args = ap.parse_args()

    src = pathlib.Path(args.src)
    if not src.exists():
        sys.exit(f"{args.src} not found")
    data = yaml.safe_load(src.read_text(encoding="utf-8"))
    validate(data)

    out = pathlib.Path(args.out)
    out.mkdir(exist_ok=True)
    e = env()

    targets = {"hybrid": ("index.html", TPL_HYBRID), "ats": ("ats.html", TPL_ATS)}
    if args.only:
        targets = {args.only: targets[args.only]}

    rendered = {}
    for name, (fname, tpl) in targets.items():
        html = e.from_string(tpl).render(r=data, generator=GENERATOR)
        (out / fname).write_text(html, encoding="utf-8")
        rendered[name] = html
        print(f"✓ {name:6s} -> {out / fname}")

    findings = lint(rendered)
    if findings:
        print("\n⚠ content lint:")
        for f in findings:
            print(f"  - {f}")
        if args.check:
            sys.exit(1)
    elif args.check:
        print("✓ lint clean")

    print("\nNext: open dist/index.html | Ctrl+P for the macchiato PDF")
    print("      upload dist/ats.html print-out to job portals")

if __name__ == "__main__":
    main()
