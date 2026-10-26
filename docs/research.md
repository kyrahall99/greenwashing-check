# Research notes for the report

Collected 2026-10-26. Everything below is either measured in this repo or
taken from the sources listed. Assumptions are marked **(assumption)**.

## 1. Existing alternatives

| Product | What it does | Method | Markets | Price | Rewrites? | Cites rules? |
|---|---|---|---|---|---|---|
| EcoClaim (ecoclaim.eu) | Scans store URLs and pasted copy for 82 banned terms | Term list, then AI rewrites | EU (5 languages, 7 country guides) | Free scans; paid tier not public | Yes | Yes (Directive 2024/825 Annex I / UCPD) |
| GreenClaims-Scanner (greenclaims-scanner.com) | Checks websites and published documents against a list of prohibited green formulations | Deterministic term list | EU (9 languages) | Free quick scan; paid tiers not public | Not stated | Not stated |
| Senken.io EmpCo checker | EmpCo compliance check with focus on carbon-offset claims | Not stated | EU | Free checker; paid ESG modules | Not stated | Annex I 4a |
| EmpCo Scanner (empco-scanner.de) | Scans sites, ads, and social posts under German law | Not stated | Germany only | Free up to 5 pages; EUR 149 for 50 pages; EUR 399 for 200 pages | Not stated | German UWG / BGH case law |
| EcoAppraise | Assesses claim evidence against independent sources; two-page scored report | Analyst plus tools | Not stated | Paid | No | Not stated |
| Bird & Bird AI scanner | Law-firm greenwashing scanner | AI plus lawyers | Enterprise | Starts with a scoped legal review | Via lawyers | Yes |
| Advertising lawyer | Manual claim review | Human | Any | U.S. average lawyer rate USD 349/hour (Clio, 2025) | Yes | Yes |

**What GreenClaim Check does differently**
- **Covers the U.S. FTC Green Guides as well as EU 2024/825.** None of the eight tools in
  EcoClaim's own 2026 comparison is described as covering FTC rules.
- **Reads claims in context instead of matching a word list.** Term lists flag
  "recyclable" whether or not it is qualified; our agents lower the risk when the
  qualification is next to the claim (compliant controls C02, C03).
- **Catches deception that has no banned word**: "bamboo" for rayon (D01, D02),
  self-made seals (D08, D09), "ocean plastic" (D12).
- **Explains the proof to keep on file** for each claim, plus a rewrite.
- **Defends against adversarial pages** (hidden text and injected instructions),
  which keyword scanners do not need but AI scanners do.

Sources: EcoClaim, "Best Greenwashing Compliance Tools 2026" (vendor-written
comparison, includes its own tool): https://www.ecoclaim.eu/blog/best-greenwashing-compliance-tools-2026 ;
GreenClaims-Scanner: https://greenclaims-scanner.com/en/ ; EcoAppraise: https://www.ecoappraise.com/ ;
Senken: https://www.senken.io/blog/free-greenwashing-compliance-checker-empco-directive ;
Clio lawyer rates: https://clio.com/resources/legal-trends/compare-lawyer-rates/

## 2. Measured quality (eval/cases.json, 22 cases, 3 runs each)

| | Full pipeline (4 agents) | Without Skeptic (3 agents) |
|---|---|---|
| Deceptive rated high (mean of 3 runs) | 10.7 / 14 | 10.0 / 14 |
| Deceptive flagged high or "needs evidence" | 14 / 14 | 14 / 14 |
| Compliant wrongly rated high | 0 / 8 | 0 / 8 |
| Accuracy of the high-risk flag | 84.9% | 81.8% |
| Same top rating in all 3 runs | 17 / 22 | 21 / 22 |
| Avg cost per review | USD 0.00090 | USD 0.00067 |
| Avg time per review | 17.7 s | 13.5 s |

Files: `eval/results_skeptic_x3.json`, `eval/results_no_skeptic_x3.json`.
Unstable cases with the Skeptic: D02, D07, D09, C01, C06.

## 3. Measured tokens per review

| Input type | Calls | New input | Cached input | Output | Cost | Time |
|---|---|---|---|---|---|---|
| Short claim (eval average) | 3.9 | 802 | 6,812 | 1,499 | USD 0.00090 | 18 s |
| Full product page (6 runs, `eval/page_runs.json`) | 4 | 3,339 | 7,089 | 6,144 | USD 0.0035 | 53 s |

- Output tokens are about 88% of the cost of a full-page review.
- Without prompt caching the same page review would cost USD 0.0041, so caching
  saves about 16%; for short claims it saves about 41% (USD 0.0015 to 0.0009).
- Prices: gpt-6-luna standard tier, USD 0.10 / 0.01 / 0.50 per 1M input / cached /
  output tokens (https://developers.openai.com/api/docs/pricing, checked 2026-10-26).
- Costs are computed from the measured token counts at these prices. The
  `cost_usd` fields inside older JSON result files used earlier placeholder
  prices; the token counts in them are unchanged and correct.

## 4. Scale

Assume a seller checks **20 product pages a month (assumption)** at the measured
full-page cost of USD 0.0035.

| Users | Reviews / month | Cost / month |
|---|---|---|
| 1 | 20 | USD 0.07 |
| 100 | 2,000 | USD 6.95 |
| 10,000 | 200,000 | USD 695 |

- **Marketplace screen:** Etsy had about 5.6 million active sellers in 2025
  (Inside Retail, reporting Etsy's results: https://insideretail.us/etsy-vows-sustained-growth-after-revenue-lift/).
  Reviewing one product page per seller would cost about USD 19,500.
- **vs. a lawyer:** at the U.S. average of USD 349/hour, one hour of review for one
  product page **(assumption)** costs about 100,000 times the agent's USD 0.0035.

## 5. Cost-cutting steps and trade-offs

1. **Shared rules prefix + cache key** (done): 7,000+ input tokens per review are
   served from cache at a tenth of the price.
2. **Turned off Portkey's whole-response cache** (done): costs a little more on
   exact repeats, but keeps every logged token count real.
3. **Quick mode without the Skeptic** (measured): 26% cheaper (USD 0.00067 vs 0.00090) and 24% faster, and
   ratings are more stable, but it rates 0.7 fewer deceptive claims high per 14.
4. **Rewriter runs only for risky claims** (done): no rewrite call when all claims
   look OK.
5. **Next:** output is 88% of cost, so shorter agent outputs (terser reasons,
   capped rewrites) are the biggest remaining saving.
