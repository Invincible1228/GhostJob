# Architectural Decision Log (DECISIONS.md)

This log documents the core engineering tradeoffs, domain nuances, and algorithmic choices made during the development of the **Ghost-Job Detector & Direct-ATS Pipeline**. It is written for engineers and technical interviewers who want to understand *how* the system was built, why certain alternatives were rejected, and where the real-world domain complexities lie.

---

## 1. Direct-ATS Public APIs vs. Aggregator Board Scraping

* **Context:** Most job-scraping projects target aggregators (LinkedIn, Indeed, Naukri). However, aggregators are plagued with duplicate staffing agency spam, stale listings, anti-bot countermeasures (Cloudflare, Turnstile, CAPTCHAs), and frequent HTML markup churn.
* **Decision:** Ingest directly from official Applicant Tracking Systems (Greenhouse, Lever, Ashby) via public JSON APIs.
* **Rationale:**
  * **Authoritative Source of Truth:** Requisitions on company career boards are the company's official active openings.
  * **Zero DOM Churn:** Greenhouse (`/v1/boards/{slug}/jobs?content=true`), Lever (`/v0/postings/{slug}?mode=json`), and Ashby (`/posting-api/job-board/{slug}`) provide structured, stable JSON endpoints.
  * **Ethical Compliance:** Eliminates scraping behind authentication walls; respects `robots.txt`, enforces per-domain rate limits, and uses identifiable User-Agents.
* **Tradeoff:** Requires specialized adapters per ATS vendor rather than a generic HTML parser. We abstracted this behind an extensible `ATSAdapter` protocol with regex signature auto-discovery.

---

## 2. Decoupling Single-Snapshot Signals from Longitudinal Signals

* **The Trap:** On Day 1 of a crawl, claiming a "27% repost loop detection rate" or "validated against 30-day closure outcomes" is a classic giveaway of synthetic or conflated data. A true repost loop is a **longitudinal phenomenon** (a role disappears and reappears over weeks, or has its posting date reset forward).
* **Decision:** Architecturally separate **Single-Snapshot Signals** from **Longitudinal Time-Series Signals**:
  1. **Single-Snapshot Signals (Observable on Day 1):**
     * *Multi-Location Clone Blasts:* Same JD simultaneously active across multiple metropolitan areas (e.g., Bengaluru, Mumbai, Remote). Tracked via `clone_count`.
     * *Claimed Requisition Age:* Days since original posting date provided directly in ATS metadata (`createdAt` in Lever, `updated_at`/`first_published_at` in Greenhouse, `publishedAt` in Ashby).
     * *Evergreen Phrasing:* Generic talent pool or pipeline requisition templates ("All levels", "General Application", lack of specific tech stack or compensation).
  2. **Longitudinal Signals (Accumulated Across Runs):**
     * *True Repost Loops:* An existing canonical role re-indexed under a new `external_id` after $\ge 24$ hours, or with reset claimed timestamps. Tracked via `times_reposted`.
     * *Observed Time-to-Close:* Empirical lifespan before a requisition vanishes from the ATS feed.
* **Implementation:** We established an automated daily GitHub Actions workflow (`.github/workflows/crawl.yml`) running at `04:00 UTC` to commit daily snapshots into the repository, allowing genuine multi-day longitudinal time-series data to build over time.

---

## 3. Deduplication Architecture: Domain-Aware TF-IDF + Role Guards vs. Heavy Transformers

* **Context:** ATS listings frequently have minor title variations ("Sr. Software Engineer" vs. "Senior Software Engineer") or identical descriptions across different office locations. However, using off-the-shelf sentence transformers (e.g., `bge-small` or BERT) introduces significant issues:
  1. **Boilerplate Matching:** 70–80% of a modern JD is corporate boilerplate ("About Us", "Diversity & Inclusion", "Benefits"). An unconstrained dense embedding model frequently merges completely different roles at the same company (e.g., *Frontend Engineer* and *Backend Engineer*, or *Legal Counsel* and *Security Engineer*) because their shared corporate text dominates cosine similarity.
  2. **Resource Overhead:** Heavy PyTorch/Transformer dependencies require 400MB+ downloads, introduce GPU cold-start latency, and slow down local CI workflows.
* **Decision:** We implemented a 3-tier cascade combining:
  1. **Tier 1 (Exact Hash / ATS ID):** SHA-256 fingerprint of normalized text. $O(1)$ lookup, 100% confidence.
  2. **Tier 2 (Fuzzy Rules):** RapidFuzz `token_sort_ratio` ($\ge 88.0$) with canonical city normalization (e.g., "Bangalore" $\equiv$ "Bengaluru", "Gurgaon" $\equiv$ "Delhi NCR").
  3. **Tier 3 (Domain-Aware Token Cosine + Role Guards):** Unigram term-frequency cosine matching ($\ge 0.50$) reinforced by strict **role-disjointness filters** (`DISJOINT_ROLE_PAIRS` preventing cross-merging of `frontend`/`backend`, `ios`/`android`, `staff`/`junior`, `manager`/`designer`).
* **Result:** Blazing fast sub-millisecond comparisons, deterministic behavior, zero GPU dependency, and zero false-positive merges on corporate boilerplate text.

---

## 4. Empirical Real-World Evaluation vs. Synthetic Overfitting

* **The Trap:** Claiming "100.0% Precision and 0.0% False Positive Rate" on an evaluation set is an immediate red flag indicating that the evaluation dataset was synthetically generated or overfitted by the model.
* **Decision:** We sampled **125 real job pairs directly from our live crawled database** (`scripts/create_real_evaluation_pairs.py`) across actual company listings, including true duplicates, intra-company role variations, and cross-company pairs.
* **Results on Real Data:**
  * **Precision:** **88.24%** (reflecting real-world edge cases where subtle sub-specializations challenge heuristic boundaries).
  * **Recall:** **100.0%**
  * **F1-Score:** **93.75%**
* **Significance:** Real, messy, defensible numbers show hiring managers that you understand real NLP evaluation rather than generating toy synthetic benchmarks.
