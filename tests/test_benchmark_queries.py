from pathlib import Path

from scripts import benchmark_queries
from scripts.benchmark_queries import (
    _extract_execution_time,
    run_benchmarks,
    write_markdown_report,
)


SAMPLE_PLAN = [
    "HashAggregate  (cost=1.09..1.11 rows=1 width=40)",
    "Planning Time: 0.184 ms",
    "Execution Time: 0.412 ms",
]


class FakeResult:
    def __init__(self, plan_lines):
        self.plan_lines = plan_lines

    def __iter__(self):
        return iter([(line,) for line in self.plan_lines])


class FakeConnection:
    def __init__(self):
        self.statements = []

    def execute(self, statement):
        self.statements.append(str(statement))
        return FakeResult(SAMPLE_PLAN)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class FakeEngine:
    def __init__(self):
        self.connection = FakeConnection()

    def connect(self):
        return self.connection


def test_extract_execution_time_parses_plan():
    assert _extract_execution_time(SAMPLE_PLAN) == 0.412


def test_extract_execution_time_returns_none_when_absent():
    assert _extract_execution_time(["Seq Scan on oil_production"]) is None


def test_run_benchmarks_explains_every_query(monkeypatch):
    engine = FakeEngine()
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
    monkeypatch.setattr(benchmark_queries, "create_engine", lambda url: engine)

    results = run_benchmarks()

    assert len(results) == len(benchmark_queries.BENCHMARK_QUERIES)
    assert {r["query_name"] for r in results} == set(benchmark_queries.BENCHMARK_QUERIES)
    assert all(r["execution_time_ms"] == 0.412 for r in results)
    assert all(
        statement.startswith("EXPLAIN ANALYZE")
        for statement in engine.connection.statements
    )


def test_write_markdown_report_includes_times_and_plans(tmp_path):
    results = [
        {
            "query_name": "oil_production_by_year",
            "execution_time_ms": 0.412,
            "plan_lines": SAMPLE_PLAN,
        }
    ]
    output_path = Path(tmp_path) / "nested" / "query_benchmark.md"

    write_markdown_report(results, output_path)

    report = output_path.read_text(encoding="utf-8")
    assert "# Query Benchmark Report" in report
    assert "`oil_production_by_year`" in report
    assert "0.412" in report
    assert "Execution Time: 0.412 ms" in report


def test_write_markdown_report_handles_missing_time(tmp_path):
    results = [
        {
            "query_name": "latest_pipeline_runs",
            "execution_time_ms": None,
            "plan_lines": ["Limit  (cost=0.00..0.02 rows=1 width=8)"],
        }
    ]
    output_path = Path(tmp_path) / "query_benchmark.md"

    write_markdown_report(results, output_path)

    assert "| N/A |" in output_path.read_text(encoding="utf-8")


def test_main_writes_report_to_requested_path(tmp_path, monkeypatch):
    engine = FakeEngine()
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
    monkeypatch.setattr(benchmark_queries, "create_engine", lambda url: engine)

    output_path = Path(tmp_path) / "report.md"
    monkeypatch.setattr("sys.argv", ["benchmark_queries.py", "--output", str(output_path)])

    benchmark_queries.main()

    assert output_path.exists()
    assert "Query Benchmark Report" in output_path.read_text(encoding="utf-8")
