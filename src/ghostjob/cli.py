"""Command Line Interface (CLI) for Ghost-Job Detector."""

import asyncio
import json
import logging
from pathlib import Path
import click
import httpx
from rich.console import Console
from rich.table import Table

from ghostjob.config import settings
from ghostjob.core.models import Company
from ghostjob.crawler.discoverer import CareerDiscoverer
from ghostjob.crawler.engine import CrawlerEngine
from ghostjob.db.repository import Repository
from ghostjob.dedup.pipeline import DeduplicationPipeline
from ghostjob.exporter.export import export_dataset
from ghostjob.scorer.engine import GhostScorerEngine

console = Console()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


@click.group()
def cli() -> None:
    """Direct-ATS Scraper, 3-Tier Deduplication & Ghost-Job Detector CLI."""
    pass


@cli.command()
@click.option("--seed-file", type=click.Path(exists=True), default=str(settings.seed_file), help="Path to companies seed JSON.")
@click.option("--limit", type=int, default=None, help="Limit number of companies to crawl.")
@click.option("--concurrency", type=int, default=settings.max_concurrency, help="Max parallel HTTP requests.")
def crawl(seed_file: str, limit: int | None, concurrency: int) -> None:
    """Scrape jobs directly from ATS public APIs into append-only snapshot database."""
    console.print(f"[bold blue]Starting direct-ATS crawl from {seed_file}...[/bold blue]")
    
    with open(seed_file, "r", encoding="utf-8") as f:
        raw_companies = json.load(f)

    companies: list[Company] = []
    for c in raw_companies:
        if c.get("ats_type") in ["greenhouse", "lever", "ashby"]:
            companies.append(Company(**c))

    if limit:
        companies = companies[:limit]

    console.print(f"Targeting [green]{len(companies)}[/green] companies with valid ATS adapters.")

    repo = Repository(settings.db_path)
    engine = CrawlerEngine(repo=repo, concurrency=concurrency)

    with console.status("[bold green]Crawling ATS endpoints...") as status:
        stats = asyncio.run(engine.run(companies))

    console.print(f"[bold green]Crawl complete![/bold green] Ingested [bold]{stats['total_jobs_scraped']}[/bold] job snapshots across {stats['successful_companies']}/{stats['companies_crawled']} companies.")


@cli.command()
@click.argument("domain")
def discover(domain: str) -> None:
    """Auto-detect ATS vendor and slug from a company domain."""
    console.print(f"Probing careers page for [cyan]{domain}[/cyan]...")
    discoverer = CareerDiscoverer()

    async def _run() -> None:
        async with httpx.AsyncClient(headers={"User-Agent": settings.user_agent}) as client:
            res = await discoverer.discover(domain, client)
            if res:
                ats_type, slug, careers_url = res
                console.print(f"[bold green]Detected ATS![/bold green]")
                console.print(f"  ATS Type:    [bold]{ats_type.value}[/bold]")
                console.print(f"  ATS Slug:    [bold]{slug}[/bold]")
                console.print(f"  Careers URL: {careers_url}")
            else:
                console.print(f"[yellow]Could not detect supported ATS on {domain}. Likely custom/Workday.[/yellow]")

    asyncio.run(_run())


@cli.command()
def dedup() -> None:
    """Run 3-tier deduplication pipeline (Exact Hash -> Fuzzy -> Semantic)."""
    console.print("[bold blue]Executing 3-tier deduplication pipeline...[/bold blue]")
    repo = Repository(settings.db_path)
    pipeline = DeduplicationPipeline(repo=repo)
    results = pipeline.run()

    table = Table(title="Deduplication Execution Summary", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="green")

    table.add_row("Snapshots Processed", str(results["snapshots_processed"]))
    table.add_row("New Canonical Jobs Created", str(results["new_canonical_created"]))
    table.add_row("Matched Existing Canonical Roles", str(results["matched_existing"]))
    table.add_row("Repost Loops Flagged", str(results["reposts_detected"]))

    console.print(table)


@cli.command()
def score() -> None:
    """Compute transparent explainable ghost-job scores on all canonical listings."""
    console.print("[bold blue]Computing ghost-job probabilities & explainability...[/bold blue]")
    repo = Repository(settings.db_path)
    engine = GhostScorerEngine(repo=repo)
    results = engine.score_all_jobs()

    console.print(f"Scored [bold green]{results['total_scored']}[/bold green] canonical jobs.")
    
    table = Table(title="Ghost Score Risk Distribution", show_header=True)
    table.add_column("Label", style="cyan")
    table.add_column("Count", style="magenta")

    for label, count in results["distribution"].items():
        table.add_row(label.capitalize(), str(count))

    console.print(table)


@cli.command()
@click.option("--format", "file_format", type=click.Choice(["json", "csv"]), default="json")
@click.option("--output", "output_path", type=click.Path(), default=None)
def export(file_format: str, output_path: str | None) -> None:
    """Export canonical job dataset with ghost scores and explanations."""
    repo = Repository(settings.db_path)
    if not output_path:
        output_path = str(settings.db_path.parent / f"exports/jobs_export.{file_format}")

    path = Path(output_path)
    count = export_dataset(repo, path, file_format)
    console.print(f"[bold green]Exported {count} jobs to {path}[/bold green]")


@cli.command()
def stats() -> None:
    """Display overall metrics dashboard."""
    repo = Repository(settings.db_path)
    summary = repo.get_metrics_summary()

    table = Table(title="Ghost-Job Detector Metrics Summary", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="bold green")

    table.add_row("Total Companies", str(summary["total_companies"]))
    table.add_row("Total Ingested Snapshots", str(summary["total_snapshots"]))
    table.add_row("Canonical Unique Jobs", str(summary["total_canonical_jobs"]))
    table.add_row("Multi-Location Clones (Single Batch)", f"{summary.get('cloned_jobs_count', 0)} ({summary.get('cloned_percentage', 0.0):.1f}%)")
    table.add_row("Longitudinal Repost Loops (Multi-Day)", f"{summary['reposted_jobs_count']} ({summary['reposted_percentage']:.1f}%)")

    console.print(table)


@cli.command()
@click.option("--port", type=int, default=8000, help="Port to run FastAPI on.")
def serve(port: int) -> None:
    """Run local FastAPI service for dashboard and job explainability."""
    import uvicorn
    console.print(f"[bold green]Starting API server at http://localhost:{port}[/bold green]")
    uvicorn.run("ghostjob.api.app:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    cli()
