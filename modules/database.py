from __future__ import annotations

from pathlib import Path
import csv
import hashlib
import sqlite3
from datetime import datetime, timezone
from typing import Any

CATEGORY_TABLES = {
    "vocab": "vocab",
    "aorist": "aorist",
    "participle": "participle",
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


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                pin_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('student', 'teacher', 'admin')),
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS vocab (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rank INTEGER NOT NULL,
                greek TEXT NOT NULL,
                meaning TEXT NOT NULL,
                hint TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS aorist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rank INTEGER NOT NULL,
                present TEXT NOT NULL,
                aorist TEXT NOT NULL,
                meaning TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS participle (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rank INTEGER NOT NULL,
                present TEXT NOT NULL,
                present_participle TEXT NOT NULL,
                aorist_participle TEXT NOT NULL,
                meaning TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS progress (
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                card_id INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('known', 'familiar', 'unknown')),
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, category, card_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )
    _migrate_users_role_if_needed(db_path)


def _migrate_users_role_if_needed(db_path: Path) -> None:
    """Allow the admin role in databases created by earlier alpha versions."""
    conn = sqlite3.connect(db_path)
    try:
        sql_row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()
        users_sql = (sql_row[0] or "") if sql_row else ""
        if "'admin'" in users_sql:
            return

        conn.execute("PRAGMA foreign_keys = OFF")
        conn.executescript(
            """
            BEGIN;
            ALTER TABLE progress RENAME TO progress_old;
            ALTER TABLE users RENAME TO users_old;

            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                pin_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('student', 'teacher', 'admin')),
                created_at TEXT NOT NULL
            );

            CREATE TABLE progress (
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                card_id INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('known', 'familiar', 'unknown')),
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, category, card_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            INSERT INTO users(id, name, pin_hash, role, created_at)
            SELECT id, name, pin_hash, role, created_at FROM users_old;

            INSERT INTO progress(user_id, category, card_id, status, updated_at)
            SELECT user_id, category, card_id, status, updated_at FROM progress_old;

            DROP TABLE progress_old;
            DROP TABLE users_old;
            COMMIT;
            """
        )
    finally:
        conn.close()


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
                "INSERT INTO users(name, pin_hash, role, created_at) VALUES (?, ?, ?, ?)",
                (name, hash_pin(pin), role, now_iso()),
            )
        return True, "Created."
    except sqlite3.IntegrityError:
        return False, "That name is already registered."


def authenticate(db_path: Path, name: str, pin: str) -> dict[str, Any] | None:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT id, name, role FROM users WHERE name = ? COLLATE NOCASE AND pin_hash = ?",
            (name.strip(), hash_pin(pin)),
        ).fetchone()
    return dict(row) if row else None


def list_users(db_path: Path) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, name, role, created_at FROM users ORDER BY role DESC, name"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_user(db_path: Path, user_id: int) -> bool:
    """Delete one user and their progress. Returns True when a row was deleted."""
    with connect(db_path) as conn:
        cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return cursor.rowcount > 0


def seed_if_empty(db_path: Path, data_dir: Path) -> None:
    for category, table in CATEGORY_TABLES.items():
        with connect(db_path) as conn:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
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
    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(columns)

    with connect(db_path) as conn:
        conn.execute("DELETE FROM progress WHERE category = ?", (category,))
        conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = ?", (table,))
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
        row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (card_id,)).fetchone()
    return dict(row) if row else None


def get_unseen_ids(db_path: Path, user_id: int, category: str, limit: int = 20) -> list[int]:
    table = CATEGORY_TABLES[category]
    with connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT c.id
            FROM {table} c
            LEFT JOIN progress p
              ON p.card_id = c.id
             AND p.category = ?
             AND p.user_id = ?
            WHERE p.card_id IS NULL
            ORDER BY c.rank, c.id
            LIMIT ?
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
            JOIN progress p
              ON p.card_id = c.id
             AND p.category = ?
             AND p.user_id = ?
            WHERE p.status = ?
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
            """
            INSERT INTO progress(user_id, category, card_id, status, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, category, card_id)
            DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at
            """,
            (user_id, category, card_id, status, now_iso()),
        )


def progress_counts(db_path: Path, user_id: int, category: str) -> dict[str, int]:
    result = {"known": 0, "familiar": 0, "unknown": 0, "unseen": 0}
    table = CATEGORY_TABLES[category]
    with connect(db_path) as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        rows = conn.execute(
            """
            SELECT status, COUNT(*) AS n
            FROM progress
            WHERE user_id = ? AND category = ?
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
            FROM progress p
            JOIN users u ON u.id = p.user_id
            JOIN {table} c ON c.id = p.card_id
            WHERE p.category = ?
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
        clauses.append("user_id = ?")
        params.append(user_id)
    if category is not None:
        clauses.append("category = ?")
        params.append(category)
    if status is not None:
        clauses.append("status = ?")
        params.append(status)

    sql = "DELETE FROM progress"
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
            JOIN progress p
              ON p.card_id = c.id
             AND p.category = ?
             AND p.user_id = ?
            WHERE p.status = ?
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
    """Return full card rows for teacher-side text extraction.

    When ``common_to_all_students`` is True, only cards assigned the selected
    status by every currently registered student are returned.
    """
    table = CATEGORY_TABLES[category]
    columns = EXPECTED_COLUMNS[category]
    select_columns = ", ".join(f"c.{col}" for col in columns)

    with connect(db_path) as conn:
        if common_to_all_students:
            student_count = conn.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'student'"
            ).fetchone()[0]
            if student_count == 0:
                return []

            rows = conn.execute(
                f"""
                SELECT {select_columns}
                FROM {table} c
                JOIN progress p
                  ON p.card_id = c.id
                 AND p.category = ?
                 AND p.status = ?
                JOIN users u
                  ON u.id = p.user_id
                 AND u.role = 'student'
                GROUP BY c.id
                HAVING COUNT(DISTINCT u.id) = ?
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
                JOIN progress p
                  ON p.card_id = c.id
                 AND p.category = ?
                 AND p.user_id = ?
                WHERE p.status = ?
                ORDER BY c.rank, c.id
                """,
                (category, user_id, status),
            ).fetchall()

    return [dict(row) for row in rows]
