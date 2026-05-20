#!/usr/bin/env python3
"""
Load unified_chats.jsonl (and optionally evaluated_prompts.jsonl) into chats.duckdb.

Usage:
    python3 load_duckdb.py
    python3 load_duckdb.py --chats unified_chats.jsonl --evals evaluated_prompts.jsonl --db chats.duckdb
"""

import sys
import argparse
from pathlib import Path

import duckdb


def load(chats_path: str, db_path: str, evals_path: str | None) -> None:
    if not Path(chats_path).exists():
        print(f"Error: {chats_path} not found. Run generate_dashboard.py first.")
        sys.exit(1)

    conn = duckdb.connect(db_path)

    conn.execute(f"""
        CREATE OR REPLACE TABLE chats AS
        SELECT * FROM read_ndjson_auto('{chats_path}')
    """)
    n_chats = conn.execute("SELECT COUNT(*) FROM chats").fetchone()[0]
    print(f"chats table: {n_chats} rows from {chats_path}")

    if evals_path and Path(evals_path).exists():
        conn.execute(f"""
            CREATE OR REPLACE TABLE evaluations AS
            SELECT * FROM read_ndjson_auto('{evals_path}')
        """)
        n_evals = conn.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0]
        print(f"evaluations table: {n_evals} rows from {evals_path}")
    else:
        if evals_path:
            print(f"Skipping evaluations: {evals_path} not found")

    conn.close()
    print(f"Written: {db_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load JSONL files into DuckDB")
    parser.add_argument("--chats", default="unified_chats.jsonl")
    parser.add_argument("--evals", default="evaluated_prompts.jsonl")
    parser.add_argument("--db", default="chats.duckdb")
    args = parser.parse_args()

    load(args.chats, args.db, args.evals)


if __name__ == "__main__":
    main()
