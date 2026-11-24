"""Probe candidate companies and build validated seeds list."""

import asyncio
import json
from pathlib import Path
import httpx

CANDIDATES = [
    # Top Indian tech & global firms with verified ATS endpoints
    {"name": "Razorpay", "domain": "razorpay.com", "ats_type": "greenhouse", "ats_slug": "razorpaysoftwareprivatelimited", "employee_count": 3200},
    {"name": "Instawork", "domain": "instawork.com", "ats_type": "greenhouse", "ats_slug": "instawork", "employee_count": 650},
    {"name": "CRED", "domain": "cred.club", "ats_type": "lever", "ats_slug": "cred", "employee_count": 900},
    {"name": "Meesho", "domain": "meesho.io", "ats_type": "lever", "ats_slug": "meesho", "employee_count": 2000},
    {"name": "Figma", "domain": "figma.com", "ats_type": "greenhouse", "ats_slug": "figma", "employee_count": 1500},
    {"name": "Coinbase", "domain": "coinbase.com", "ats_type": "greenhouse", "ats_slug": "coinbase", "employee_count": 3400},
    {"name": "Ramp", "domain": "ramp.com", "ats_type": "ashby", "ats_slug": "ramp", "employee_count": 900},
    {"name": "Linear", "domain": "linear.app", "ats_type": "ashby", "ats_slug": "linear", "employee_count": 80},
    {"name": "Vercel", "domain": "vercel.com", "ats_type": "ashby", "ats_slug": "vercel", "employee_count": 600},
    {"name": "Retool", "domain": "retool.com", "ats_type": "ashby", "ats_slug": "retool", "employee_count": 500},
    {"name": "Supabase", "domain": "supabase.com", "ats_type": "ashby", "ats_slug": "supabase", "employee_count": 120},
    {"name": "Deel", "domain": "deel.com", "ats_type": "ashby", "ats_slug": "deel", "employee_count": 3000},
    {"name": "Stripe", "domain": "stripe.com", "ats_type": "greenhouse", "ats_slug": "stripe", "employee_count": 8000},
    {"name": "Cloudflare", "domain": "cloudflare.com", "ats_type": "greenhouse", "ats_slug": "cloudflare", "employee_count": 3500},
    {"name": "Reddit", "domain": "reddit.com", "ats_type": "greenhouse", "ats_slug": "reddit", "employee_count": 2000},
    {"name": "Datadog", "domain": "datadoghq.com", "ats_type": "greenhouse", "ats_slug": "datadog", "employee_count": 5000},
    {"name": "Rippling", "domain": "rippling.com", "ats_type": "greenhouse", "ats_slug": "rippling", "employee_count": 2500},
    {"name": "Pinterest", "domain": "pinterest.com", "ats_type": "greenhouse", "ats_slug": "pinterest", "employee_count": 4000},
    {"name": "Rubrik", "domain": "rubrik.com", "ats_type": "greenhouse", "ats_slug": "rubrik", "employee_count": 3500},
    {"name": "Snowflake", "domain": "snowflake.com", "ats_type": "greenhouse", "ats_slug": "snowflake", "employee_count": 7000},
    {"name": "Twitch", "domain": "twitch.tv", "ats_type": "greenhouse", "ats_slug": "twitch", "employee_count": 1800},
    {"name": "Discord", "domain": "discord.com", "ats_type": "greenhouse", "ats_slug": "discord", "employee_count": 1000},
    {"name": "GitHub", "domain": "github.com", "ats_type": "greenhouse", "ats_slug": "github", "employee_count": 3000},
    {"name": "GitLab", "domain": "gitlab.com", "ats_type": "greenhouse", "ats_slug": "gitlab", "employee_count": 2200},
    {"name": "Robinhood", "domain": "robinhood.com", "ats_type": "greenhouse", "ats_slug": "robinhood", "employee_count": 2400},
    {"name": "Gusto", "domain": "gusto.com", "ats_type": "greenhouse", "ats_slug": "gusto", "employee_count": 2500},
    {"name": "Brex", "domain": "brex.com", "ats_type": "greenhouse", "ats_slug": "brex", "employee_count": 1100},
    {"name": "Airtable", "domain": "airtable.com", "ats_type": "greenhouse", "ats_slug": "airtable", "employee_count": 1200},
    {"name": "Carta", "domain": "carta.com", "ats_type": "greenhouse", "ats_slug": "carta", "employee_count": 1800},
    {"name": "Miro", "domain": "miro.com", "ats_type": "greenhouse", "ats_slug": "miro", "employee_count": 1800},
    {"name": "Toast", "domain": "pos.toasttab.com", "ats_type": "greenhouse", "ats_slug": "toast", "employee_count": 4500},
    {"name": "MongoDB", "domain": "mongodb.com", "ats_type": "greenhouse", "ats_slug": "mongodb", "employee_count": 5000},
    {"name": "Elastic", "domain": "elastic.co", "ats_type": "greenhouse", "ats_slug": "elastic", "employee_count": 3200},
    {"name": "Okta", "domain": "okta.com", "ats_type": "greenhouse", "ats_slug": "okta", "employee_count": 6000},
    {"name": "HashiCorp", "domain": "hashicorp.com", "ats_type": "greenhouse", "ats_slug": "hashicorp", "employee_count": 2500},
    {"name": "Chainalysis", "domain": "chainalysis.com", "ats_type": "greenhouse", "ats_slug": "chainalysis", "employee_count": 900},
    {"name": "Affirm", "domain": "affirm.com", "ats_type": "greenhouse", "ats_slug": "affirm", "employee_count": 2100},
    {"name": "Plaid", "domain": "plaid.com", "ats_type": "greenhouse", "ats_slug": "plaid", "employee_count": 1100},
    {"name": "DoorDash", "domain": "doordash.com", "ats_type": "greenhouse", "ats_slug": "doordash", "employee_count": 15000},
    {"name": "Samsara", "domain": "samsara.com", "ats_type": "greenhouse", "ats_slug": "samsara", "employee_count": 3000},
    {"name": "Cockroach Labs", "domain": "cockroachlabs.com", "ats_type": "greenhouse", "ats_slug": "cockroachlabs", "employee_count": 500},
    {"name": "dbt Labs", "domain": "getdbt.com", "ats_type": "greenhouse", "ats_slug": "dbtlabs", "employee_count": 450},
    {"name": "Benchling", "domain": "benchling.com", "ats_type": "lever", "ats_slug": "benchling", "employee_count": 800},
    {"name": "Kraken", "domain": "kraken.com", "ats_type": "lever", "ats_slug": "kraken", "employee_count": 2500},
    {"name": "Spotify", "domain": "spotify.com", "ats_type": "lever", "ats_slug": "spotify", "employee_count": 9000},
    {"name": "FullStory", "domain": "fullstory.com", "ats_type": "lever", "ats_slug": "fullstory", "employee_count": 500},
    {"name": "Hotjar", "domain": "hotjar.com", "ats_type": "lever", "ats_slug": "hotjar", "employee_count": 400},
    {"name": "Scale AI", "domain": "scale.com", "ats_type": "ashby", "ats_slug": "scaleai", "employee_count": 1000},
    {"name": "Synthesia", "domain": "synthesia.io", "ats_type": "ashby", "ats_slug": "synthesia", "employee_count": 350},
    {"name": "ElevenLabs", "domain": "elevenlabs.io", "ats_type": "ashby", "ats_slug": "elevenlabs", "employee_count": 80},
    {"name": "Perplexity", "domain": "perplexity.ai", "ats_type": "ashby", "ats_slug": "perplexity", "employee_count": 60},
]


async def main():
    valid = []
    headers = {"User-Agent": "Mozilla/5.0 GhostJobValidator/1.0"}
    async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
        for c in CANDIDATES:
            ats = c["ats_type"]
            slug = c["ats_slug"]
            if ats == "greenhouse":
                url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
            elif ats == "lever":
                url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
            else:
                url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
            try:
                r = await client.get(url)
                if r.status_code == 200:
                    valid.append(c)
                    print(f"[VALID] {c['name']} ({ats})")
                else:
                    print(f"[FAIL {r.status_code}] {c['name']}")
            except Exception as e:
                print(f"[ERR] {c['name']}: {e}")

    out_file = Path("data/seeds/companies.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(valid, f, indent=2)

    print(f"\nSaved {len(valid)} verified target companies to {out_file}!")


if __name__ == "__main__":
    asyncio.run(main())
