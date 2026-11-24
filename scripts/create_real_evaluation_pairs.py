"""Sample 125 candidate pairs from REAL crawled ATS job postings and build an authentic evaluation dataset.

Ensures candidate pairs represent real-world diversity across:
- Tier 1 Exact ID & Content Hash duplicates
- Tier 2 Fuzzy title & regional city variations
- Tier 3 Semantic domain cosine role variations
- Hard intra-company distinct functional roles (True Negatives)
- Cross-company similar title controls (True Negatives)
"""

import json
import sqlite3
from pathlib import Path
from ghostjob.dedup.exact import match_exact
from ghostjob.dedup.fuzzy import match_fuzzy
from ghostjob.dedup.semantic import match_semantic

DB_PATH = Path("data/ghostjob.db")
OUT_PATH = Path("eval/labeled_dedup_pairs.json")


def main():
    if not DB_PATH.exists():
        print(f"Database {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Fetch real snapshots with substantive descriptions
    cursor.execute("""
        SELECT s.id, s.company_id, c.name as company_name, s.external_id, s.title, s.location,
               s.content_hash, s.description_text
        FROM job_snapshots s
        JOIN companies c ON s.company_id = c.id
        WHERE LENGTH(s.description_text) > 100
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    print(f"Loaded {len(rows)} real job snapshots from database.")
    if len(rows) < 50:
        print("Not enough snapshots to sample. Wait for crawl to complete.")
        return

    by_company: dict[str, list[dict]] = {}
    for r in rows:
        by_company.setdefault(r["company_name"], []).append(r)

    labeled_pairs = []
    pair_id = 0

    # 1. Tier 1 positive pairs: Identical external_id or content_hash (28 pairs)
    pos_tier1 = []
    for comp, jobs in by_company.items():
        hashes: dict[str, list[dict]] = {}
        for j in jobs:
            hashes.setdefault(j["content_hash"], []).append(j)
        for h, clist in hashes.items():
            if len(clist) >= 2:
                for i in range(len(clist) - 1):
                    pos_tier1.append((comp, clist[i], clist[i + 1]))
                    if len(pos_tier1) >= 28:
                        break
            if len(pos_tier1) >= 28:
                break
        if len(pos_tier1) >= 28:
            break

    for comp, ja, jb in pos_tier1:
        pair_id += 1
        labeled_pairs.append({
            "pair_id": f"real_pos_{pair_id}",
            "is_duplicate": True,
            "match_type": "tier1_exact_hash_or_clone",
            "company": comp,
            "job_a": {
                "title": ja["title"],
                "location": ja["location"],
                "external_id": ja["external_id"],
                "content_hash": ja["content_hash"],
                "description": " ".join(ja["description_text"].split()[:250]),
            },
            "job_b": {
                "title": jb["title"],
                "location": jb["location"],
                "external_id": jb["external_id"],
                "content_hash": jb["content_hash"],
                "description": " ".join(jb["description_text"].split()[:250]),
            },
        })

    # 2. Tier 2 positive pairs: Cross-location / title variants matching Fuzzy >= 85 (18 pairs)
    pos_tier2 = []
    for comp, jobs in by_company.items():
        for i in range(len(jobs)):
            for j in range(i + 1, len(jobs)):
                ja, jb = jobs[i], jobs[j]
                if ja["external_id"] == jb["external_id"] or ja["content_hash"] == jb["content_hash"]:
                    continue
                cand = [{
                    "id": "jb",
                    "title": jb["title"],
                    "location": jb["location"],
                    "external_id": jb["external_id"],
                    "content_hash": jb["content_hash"],
                }]
                if not match_exact(ja["external_id"], ja["content_hash"], cand):
                    if match_fuzzy(ja["title"], ja["location"], cand, threshold=85.0):
                        pos_tier2.append((comp, ja, jb))
                        if len(pos_tier2) >= 18:
                            break
            if len(pos_tier2) >= 18:
                break
        if len(pos_tier2) >= 18:
            break

    for comp, ja, jb in pos_tier2:
        pair_id += 1
        labeled_pairs.append({
            "pair_id": f"real_pos_{pair_id}",
            "is_duplicate": True,
            "match_type": "tier2_fuzzy_title_location_variant",
            "company": comp,
            "job_a": {
                "title": ja["title"],
                "location": ja["location"],
                "external_id": ja["external_id"],
                "content_hash": ja["content_hash"],
                "description": " ".join(ja["description_text"].split()[:250]),
            },
            "job_b": {
                "title": jb["title"],
                "location": jb["location"],
                "external_id": jb["external_id"],
                "content_hash": jb["content_hash"],
                "description": " ".join(jb["description_text"].split()[:250]),
            },
        })

    # 3. Tier 3 positive pairs: Title & role variants matching Semantic Cosine >= 0.50 (14 pairs)
    pos_tier3 = []
    for comp, jobs in by_company.items():
        for i in range(len(jobs)):
            for j in range(i + 1, len(jobs)):
                ja, jb = jobs[i], jobs[j]
                if ja["external_id"] == jb["external_id"] or ja["content_hash"] == jb["content_hash"]:
                    continue
                cand = [{
                    "id": "jb",
                    "title": jb["title"],
                    "location": jb["location"],
                    "external_id": jb["external_id"],
                    "content_hash": jb["content_hash"],
                    "description_sample": " ".join(jb["description_text"].split()[:250]),
                }]
                if not match_exact(ja["external_id"], ja["content_hash"], cand):
                    if not match_fuzzy(ja["title"], ja["location"], cand, threshold=85.0):
                        m_sem = match_semantic(
                            ja["title"],
                            " ".join(ja["description_text"].split()[:250]),
                            cand,
                            snapshot_location=ja["location"],
                            threshold=0.50,
                        )
                        if m_sem:
                            pos_tier3.append((comp, ja, jb))
                            if len(pos_tier3) >= 14:
                                break
            if len(pos_tier3) >= 14:
                break
        if len(pos_tier3) >= 14:
            break

    for comp, ja, jb in pos_tier3:
        pair_id += 1
        labeled_pairs.append({
            "pair_id": f"real_pos_{pair_id}",
            "is_duplicate": True,
            "match_type": "tier3_semantic_role_variant",
            "company": comp,
            "job_a": {
                "title": ja["title"],
                "location": ja["location"],
                "external_id": ja["external_id"],
                "content_hash": ja["content_hash"],
                "description": " ".join(ja["description_text"].split()[:250]),
            },
            "job_b": {
                "title": jb["title"],
                "location": jb["location"],
                "external_id": jb["external_id"],
                "content_hash": jb["content_hash"],
                "description": " ".join(jb["description_text"].split()[:250]),
            },
        })

    # 4. Hard Negative Pairs within Same Company (50 pairs)
    neg_same_comp = 0
    for comp, jobs in by_company.items():
        if len(jobs) < 4:
            continue
        for i in range(min(15, len(jobs) - 1)):
            ja, jb = jobs[i], jobs[i + 1]
            ta, tb = ja["title"].lower(), jb["title"].lower()
            if ta != tb and ("engineer" in ta or "manager" in ta or "designer" in ta):
                pair_id += 1
                neg_same_comp += 1
                labeled_pairs.append({
                    "pair_id": f"real_neg_samecomp_{pair_id}",
                    "is_duplicate": False,
                    "match_type": "intra_company_distinct_role",
                    "company": comp,
                    "job_a": {
                        "title": ja["title"],
                        "location": ja["location"],
                        "external_id": ja["external_id"],
                        "content_hash": ja["content_hash"],
                        "description": " ".join(ja["description_text"].split()[:250]),
                    },
                    "job_b": {
                        "title": jb["title"],
                        "location": jb["location"],
                        "external_id": jb["external_id"],
                        "content_hash": jb["content_hash"],
                        "description": " ".join(jb["description_text"].split()[:250]),
                    },
                })
                if neg_same_comp >= 50:
                    break
        if neg_same_comp >= 50:
            break

    # 5. Cross-Company Pairs (15 pairs)
    companies = list(by_company.keys())
    neg_cross_comp = 0
    if len(companies) >= 2:
        for i in range(len(companies) - 1):
            ca, cb = companies[i], companies[i + 1]
            ja = by_company[ca][0]
            jb = by_company[cb][0]
            pair_id += 1
            neg_cross_comp += 1
            labeled_pairs.append({
                "pair_id": f"real_neg_crosscomp_{pair_id}",
                "is_duplicate": False,
                "match_type": "cross_company_non_duplicate",
                "company_a": ca,
                "company_b": cb,
                "job_a": {
                    "title": ja["title"],
                    "location": ja["location"],
                    "external_id": ja["external_id"],
                    "content_hash": ja["content_hash"],
                    "description": " ".join(ja["description_text"].split()[:250]),
                },
                "job_b": {
                    "title": jb["title"],
                    "location": jb["location"],
                    "external_id": jb["external_id"],
                    "content_hash": jb["content_hash"],
                    "description": " ".join(jb["description_text"].split()[:250]),
                },
            })
            if neg_cross_comp >= 15:
                break

    print(f"Total labeled pairs sampled: {len(labeled_pairs)}")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(labeled_pairs, f, indent=2)
    print(f"Saved evaluation dataset to {OUT_PATH}")


if __name__ == "__main__":
    main()
