#!/usr/bin/env python3
"""
resume build pipeline — resume.yaml -> dist/index.html + dist/ats.html
=======================================================================
Usage:
    pip install pyyaml jinja2
    python build.py                  # builds both targets into ./dist
    python build.py --only ats       # or: --only hybrid

Schema: JSON Resume (https://jsonresume.org/schema/) with two extensions:
  1. A work entry may contain `subsections` (list of {name, keywords, highlights})
     — used to group multiple projects under ONE employer (e.g. Poonawalla).
  2. Volunteer entries are rendered inside Experience, tagged "(Volunteer)".

Optional GitHub Pages auto-deploy — save as .github/workflows/deploy.yml:
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
        - run: pip install pyyaml jinja2 && python build.py
        - uses: peaceiris/actions-gh-pages@v4
          with:
            github_token: ${{ secrets.GITHUB_TOKEN }}
            publish_dir: ./dist
  ---------------------------------------------------------------
Now `git push` = resume deployed. That's the whole pipeline.
"""
import argparse
import datetime
import pathlib
import sys

try:
    import yaml
    from jinja2 import Environment, BaseLoader
except ImportError:
    sys.exit("Missing deps. Run: pip install pyyaml jinja2")

# ---------------------------------------------------------------- helpers

def fmt_date(iso, default="Present"):
    """'2026-04-01' -> 'April 2026'; None/'' -> 'Present'."""
    if not iso:
        return default
    d = datetime.date.fromisoformat(str(iso)[:10])
    return d.strftime("%B %Y")

def daterange(item):
    return f"{fmt_date(item.get('startDate'))} – {fmt_date(item.get('endDate'))}"

def env():
    e = Environment(loader=BaseLoader(), autoescape=True,
                    trim_blocks=True, lstrip_blocks=True)
    e.filters["daterange"] = daterange
    e.filters["fmtdate"] = fmt_date
    return e

# ---------------------------------------------------------------- macros
# Shared Jinja fragments used by both templates.

MACRO_HEAD = """
{% set b = r.basics %}
{% set gh = (r.basics.profiles | selectattr('network','equalto','GitHub') | list | first) %}
{% set li = (r.basics.profiles | selectattr('network','equalto','LinkedIn') | list | first) %}
"""

# ---------------------------------------------------------------- ATS (linear)

TPL_ATS = MACRO_HEAD + """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>{{ b.name }} — Resume</title>
<style>
@page{margin:.4in;size:letter}
body{font-family:Georgia,"Times New Roman",serif;color:#1a1a1a;font-size:10pt;
line-height:1.25;max-width:8.5in;margin:0 auto;padding:.4in;background:#fff}
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
@media print{.card{page-break-inside:avoid}.allow-break{page-break-inside:auto}}
</style></head><body>

<h1>{{ b.name | upper }}</h1>
<p class="role">{{ b.label }}</p>
<p class="contact">{{ b.location.city }}, {{ b.location.region }}, India | {{ b.phone }} | {{ b.email }}</p>
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
<h2>Volunteer Experience</h2>
{% for v in r.volunteer %}
<div class="card">
<h3>{{ v.position }} (Volunteer) — {{ v.organization }}</h3>
<p class="when">{{ v | daterange }}</p>
<ul>{% for h in v.highlights %}<li>{{ h }}</li>{% endfor %}</ul>
</div>
{% endfor %}
{% endif %}

<h2>Projects</h2>
{% for p in r.projects %}
<div class="card">
<h3>{{ p.name }}</h3>
<p class="when">{{ p | daterange }}{% if p.keywords %} | {{ p.keywords | join(', ') }}{% endif %}</p>
<ul>{% for h in p.highlights %}<li>{{ h }}</li>{% endfor %}</ul>
</div>
{% endfor %}

<h2>Education</h2>
{% for e in r.education %}
<h3>{{ e.studyType }}, {{ e.area }}</h3>
<p class="when">{{ e | daterange }} | {{ e.institution }} | CGPA: {{ e.score }}</p>
{% endfor %}

{% if r.publications %}
<h2>Publications</h2>
{% for p in r.publications %}
<p>"{{ p.name }}" — {{ p.publisher }}, {{ p.releaseDate | fmtdate }}. {{ p.summary }}</p>
{% endfor %}
{% endif %}

<h2>Languages</h2>
<p>{% for l in r.languages %}{{ l.language }} ({{ l.fluency }}){% if not loop.last %} | {% endif %}{% endfor %}</p>

</body></html>
"""

# ---------------------------------------------------------------- hybrid
# Terminal on screen, macchiato in print. Same architecture as approved:
# .side/.main are display:contents on screen (flex `order` re-sequences),
# and re-form as macchiato columns in @media print.

TPL_HYBRID = MACRO_HEAD + """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ b.name }} — {{ b.label }}</title>
<style>
:root{--bg:#0a0e14;--panel:#11161f;--panel2:#161d29;--ink:#d6dde8;--dim:#7d8799;
--green:#7ee787;--cyan:#79c0ff;--amber:#ffbe5c;--pink:#ff7b9c;--purple:#c497ff;--rule:#232c3b;
--mono:"SF Mono","Cascadia Code",Consolas,monospace;--sans:"Segoe UI",system-ui,sans-serif;
--teal:#3d8b7d;--teal-dark:#2e6b60;--m-ink:#2b2b2b;--m-gray:#6b6b6b;--m-light:#9a9a9a;
--chipbg:#f0f2f1;--m-rule:#e3e3e3}
*{box-sizing:border-box;margin:0}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);line-height:1.55}
.wrap{max-width:880px;margin:0 auto;padding:40px 24px 80px}
.print-topbar{display:none}
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
.side,.main{display:contents}
{% for i in range(1,8) %}.o{{ i }}{order:{{ i }}}{% endfor %}
section{margin-top:44px}
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
@media print{
@page{margin:0;size:letter}
body{background:#fff;color:var(--m-ink);line-height:1.4}
.wrap{max-width:100%;padding:0 0 .3in 0}
.screen-only,.term-bar,nav.pills,.btn-print,.cursor,.prompt-line,footer .hint{display:none!important}
.print-topbar{display:block;height:10px;background:var(--teal);
-webkit-print-color-adjust:exact;print-color-adjust:exact}
.term{background:none;border:none;box-shadow:none;border-radius:0}
.term-body{padding:.26in .45in .1in;font-family:var(--sans)}
.name{font-family:Georgia,serif;font-size:26pt;letter-spacing:4px;color:#222;margin:0}
.name .accent{color:#222}
.role{font-family:var(--sans);font-size:11pt;color:var(--m-gray);letter-spacing:2.5px;margin:2px 0 8px}
.contactline{font-family:var(--sans);font-size:8.5pt;color:var(--m-gray);overflow-wrap:anywhere}
.contactline a{color:var(--m-gray);border:none}
.cols{flex-direction:row;align-items:flex-start;gap:.32in;padding:0 .45in}
.side{display:block;width:29%;flex:0 0 29%;min-width:0}
.main{display:block;width:71%;flex:1 1 auto;min-width:0}
{% for i in range(1,8) %}.o{{ i }}{order:0}{% endfor %}
section{margin-top:0}
h2.sec{font-family:var(--sans);font-size:10pt;font-weight:400;color:var(--m-light);
letter-spacing:1.5px;margin:12px 0 6px}
h2.sec::before{content:""}
h2.sec::after{width:34px;height:2px;background:var(--teal);margin-top:3px;
-webkit-print-color-adjust:exact;print-color-adjust:exact}
.card{background:none;border:none;border-radius:0;padding:6px 0 5px;margin:0;
border-bottom:1px dashed var(--m-rule);page-break-inside:avoid;transform:none}
.card.allow-break{page-break-inside:auto}
.card:last-child,.side .card{border-bottom:none}
.side .card{padding:2px 0}
.card h3{font-size:11pt;color:#222}
.card h3 .at{color:var(--m-gray);font-size:9.5pt}
.dates{font-family:var(--sans);font-size:8.2pt;color:var(--m-light);font-style:italic;white-space:nowrap}
.blurb{font-size:8.8pt;color:var(--m-gray);margin:1px 0 3px}
.sub{font-family:var(--sans);font-size:9pt;font-weight:700;color:#222;margin:6px 0 1px}
.card ul{padding-left:15px;margin:2px 0 3px}
.card li{font-size:9pt;line-height:1.4;margin-bottom:2px}
.card li::marker{color:var(--teal);-webkit-print-color-adjust:exact;print-color-adjust:exact}
.chips{gap:3px;margin:2px 0 3px}
.chip{font-family:var(--sans);font-size:7.8pt;color:#3a3a3a;background:var(--chipbg);
border:none;border-radius:3px;padding:2px 6px;
-webkit-print-color-adjust:exact;print-color-adjust:exact}
.group{margin-bottom:9px}
.group h3{font-family:var(--sans);font-size:8.5pt;font-weight:700;color:var(--m-ink);margin:0 0 3px}
.plainlist{font-size:8.3pt;line-height:1.6;color:var(--m-ink)}
.plainlist i{color:var(--m-light);font-size:7.8pt}
footer{margin:6px .45in 0;text-align:left;font-size:7.5pt;color:var(--m-gray);font-family:var(--sans)}
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
<p class="contactline">{{ b.location.city }}, {{ b.location.region }}, India · {{ b.phone }} · {{ b.email }}</p>
<p class="contactline">{% if li %}LinkedIn: <a href="{{ li.url }}">{{ li.url | replace('https://www.','') }}</a>{% endif %}
{% if gh %} · GitHub: <a href="{{ gh.url }}">{{ gh.url | replace('https://','') }}</a>{% endif %}</p>
<nav class="pills screen-only"><a href="#exp">experience</a><a href="#skills">skills</a>
<a href="#projects">projects</a><a href="#edu">education</a>
<button class="btn-print" onclick="window.print()">⎙ print → macchiato PDF</button></nav>
</div></div>

<div class="cols">
<aside class="side">

<section class="o2" id="skills"><h2 class="sec">Skills</h2><div class="card">
{% for s in r.skills %}
<div class="group"><h3>{{ s.name | lower | replace(' & ','_') | replace(' ','_') }}:</h3>
<div class="chips">{% for k in s.keywords %}<span class="chip">{{ k }}</span>{% endfor %}</div></div>
{% endfor %}
</div></section>

<section class="o5" id="edu"><h2 class="sec">Education</h2>
{% for e in r.education %}<div class="card">
<div class="erow"><h3>{{ e.studyType }} <span class="at">— {{ e.area }}</span></h3></div>
<div class="plainlist">{{ e.institution }}<br>
<i>{{ e | daterange }}</i> · CGPA: {{ e.score }}</div>
</div>{% endfor %}</section>

{% if r.publications %}
<section class="o6"><h2 class="sec">Publication</h2>
{% for p in r.publications %}<div class="card"><div class="plainlist">
"{{ p.name }}" — {{ p.publisher }}, {{ p.releaseDate | fmtdate }}</div></div>{% endfor %}
</section>{% endif %}

<section class="o7"><h2 class="sec">Languages</h2><div class="card"><div class="plainlist">
{% for l in r.languages %}{{ l.language }} <i>({{ l.fluency }})</i>{% if not loop.last %}<br>{% endif %}{% endfor %}
</div></div></section>

</aside>
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
{% for v in r.volunteer or [] %}
<div class="card">
<div class="erow"><h3>{{ v.position }} <span class="at">· {{ v.organization }} (Volunteer, Part-Time)</span></h3>
<span class="dates">{{ v | daterange }}</span></div>
<ul>{% for h in v.highlights %}<li>{{ h }}</li>{% endfor %}</ul>
</div>
{% endfor %}
</section>

<section class="o4" id="projects"><h2 class="sec">Open Source Projects</h2>
{% for p in r.projects %}
<div class="card">
<div class="erow"><h3>{{ p.name }}</h3><span class="dates">{{ p | daterange }}</span></div>
{% if p.keywords %}<div class="chips">{% for k in p.keywords %}<span class="chip">{{ k }}</span>{% endfor %}</div>{% endif %}
<ul>{% for h in p.highlights %}<li>{{ h }}</li>{% endfor %}</ul>
</div>
{% endfor %}
</section>

</main></div>

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
    args = ap.parse_args()

    data = yaml.safe_load(pathlib.Path(args.src).read_text(encoding="utf-8"))
    out = pathlib.Path(args.out)
    out.mkdir(exist_ok=True)
    e = env()

    targets = {"hybrid": ("index.html", TPL_HYBRID), "ats": ("ats.html", TPL_ATS)}
    if args.only:
        targets = {args.only: targets[args.only]}

    for name, (fname, tpl) in targets.items():
        html = e.from_string(tpl).render(r=data)
        (out / fname).write_text(html, encoding="utf-8")
        print(f"✓ {name:6s} -> {out / fname}")

    print("\nNext: open dist/index.html | Ctrl+P for the macchiato PDF")
    print("      upload dist/ats.html print-out to job portals")

if __name__ == "__main__":
    main()