"""Run GreenClaim Check on the labeled test set and report accuracy, tokens, and cost.

Usage (from the repo folder):
    .venv/bin/python -m eval.run_eval              # defenses on
    .venv/bin/python -m eval.run_eval --workers 4  # run cases in parallel
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from greenclaim.agents import run_review

HERE = Path(__file__).parent
RISK = {"low": 0, "medium": 1, "high": 2}


def run_case(case: dict) -> dict:
    r = run_review(text=case["text"], market=case["market"])
    risks = [c.get("risk", "low") for c in r["claims"]]
    top = max(risks, key=lambda x: RISK.get(x, 0)) if risks else "none"
    return {
        "id": case["id"], "label": case["label"], "top_risk": top,
        "flagged_high": top == "high", "flagged_any": top in ("high", "medium"),
        "n_claims": len(r["claims"]), "stopped": r["stopped"],
        "usage": {k: v for k, v in r["usage"].items() if k != "steps"},
        "wall_seconds": r["wall_seconds"],
        "claims": [{"quote": c["quote"], "risk": c.get("risk"), "rules": c.get("rule_ids")} for c in r["claims"]],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    cases = json.loads((HERE / "cases.json").read_text())
    start = time.time()
    with ThreadPoolExecutor(args.workers) as pool:
        results = list(pool.map(run_case, cases))

    dec = [r for r in results if r["label"] == "deceptive"]
    ok = [r for r in results if r["label"] == "compliant"]
    summary = {
        "cases": len(results),
        "deceptive_caught_as_high": f"{sum(r['flagged_high'] for r in dec)}/{len(dec)}",
        "deceptive_caught_high_or_medium": f"{sum(r['flagged_any'] for r in dec)}/{len(dec)}",
        "compliant_wrongly_high": f"{sum(r['flagged_high'] for r in ok)}/{len(ok)}",
        "compliant_rated_low": f"{sum(r['top_risk'] == 'low' for r in ok)}/{len(ok)}",
        "avg_input_tokens": round(sum(r["usage"]["input"] for r in results) / len(results)),
        "avg_cached_input_tokens": round(sum(r["usage"]["cached_input"] for r in results) / len(results)),
        "avg_output_tokens": round(sum(r["usage"]["output"] for r in results) / len(results)),
        "avg_cost_usd": round(sum(r["usage"]["cost_usd"] for r in results) / len(results), 5),
        "avg_seconds_per_review": round(sum(r["wall_seconds"] for r in results) / len(results), 1),
        "total_cost_usd": round(sum(r["usage"]["cost_usd"] for r in results), 4),
        "batch_seconds": round(time.time() - start, 1),
    }
    out = HERE / "results.json"
    out.write_text(json.dumps({"summary": summary, "results": results}, indent=2))
    print(json.dumps(summary, indent=2))
    print("\nPer case:")
    for r in results:
        mark = "OK " if (r["label"] == "deceptive") == r["flagged_high"] else "MISS"
        print(f"  {mark} {r['id']} {r['label']:9} top={r['top_risk']:6} claims={r['n_claims']}")
    print(f"\nFull results: {out}")


if __name__ == "__main__":
    main()
