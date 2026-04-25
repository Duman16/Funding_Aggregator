"""
Seed script: runs both collectors and stores results to DB.
Usage (inside container):
    python -m scripts.seed
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


async def main():
    from app.collector.grants_gov import GrantsGovCollector
    from app.collector.nih_reporter import NIHReporterCollector
    from app.processor.pipeline import run_pipeline
    from app.database import AsyncSessionLocal

    print("=== Funding Aggregator Seed Script ===\n")

    collectors = [
        ("grants_gov", GrantsGovCollector()),
        ("nih_reporter", NIHReporterCollector()),
    ]

    for source, collector in collectors:
        print(f"[{source}] Collecting...")
        result = await collector.run()

        if result["status"] == "success" and result["data"]:
            async with AsyncSessionLocal() as db:
                log = await run_pipeline(db, result["data"], source)
            print(
                f"[{source}] Done — "
                f"collected={log.records_collected}, "
                f"new={log.records_new}, "
                f"updated={log.records_updated}"
            )
        else:
            print(f"[{source}] Failed: {result.get('error', 'unknown error')}")

    print("\n=== Seeding complete ===")


if __name__ == "__main__":
    asyncio.run(main())
