"""Run GreenClaim Check on the labeled test set and report accuracy, tokens, and cost.

Usage (from the repo folder):
    .venv/bin/python -m eval.run_eval              # defenses on
    .venv/bin/python -m eval.run_eval --workers 4  # run cases in parallel
    .venv/bin/python -m eval.run_eval --repeats 3  # measure run-to-run stability
    .venv/bin/python -m eval.run_eval --no-skeptic # measure what the Skeptic adds
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from greenclaim.agents import run_review

HERE = Path(__file__).parent
RISK = {"low": 0, "medium": 1, "high": 2}


def run_case(case: dict, skeptic: bool = True) -> dict:
    r = run_review(text=case["text"], market=case["market"], skeptic=skeptic)
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


def summarize(results: list[dict]) -> dict:
    dec = [r for r in results if r["label"] == "deceptive"]
    ok = [r for r in results if r["label"] == "compliant"]
    n = len(results)
    return {
        "cases": n,
        "deceptive_caught_as_high": sum(r["flagged_high"] for r in dec),
        "deceptive_caught_high_or_medium": sum(r["flagged_any"] for r in dec),
        "deceptive_total": len(dec),
        "compliant_wrongly_high": sum(r["flagged_high"] for r in ok),
        "compliant_rated_low": sum(r["top_risk"] == "low" for r in ok),
        "compliant_total": len(ok),
        "accuracy_high_vs_not": round(sum((r["label"] == "deceptive") == r["flagged_high"] for r in results) / n, 3),
        "avg_calls": round(sum(r["usage"]["calls"] for r in results) / n, 2),
        "avg_input_tokens": round(sum(r["usage"]["input"] for r in results) / n),
        "avg_cached_input_tokens": round(sum(r["usage"]["cached_input"] for r in results) / n),
        "avg_output_tokens": round(sum(r["usage"]["output"] for r in results) / n),
        "avg_cost_usd": round(sum(r["usage"]["cost_usd"] for r in results) / n, 5),
        "avg_seconds_per_review": round(sum(r["wall_seconds"] for r in results) / n, 1),
        "total_cost_usd": round(sum(r["usage"]["cost_usd"] for r in results), 4),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--no-skeptic", action="store_true")
    args = ap.parse_args()
    skeptic = not args.no_skeptic
    cases = json.loads((HERE / "cases.json").read_text())
    start = time.time()
    runs = []
    for rep in range(args.repeats):
        with ThreadPoolExecutor(args.workers) as pool:
            runs.append(list(pool.map(lambda c: run_case(c, skeptic), cases)))
        print(f"repeat {rep + 1}: {json.dumps(summarize(runs[-1]))}")

    per_run = [summarize(r) for r in runs]
    keys = [k for k in per_run[0] if k != "cases"]
    mean = {k: round(sum(p[k] for p in per_run) / len(per_run), 4) for k in keys}
    stability = {}
    if len(runs) > 1:
        same_top = sum(len({run[i]["top_risk"] for run in runs}) == 1 for i in range(len(cases)))
        same_flag = sum(len({run[i]["flagged_high"] for run in runs}) == 1 for i in range(len(cases)))
        stability = {
            "cases_same_top_risk_every_run": f"{same_top}/{len(cases)}",
            "cases_same_high_flag_every_run": f"{same_flag}/{len(cases)}",
            "unstable_cases": [cases[i]["id"] + ": " + "/".join(run[i]["top_risk"] for run in runs)
                               for i in range(len(cases)) if len({run[i]["top_risk"] for run in runs}) > 1],
        }
    tag = ("skeptic" if skeptic else "no_skeptic") + (f"_x{args.repeats}" if args.repeats > 1 else "")
    out = HERE / f"results_{tag}.json"
    out.write_text(json.dumps({"skeptic": skeptic, "repeats": args.repeats, "mean": mean,
                               "stability": stability, "per_run": per_run, "runs": runs}, indent=2))
    print("\nMean over runs:", json.dumps(mean, indent=2))
    if stability:
        print("Stability:", json.dumps(stability, indent=2))
    print(f"batch seconds: {round(time.time() - start, 1)}\nFull results: {out}")


if __name__ == "__main__":
    main()
