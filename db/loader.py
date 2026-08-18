"""SQLite loader -- Day 4 deliverable.

Creates nifty100.db from db/schema.sql, then inserts the cleaned
DataFrames that src/etl/pipeline.py already produces. This module doesn't
re-implement cleaning; it trusts pipeline.py's output completely, because
duplicating the clean_table() logic here would create two places that could
disagree about what "clean" means for the same table.

Run with: python db/loader.py
Produces: db/nifty100.db
"""

import os
import sqlite3
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "etl"))
from pipeline import run_pipeline

DB_DIR = os.path.dirname(__file__)
SCHEMA_PATH = os.path.join(DB_DIR, "schema.sql")
# config/.env.template (from the original project scaffold, predating this
# module) declares DB_PATH=data/nifty100.db -- that's the convention the
# rest of the project expects (Makefile's `load` target, any future .env a
# teammate creates), so the DB file lives there, not next to schema.sql.
DB_PATH = os.path.join(DB_DIR, "..", "data", "nifty100.db")

# documents.xlsx loads with its original Excel headers ('Year',
# 'Annual_Report') because loader.py deliberately doesn't rename columns --
# it just normalises values. The DB schema uses lowercase names for
# consistency with every other table, so the rename happens here, at the
# DB-loading boundary, rather than by making loader.py inconsistent with
# the source file's documented column names.
_COLUMN_RENAMES = {
    "documents": {"Year": "year", "Annual_Report": "annual_report"},
}

# Every source Excel file carries its own 'id' row-number column (spec
# calls it "not analytically meaningful" wherever a real composite key
# exists). profitandloss/balancesheet/cashflow keep it anyway as a plain
# traceability column since the schema declares a column for it -- but the
# 5 supplementary tables' schemas don't declare an id column at all
# (company_id or a composite is the real key), so their source 'id' has to
# be dropped here or the INSERT fails with "no such column".
_DROP_ID_COLUMN = {"sectors", "stock_prices", "market_cap", "financial_ratios", "peer_groups"}


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Open a connection with foreign key enforcement turned on.

    SQLite ships with FK enforcement OFF by default for backwards
    compatibility with pre-3.6.19 databases -- every connection this project
    opens needs this pragma re-applied, since it's a per-connection setting,
    not a database-level one baked into the file.

    check_same_thread=False: found necessary during Sprint 4's dashboard QA
    (actually running the Streamlit app, not just reading the code) --
    Streamlit's st.cache_resource caches this connection object across
    script reruns, but reruns can execute on a different worker thread than
    the one that created the connection. Python's sqlite3 module refuses
    cross-thread use of a connection by default and raises
    ProgrammingError. This is safe to disable here because every caller in
    this project only reads or does single-writer batch loads -- nothing
    does concurrent writes from multiple threads that this guard would
    have been protecting against.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())


def insert_dataframe(conn: sqlite3.Connection, df: pd.DataFrame, table_name: str) -> int:
    """Insert a cleaned DataFrame into an existing table. Returns row count inserted."""
    df = df.rename(columns=_COLUMN_RENAMES.get(table_name, {}))
    if table_name in _DROP_ID_COLUMN:
        df = df.drop(columns=["id"])
    df.to_sql(table_name, conn, if_exists="append", index=False)
    return len(df)


def load_all_core_tables(conn: sqlite3.Connection, tables: dict) -> dict:
    """Insert all 12 tables in FK-safe order: companies first, then every child.

    SQLite checks FK constraints at INSERT time (with the pragma on), so
    inserting a child row before its parent company_id exists would fail --
    this order isn't just tidy, it's required.
    """
    load_order = [
        "companies", "profitandloss", "balancesheet", "cashflow",
        "analysis", "documents", "prosandcons",
        "sectors", "stock_prices", "market_cap", "financial_ratios", "peer_groups",
    ]
    counts = {}
    for table_name in load_order:
        counts[table_name] = insert_dataframe(conn, tables[table_name], table_name)
    return counts


if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        # Re-running the loader against an existing DB would violate the
        # PRIMARY KEY constraints on the second insert -- rather than fail
        # halfway through with a partially-loaded DB, start clean every time
        # this script runs directly. (This is safe because nifty100.db is a
        # derived artifact, fully reproducible from data/raw/ + this code --
        # never a place to store anything unique.)
        os.remove(DB_PATH)

    tables = run_pipeline(check_urls=False)

    conn = get_connection()
    try:
        create_schema(conn)
        counts = load_all_core_tables(conn, tables)
        conn.commit()
    finally:
        conn.close()

    print("Loaded nifty100.db:")
    for table_name, count in counts.items():
        print(f"  {table_name}: {count} rows")
