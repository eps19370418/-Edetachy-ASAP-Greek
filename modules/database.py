from __future__ import annotations

from pathlib import Path
import csv
import hashlib
from datetime import datetime, timezone
from typing import Any

import psycopg2
import psycopg2.extras
import streamlit as st

USERS_TABLE = "greek_users"
PROGRESS_TABLE = "greek_progress"

CATEGORY_TABLES = {
    "vocab": "greek_vocab",
    "aorist": "greek_aorist",
    "participle": "greek_participle",
}

EXPECTED_COLUMNS = {
    "vocab": ["rank", "greek", "meaning", "hint"],
    "aorist": ["rank", "present", "aorist", "meaning"],
    "participle": [
        "rank",
        "present",
        "present_participle",
        "aorist_participle",
        "meaning",
    ],
}


class _ConnWrapper:
    """Thin wrapper so psycopg2 connections support the same
    conn.execute(...) shorthand that sqlite3.Connection provides."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params or ())
        return cur

    def executemany(self, sql, seq_of_params):
        cur = self._conn.cursor()
        cur.executemany(sql, seq_of_params)
        return cur

    def executescript(self, sql):
        cur = self._conn.cursor()
        cur.execute(sql)
        return cur

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        self._conn.close()
        return False


def connect(db_path: Path | None = None) -> _ConnWrapper:
    cfg = st.secrets["postgres"]
    conn = psycopg2.connect(
        host=cfg["host"],
        port=cfg["port"],
        dbname=cfg["database"],
        user=cfg["user"],
        password=cfg["password"],
        sslmode="require",
    )
    return _ConnWrapper(conn)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def init_db(db_path: Path | None = None) -> None:
    with connect(db_path) as conn:
        conn.executescript(
            f"""
            CREATE TABLE IF NOT EXISTS {USERS_TABLE} (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                pin_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('student', 'teacher', 'admin')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );

            CREATE TABLE IF NOT EXISTS greek_vocab (
                id SERIAL PRIMARY KEY,
                rank INTEGER NOT NULL,
                greek TEXT NOT NULL,
                meaning TEXT NOT NULL,
                hint TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS greek_aorist (
                id SERIAL PRIMARY KEY,
                rank INTEGER NOT NULL,
                present TEXT NOT NULL,
                aorist TEXT NOT NULL,
                meaning TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS greek_participle (
                id SERIAL PRIMARY KEY,
                rank INTEGER NOT NULL,
                present TEXT NOT NULL,
                present_participle TEXT NOT NULL,
                aorist_participle TEXT NOT NULL,
                meaning TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS {PROGRESS_TABLE} (
                user_id INTEGER NOT NULL REFERENCES {USERS_TABLE}(id) ON DELETE CASCADE,
                category TEXT NOT NULL,
                card_id INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('known', 'familiar', 'unknown')),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (user_id, category, card_id)
            );

            CREATE UNIQUE INDEX IF NOT EXISTS greek_users_name_lower_idx
            ON {USERS_TABLE} (LOWER(name));
            """
        )


def create_user(db_path: Path, name: str, pin: str, role: str) -> tuple[bool, str]:
    name = name.strip()
    if not name:
        return False, "Name is required."
    if not (pin.isdigit() and len(pin) == 4):
        return False, "PIN must contain exactly four digits."
    if role not in {"student", "teacher", "admin"}:
        return False, "Invalid role."

    try:
        with connect(db_path) as conn:
            conn.execute(
                f"INSERT INTO {USERS_TABLE}(name, pin_hash, role, created_at) VALUES (%s, %s, %s, %s)",
                (name, hash_pin(pin), role, now_iso()),
            )
        return True, "Created."
    except psycopg2.IntegrityError:
        return False, "That name is already registered."


def authenticate(db_path: Path, name: str, pin: str) -> dict[str, Any] | None:
    with connect(db_path) as conn:
        row = conn.execute(
            f"SELECT id, name, role FROM {USERS_TABLE} WHERE LOWER(name) = LOWER(%s) AND pin_hash = %s",
            (name.strip(), hash_pin(pin)),
        ).fetchone()
    return dict(row) if row else None


def list_users(db_path: Path) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT id, name, role, created_at FROM {USERS_TABLE} ORDER BY role DESC, name"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_user(db_path: Path, user_id: int) -> bool:
    with connect(db_path) as conn:
        cursor = conn.execute(f"DELETE FROM {USERS_TABLE} WHERE id = %s", (user_id,))
    return cursor.rowcount > 0


def seed_if_empty(db_path: Path, data_dir: Path) -> None:
    for category, table in CATEGORY_TABLES.items():
        with connect(db_path) as conn:
            count = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
        if count == 0:
            csv_path = data_dir / f"{category}.csv"
            if csv_path.exists():
                rows = read_csv_rows(csv_path, category)
                replace_cards(db_path, category, rows)


def read_csv_rows(path_or_file: Any, category: str) -> list[dict[str, str]]:
    if hasattr(path_or_file, "getvalue"):
        text = path_or_file.getvalue().decode("utf-8-sig")
        lines = text.splitlines()
    else:
        with open(path_or_file, "r", encoding="utf-8-sig", newline="") as f:
            lines = f.read().splitlines()

    reader = csv.DictReader(lines)
    expected = EXPECTED_COLUMNS[category]
    actual = reader.fieldnames or []
    missing = [c for c in expected if c not in actual]
    if missing:
        raise ValueError(f"Missing columns: {', '.join(missing)}")

    rows: list[dict[str, str]] = []
    for index, row in enumerate(reader, start=1):
        cleaned = {key: (row.get(key) or "").strip() for key in expected}
        cleaned["rank"] = cleaned["rank"] or str(index)
        if category == "vocab" and not cleaned["greek"]:
            continue
        if category in {"aorist", "participle"} and not cleaned["present"]:
            continue
        rows.append(cleaned)
    return rows


def replace_cards(db_path: Path, category: str, rows: list[dict[str, str]]) -> None:
    table = CATEGORY_TABLES[category]
    columns = EXPECTED_COLUMNS[category]
    placeholders = ", ".join("%s" for _ in columns)
    column_sql = ", ".join(columns)

    with connect(db_path) as conn:
        conn.execute(f"DELETE FROM {PROGRESS_TABLE} WHERE category = %s", (category,))
        conn.execute(f"DELETE FROM {table}")
        conn.executemany(
            f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})",
            [
                tuple(int(row["rank"]) if col == "rank" else row[col] for col in columns)
                for row in rows
            ],
        )


def get_cards(db_path: Path, category: str) -> list[dict[str, Any]]:
    table = CATEGORY_TABLES[category]
    with connect(db_path) as conn:
        rows = conn.execute(f"SELECT * FROM {table} ORDER BY rank, id").fetchall()
    return [dict(r) for r in rows]


def get_card(db_path: Path, category: str, card_id: int) -> dict[str, Any] | None:
    table = CATEGORY_TABLES[category]
    with connect(db_path) as conn:
        row = conn.execute(f"SELECT * FROM {table} WHERE id = %s", (card_id,)).fetchone()
    return dict(row) if row else None


def get_unseen_ids(db_path: Path, user_id: int, category: str, limit: int = 20) -> list[int]:
    table = CATEGORY_TABLES[category]
    with connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT c.id
            FROM {table} c
            LEFT JOIN {PROGRESS_TABLE} p
              ON p.card_id = c.id
             AND p.category = %s
             AND p.user_id = %s
            WHERE p.card_id IS NULL
            ORDER BY c.rank, c.id
            LIMIT %s
            """,
            (category, user_id, limit),
        ).fetchall()
    return [int(r["id"]) for r in rows]


def get_ids_by_status(
    db_path: Path, user_id: int, category: str, status: str
) -> list[int]:
    table = CATEGORY_TABLES[category]
    with connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT c.id
            FROM {table} c
            JOIN {PROGRESS_TABLE} p
              ON p.card_id = c.id
             AND p.category = %s
             AND p.user_id = %s
            WHERE p.status = %s
            ORDER BY c.rank, c.id
            """,
            (category, user_id, status),
        ).fetchall()
    return [int(r["id"]) for r in rows]


def save_progress(
    db_path: Path, user_id: int, category: str, card_id: int, status: str
) -> None:
    with connect(db_path) as conn:
        conn.execute(
            f"""
            INSERT INTO {PROGRESS_TABLE}(user_id, category, card_id, status, updated_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT(user_id, category, card_id)
            DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at
            """,
            (user_id, category, card_id, status, now_iso()),
        )


def progress_counts(db_path: Path, user_id: int, category: str) -> dict[str, int]:
    result = {"known": 0, "familiar": 0, "unknown": 0, "unseen": 0}
    table = CATEGORY_TABLES[category]
    with connect(db_path) as conn:
        total = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
        rows = conn.execute(
            f"""
            SELECT status, COUNT(*) AS n
            FROM {PROGRESS_TABLE}
            WHERE user_id = %s AND category = %s
            GROUP BY status
            """,
            (user_id, category),
        ).fetchall()
    seen_total = 0
    for row in rows:
        result[row["status"]] = row["n"]
        seen_total += row["n"]
    result["unseen"] = total - seen_total
    return result


def user_progress_rows(db_path: Path, category: str) -> list[dict[str, Any]]:
    table = CATEGORY_TABLES[category]
    display_col = "greek" if category == "vocab" else "present"
    with connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT c.rank, c.{display_col} AS card, u.name, p.status, p.updated_at
            FROM {PROGRESS_TABLE} p
            JOIN {USERS_TABLE} u ON u.id = p.user_id
            JOIN {table} c ON c.id = p.card_id
            WHERE p.category = %s
            ORDER BY c.rank, u.name
            """,
            (category,),
        ).fetchall()
    return [dict(r) for r in rows]


def reset_progress(
    db_path: Path,
    user_id: int | None = None,
    category: str | None = None,
    status: str | None = None,
) -> None:
    clauses = []
    params: list[Any] = []
    if user_id is not None:
        clauses.append("user_id = %s")
        params.append(user_id)
    if category is not None:
        clauses.append("category = %s")
        params.append(category)
    if status is not None:
        clauses.append("status = %s")
        params.append(status)

    sql = f"DELETE FROM {PROGRESS_TABLE}"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    with connect(db_path) as conn:
        conn.execute(sql, params)


def cards_for_export(
    db_path: Path,
    user_id: int,
    category: str,
    status: str | None = None,
) -> list[dict[str, Any]]:
    table = CATEGORY_TABLES[category]
    if status is None:
        return get_cards(db_path, category)

    with connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT c.*
            FROM {table} c
            JOIN {PROGRESS_TABLE} p
              ON p.card_id = c.id
             AND p.category = %s
             AND p.user_id = %s
            WHERE p.status = %s
            ORDER BY c.rank, c.id
            """,
            (category, user_id, status),
        ).fetchall()
    return [dict(r) for r in rows]


def progress_text_rows(
    db_path: Path,
    category: str,
    status: str,
    user_id: int | None = None,
    common_to_all_students: bool = False,
) -> list[dict[str, Any]]:
    table = CATEGORY_TABLES[category]
    columns = EXPECTED_COLUMNS[category]
    select_columns = ", ".join(f"c.{col}" for col in columns)

    with connect(db_path) as conn:
        if common_to_all_students:
            student_count = conn.execute(
                f"SELECT COUNT(*) AS n FROM {USERS_TABLE} WHERE role = 'student'"
            ).fetchone()["n"]
            if student_count == 0:
                return []

            rows = conn.execute(
                f"""
                SELECT {select_columns}
                FROM {table} c
                JOIN {PROGRESS_TABLE} p
                  ON p.card_id = c.id
                 AND p.category = %s
                 AND p.status = %s
                JOIN {USERS_TABLE} u
                  ON u.id = p.user_id
                 AND u.role = 'student'
                GROUP BY c.id, {select_columns}
                HAVING COUNT(DISTINCT u.id) = %s
                ORDER BY c.rank, c.id
                """,
                (category, status, student_count),
            ).fetchall()
        else:
            if user_id is None:
                return []
            rows = conn.execute(
                f"""
                SELECT {select_columns}
                FROM {table} c
                JOIN {PROGRESS_TABLE} p
                  ON p.card_id = c.id
                 AND p.category = %s
                 AND p.user_id = %s
                WHERE p.status = %s
                ORDER BY c.rank, c.id
                """,
                (category, user_id, status),
            ).fetchall()

    return [dict(row) for row in rows]

