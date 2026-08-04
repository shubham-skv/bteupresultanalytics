"""
core/fetcher.py  —  BTEUP result scraper
Uses requests + BeautifulSoup (same approach as getMarks.py — fast, no browser needed).
"""
import base64
import re
import time
import urllib3
import requests
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://result.bteexam.com/even/main/oddresult.aspx"
SESSION = requests.Session()
SESSION.verify = False
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})


def _b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


def _clean(s: str) -> str:
    return s.replace('\r', '').replace('\n', ' ').replace('\xa0', ' ').strip()


def _extract_result(enrollment: str, html: str, dob: str) -> list[dict]:
    """
    Parse BTEUP result HTML into a list of subject-level rows.
    Each row contains: enrollment, dob, institute, student_name, father_name,
                       branch, roll_nos, grand_total, paper_code, paper_name,
                       max_marks, min_marks, marks_obtained
    """
    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.find_all('table')

    if len(tables) < 4:
        return []

    # ── Table 0: General Info ───────────────────────────────────────────────
    general = {}
    t0_rows = tables[0].find_all('tr')

    # Institute (row 4, index 4)
    if len(t0_rows) >= 5:
        cells = t0_rows[4].find_all(['th', 'td'])
        if len(cells) >= 2:
            general["institute"] = _clean(cells[1].get_text())

    # Branch (row 5)
    if len(t0_rows) >= 6:
        cells = t0_rows[5].find_all(['th', 'td'])
        if len(cells) >= 2:
            general["branch"] = _clean(cells[1].get_text())

    # Student + Father Name (row 6)
    if len(t0_rows) >= 7:
        cells = t0_rows[6].find_all(['th', 'td'])
        if len(cells) >= 2:
            info_text = _clean(cells[1].get_text())
            s_match = re.search(r'^(.*?)(?=\s*Father Name\s*:)', info_text)
            f_match = re.search(r'Father Name\s*:\s*(.+)', info_text)
            general["student_name"] = s_match.group(1).strip() if s_match else ""
            general["father_name"] = f_match.group(1).strip() if f_match else ""

    # Roll Numbers (row 8)
    roll_parts = []
    if len(t0_rows) >= 9:
        cells = t0_rows[8].find_all(['th', 'td'])
        for cell in cells:
            text = _clean(cell.get_text())
            matches = re.findall(r'semester\s*:\s*\d+\s*--\s*roll No\s*(\d+)', text, re.IGNORECASE)
            roll_parts.extend(matches)
            # Fallback: grab last 13 chars which often hold roll no
            if text and not matches:
                roll_parts.append(text[-13:])
    general["roll_nos"] = " | ".join(dict.fromkeys(roll_parts))

    # ── Table 3: Grand Total row ────────────────────────────────────────────
    t3_rows = tables[3].find_all('tr')
    grand_total = ""
    if t3_rows:
        last_row_text = _clean(t3_rows[-1].find_all('td')[0].get_text()) if t3_rows[-1].find_all('td') else ""
        last_row_text = re.sub(r'\s+', ' ', last_row_text).replace('Â', '').strip()
        grand_total = re.sub(r'Grand Total : | Result', '', last_row_text).strip()
    general["grand_total"] = grand_total

    # ── Tables 4 & 5: Subject-level marks ──────────────────────────────────
    result_rows = []
    for table_idx in [4, 5]:
        if table_idx >= len(tables):
            continue
        rows = tables[table_idx].find_all('tr')
        for row_idx, row in enumerate(rows):
            if row_idx < 2:
                continue  # skip header rows
            cells = row.find_all('td')
            if not cells:
                continue
            cell_texts = [_clean(c.get_text()) for c in cells]
            if len(cell_texts) < 4:
                continue

            result_rows.append({
                "enrollment": enrollment,
                "dob": dob,
                "institute": general.get("institute", ""),
                "student_name": general.get("student_name", ""),
                "father_name": general.get("father_name", ""),
                "branch": general.get("branch", ""),
                "roll_nos": general.get("roll_nos", ""),
                "grand_total": grand_total,
                "paper_code": cell_texts[0] if len(cell_texts) > 0 else "",
                "paper_name": cell_texts[1] if len(cell_texts) > 1 else "",
                "max_marks": cell_texts[2] if len(cell_texts) > 2 else "",
                "min_marks": cell_texts[3] if len(cell_texts) > 3 else "",
                "marks_obtained": cell_texts[4] if len(cell_texts) > 4 else "",
            })

    return result_rows


def fetch_student_result(enrollment: str, dob: str, retry: int = 2) -> tuple[list[dict], str]:
    """
    Fetch result for a single student.
    Returns (rows, status) where status is 'ok', 'not_found', or 'error:<msg>'
    """
    url = f"{BASE_URL}?id={_b64(enrollment)}&id2={_b64(dob)}"
    for attempt in range(retry + 1):
        try:
            resp = SESSION.get(url, timeout=15)
            resp.raise_for_status()
            html = resp.text
            # Quick check: if tblprint class absent, result not available
            if 'tblprint' not in html:
                return [], "not_found"
            rows = _extract_result(enrollment, html, dob)
            if not rows:
                return [], "not_found"
            return rows, "ok"
        except requests.exceptions.Timeout:
            if attempt < retry:
                time.sleep(2)
            else:
                return [], "error:Timeout"
        except Exception as e:
            if attempt < retry:
                time.sleep(1)
            else:
                return [], f"error:{e}"
    return [], "error:unknown"


def fetch_branch_results(
    students: list[dict],
    skip_enrollments: set = None,
    progress_callback=None,
) -> tuple[list[dict], dict]:
    """
    Fetch results for a list of students.
    
    students: list of dicts with keys 'enrollment' and 'dob'
    skip_enrollments: set of enrollment numbers to skip (already fetched)
    progress_callback: callable(current, total, enrollment, status)
    
    Returns: (all_result_rows, stats_dict)
    """
    skip_enrollments = skip_enrollments or set()
    all_rows = []
    stats = {"ok": 0, "not_found": 0, "skipped": 0, "error": 0, "total": len(students)}

    for i, student in enumerate(students):
        enroll = student["enrollment"]
        dob = student["dob"]

        if enroll in skip_enrollments:
            stats["skipped"] += 1
            if progress_callback:
                progress_callback(i + 1, len(students), enroll, "skipped")
            continue

        rows, status = fetch_student_result(enroll, dob)
        if status == "ok":
            all_rows.extend(rows)
            stats["ok"] += 1
        elif status == "not_found":
            stats["not_found"] += 1
        else:
            stats["error"] += 1

        if progress_callback:
            progress_callback(i + 1, len(students), enroll, status)

        # Polite delay
        time.sleep(0.3)

    return all_rows, stats
