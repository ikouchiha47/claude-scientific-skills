#!/usr/bin/env python3
"""
memory_store.py — SQLite-based memory for AI agent sessions.

Stores observations, analyses, strategies, and correlations discovered
during research sessions. Designed for LLM-driven paginated search
(no vector DB needed — the LLM reads and filters).

Usage:
    # Insert
    uv run python memory_store.py insert observations '{"content": "NMDC dropped 3% after M6.2 quake near Bellary", "tags": "mining,earthquake,NMDC", "source": "geo-intelligence + yfinance", "confidence": "high"}'

    # Search
    uv run python memory_store.py search observations "earthquake mining" --limit 10 --offset 0

    # List tables
    uv run python memory_store.py tables

    # Recent entries
    uv run python memory_store.py recent observations --limit 20

    # Export
    uv run python memory_store.py export observations --format json
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Default memory directory
# .memory/ lives at the project root (same level as memory/ directory)
MEMORY_DIR = Path(os.environ.get("MEMORY_DIR", Path(__file__).parent.parent.parent / ".memory"))

SCHEMA = {
    "observations": """
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT (datetime('now')),
            content TEXT NOT NULL,
            tags TEXT,
            source TEXT,
            confidence TEXT DEFAULT 'medium'
        )
    """,
    "analyses": """
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT (datetime('now')),
            symbol TEXT,
            analysis_type TEXT,
            timeframe TEXT,
            findings TEXT NOT NULL,
            recommendation TEXT,
            data_sources TEXT,
            confidence TEXT DEFAULT 'medium'
        )
    """,
    "strategies": """
        CREATE TABLE IF NOT EXISTS strategies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT (datetime('now')),
            name TEXT NOT NULL,
            description TEXT,
            symbols TEXT,
            parameters TEXT,
            total_return REAL,
            sharpe_ratio REAL,
            max_drawdown REAL,
            win_rate REAL,
            backtest_period TEXT,
            notes TEXT
        )
    """,
    "correlations": """
        CREATE TABLE IF NOT EXISTS correlations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT (datetime('now')),
            signal_type TEXT NOT NULL,
            signal_source TEXT,
            asset TEXT NOT NULL,
            correlation_strength REAL,
            direction TEXT,
            lag_days INTEGER,
            timeframe TEXT,
            evidence TEXT,
            confidence TEXT DEFAULT 'medium'
        )
    """,
    "sessions": """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT (datetime('now')),
            query TEXT,
            skills_used TEXT,
            summary TEXT,
            status TEXT DEFAULT 'active'
        )
    """,
}


# FTS5 virtual tables mirroring text-heavy tables for full-text search
FTS_TABLES = {
    "observations": """
        CREATE VIRTUAL TABLE IF NOT EXISTS observations_fts USING fts5(
            content, tags, source, confidence,
            content_rowid='id', content='observations'
        )
    """,
    "analyses": """
        CREATE VIRTUAL TABLE IF NOT EXISTS analyses_fts USING fts5(
            symbol, analysis_type, findings, recommendation, data_sources,
            content_rowid='id', content='analyses'
        )
    """,
    "correlations": """
        CREATE VIRTUAL TABLE IF NOT EXISTS correlations_fts USING fts5(
            signal_type, signal_source, asset, evidence,
            content_rowid='id', content='correlations'
        )
    """,
}

# Triggers to keep FTS in sync with main tables
FTS_TRIGGERS = {
    "observations": [
        """CREATE TRIGGER IF NOT EXISTS observations_ai AFTER INSERT ON observations BEGIN
            INSERT INTO observations_fts(rowid, content, tags, source, confidence)
            VALUES (new.id, new.content, new.tags, new.source, new.confidence);
        END""",
        """CREATE TRIGGER IF NOT EXISTS observations_ad AFTER DELETE ON observations BEGIN
            INSERT INTO observations_fts(observations_fts, rowid, content, tags, source, confidence)
            VALUES ('delete', old.id, old.content, old.tags, old.source, old.confidence);
        END""",
    ],
    "analyses": [
        """CREATE TRIGGER IF NOT EXISTS analyses_ai AFTER INSERT ON analyses BEGIN
            INSERT INTO analyses_fts(rowid, symbol, analysis_type, findings, recommendation, data_sources)
            VALUES (new.id, new.symbol, new.analysis_type, new.findings, new.recommendation, new.data_sources);
        END""",
        """CREATE TRIGGER IF NOT EXISTS analyses_ad AFTER DELETE ON analyses BEGIN
            INSERT INTO analyses_fts(analyses_fts, rowid, symbol, analysis_type, findings, recommendation, data_sources)
            VALUES ('delete', old.id, old.symbol, old.analysis_type, old.findings, old.recommendation, old.data_sources);
        END""",
    ],
    "correlations": [
        """CREATE TRIGGER IF NOT EXISTS correlations_ai AFTER INSERT ON correlations BEGIN
            INSERT INTO correlations_fts(rowid, signal_type, signal_source, asset, evidence)
            VALUES (new.id, new.signal_type, new.signal_source, new.asset, new.evidence);
        END""",
        """CREATE TRIGGER IF NOT EXISTS correlations_ad AFTER DELETE ON correlations BEGIN
            INSERT INTO correlations_fts(correlations_fts, rowid, signal_type, signal_source, asset, evidence)
            VALUES ('delete', old.id, old.signal_type, old.signal_source, old.asset, old.evidence);
        END""",
    ],
}


def get_db(table: str) -> sqlite3.Connection:
    """Get connection to the SQLite DB for a table. Each logical group gets its own file."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    # Group tables into DB files
    db_map = {
        "observations": "research.db",
        "analyses": "research.db",
        "correlations": "research.db",
        "strategies": "strategies.db",
        "sessions": "sessions.db",
    }
    db_file = MEMORY_DIR / db_map.get(table, "general.db")
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row

    # SQLite optimizations (WAL mode, pragmas)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA mmap_size=268435456")  # 256MB mmap
    conn.execute("PRAGMA busy_timeout=5000")

    # Create main table
    if table in SCHEMA:
        conn.execute(SCHEMA[table])
        conn.commit()

    # Create FTS table and triggers
    if table in FTS_TABLES:
        conn.execute(FTS_TABLES[table])
        for trigger in FTS_TRIGGERS.get(table, []):
            conn.execute(trigger)
        conn.commit()

    return conn


def insert(table: str, data: dict) -> int:
    """Insert a record into a table. Returns the row ID."""
    conn = get_db(table)
    columns = ", ".join(data.keys())
    placeholders = ", ".join(["?" for _ in data])
    cursor = conn.execute(
        f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
        list(data.values()),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def search(table: str, query: str, limit: int = 20, offset: int = 0) -> list[dict]:
    """Search a table. Uses FTS5 if available, falls back to LIKE."""
    conn = get_db(table)
    fts_table = f"{table}_fts"

    # Try FTS5 first (much faster, ranked by relevance)
    if table in FTS_TABLES:
        try:
            rows = conn.execute(
                f"""SELECT {table}.* FROM {fts_table}
                    JOIN {table} ON {table}.id = {fts_table}.rowid
                    WHERE {fts_table} MATCH ?
                    ORDER BY rank
                    LIMIT ? OFFSET ?""",
                [query, limit, offset],
            ).fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception:
            pass  # Fall back to LIKE

    # Fallback: LIKE search on text columns
    cursor = conn.execute(f"PRAGMA table_info({table})")
    columns = [row["name"] for row in cursor.fetchall()]
    text_cols = [c for c in columns if c not in ("id", "created_at")]

    terms = query.split()
    conditions = []
    params = []
    for term in terms:
        col_conditions = [f"{col} LIKE ?" for col in text_cols]
        conditions.append(f"({' OR '.join(col_conditions)})")
        params.extend([f"%{term}%" for _ in text_cols])

    where = " AND ".join(conditions) if conditions else "1=1"
    rows = conn.execute(
        f"SELECT * FROM {table} WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()

    conn.close()
    return [dict(row) for row in rows]


def recent(table: str, limit: int = 20) -> list[dict]:
    """Get most recent entries from a table."""
    conn = get_db(table)
    rows = conn.execute(
        f"SELECT * FROM {table} ORDER BY created_at DESC LIMIT ?", [limit]
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def count(table: str) -> int:
    """Count total rows in a table."""
    conn = get_db(table)
    result = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    conn.close()
    return result[0]


def list_tables() -> dict:
    """List all tables and their row counts."""
    result = {}
    for table in SCHEMA:
        try:
            result[table] = count(table)
        except Exception:
            result[table] = 0
    return result


def export_table(table: str, fmt: str = "json") -> str:
    """Export entire table as JSON or CSV."""
    conn = get_db(table)
    rows = conn.execute(f"SELECT * FROM {table} ORDER BY created_at DESC").fetchall()
    conn.close()

    data = [dict(row) for row in rows]
    if fmt == "json":
        return json.dumps(data, indent=2)
    elif fmt == "csv":
        if not data:
            return ""
        import csv
        import io
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        return output.getvalue()
    return json.dumps(data, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Memory store for AI agent sessions")
    subparsers = parser.add_subparsers(dest="command")

    # insert
    p_insert = subparsers.add_parser("insert", help="Insert a record")
    p_insert.add_argument("table", help="Table name")
    p_insert.add_argument("data", help="JSON object with column values")

    # search
    p_search = subparsers.add_parser("search", help="Search records")
    p_search.add_argument("table", help="Table name")
    p_search.add_argument("query", help="Search terms (space-separated)")
    p_search.add_argument("--limit", type=int, default=20)
    p_search.add_argument("--offset", type=int, default=0)

    # recent
    p_recent = subparsers.add_parser("recent", help="Recent entries")
    p_recent.add_argument("table", help="Table name")
    p_recent.add_argument("--limit", type=int, default=20)

    # tables
    subparsers.add_parser("tables", help="List tables and counts")

    # export
    p_export = subparsers.add_parser("export", help="Export table")
    p_export.add_argument("table", help="Table name")
    p_export.add_argument("--format", choices=["json", "csv"], default="json")

    # count
    p_count = subparsers.add_parser("count", help="Count rows")
    p_count.add_argument("table", help="Table name")

    args = parser.parse_args()

    if args.command == "insert":
        data = json.loads(args.data)
        row_id = insert(args.table, data)
        print(f"Inserted row {row_id} into {args.table}")

    elif args.command == "search":
        results = search(args.table, args.query, args.limit, args.offset)
        print(json.dumps(results, indent=2))
        print(f"\n({len(results)} results, offset={args.offset})")

    elif args.command == "recent":
        results = recent(args.table, args.limit)
        print(json.dumps(results, indent=2))

    elif args.command == "tables":
        tables = list_tables()
        for t, c in tables.items():
            print(f"  {t}: {c} rows")

    elif args.command == "export":
        print(export_table(args.table, args.format))

    elif args.command == "count":
        print(f"{args.table}: {count(args.table)} rows")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
