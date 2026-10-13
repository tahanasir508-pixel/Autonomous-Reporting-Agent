"""
db_connector.py
Connects to a user's own database (MySQL, PostgreSQL, SQL Server, or
SQLite) and pulls rows into the same 6-column shape the rest of the
system expects (date, region, product, units_sold, revenue,
transaction_count) — using whatever their actual column names are,
via a mapping they configure once.

Uses SQLAlchemy, which means the SAME code here works across every
supported database type; only the connection string format differs.
"""

import pandas as pd
from sqlalchemy import create_engine, text

# Maps a friendly db_type name to the SQLAlchemy "dialect+driver" prefix
# and which pip package provides that driver.
DB_DRIVERS = {
    "postgresql": {"prefix": "postgresql+psycopg2", "pip_package": "psycopg2-binary"},
    "mysql": {"prefix": "mysql+pymysql", "pip_package": "pymysql"},
    "sqlserver": {"prefix": "mssql+pyodbc", "pip_package": "pyodbc"},
    "sqlite": {"prefix": "sqlite", "pip_package": None},  # built into Python
}

REQUIRED_COLUMNS = ["date", "region", "product", "units_sold", "revenue", "transaction_count"]


def build_connection_string(db_type, host, port, database, username, password) -> str:
    if db_type not in DB_DRIVERS:
        raise ValueError(f"Unsupported database type: {db_type}. Choose from: {list(DB_DRIVERS)}")

    if db_type == "sqlite":
        # For SQLite, "database" is a file path, not a server database name.
        return f"sqlite:///{database}"

    prefix = DB_DRIVERS[db_type]["prefix"]
    return f"{prefix}://{username}:{password}@{host}:{port}/{database}"


def test_connection(db_type, host, port, database, username, password) -> tuple[bool, str]:
    """Tries to actually connect and run a trivial query. Returns
    (success, message) — never raises, so a bad connection attempt
    never crashes the caller."""
    try:
        conn_str = build_connection_string(db_type, host, port, database, username, password)
        engine = create_engine(conn_str, connect_args={"timeout": 10} if db_type == "sqlite" else {})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "Connection successful."
    except ModuleNotFoundError:
        driver_pkg = DB_DRIVERS.get(db_type, {}).get("pip_package")
        return False, f"Missing driver for {db_type}. Install it with: pip install {driver_pkg}"
    except Exception as e:
        return False, f"Connection failed: {e}"


def fetch_new_rows(db_type, host, port, database, username, password,
                    table, column_mapping, since_date=None) -> tuple[bool, str, pd.DataFrame]:
    """
    column_mapping: dict mapping OUR column names to THEIR column names,
    e.g. {"date": "sale_date", "region": "city", "product": "item_name",
          "units_sold": "qty", "revenue": "amount", "transaction_count": "num_transactions"}

    since_date: if given, only fetches rows with a date strictly after
    this (as a string "YYYY-MM-DD"). Used for daily top-ups, so we
    don't re-pull the entire table every time.

    Returns (success, message, dataframe). On failure, dataframe is empty.
    """
    missing_map_keys = [c for c in REQUIRED_COLUMNS if c not in column_mapping]
    if missing_map_keys:
        return False, f"Column mapping is missing: {missing_map_keys}", pd.DataFrame()

    their_date_col = column_mapping["date"]
    select_cols = ", ".join(f'"{column_mapping[c]}"' for c in REQUIRED_COLUMNS)

    query = f'SELECT {select_cols} FROM "{table}"'
    params = {}
    if since_date:
        query += f' WHERE "{their_date_col}" > :since_date'
        params["since_date"] = since_date

    try:
        conn_str = build_connection_string(db_type, host, port, database, username, password)
        engine = create_engine(conn_str)
        with engine.connect() as conn:
            result_df = pd.read_sql(text(query), conn, params=params)
    except ModuleNotFoundError:
        driver_pkg = DB_DRIVERS.get(db_type, {}).get("pip_package")
        return False, f"Missing driver for {db_type}. Install it with: pip install {driver_pkg}", pd.DataFrame()
    except Exception as e:
        return False, f"Query failed: {e}", pd.DataFrame()

    if result_df.empty:
        return True, "No new rows found.", result_df

    # Rename their columns back to OUR standard schema
    reverse_mapping = {v: k for k, v in column_mapping.items()}
    result_df = result_df.rename(columns=reverse_mapping)
    result_df = result_df[REQUIRED_COLUMNS]

    return True, f"Fetched {len(result_df)} row(s).", result_df