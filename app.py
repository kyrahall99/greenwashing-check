"""GreenClaim Check: Streamlit front end."""

import html
from pathlib import Path

import pandas as pd
import streamlit as st

from greenclaim.agents import run_review
from greenclaim.llm import MAX_INPUT_CHARS, PRICE_PER_M, BudgetExceeded

ROOT = Path(__file__).parent
SAMPLES = {
    "Candle shop listing (US + EU)": ("text", ROOT / "samples" / "candle_shop.txt", "United States and EU"),
    "Bamboo sheets page with hidden AI instructions": ("html", ROOT / "samples" / "injected_page.html", "United States"),
    "Bottle listing that talks to the AI": ("text", ROOT / "samples" / "visible_injection.txt", "United States"),
}
RISK_STYLE = {
    "high": ("#b42318", "#fef3f2", "High risk"),
    "medium": ("#b54708", "#fffaeb", "Needs evidence"),
    "low": ("#067647", "#ecfdf3", "Looks OK"),
}

st.set_page_config(page_title="Check your product for greenwashing", page_icon="🌿", layout="wide")
st.markdown(
    """<style>
    .block-container {max-width: 1100px; padding-top: 2rem;}
    .claim {border-radius: 10px; padding: 14px 18px; margin-bottom: 12px; border-left: 6px solid;}
    .claim .quote {font-size: 1.05rem; font-weight: 600; margin-bottom: 6px;}
    .claim .tag {display:inline-block; font-size:.75rem; font-weight:700; padding:2px 8px;
                 border-radius:999px; color:white; margin-right:6px;}
    .claim .rule {display:inline-block; font-size:.75rem; padding:2px 8px; border-radius:999px;
                  background:#eef2f6; color:#344054; margin-right:4px;}
    .claim .rewrite {background:white; border:1px solid #d0d5dd; border-radius:8px; padding:8px 12px; margin-top:8px;}
    .muted {color:#667085; font-size:.9rem;}
    </style>""",
    unsafe_allow_html=True,
)

# ---------- Sidebar ----------
if "pending_market" in st.session_state:
    st.session_state.market = st.session_state.pop("pending_market")
with st.sidebar:
    st.header("Settings")
    market = st.selectbox(
        "Where do you sell?",
        ["United States", "European Union", "United States and EU"],
        key="market",
        help="EU rules ban some claims (like offset-based 'carbon neutral') that the US only restricts.",
    )
    defenses = st.toggle(
        "Safety defenses", value=True,
        help="Strips hidden webpage text, removes text aimed at the AI, and checks every quote and "
             "rule citation. Turn off only to test what happens without them.",
    )
    if not defenses:
        st.warning("Defenses are off. Use this only for testing.")
    quick = st.toggle(
        "Quick mode", value=False,
        help="Skips the Skeptic agent. In our tests this was 26% cheaper and 24% faster, "
             "but rated slightly fewer deceptive claims as high risk.",
    )
    st.divider()
    st.caption(
        f"Model: gpt-6-luna. Prices used for cost (per 1M tokens): input \\${PRICE_PER_M['input']}, "
        f"cached \\${PRICE_PER_M['cached_input']}, output \\${PRICE_PER_M['output']}."
    )
    st.caption("This tool flags risk. It is not legal advice.")

# ---------- Header ----------
st.title("🌿 Check your product for greenwashing")
st.markdown(
    "<div style='background:#ecfdf3;border-radius:10px;padding:14px 18px;margin-bottom:12px;color:#05603a'>"
    "<b>Why this matters.</b> Greenwashing is when a product is made to sound better for the planet "
    "than it really is, with words like “eco-friendly”, “biodegradable”, or “carbon neutral” that "
    "have no proof behind them. It misleads shoppers who are trying to make good choices, rewards "
    "companies for marketing instead of real improvements, and makes it harder for honest brands to "
    "stand out. Knowing which claims are specific and backed by evidence helps you shop as an informed "
    "consumer, and helps sellers make claims they can stand behind."
    "</div>",
    unsafe_allow_html=True,
)
st.markdown(
    "Paste your product description or link your product page. A team of AI agents finds every "
    "environmental claim, checks it against the **FTC Green Guides** and the **EU green claims rules**, "
    "and suggests wording you can defend."
)

# ---------- Input ----------
if "input_text" not in st.session_state:
    st.session_state.input_text = ""
    st.session_state.input_html = ""
    st.session_state.mode = "Paste text"

with st.expander("Try a sample", expanded=False):
    cols = st.columns(len(SAMPLES))
    for col, (label, (kind, path, mkt)) in zip(cols, SAMPLES.items()):
        if col.button(label, width="stretch"):
            content = path.read_text()
            st.session_state.pending_market = mkt  # applied before the sidebar is drawn
            if kind == "text":
                st.session_state.input_text = content
                st.session_state.mode = "Paste text"
            else:
                st.session_state.input_html = content
                st.session_state.mode = "Webpage HTML file"
            st.rerun()

mode = st.radio("Input", ["Paste text", "Product page URL", "Webpage HTML file"], horizontal=True,
                key="mode", label_visibility="collapsed")
text = url = page_html = ""
if mode == "Paste text":
    text = st.text_area("Marketing text", key="input_text", height=220,
                        placeholder="Paste a product description, label text, or ad copy…")
    st.caption(f"{len(text):,} / {MAX_INPUT_CHARS:,} characters")
elif mode == "Product page URL":
    url = st.text_input("Product page URL", placeholder="https://…")
else:
    up = st.file_uploader("Upload a saved webpage (.html)", type=["html", "htm"])
    page_html = up.read().decode("utf-8", "ignore") if up else st.session_state.input_html
    if page_html and not up:
        st.caption("Using the sample webpage.")

run = st.button("Check my claims", type="primary", width="stretch")

# ---------- Run ----------
if run and len(text) > MAX_INPUT_CHARS:
    st.error(f"Stopped before spending anything: the text is {len(text):,} characters and the limit is "
             f"{MAX_INPUT_CHARS:,}. Paste only the product description and claims.")
    run = False
if run:
    try:
        with st.status("Reviewing…", expanded=True) as status:
            report = run_review(text=text, url=url, html=page_html, market=market, defenses=defenses,
                                skeptic=not quick, on_step=lambda s: st.write(s))
            status.update(label=f"Review finished in {report['wall_seconds']} s", state="complete", expanded=False)
        st.session_state.report = report
    except BudgetExceeded as e:
        st.error(f"Stopped before spending anything: {e}")
    except ValueError as e:
        st.warning(str(e))
    except Exception as e:  # network or provider errors
        st.error(f"Something went wrong: {e}")

report = st.session_state.get("report")
if not report:
    st.stop()


def _e(s) -> str:
    return html.escape(str(s or ""))


def report_markdown(r: dict) -> str:
    """Plain-text report a seller can save, share with a lawyer, or attach to a ticket."""
    label = {"high": "HIGH RISK", "medium": "NEEDS EVIDENCE", "low": "LOOKS OK"}
    lines = [
        "# Greenwashing check report", "",
        f"- Date: {r['timestamp']}", f"- Market: {r['market']}",
        f"- Product: {r['product_summary']}",
        f"- Results: {r['counts']['high']} high risk, {r['counts']['medium']} need evidence, "
        f"{r['counts']['low']} look OK", "",
    ]
    if r["summary"]:
        lines += ["## Summary", "", r["summary"], ""]
    lines += ["## Claims", ""]
    for i, c in enumerate(r["claims"], 1):
        lines += [f"### {i}. \"{c['quote']}\" ({label.get(c.get('risk'), 'NOT RATED')})", ""]
        if c.get("rule_ids"):
            lines.append(f"- Rules: {', '.join(c['rule_ids'])}")
        for key, name in (("reason", "Why"), ("evidence_needed", "Keep on file"),
                          ("skeptic_note", "Skeptic"), ("rewrite", "Try instead")):
            if c.get(key):
                lines.append(f"- {name}: {c[key]}")
        lines.append("")
    s = r["safety"]
    removed = len(s["hidden_text_removed"]) + len(s["injections_removed"])
    lines += ["## Safety", "", f"- Text aimed at the AI that was removed: {removed} block(s)",
              f"- Output checks: {len(s['validation_flags'])} issue(s) corrected", "",
              "This tool flags risk. It is not legal advice.", ""]
    return "\n".join(lines)


# ---------- Results ----------
st.divider()
if report["stopped"]:
    st.error(f"**Review stopped.** {report['stopped']}")
if report["product_summary"]:
    st.markdown(f"<span class='muted'>Reviewed: {_e(report['product_summary'])}</span>", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
c1.metric("High risk", report["counts"]["high"])
c2.metric("Needs evidence", report["counts"]["medium"])
c3.metric("Looks OK", report["counts"]["low"])
c4.metric("Cost of this review", f"${report['usage']['cost_usd']:.4f}")
if report["summary"]:
    st.info(report["summary"])
st.download_button("Download report", report_markdown(report), file_name="greenwashing_check_report.md",
                   mime="text/markdown", icon=":material/download:")

tab_claims, tab_safety, tab_cost = st.tabs(["Claims", "Safety checks", "Tokens and cost"])

with tab_claims:
    if not report["claims"]:
        st.write("No environmental claims found.")
    for c in report["claims"]:
        risk = c.get("risk")
        color, bg, label = RISK_STYLE.get(risk, ("#475467", "#f2f4f7", "Not rated"))
        rules = "".join(f"<span class='rule'>{_e(r)}</span>" for r in c.get("rule_ids", []))
        parts = [
            f"<div class='claim' style='border-color:{color};background:{bg}'>",
            f"<span class='tag' style='background:{color}'>{label}</span>{rules}",
            f"<div class='quote'>“{_e(c['quote'])}”</div>",
        ]
        if c.get("reason"):
            parts.append(f"<div>{_e(c['reason'])}</div>")
        if c.get("evidence_needed"):
            parts.append(f"<div class='muted'><b>Keep on file:</b> {_e(c['evidence_needed'])}</div>")
        if c.get("skeptic_note"):
            before = f" (was {c['checker_risk']})" if c.get("checker_risk") and c["checker_risk"] != risk else ""
            parts.append(f"<div class='muted'><b>Skeptic{before}:</b> {_e(c['skeptic_note'])}</div>")
        if c.get("rewrite"):
            parts.append(f"<div class='rewrite'><b>Try instead:</b> {_e(c['rewrite'])}"
                         f"<div class='muted'>{_e(c.get('why_it_works'))}</div></div>")
        parts.append("</div>")
        st.markdown("".join(parts), unsafe_allow_html=True)

with tab_safety:
    s = report["safety"]
    st.markdown(f"Defenses were **{'on' if report['defenses'] else 'off'}** for this review.")
    any_issue = False
    if s["hidden_text_removed"]:
        any_issue = True
        st.warning(f"Removed {len(s['hidden_text_removed'])} hidden text block(s) from the webpage before the agents saw it:")
        for h in s["hidden_text_removed"]:
            st.markdown(f"> {h}")
    if s["injections_removed"]:
        any_issue = True
        st.warning(f"Removed {len(s['injections_removed'])} sentence(s) addressed to the AI reviewer:")
        for h in s["injections_removed"]:
            st.markdown(f"> {h}")
    if s["manipulation_noticed"]:
        any_issue = True
        st.warning(f"The Skeptic noticed: {s['manipulation_noticed']}")
    if s["validation_flags"]:
        any_issue = True
        st.markdown("**Output checks:**")
        for f in s["validation_flags"]:
            st.markdown(f"- {f}")
    if not any_issue:
        st.success("No hidden text, injected instructions, or made-up quotes were found.")

with tab_cost:
    u = report["usage"]
    st.markdown(
        f"**{u['calls']} model calls**, {u['input']:,} new input tokens, {u['cached_input']:,} cached input "
        f"tokens, {u['output']:,} output tokens. Total cost **\\${u['cost_usd']:.4f}**."
    )
    rows = []
    for step in u["steps"]:
        cost = (step["input"] * PRICE_PER_M["input"] + step["cached_input"] * PRICE_PER_M["cached_input"]
                + step["output"] * PRICE_PER_M["output"]) / 1e6
        note = "blocked by provider" if step.get("blocked") else "replayed from cache" if step.get("replayed") else ""
        rows.append({"Agent": step["agent"].replace("_", " ").title(), "Input": step["input"],
                     "Cached input": step["cached_input"], "Output": step["output"],
                     "Seconds": step["seconds"], "Cost ($)": round(cost, 5), "Note": note})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("Every review is also logged to logs/runs.jsonl.")
