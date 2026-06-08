# Query Benchmark Report

Benchmark results have not been generated yet.

This project includes `scripts/benchmark_queries.py`, which connects to
PostgreSQL and writes real `EXPLAIN ANALYZE` output to this file.

Run it after loading the database:

```bash
python scripts/benchmark_queries.py
```

No query-speed improvement claims should be made until this report contains real
PostgreSQL execution plans and timings.
