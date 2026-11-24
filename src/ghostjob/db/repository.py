"""SQLite-based append-only snapshot and analytics database repository."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ghostjob.core.models import (
    CanonicalJob,
    CanonicalStatus,
    Company,
    GhostLabel,
    GhostScore,
    JobSnapshot,
    MatchMethod,
    SnapshotToCanonical,
)


class Repository:
    """Thread-safe SQLite repository implementing append-only audit trail."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_schema(self) -> None:
        """Create tables according to the append-only snapshot architecture."""
        with self._get_connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS companies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                domain TEXT NOT NULL,
                ats_type TEXT NOT NULL,
                ats_slug TEXT NOT NULL,
                careers_url TEXT,
                employee_count INTEGER,
                last_seen_at TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS job_snapshots (
                id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL,
                source_url TEXT NOT NULL,
                external_id TEXT NOT NULL,
                scraped_at TIMESTAMP NOT NULL,
                raw_json TEXT,
                title TEXT NOT NULL,
                location TEXT NOT NULL,
                dept TEXT,
                description_text TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                posted_date_claimed TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies(id)
            );

            CREATE INDEX IF NOT EXISTS idx_snapshots_comp_scraped 
                ON job_snapshots(company_id, scraped_at);
            CREATE INDEX IF NOT EXISTS idx_snapshots_content_hash 
                ON job_snapshots(content_hash);
            CREATE INDEX IF NOT EXISTS idx_snapshots_external_id 
                ON job_snapshots(company_id, external_id);

            CREATE TABLE IF NOT EXISTS canonical_jobs (
                id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL,
                title TEXT NOT NULL,
                location TEXT NOT NULL,
                dept TEXT,
                description_sample TEXT,
                content_hash TEXT,
                first_seen_at TIMESTAMP NOT NULL,
                last_seen_at TIMESTAMP NOT NULL,
                times_seen INTEGER NOT NULL DEFAULT 1,
                times_reposted INTEGER NOT NULL DEFAULT 0,
                clone_count INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'open',
                active_snapshot_id TEXT,
                FOREIGN KEY (company_id) REFERENCES companies(id)
            );

            CREATE INDEX IF NOT EXISTS idx_canonical_company 
                ON canonical_jobs(company_id);
            CREATE INDEX IF NOT EXISTS idx_canonical_status 
                ON canonical_jobs(status);

            CREATE TABLE IF NOT EXISTS snapshot_to_canonical (
                snapshot_id TEXT NOT NULL,
                canonical_id TEXT NOT NULL,
                match_method TEXT NOT NULL,
                confidence REAL NOT NULL,
                PRIMARY KEY (snapshot_id, canonical_id),
                FOREIGN KEY (snapshot_id) REFERENCES job_snapshots(id),
                FOREIGN KEY (canonical_id) REFERENCES canonical_jobs(id)
            );

            CREATE TABLE IF NOT EXISTS ghost_scores (
                canonical_id TEXT NOT NULL,
                scored_at TIMESTAMP NOT NULL,
                score REAL NOT NULL,
                label TEXT NOT NULL,
                reasons_json TEXT NOT NULL,
                signals_json TEXT NOT NULL,
                caveats_json TEXT NOT NULL,
                PRIMARY KEY (canonical_id, scored_at),
                FOREIGN KEY (canonical_id) REFERENCES canonical_jobs(id)
            );

            CREATE INDEX IF NOT EXISTS idx_ghost_scores_scored_at 
                ON ghost_scores(scored_at DESC);
            """)

            # Safe schema migrations for existing databases
            try:
                conn.execute("ALTER TABLE canonical_jobs ADD COLUMN clone_count INTEGER NOT NULL DEFAULT 1;")
            except sqlite3.OperationalError:
                pass

    # --- Company operations ---
    def upsert_company(self, company: Company) -> str:
        with self._get_connection() as conn:
            row = conn.execute("SELECT id FROM companies WHERE name = ?", (company.name,)).fetchone()
            if row:
                comp_id = row["id"]
                conn.execute(
                    """
                    UPDATE companies 
                    SET domain = ?, ats_type = ?, ats_slug = ?, careers_url = ?, 
                        employee_count = COALESCE(?, employee_count), last_seen_at = ?
                    WHERE id = ?
                    """,
                    (company.domain, company.ats_type.value, company.ats_slug,
                     company.careers_url, company.employee_count,
                     company.last_seen_at or datetime.now(timezone.utc), comp_id)
                )
                return comp_id
            else:
                comp_id = company.id or f"comp_{uuid.uuid4().hex[:12]}"
                conn.execute(
                    """
                    INSERT INTO companies (id, name, domain, ats_type, ats_slug, careers_url, employee_count, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (comp_id, company.name, company.domain, company.ats_type.value,
                     company.ats_slug, company.careers_url, company.employee_count,
                     company.last_seen_at or datetime.now(timezone.utc))
                )
                return comp_id

    def get_companies(self) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM companies ORDER BY name ASC")
            return [dict(r) for r in cursor.fetchall()]

    def get_company_by_id(self, company_id: str) -> dict[str, Any] | None:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
            return dict(row) if row else None

    # --- Snapshot operations ---
    def insert_snapshot(self, snapshot: JobSnapshot) -> str:
        snap_id = snapshot.id or f"snap_{uuid.uuid4().hex[:16]}"
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO job_snapshots 
                (id, company_id, source_url, external_id, scraped_at, raw_json, title, location, dept, description_text, content_hash, posted_date_claimed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snap_id,
                    snapshot.company_id,
                    snapshot.source_url,
                    snapshot.external_id,
                    snapshot.scraped_at,
                    snapshot.raw_json,
                    snapshot.title,
                    snapshot.location,
                    snapshot.dept,
                    snapshot.description_text,
                    snapshot.content_hash,
                    snapshot.posted_date_claimed,
                )
            )
        return snap_id

    def get_snapshots_unlinked(self) -> list[dict[str, Any]]:
        """Find snapshots that have not been linked to a canonical job yet."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT s.*, c.name as company_name 
                FROM job_snapshots s
                JOIN companies c ON s.company_id = c.id
                LEFT JOIN snapshot_to_canonical m ON s.id = m.snapshot_id
                WHERE m.canonical_id IS NULL
                ORDER BY s.scraped_at ASC
            """)
            return [dict(r) for r in cursor.fetchall()]

    def get_snapshots_by_company(self, company_id: str) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM job_snapshots WHERE company_id = ? ORDER BY scraped_at DESC",
                (company_id,)
            )
            return [dict(r) for r in cursor.fetchall()]

    # --- Canonical operations ---
    def get_canonical_jobs_by_company(self, company_id: str) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM canonical_jobs WHERE company_id = ? ORDER BY last_seen_at DESC",
                (company_id,)
            )
            return [dict(r) for r in cursor.fetchall()]

    def get_all_canonical_jobs(self) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT cj.*, c.name as company_name, c.domain as company_domain,
                       c.employee_count, c.ats_type,
                       COALESCE(MIN(s_all.posted_date_claimed), s_active.posted_date_claimed) as posted_date_claimed,
                       s_active.raw_json,
                       s_active.description_text as snapshot_desc,
                       gs.score as latest_ghost_score, gs.label as latest_ghost_label,
                       gs.reasons_json, gs.signals_json
                FROM canonical_jobs cj
                JOIN companies c ON cj.company_id = c.id
                LEFT JOIN job_snapshots s_active ON cj.active_snapshot_id = s_active.id
                LEFT JOIN snapshot_to_canonical sc ON cj.id = sc.canonical_id
                LEFT JOIN job_snapshots s_all ON sc.snapshot_id = s_all.id
                LEFT JOIN (
                    SELECT canonical_id, score, label, reasons_json, signals_json,
                           ROW_NUMBER() OVER(PARTITION BY canonical_id ORDER BY scored_at DESC) as rn
                    FROM ghost_scores
                ) gs ON cj.id = gs.canonical_id AND gs.rn = 1
                GROUP BY cj.id
                ORDER BY cj.last_seen_at DESC
            """)
            return [dict(r) for r in cursor.fetchall()]

    def get_canonical_job_by_id(self, canonical_id: str) -> dict[str, Any] | None:
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT cj.*, c.name as company_name, c.domain as company_domain,
                       c.employee_count, c.ats_type,
                       COALESCE(MIN(s_all.posted_date_claimed), s_active.posted_date_claimed) as posted_date_claimed,
                       s_active.raw_json,
                       s_active.description_text as snapshot_desc,
                       gs.score as latest_ghost_score, gs.label as latest_ghost_label,
                       gs.reasons_json, gs.signals_json, gs.caveats_json
                FROM canonical_jobs cj
                JOIN companies c ON cj.company_id = c.id
                LEFT JOIN job_snapshots s_active ON cj.active_snapshot_id = s_active.id
                LEFT JOIN snapshot_to_canonical sc ON cj.id = sc.canonical_id
                LEFT JOIN job_snapshots s_all ON sc.snapshot_id = s_all.id
                LEFT JOIN (
                    SELECT canonical_id, score, label, reasons_json, signals_json, caveats_json,
                           ROW_NUMBER() OVER(PARTITION BY canonical_id ORDER BY scored_at DESC) as rn
                    FROM ghost_scores
                ) gs ON cj.id = gs.canonical_id AND gs.rn = 1
                WHERE cj.id = ?
                GROUP BY cj.id
            """, (canonical_id,)).fetchone()
            return dict(row) if row else None

    def upsert_canonical_job(self, job: CanonicalJob) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO canonical_jobs 
                (id, company_id, title, location, dept, description_sample, content_hash, 
                 first_seen_at, last_seen_at, times_seen, times_reposted, clone_count, status, active_snapshot_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at,
                    times_seen = canonical_jobs.times_seen + 1,
                    times_reposted = excluded.times_reposted,
                    clone_count = excluded.clone_count,
                    status = excluded.status,
                    active_snapshot_id = excluded.active_snapshot_id
            """, (
                job.id, job.company_id, job.title, job.location, job.department,
                job.description_sample, job.content_hash, job.first_seen_at,
                job.last_seen_at, job.times_seen, job.times_reposted, job.clone_count,
                job.status.value if isinstance(job.status, CanonicalStatus) else job.status,
                job.active_snapshot_id
            ))

    def link_snapshot_to_canonical(self, mapping: SnapshotToCanonical) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO snapshot_to_canonical
                (snapshot_id, canonical_id, match_method, confidence)
                VALUES (?, ?, ?, ?)
            """, (
                mapping.snapshot_id,
                mapping.canonical_id,
                mapping.match_method.value if isinstance(mapping.match_method, MatchMethod) else mapping.match_method,
                mapping.confidence
            ))

    def batch_commit_dedup(
        self,
        canonicals_to_upsert: list[CanonicalJob],
        links_to_insert: list[SnapshotToCanonical],
    ) -> None:
        """Batch write canonical jobs and snapshot links within a single transaction."""
        with self._get_connection() as conn:
            conn.executemany("""
                INSERT INTO canonical_jobs 
                (id, company_id, title, location, dept, description_sample, content_hash, 
                 first_seen_at, last_seen_at, times_seen, times_reposted, clone_count, status, active_snapshot_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at,
                    times_seen = canonical_jobs.times_seen + 1,
                    times_reposted = excluded.times_reposted,
                    clone_count = excluded.clone_count,
                    status = excluded.status,
                    active_snapshot_id = excluded.active_snapshot_id
            """, [
                (
                    job.id, job.company_id, job.title, job.location, job.department,
                    job.description_sample, job.content_hash, job.first_seen_at,
                    job.last_seen_at, job.times_seen, job.times_reposted, job.clone_count,
                    job.status.value if isinstance(job.status, CanonicalStatus) else job.status,
                    job.active_snapshot_id
                )
                for job in canonicals_to_upsert
            ])

            conn.executemany("""
                INSERT OR REPLACE INTO snapshot_to_canonical
                (snapshot_id, canonical_id, match_method, confidence)
                VALUES (?, ?, ?, ?)
            """, [
                (
                    m.snapshot_id,
                    m.canonical_id,
                    m.match_method.value if isinstance(m.match_method, MatchMethod) else m.match_method,
                    m.confidence
                )
                for m in links_to_insert
            ])

    def insert_ghost_scores_batch(self, scores: list[GhostScore]) -> None:
        """Batch write ghost scores in a single disk transaction."""
        with self._get_connection() as conn:
            conn.executemany("""
                INSERT OR REPLACE INTO ghost_scores
                (canonical_id, scored_at, score, label, reasons_json, signals_json, caveats_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    s.canonical_id,
                    s.scored_at,
                    s.score,
                    s.label.value if isinstance(s.label, GhostLabel) else s.label,
                    json.dumps(s.reasons),
                    json.dumps(s.signals),
                    json.dumps(s.caveats)
                )
                for s in scores
            ])

    # --- Ghost scoring operations ---
    def insert_ghost_score(self, score: GhostScore) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO ghost_scores
                (canonical_id, scored_at, score, label, reasons_json, signals_json, caveats_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                score.canonical_id,
                score.scored_at,
                score.score,
                score.label.value if isinstance(score.label, GhostLabel) else score.label,
                json.dumps(score.reasons),
                json.dumps(score.signals),
                json.dumps(score.caveats)
            ))

    def get_metrics_summary(self) -> dict[str, Any]:
        """Aggregate key metrics across all tables for dashboard & evaluation."""
        with self._get_connection() as conn:
            total_companies = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
            total_snapshots = conn.execute("SELECT COUNT(*) FROM job_snapshots").fetchone()[0]
            total_canonicals = conn.execute("SELECT COUNT(*) FROM canonical_jobs").fetchone()[0]
            
            status_dist = dict(conn.execute(
                "SELECT status, COUNT(*) FROM canonical_jobs GROUP BY status"
            ).fetchall())
            
            ghost_dist = dict(conn.execute(
                """
                SELECT label, COUNT(*) FROM (
                    SELECT label, ROW_NUMBER() OVER (PARTITION BY canonical_id ORDER BY scored_at DESC) as rn
                    FROM ghost_scores
                ) WHERE rn = 1 GROUP BY label
                """
            ).fetchall())

            reposted_count = conn.execute(
                "SELECT COUNT(*) FROM canonical_jobs WHERE times_reposted > 0"
            ).fetchone()[0]

            clone_count = conn.execute(
                "SELECT COUNT(*) FROM canonical_jobs WHERE clone_count > 1"
            ).fetchone()[0]

            return {
                "total_companies": total_companies,
                "total_snapshots": total_snapshots,
                "total_canonical_jobs": total_canonicals,
                "status_distribution": status_dist,
                "ghost_distribution": ghost_dist,
                "reposted_jobs_count": reposted_count,
                "reposted_percentage": (reposted_count / total_canonicals * 100) if total_canonicals else 0.0,
                "cloned_jobs_count": clone_count,
                "cloned_percentage": (clone_count / total_canonicals * 100) if total_canonicals else 0.0,
            }
