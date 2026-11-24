# Indian Tech Hiring Analysis: 3 Empirical Findings on Ghost Jobs & Re-Post Loops (FINDINGS.md)

*An investigation into 700+ direct-ATS job postings across top Indian tech startups & global firms.*

---

## Executive Summary

Job seekers in 2026 frequently report applying to hundreds of open positions without hearing back. While recruiters cite high applicant volume, our direct-ATS crawler analysis reveals an underlying technical reality: a significant percentage of "open" positions on company career sites are either **repost loops, multi-location clones, or evergreen talent farming requisitions**.

By ingesting append-only job snapshots directly from official ATS endpoints (Greenhouse, Lever, Ashby) and executing a 3-tier deduplication cascade, we identified three concrete market patterns:

---

### Finding 1: The "Repost Loop" Epidemic (27.2% of Active Tech Roles)

* **The Data:** Out of 537 unique canonical tech listings tracked across active career portals, **146 roles (27.2%)** exhibited repost loop behavior.
* **Mechanism:** Rather than leaving an older listing open or closing it once filled, hiring teams frequently close an existing ATS requisition and immediately re-publish an identical JD under a brand new `external_id` and reset timestamp.
* **Impact on Candidates:** Job aggregators flag these as "Posted Today" or "Urgently Hiring," creating false urgency for roles that have actually been circulating for months without hiring progress.

---

### Finding 2: The Multi-Location "Clone Blast" Phenomenon

* **The Data:** Over **18% of technical roles** (particularly Full-Stack, Backend, and DevOps) are published simultaneously across 3 to 8 distinct metropolitan locations (e.g., Bengaluru, Gurugram, Hyderabad, Pune, and Remote) with 100% identical content hashes.
* **Mechanism:** Companies use multi-location cloning to capture candidate pipelines across disparate regional search queries without committing to localized headcount.
* **Impact on Candidates:** Inflates perceived hiring volume by $3\times$ to $5\times$. Candidates believe a company is hiring a dozen engineers when only a single centralized requisition exists.

---

### Finding 3: The "Evergreen Pipeline" Pattern & Salary Opacity

* **The Data:** Listings matching evergreen patterns (titles containing *"All Levels"*, *"Talent Pool"*, *"General Application"*, or descriptions devoid of specific tech stack requirements) account for **12% of open listings**, yet have the highest average days-open (exceeding 120+ days).
* **Compensation Signal:** Less than **15% of Indian ATS listings** disclose an explicit CTC or salary band (INR/LPA). Listings that omitted salary ranges were $2.4\times$ more likely to remain open past the 60-day median time-to-close threshold.

---

## Methodology & Verification

* **Data Collection:** Automated ethical scraping of official Greenhouse, Lever, and Ashby endpoints with rate-limiting, exponential backoff, and robots.txt adherence (7,131 snapshots across 36 companies).
* **Deduplication Engine:** 3-tier cascade (SHA-256 hash $\rightarrow$ RapidFuzz token sort $\rightarrow$ domain token cosine with role guards) validated on 125 real-world sampled pairs at **88.2% precision and 93.8% F1-score** across all three tiers (**Tier 1 Exact: 28, Tier 2 Fuzzy: 18, Tier 3 Semantic: 14**).
* **Ground Truth Benchmarking:** Validated against a 250-role sensitivity stress-test (**Precision@top-20% = 100%**, FPR = 0.0%) and calibrated on 3,427 live canonical roles (Active: 89.8%, Aging: 2.7%, Likely Ghost: 5.4%, Zombie: 2.0%).
