"""
Migrate MySQL schema + data into Supabase Postgres (no Docker required).

This script:
- Connects to MySQL (source) and Supabase Postgres (target)
- Creates tables in Postgres with best-effort type mapping
- Copies all rows table-by-table

Notes:
- Foreign keys and indexes are not migrated in this first pass.
- Column defaults are applied only when easy/safe to map.
"""

from __future__ import annotations

import os
import re
import sys
import socket
from urllib.parse import urlparse, unquote, parse_qs
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import mysql.connector
from dotenv import load_dotenv
import psycopg2
import psycopg2.extras
from psycopg2.extensions import connection as PgConn


load_dotenv()


@dataclass(frozen=True)
class MysqlConfig:
    host: str
    port: int
    user: str
    password: str
    database: str


def env(name: str, default: Optional[str] = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def get_mysql_config() -> MysqlConfig:
    return MysqlConfig(
        host=env("DB_HOST", "localhost"),
        port=int(env("DB_PORT", "3306")),
        user=env("DB_USER", "root"),
        password=env("DB_PASSWORD", env("DB_PASS", "")),
        database=env("DB_NAME", "krushibandhu_ai"),
    )


def get_pg_dsn() -> str:
    dsn = os.getenv("SUPABASE_DB_URL")
    if not dsn:
        raise RuntimeError("Missing SUPABASE_DB_URL in environment (.env)")
    return dsn


def connect_postgres_preferring_ipv4(dsn: str) -> PgConn:
    """
    Supabase DB host sometimes resolves to IPv6-only on some ISPs/DNS resolvers.
    psycopg2 may fail if the system has no IPv6 route. This helper resolves the
    hostname and prefers an IPv4 address when available.
    """
    parsed = urlparse(dsn)
    host = parsed.hostname
    if not host:
        return psycopg2.connect(dsn)

    # Resolve and prefer IPv4
    ipv4: Optional[str] = None
    ipv6: Optional[str] = None
    try:
        for family, _socktype, _proto, _canonname, sockaddr in socket.getaddrinfo(host, parsed.port or 5432):
            if family == socket.AF_INET and not ipv4:
                ipv4 = sockaddr[0]
            if family == socket.AF_INET6 and not ipv6:
                ipv6 = sockaddr[0]
    except Exception:
        # If system resolver is broken, allow manual override
        override = os.getenv("SUPABASE_DB_HOSTADDR")
        if override:
            ipv6 = override
        else:
            return psycopg2.connect(dsn)

    # Build kwargs instead of relying on URI host resolution
    user = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    dbname = (parsed.path or "/postgres").lstrip("/") or "postgres"
    port = parsed.port or 5432
    sslmode = parse_qs(parsed.query).get("sslmode", ["require"])[0]

    target_host = ipv4 or ipv6 or host
    return psycopg2.connect(
        user=user,
        password=password,
        dbname=dbname,
        host=target_host,
        port=port,
        sslmode=sslmode,
    )


def mysql_to_pg_type(mysql_type: str, char_len: Optional[int], num_prec: Optional[int], num_scale: Optional[int]) -> str:
    t = mysql_type.lower()
    if t in ("varchar", "char"):
        if char_len and char_len > 0:
            return f"varchar({char_len})"
        return "text"
    if t in ("text", "tinytext", "mediumtext", "longtext"):
        return "text"
    if t in ("int", "integer", "mediumint"):
        return "integer"
    if t == "bigint":
        return "bigint"
    if t == "smallint":
        return "smallint"
    if t == "tinyint":
        return "smallint"
    if t in ("decimal", "numeric"):
        if num_prec and num_scale is not None:
            return f"numeric({num_prec},{num_scale})"
        return "numeric"
    if t in ("float",):
        return "real"
    if t in ("double", "double precision"):
        return "double precision"
    if t in ("datetime",):
        return "timestamp"
    if t in ("timestamp",):
        return "timestamp"
    if t in ("date",):
        return "date"
    if t in ("time",):
        return "time"
    if t in ("json",):
        return "jsonb"
    if t in ("blob", "tinyblob", "mediumblob", "longblob", "binary", "varbinary"):
        return "bytea"
    if t in ("enum", "set"):
        return "text"
    if t in ("bit", "boolean", "bool"):
        return "boolean"
    # fallback
    return "text"


def sanitize_ident(name: str) -> str:
    # Keep as-is but quote; ensure no NUL.
    return name.replace("\x00", "")


def quote_ident(name: str) -> str:
    return '"' + sanitize_ident(name).replace('"', '""') + '"'


def quote_mysql_ident(name: str) -> str:
    return "`" + sanitize_ident(name).replace("`", "``") + "`"


def get_mysql_tables(cur) -> List[str]:
    cur.execute("SHOW TABLES")
    return [r[0] for r in cur.fetchall()]


def get_mysql_columns(cur, table: str) -> List[Dict[str, Any]]:
    cur.execute(
        """
        SELECT
          COLUMN_NAME,
          DATA_TYPE,
          CHARACTER_MAXIMUM_LENGTH,
          NUMERIC_PRECISION,
          NUMERIC_SCALE,
          IS_NULLABLE,
          COLUMN_DEFAULT,
          EXTRA
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        ORDER BY ORDINAL_POSITION
        """,
        (env("DB_NAME", "krushibandhu_ai"), table),
    )
    cols = []
    for row in cur.fetchall():
        cols.append(
            {
                "name": row[0],
                "data_type": row[1],
                "char_len": row[2],
                "num_prec": row[3],
                "num_scale": row[4],
                "is_nullable": row[5] == "YES",
                "default": row[6],
                "extra": row[7] or "",
            }
        )
    return cols


def get_mysql_primary_key(cur, table: str) -> List[str]:
    cur.execute(
        """
        SELECT k.COLUMN_NAME
        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS t
        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE k
          ON t.CONSTRAINT_NAME = k.CONSTRAINT_NAME
         AND t.TABLE_SCHEMA = k.TABLE_SCHEMA
         AND t.TABLE_NAME = k.TABLE_NAME
        WHERE t.TABLE_SCHEMA = %s
          AND t.TABLE_NAME = %s
          AND t.CONSTRAINT_TYPE = 'PRIMARY KEY'
        ORDER BY k.ORDINAL_POSITION
        """,
        (env("DB_NAME", "krushibandhu_ai"), table),
    )
    return [r[0] for r in cur.fetchall()]


def pg_table_exists(pg_cur, table: str) -> bool:
    pg_cur.execute(
        """
        SELECT EXISTS(
          SELECT 1
          FROM information_schema.tables
          WHERE table_schema='public' AND table_name=%s
        )
        """,
        (table,),
    )
    return bool(pg_cur.fetchone()[0])


def normalize_default(default: Any) -> Optional[str]:
    if default is None:
        return None
    if isinstance(default, (int, float)):
        return str(default)
    s = str(default).strip()
    if s.upper() in ("CURRENT_TIMESTAMP", "NOW()"):
        return "CURRENT_TIMESTAMP"
    if s in ("0", "1"):
        return s
    # strip surrounding quotes if present
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        s = s[1:-1]
    # escape single quotes for SQL literal
    s = s.replace("'", "''")
    return f"'{s}'"


def create_pg_table(pg_cur, table: str, columns: List[Dict[str, Any]], pk: List[str]) -> None:
    col_sql: List[str] = []
    for col in columns:
        col_name = quote_ident(col["name"])
        pg_type = mysql_to_pg_type(col["data_type"], col["char_len"], col["num_prec"], col["num_scale"])
        nullable = "" if col["is_nullable"] else " NOT NULL"

        # Handle auto_increment: create identity
        extra = col["extra"].lower()
        if "auto_increment" in extra and pg_type in ("integer", "bigint"):
            pg_type = f"{pg_type} GENERATED BY DEFAULT AS IDENTITY"
            default_sql = ""
        else:
            d = normalize_default(col["default"])
            default_sql = f" DEFAULT {d}" if d is not None else ""

        col_sql.append(f"{col_name} {pg_type}{default_sql}{nullable}")

    pk_sql = f", PRIMARY KEY ({', '.join(quote_ident(c) for c in pk)})" if pk else ""
    sql = f"CREATE TABLE IF NOT EXISTS {quote_ident(table)} (\n  " + ",\n  ".join(col_sql) + pk_sql + "\n);"
    pg_cur.execute(sql)


def fetch_mysql_rows(cur, table: str) -> Tuple[List[str], List[Tuple[Any, ...]]]:
    cur.execute(f"SELECT * FROM {quote_mysql_ident(table)}")
    rows = cur.fetchall()
    col_names = [d[0] for d in cur.description]
    return col_names, rows


def truncate_pg_table(pg_cur, table: str) -> None:
    pg_cur.execute(f"TRUNCATE TABLE {quote_ident(table)};")


def insert_pg_rows(pg_cur, table: str, col_names: List[str], rows: List[Tuple[Any, ...]]) -> None:
    if not rows:
        return
    cols_sql = ", ".join(quote_ident(c) for c in col_names)
    placeholders = ", ".join(["%s"] * len(col_names))
    sql = f"INSERT INTO {quote_ident(table)} ({cols_sql}) VALUES ({placeholders})"
    psycopg2.extras.execute_batch(pg_cur, sql, rows, page_size=1000)


def main() -> int:
    mysql_cfg = get_mysql_config()
    pg_dsn = get_pg_dsn()

    print("Connecting to MySQL...")
    mysql_conn = mysql.connector.connect(
        host=mysql_cfg.host,
        port=mysql_cfg.port,
        user=mysql_cfg.user,
        password=mysql_cfg.password,
        database=mysql_cfg.database,
    )
    mysql_cur = mysql_conn.cursor()

    print("Connecting to Supabase Postgres...")
    pg_conn: PgConn = connect_postgres_preferring_ipv4(pg_dsn)
    pg_conn.autocommit = False
    pg_cur = pg_conn.cursor()

    try:
        tables = get_mysql_tables(mysql_cur)
        print(f"Found {len(tables)} MySQL tables.")

        # Create schema
        for table in tables:
            cols = get_mysql_columns(mysql_cur, table)
            pk = get_mysql_primary_key(mysql_cur, table)
            if not pg_table_exists(pg_cur, table):
                print(f"Creating table {table}...")
            create_pg_table(pg_cur, table, cols, pk)
        pg_conn.commit()

        # Copy data
        for table in tables:
            print(f"Migrating data for {table}...")
            col_names, rows = fetch_mysql_rows(mysql_cur, table)
            truncate_pg_table(pg_cur, table)
            # Insert in chunks to avoid huge batches
            chunk = 5000
            for i in range(0, len(rows), chunk):
                part = rows[i : i + chunk]
                # convert MySQL bytes/bytearray to memoryview-friendly bytes
                part2 = []
                for r in part:
                    rr = []
                    for v in r:
                        if isinstance(v, (bytearray, bytes)):
                            rr.append(bytes(v))
                        else:
                            rr.append(v)
                    part2.append(tuple(rr))
                psycopg2.extras.execute_batch(
                    pg_cur,
                    f"INSERT INTO {quote_ident(table)} ({', '.join(quote_ident(c) for c in col_names)}) VALUES ({', '.join(['%s']*len(col_names))})",
                    part2,
                    page_size=1000,
                )
            pg_conn.commit()

        print("Migration complete.")
        return 0
    except Exception as e:
        pg_conn.rollback()
        print(f"Migration failed: {e}")
        return 1
    finally:
        try:
            mysql_cur.close()
            mysql_conn.close()
        except Exception:
            pass
        try:
            pg_cur.close()
            pg_conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())

