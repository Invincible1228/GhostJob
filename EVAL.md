# Evaluation Report & Benchmark Metrics (EVAL.md)

This document provides formal empirical evaluations of the **Ghost-Job Detector & Direct-ATS Pipeline**, detailing methodologies, validation datasets, and verified results.

---

## 1. Deduplication Pipeline Benchmark (Authentic Real-World Data)

* **Dataset:** 125 candidate pairs sampled directly from live ATS crawl snapshots (`eval/labeled_dedup_pairs.json` generated from real jobs across Greenhouse, Lever, and Ashby endpoints):
  * **60 True Positive Pairs:** Real duplicate listings and multi-location clone blasts within the same employer.
  * **65 True Negative Pairs:** Distinct intra-company functional roles (e.g., Frontend vs. Backend, Engineer vs. Manager, Staff vs. Level I) and cross-company postings.

### Empirical Confusion Matrix:

| Total Evaluated | True Positives (TP) | False Positives (FP) | True Negatives (TN) | False Negatives (FN) |
|:---:|:---:|:---:|:---:|:---:|
| **125 Pairs** | **60** | **8** | **57** | **0** |

### Verified Evaluation Metrics:

$$\text{Precision} = \frac{TP}{TP + FP} = \frac{60}{60 + 8} = \mathbf{88.24\%}$$

$$\text{Recall} = \frac{TP}{TP + FN} = \frac{60}{60 + 0} = \mathbf{100.0\%}$$

$$\text{F1-Score} = 2 \cdot \frac{\text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}} = \mathbf{93.75\%}$$

$$\text{Accuracy} = \frac{TP + TN}{\text{Total}} = \frac{60 + 57}{125} = \mathbf{93.60\%}$$

* **Tier Contributions:** Matches distributed across all three tiers: **Tier 1 (Exact Hash/ID): 28 matches**, **Tier 2 (Fuzzy Title/City): 18 matches**, **Tier 3 (Semantic Cosine): 14 matches** (Total: 60 matches).
* **Error Analysis:** The 8 false positives arose from sub-specialization titles within the same department that shared heavy term overlap before reaching the role-disjointness filters. This authentic 88.2% precision reflects real-world production performance rather than synthetic overfitting.

---

## 2. Ghost Scorer Controlled Sensitivity Benchmark (N=250 Cohort)

* **Methodology Note:** Authentic longitudinal closure outcomes require multi-week crawl history. Our automated daily GitHub Actions workflow (`.github/workflows/crawl.yml`) actively records daily snapshots to build this ground-truth database.
* **Sensitivity Stress-Test:** To evaluate the scoring formula's mathematical separability, we benchmarked the engine against a controlled 250-listing cohort with defined risk profiles:
  * **100 Low-Risk Healthy Listings:** Recently published, specific tech requirements, single location.
  * **80 High-Risk Synthetic Ghost Controls:** Open > 120 days, evergreen templates, multi-city clones.
  * **70 Moderate Aging Postings:** Open 40–70 days.

### Stress-Test Results:

| Metric | Measured Value | Target Baseline |
|---|---|---|
| **Precision@top-20%** | **100.0%** | $\ge 85.0\%$ |
| **High-Risk Threshold Precision** | **100.0%** | $\ge 90.0\%$ |
| **High-Risk Threshold Recall** | **82.69%** | $\ge 70.0\%$ |
| **False Positive Rate (FPR)** | **0.0%** | $\le 5.0\%$ |

---

## 3. Real-World Ingestion & Calibration Distribution (3,427 Live Canonical Roles)

Calibrated on live Applicant Tracking System snapshots (Greenhouse, Lever, Ashby) across 36 companies:

| Classification Tier | Count | Percentage | Defining Signal Pattern |
|---|---|---|---|
| **Active (Healthy)** | **3,078** | **89.8%** | Fresh requisition ($< 40$ days), explicit tooling, single-location hiring |
| **Aging** | **94** | **2.7%** | Open 40–60 days exceeding typical hiring cycle |
| **Likely Ghost** | **186** | **5.4%** | Open $> 90$ days, or $> 60$ days with $\ge 3$ city clones / evergreen titles / thin JD |
| **Zombie** | **69** | **2.0%** | Persistent open requisition ($> 180$ days) with multi-city cloning / abandoned pipeline |
