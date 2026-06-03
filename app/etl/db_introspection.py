"""Lecture et profilage d'une source PostgreSQL (schéma + échantillon masqué RGPD)."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import asyncpg

from app.config import get_settings
from app.guardian.pii import mask_structure, scan_structure

FORBIDDEN_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|COPY)\b",
    re.IGNORECASE,
)


def _asyncpg_dsn(sqlalchemy_url: str) -> str:
    return sqlalchemy_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def resolve_source_dsn(node_data: dict[str, Any]) -> str:
    if node_data.get("connection_url"):
        return _asyncpg_dsn(str(node_data["connection_url"]))
    if node_data.get("use_app_database", True):
        return _asyncpg_dsn(get_settings().database_url)
    conn = node_data.get("connection") or {}
    user = conn.get("user", "datapipe")
    password = conn.get("password", "datapipe")
    host = conn.get("host", "localhost")
    port = conn.get("port", 5432)
    database = conn.get("database", "datapipe")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


async def introspect_table(
    node_data: dict[str, Any],
    *,
    sample_limit: int = 8,
) -> dict[str, Any]:
    schema = node_data.get("schema") or "public"
    table = node_data.get("table")
    if not table:
        return {"error": "Champ 'table' requis dans la configuration SOURCE", "connected": False}

    dsn = resolve_source_dsn(node_data)
    qualified = f'"{schema}"."{table}"' if schema != "public" else f'"{table}"'

    try:
        conn = await asyncpg.connect(dsn, timeout=15)
    except Exception as exc:
        return {"connected": False, "error": str(exc), "schema": schema, "table": table}

    try:
        cols = await conn.fetch(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            ORDER BY ordinal_position
            """,
            schema,
            table,
        )
        row_count = await conn.fetchval(f"SELECT COUNT(*)::bigint FROM {qualified}")
        sample_rows = await conn.fetch(
            f"SELECT * FROM {qualified} ORDER BY 1 LIMIT $1",
            sample_limit,
        )
    except Exception as exc:
        await conn.close()
        return {"connected": False, "error": str(exc), "schema": schema, "table": table}
    finally:
        if not conn.is_closed():
            await conn.close()

    columns = [
        {"name": r["column_name"], "type": r["data_type"], "nullable": r["is_nullable"] == "YES"}
        for r in cols
    ]
    samples = [dict(r) for r in sample_rows]
    for row in samples:
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()
            elif v is not None and not isinstance(v, (str, int, float, bool)):
                row[k] = str(v)

    masked_samples, pii_findings = mask_structure(samples)
    parsed = urlparse(dsn)
    return {
        "connected": True,
        "host": parsed.hostname,
        "database": parsed.path.lstrip("/"),
        "schema": schema,
        "table": table,
        "qualified_name": f"{schema}.{table}",
        "row_count": int(row_count or 0),
        "columns": columns,
        "sample_rows": masked_samples if isinstance(masked_samples, list) else samples,
        "sample_count": len(samples),
        "pii_in_samples": [f.to_dict() for f in scan_structure(samples)],
        "column_names": [c["name"] for c in columns],
    }


def assert_readonly_sql(sql: str) -> str:
    cleaned = sql.strip().rstrip(";")
    if FORBIDDEN_SQL.search(cleaned):
        raise ValueError("Seules les requêtes SELECT sont autorisées")
    if not re.match(r"^\s*SELECT\b", cleaned, re.IGNORECASE):
        raise ValueError("La requête doit commencer par SELECT")
    if ";" in cleaned:
        raise ValueError("Une seule requête SELECT autorisée")
    return cleaned


async def execute_readonly_query(node_data: dict[str, Any], sql: str, *, limit: int = 50) -> dict[str, Any]:
    safe_sql = assert_readonly_sql(sql)
    if "LIMIT" not in safe_sql.upper():
        safe_sql = f"{safe_sql} LIMIT {limit}"

    dsn = resolve_source_dsn(node_data)
    conn = await asyncpg.connect(dsn, timeout=30)
    try:
        rows = await conn.fetch(safe_sql)
    finally:
        await conn.close()

    result = []
    for r in rows:
        row = dict(r)
        for k, v in row.items():
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()
            elif v is not None and not isinstance(v, (str, int, float, bool)):
                row[k] = str(v)
        result.append(row)

    masked, _ = mask_structure(result)
    return {
        "sql": safe_sql,
        "row_count": len(result),
        "rows": masked if isinstance(masked, list) else result,
    }
