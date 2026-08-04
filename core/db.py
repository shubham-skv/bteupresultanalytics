"""
core/db.py  —  SQLite persistence layer for BTEUP Analytics Suite
"""
import sqlite3
import os
import pandas as pd
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bteup_data.db")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist."""
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment TEXT NOT NULL,
            name TEXT,
            father_name TEXT,
            dob TEXT,
            branch TEXT,
            semester TEXT,
            rollno TEXT,
            source_file TEXT,
            UNIQUE(enrollment)
        );

        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment TEXT NOT NULL,
            dob TEXT,
            institute TEXT,
            student_name TEXT,
            father_name TEXT,
            branch TEXT,
            roll_nos TEXT,
            grand_total TEXT,
            paper_code TEXT,
            paper_name TEXT,
            max_marks TEXT,
            min_marks TEXT,
            marks_obtained TEXT,
            fetched_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_results_enrollment ON results(enrollment);
        CREATE INDEX IF NOT EXISTS idx_results_branch ON results(branch);
        CREATE INDEX IF NOT EXISTS idx_results_paper ON results(paper_name);
        """)


def upsert_students(students: list[dict]):
    """Insert or replace student records."""
    with get_conn() as conn:
        conn.executemany("""
            INSERT INTO students (enrollment, name, father_name, dob, branch, semester, rollno, source_file)
            VALUES (:enrollment, :name, :father_name, :dob, :branch, :semester, :rollno, :source_file)
            ON CONFLICT(enrollment) DO UPDATE SET
                name=excluded.name,
                father_name=excluded.father_name,
                dob=excluded.dob,
                branch=excluded.branch,
                semester=excluded.semester,
                rollno=excluded.rollno,
                source_file=excluded.source_file
        """, students)
    return len(students)


def get_all_students() -> pd.DataFrame:
    with get_conn() as conn:
        return pd.read_sql("SELECT * FROM students ORDER BY branch, semester, name", conn)


def get_branches() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT DISTINCT branch FROM students ORDER BY branch").fetchall()
        return [r[0] for r in rows if r[0]]


def get_semesters_for_branch(branch: str) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT semester FROM students WHERE branch=? ORDER BY semester", (branch,)
        ).fetchall()
        return [r[0] for r in rows if r[0]]


def get_students_for_branch(branch: str, semester: str = None) -> pd.DataFrame:
    with get_conn() as conn:
        if semester:
            return pd.read_sql(
                "SELECT * FROM students WHERE branch=? AND semester=? ORDER BY name",
                conn, params=(branch, semester)
            )
        return pd.read_sql(
            "SELECT * FROM students WHERE branch=? ORDER BY semester, name",
            conn, params=(branch,)
        )


def get_already_fetched_enrollments() -> set:
    with get_conn() as conn:
        rows = conn.execute("SELECT DISTINCT enrollment FROM results").fetchall()
        return {r[0] for r in rows}


def insert_results(rows: list[dict]):
    """Insert result rows (subject-level rows). Delete existing first to avoid dups."""
    if not rows:
        return
    enrollments = list({r['enrollment'] for r in rows})
    with get_conn() as conn:
        # Remove old records for these enrollments first
        placeholders = ",".join("?" * len(enrollments))
        conn.execute(f"DELETE FROM results WHERE enrollment IN ({placeholders})", enrollments)
        conn.executemany("""
            INSERT INTO results
                (enrollment, dob, institute, student_name, father_name, branch, roll_nos,
                 grand_total, paper_code, paper_name, max_marks, min_marks, marks_obtained)
            VALUES
                (:enrollment, :dob, :institute, :student_name, :father_name, :branch, :roll_nos,
                 :grand_total, :paper_code, :paper_name, :max_marks, :min_marks, :marks_obtained)
        """, rows)


def get_all_results() -> pd.DataFrame:
    with get_conn() as conn:
        return pd.read_sql("SELECT * FROM results", conn)


def get_results_for_branch(branch: str) -> pd.DataFrame:
    with get_conn() as conn:
        return pd.read_sql(
            "SELECT * FROM results WHERE branch=? ORDER BY student_name", conn, params=(branch,)
        )


def clear_students():
    with get_conn() as conn:
        conn.execute("DELETE FROM students")


def clear_results():
    with get_conn() as conn:
        conn.execute("DELETE FROM results")


def get_student_count() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(DISTINCT enrollment) FROM students").fetchone()[0]


def get_result_count() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(DISTINCT enrollment) FROM results").fetchone()[0]


# Initialise on import
init_db()
