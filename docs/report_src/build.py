"""Build report.html and slides.html (self-contained, screenshots embedded as base64).

Run with any Python that has Pillow:  python docs/report_src/build.py
"""

import base64
import io
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC = Path(__file__).parent
SHOTS = ROOT / "docs" / "screenshots"
REAL = ROOT / "docs" / "real_runs"

PRICE = {"input": 0.10, "cached_input": 0.01, "output": 0.50}  # gpt-6-luna, USD per 1M tokens

# name: (file, crop box as fractions (left, top, right, bottom) or None)
IMAGES = {
    "home": (SHOTS / "01_home.png", (0, 0, 1, 0.62)),
    "bronner_claims": (REAL / "dr_bronners_claims.webp", None),
    "bronner_safety": (REAL / "dr_bronners_safety.webp", None),
    "bronner_tokens": (REAL / "dr_bronners_tokens.webp", None),
    "credo": (REAL / "credo_user_test_claims.webp", None),
    "inject_on": (SHOTS / "03_inject_on_safety.png", None),
    "inject_off": (SHOTS / "04_inject_off_results.png", None),
    "visible_inject": (SHOTS / "05_visible_inject_safety.png", None),
    "spend_cap": (SHOTS / "06_spend_cap.png", None),
}
CROPS = json.loads((SRC / "crops.json").read_text()) if (SRC / "crops.json").exists() else {}

# Full reviews of real product pages on 2026-10-26 (from logs/runs.jsonl):
# (label, new input, cached input, output, seconds)
REAL_RUNS = [
    ("First test page (product not recorded)", 18234, 0, 10042, 80.58),
    ("Who Gives a Crap toilet paper", 13003, 7045, 10911, 87.16),
    ("Dr. Bronner's soap, run 1", 13193, 7045, 9439, 78.44),
    ("Dr. Bronner's soap, run 2 (Figure 4)", 11916, 8843, 11364, 90.24),
    ("Credo mascara (user test)", 12498, 7045, 6753, 53.58),
]


def cost(i, c, o):
    return (i * PRICE["input"] + c * PRICE["cached_input"] + o * PRICE["output"]) / 1e6


def img_tag(name: str, cls: str = "", max_w: int = 1600) -> str:
    path, crop = IMAGES[name]
    crop = CROPS.get(name, crop)
    im = Image.open(path).convert("RGB")
    if crop:
        w, h = im.size
        im = im.crop((int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h)))
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82, optimize=True)
    data = base64.b64encode(buf.getvalue()).decode()
    c = f' class="{cls}"' if cls else ""
    return f'<img{c} alt="{name}" src="data:image/jpeg;base64,{data}">'


DIAGRAM = """<svg class="diagram" viewBox="0 0 960 300" xmlns="http://www.w3.org/2000/svg" font-family="-apple-system, Segoe UI, Roboto, Arial, sans-serif">
  <defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#475467"/></marker></defs>
  <rect x="10" y="95" width="130" height="90" rx="12" fill="#f2f4f7" stroke="#98a2b3"/>
  <text x="75" y="130" text-anchor="middle" font-size="15" font-weight="700" fill="#101828">Product page</text>
  <text x="75" y="152" text-anchor="middle" font-size="12" fill="#475467">text, URL, or</text>
  <text x="75" y="168" text-anchor="middle" font-size="12" fill="#475467">saved HTML</text>
  <rect x="165" y="80" width="130" height="120" rx="12" fill="#fffaeb" stroke="#b54708"/>
  <text x="230" y="110" text-anchor="middle" font-size="14" font-weight="700" fill="#b54708">Safety layer</text>
  <text x="230" y="132" text-anchor="middle" font-size="11.5" fill="#344054">strip hidden text</text>
  <text x="230" y="149" text-anchor="middle" font-size="11.5" fill="#344054">redact AI-directed</text>
  <text x="230" y="166" text-anchor="middle" font-size="11.5" fill="#344054">sentences</text>
  <text x="230" y="183" text-anchor="middle" font-size="11.5" fill="#344054">size + budget caps</text>
  <g font-size="15" font-weight="700" fill="#fff">
    <rect x="320" y="95" width="130" height="90" rx="12" fill="#067647"/><text x="385" y="135" text-anchor="middle">1. Extractor</text>
    <rect x="475" y="95" width="130" height="90" rx="12" fill="#067647"/><text x="540" y="135" text-anchor="middle">2. Rules</text><text x="540" y="153" text-anchor="middle">Checker</text>
    <rect x="630" y="95" width="130" height="90" rx="12" fill="#067647"/><text x="695" y="135" text-anchor="middle">3. Skeptic</text>
    <rect x="785" y="95" width="130" height="90" rx="12" fill="#067647"/><text x="850" y="135" text-anchor="middle">4. Rewriter</text>
  </g>
  <g font-size="11.5" fill="#d1fadf" text-anchor="middle">
    <text x="385" y="160">exact quotes</text><text x="540" y="172">risk + rule IDs</text>
    <text x="695" y="160">challenge both</text><text x="695" y="174">ways, add missed</text>
    <text x="850" y="160">honest wording</text><text x="850" y="174">(risky claims only)</text>
  </g>
  <g stroke="#475467" stroke-width="2" marker-end="url(#a)">
    <line x1="140" y1="140" x2="163" y2="140"/><line x1="295" y1="140" x2="318" y2="140"/>
    <line x1="450" y1="140" x2="473" y2="140"/><line x1="605" y1="140" x2="628" y2="140"/><line x1="760" y1="140" x2="783" y2="140"/>
  </g>
  <rect x="320" y="20" width="595" height="40" rx="10" fill="#ecfdf3" stroke="#067647" stroke-dasharray="5 4"/>
  <text x="617" y="45" text-anchor="middle" font-size="13" fill="#05603a">Shared, cached rules reference: FTC Green Guides (GG-260.x) + EU 2024/825 (EU-x) · model: gpt-6-luna</text>
  <rect x="320" y="220" width="440" height="40" rx="10" fill="#fef3f2" stroke="#b42318" stroke-dasharray="5 4"/>
  <text x="540" y="245" text-anchor="middle" font-size="13" fill="#912018">Code checks: every quote must be on the page · every rule ID must exist</text>
  <text x="850" y="245" text-anchor="middle" font-size="13" font-weight="700" fill="#101828">→ Report: claims,</text>
  <text x="850" y="263" text-anchor="middle" font-size="13" font-weight="700" fill="#101828">tokens, safety log</text>
</svg>"""


def main() -> None:
    n = len(REAL_RUNS)
    avg = [sum(r[k] for r in REAL_RUNS) / n for k in (1, 2, 3, 4)]
    avg_cost = cost(*avg[:3])
    nocache = cost(avg[0] + avg[1], 0, avg[2])
    rows = "\n  ".join(
        f'<tr><td>{lab}</td><td class="num">4</td><td class="num">{i:,}</td><td class="num">{c:,}</td>'
        f'<td class="num">{o:,}</td><td class="num">{cost(i, c, o):.4f}</td><td class="num">{s:.0f} s</td></tr>'
        for lab, i, c, o, s in REAL_RUNS
    )
    values = {
        "{{REAL_ROWS}}": rows,
        "{{AVG_IN}}": f"{avg[0]:,.0f}", "{{AVG_CA}}": f"{avg[1]:,.0f}", "{{AVG_OUT}}": f"{avg[2]:,.0f}",
        "{{AVG_SEC}}": f"{avg[3]:.0f}", "{{AVG_COST}}": f"{avg_cost:.4f}",
        "{{U1}}": f"{20 * avg_cost:.2f}", "{{U100}}": f"{2000 * avg_cost:,.2f}", "{{U10K}}": f"{200000 * avg_cost:,.0f}",
        "{{ETSY}}": f"{5.6e6 * avg_cost:,.0f}", "{{LAWYER_X}}": f"{349 / avg_cost:,.0f}",
        "{{NOCACHE_PCT}}": f"{(nocache / avg_cost - 1) * 100:.0f}",
        "{{DIAGRAM}}": DIAGRAM,
    }
    for name, max_w in (("report", 1600), ("slides", 1400)):
        html = (SRC / f"{name}_template.html").read_text()
        for k, v in values.items():
            html = html.replace(k, v)
        for img in IMAGES:
            key = "{{IMG:" + img + "}}"
            if key in html:
                cls = "shot" if name == "slides" else ""
                html = html.replace(key, img_tag(img, cls, max_w))
        assert "{{" not in html, f"unfilled placeholder in {name}"
        out = ROOT / f"{name}.html"
        out.write_text(html)
        print(f"{out.name}: {out.stat().st_size / 1e6:.1f} MB")
    print(json.dumps({k: v for k, v in values.items() if k not in ("{{REAL_ROWS}}", "{{DIAGRAM}}")}, indent=1))


if __name__ == "__main__":
    main()
