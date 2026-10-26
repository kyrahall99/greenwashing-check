# 🌿 GreenClaim Check

**Find risky environmental marketing claims before regulators or customers do.**

Small businesses write "eco-friendly", "biodegradable", or "carbon neutral" on
products without knowing these claims are regulated by the FTC Green Guides in
the US and banned outright in many cases under the EU's new green claims rules
(Directive 2024/825, in force from 27 September 2026). GreenClaim Check is a team
of four AI agents that reads your product copy or product page, finds every
environmental claim, rates its legal risk, cites the rule, lists the proof you
need to keep, and suggests compliant wording.

MGT 409 final project by Kyra Hall.

## How it works

```
Input (text, URL, or saved webpage)
   │  Safety layer: strip hidden HTML text, remove sentences aimed at the AI,
   │  cap input size
   ▼
1. Extractor      finds every environmental claim, quoted word for word
   │  check: every quote must really appear in the input
   ▼
2. Rules Checker  rates each claim high / needs evidence / OK and cites rules
   ▼
3. Skeptic        challenges ratings both ways and adds missed claims
   │  check: every cited rule ID must exist in the rules reference
   ▼
4. Rewriter       drafts compliant wording for risky claims
   ▼
Report: claims, rules, evidence to keep, rewrites, safety log, tokens and cost
```

All agents run on **gpt-6-luna** through Portkey. They share one long
system-prompt prefix (the rules reference in `greenclaim/rules.md`), so most input
tokens are served from the prompt cache. Each review is capped at 6 model calls,
60,000 tokens, and 20,000 input characters.

## Run it (about 3 minutes)

You need **Python 3.10 or newer** (tested on 3.14).

1. **Clone the repo**

   ```bash
   git clone <this-repo-url> greenclaim-check
   cd greenclaim-check
   ```

2. **Add your API key.** Copy `.env.example` to `.env` and paste your key after
   `PORTKEY_API_KEY=`. The app looks for `.env` in this folder first, then in the
   folder one level above, so a `.env` you already keep one level up works as is.

   ```bash
   cp .env.example .env
   ```

3. **Create a virtual environment and install the packages**

   macOS / Linux:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

   Windows (PowerShell):

   ```powershell
   py -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```

4. **Start the app**

   macOS / Linux: `.venv/bin/streamlit run app.py`
   Windows: `.venv\Scripts\streamlit run app.py`

   Your browser opens at http://localhost:8501. If it doesn't, open that address.

5. **Try it.** Open **Try a sample**, choose **Candle shop listing**, and click
   **Check my claims**. A review takes about 15 to 50 seconds. Then try **Bamboo
   sheets page with hidden AI instructions** and open the **Safety checks** tab to
   see the hidden text the app removed.

## Using it

- **Paste text:** a product description, label text, or ad copy.
- **Product page URL:** the app downloads the page and reviews its visible text.
- **Webpage HTML file:** upload a saved page (File → Save Page As in your browser).
- **Where do you sell?** EU rules are stricter, so pick the right market.
- **Quick mode** (sidebar) skips the Skeptic: in our tests 26% cheaper and 24%
  faster, but it rated slightly fewer deceptive claims as high risk.
- **Download report** saves the review as a Markdown file you can share.
- **Safety defenses** (sidebar) are on by default. Turning them off shows what
  happens without them; use that only for testing.
- The **Tokens and cost** tab shows tokens and cost for each agent. Every review
  is also logged to `logs/runs.jsonl`.

## Test set

`eval/cases.json` holds 22 short claims: 14 based on real enforcement actions
(FTC, EU national courts and regulators, ACCC) and 8 compliant controls written
from the Green Guides' own examples. Run all of them in parallel:

```bash
.venv/bin/python -m eval.run_eval --workers 5
```

Add `--repeats 3` to measure run-to-run stability and `--no-skeptic` to measure
what the Skeptic adds. Results are saved to `eval/results_*.json`. One pass costs
about $0.02. A summary of all measured results is in `docs/research.md`.

## Repo layout

| Path | What it is |
|---|---|
| `app.py` | Streamlit interface |
| `greenclaim/agents.py` | The four agents and the review pipeline |
| `greenclaim/rules.md` | Rules reference (FTC Green Guides and EU 2024/825 summary) |
| `greenclaim/safety.py` | Hidden-text stripping, injection redaction, quote checks |
| `greenclaim/llm.py` | Model client, `.env` loading, token and cost tracking, spend limits |
| `samples/` | Sample inputs, including a page with planted AI instructions |
| `eval/` | Labeled test set and evaluation script |
| `docs/screenshots/` | Screenshots used in the report |

## Notes

- Cost figures use the prices set in `PRICE_PER_M` in `greenclaim/llm.py`.
- GreenClaim Check flags risk. It is not legal advice.
- Never commit your `.env`; it is listed in `.gitignore`.
