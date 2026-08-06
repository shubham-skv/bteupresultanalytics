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
            institute TEXT,
            UNIQUE(enrollment)
        );
        
        -- Migration for existing databases
        BEGIN;
        PRAGMA user_version;
        COMMIT;
        """)
        
        # Add institute column if missing
        try:
            conn.execute("SELECT institute FROM students LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE students ADD COLUMN institute TEXT")
            
        conn.executescript("""
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
            INSERT INTO students (enrollment, name, father_name, dob, branch, semester, rollno, source_file, institute)
            VALUES (:enrollment, :name, :father_name, :dob, :branch, :semester, :rollno, :source_file, :institute)
            ON CONFLICT(enrollment) DO UPDATE SET
                name=excluded.name,
                father_name=excluded.father_name,
                dob=excluded.dob,
                branch=excluded.branch,
                semester=excluded.semester,
                rollno=excluded.rollno,
                source_file=excluded.source_file,
                institute=excluded.institute
        """, students)
    return len(students)


def get_all_students(institute: str = None) -> pd.DataFrame:
    with get_conn() as conn:
        if institute:
            return pd.read_sql("SELECT * FROM students WHERE institute=? ORDER BY branch, semester, name", conn, params=(institute,))
        return pd.read_sql("SELECT * FROM students ORDER BY branch, semester, name", conn)


def get_institutes() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT DISTINCT institute FROM students WHERE institute IS NOT NULL ORDER BY institute").fetchall()
        return [r[0] for r in rows if r[0]]


def get_branches(institute: str = None) -> list[str]:
    with get_conn() as conn:
        if institute:
            rows = conn.execute("SELECT DISTINCT branch FROM students WHERE institute=? ORDER BY branch", (institute,)).fetchall()
        else:
            rows = conn.execute("SELECT DISTINCT branch FROM students ORDER BY branch").fetchall()
        return [r[0] for r in rows if r[0]]


def get_semesters_for_branch(branch: str, institute: str = None) -> list[str]:
    with get_conn() as conn:
        if institute:
            rows = conn.execute(
                "SELECT DISTINCT semester FROM students WHERE branch=? AND institute=? ORDER BY semester", (branch, institute)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT DISTINCT semester FROM students WHERE branch=? ORDER BY semester", (branch,)
            ).fetchall()
        return [r[0] for r in rows if r[0]]


def get_students_for_branch(branch: str, semester: str = None, institute: str = None) -> pd.DataFrame:
    with get_conn() as conn:
        query = "SELECT * FROM students WHERE branch=?"
        params = [branch]
        
        if semester:
            query += " AND semester=?"
            params.append(semester)
        if institute:
            query += " AND institute=?"
            params.append(institute)
            
        query += " ORDER BY semester, name"
        return pd.read_sql(query, conn, params=params)


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


def get_all_results(institute: str = None) -> pd.DataFrame:
    with get_conn() as conn:
        if institute:
            # We join with students table to filter results by the student's nominal roll institute
            query = """
                SELECT r.* FROM results r
                JOIN students s ON r.enrollment = s.enrollment
                WHERE s.institute = ?
            """
            return pd.read_sql(query, conn, params=(institute,))
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


def get_student_count(institute: str = None) -> int:
    with get_conn() as conn:
        if institute:
            return conn.execute("SELECT COUNT(DISTINCT enrollment) FROM students WHERE institute=?", (institute,)).fetchone()[0]
        return conn.execute("SELECT COUNT(DISTINCT enrollment) FROM students").fetchone()[0]


def get_result_count(institute: str = None) -> int:
    with get_conn() as conn:
        if institute:
            return conn.execute("""
                SELECT COUNT(DISTINCT r.enrollment) FROM results r
                JOIN students s ON r.enrollment = s.enrollment
                WHERE s.institute = ?
            """, (institute,)).fetchone()[0]
        return conn.execute("SELECT COUNT(DISTINCT enrollment) FROM results").fetchone()[0]


# Initialise on import
init_db()
