from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text

from scripts.load import get_database_url


BENCHMARK_QUERIES = {
    "oil_production_by_year": """
        SELECT
            EXTRACT(YEAR FROM production_date) AS production_year,
            SUM(volume_m3) AS total_volume_m3
        FROM oil_production
        GROUP BY production_year
        ORDER BY production_year;
    """,
    "gas_production_by_year": """
        SELECT
            EXTRACT(YEAR FROM production_date) AS production_year,
            SUM(volume_m3) AS total_volume_m3
        FROM gas_production
        GROUP BY production_year
        ORDER BY production_year;
    """,
    "latest_pipeline_runs": """
        SELECT
            source_name,
            status,
            rows_loaded,
            rows_rejected,
            error_rate,
            finished_at
        FROM pipeline_runs
        ORDER BY started_at DESC
        LIMIT 10;
    """,
}


def _extract_execution_time(plan_lines: list[str]) -> float | None:
    for line in plan_lines:
        match = re.search(r"Execution Time: ([0-9.]+) ms", line)
        if match:
            return float(match.group(1))
    return None


def run_benchmarks() -> list[dict]:
    engine = create_engine(get_database_url())
    results = []

    with engine.connect() as conn:
        for query_name, query_sql in BENCHMARK_QUERIES.items():
            plan_result = conn.execute(text(f"EXPLAIN ANALYZE {query_sql}"))
            plan_lines = [row[0] for row in plan_result]
            results.append(
                {
                    "query_name": query_name,
                    "execution_time_ms": _extract_execution_time(plan_lines),
                    "plan_lines": plan_lines,
                }
            )

    return results


def write_markdown_report(results: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        "# Query Benchmark Report",
        "",
        f"Generated at: `{generated_at}`",
        "",
        "This report is generated from PostgreSQL `EXPLAIN ANALYZE` output.",
        "Only use performance claims that are directly supported by these results.",
        "",
        "## Summary",
        "",
        "| Query | Execution time (ms) |",
        "| --- | ---: |",
    ]

    for result in results:
        execution_time = result["execution_time_ms"]
        display_time = f"{execution_time:.3f}" if execution_time is not None else "N/A"
        lines.append(f"| `{result['query_name']}` | {display_time} |")

    for result in results:
        lines.extend(
            [
                "",
                f"## {result['query_name']}",
                "",
                "```text",
                *result["plan_lines"],
                "```",
            ]
        )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run PostgreSQL EXPLAIN ANALYZE benchmarks for portfolio queries."
    )
    parser.add_argument(
        "--output",
        default="reports/query_benchmark.md",
        help="Markdown report path.",
    )
    args = parser.parse_args()

    results = run_benchmarks()
    write_markdown_report(results, Path(args.output))
    print(f"Wrote benchmark report to {args.output}")


if __name__ == "__main__":
    main()
