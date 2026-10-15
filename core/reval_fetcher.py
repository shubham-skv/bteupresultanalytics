"""
core/reval_fetcher.py  —  BTEUP Re-Evaluation Result Scraper
Fetches and parses Re-Evaluation results from:
https://result.bteexam.com/even/REVAL/REVAL_RollNo.aspx?id={b64(enrollment)}&id2={b64(dob)}
"""
import base64
import re
import time
import urllib3
import requests
from bs4 import BeautifulSoup
import concurrent.futures

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REVAL_URL = "https://result.bteexam.com/even/REVAL/REVAL_RollNo.aspx"
SESSION = requests.Session()
SESSION.verify = False
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})


def _b64(s: str) -> str:
    if s is None:
        s = ""
    return base64.b64encode(str(s).strip().encode()).decode()


def parse_reval_html(enrollment: str, dob: str, html: str) -> tuple[list[dict], str]:
    """
    Parse BTEUP REVAL HTML into structured subject rows.
    Returns (rows, status) where status is:
      - 'ok' (found subject rows)
      - 'not_found' (student did not fill reval or no record found)
      - 'error' (unexpected HTML format)
    """
    # Check for "No Record Found" alert or missing tables
    if "No Record Found" in html or "alert(" in html or "tblprint" not in html:
        return [{
            "enrollment": enrollment,
            "dob": dob,
            "roll_no": "",
            "qp_no": "-",
            "paper_name": "NO RECORD FOUND",
            "reval_marks": "-",
            "remarks": "Not Applied / No Record Found",
            "status": "NOT_FOUND"
        }], "not_found"

    soup = BeautifulSoup(html, "html.parser")

    # Extract Roll Number from page
    roll_no = ""
    roll_match = re.search(r'Roll\s*Number\s*&nbsp;&nbsp;</td>.*?<td[^>]*>&nbsp;\s*(\w+)', html, re.IGNORECASE | re.DOTALL)
    if roll_match:
        roll_no = roll_match.group(1).strip()
    else:
        for td in soup.find_all("td"):
            if "ROLL NUMBER" in td.get_text().upper():
                nxt = td.find_next_sibling("td")
                if nxt:
                    roll_no = nxt.get_text(strip=True)
                break

    # Extract Enrollment from page if present
    enr_match = re.search(r'ENrollment\s*No\.\s*&nbsp;</td>.*?<td[^>]*>\s*([A-Z0-9]+)', html, re.IGNORECASE | re.DOTALL)
    page_enrollment = enr_match.group(1).strip() if enr_match else enrollment

    # Parse subject rows:
    # Row structure: QPNO, Paper Name, Marks Obtained / Re-Evaluation Marks, Remarks
    subject_rows = []
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) == 4:
            col0 = tds[0].get_text(strip=True)
            col1 = tds[1].get_text(strip=True)
            col2 = tds[2].get_text(strip=True)
            col3 = tds[3].get_text(strip=True)
            # QPNO is numeric like 4101, 4102, 3521, etc.
            if col0.isdigit() and col1:
                subject_rows.append({
                    "enrollment": page_enrollment or enrollment,
                    "dob": dob,
                    "roll_no": roll_no,
                    "qp_no": col0,
                    "paper_name": col1,
                    "reval_marks": col2,
                    "remarks": col3,
                    "status": "FOUND"
                })

    if subject_rows:
        return subject_rows, "ok"
    else:
        return [{
            "enrollment": enrollment,
            "dob": dob,
            "roll_no": roll_no,
            "qp_no": "-",
            "paper_name": "NO RECORD FOUND",
            "reval_marks": "-",
            "remarks": "Not Applied / No Record Found",
            "status": "NOT_FOUND"
        }], "not_found"


def fetch_single_reval(enrollment: str, dob: str, retry: int = 2) -> tuple[list[dict], str]:
    """
    Fetch and parse REVAL result for a single student.
    Returns (rows, status)
    """
    enr_b64 = _b64(enrollment)
    dob_b64 = _b64(dob)
    url = f"{REVAL_URL}?id={enr_b64}&id2={dob_b64}"
    
    for attempt in range(retry + 1):
        try:
            resp = SESSION.get(url, timeout=15)
            resp.raise_for_status()
            return parse_reval_html(enrollment, dob, resp.text)
        except requests.exceptions.Timeout:
            if attempt < retry:
                time.sleep(1.5)
            else:
                return [{
                    "enrollment": enrollment,
                    "dob": dob,
                    "roll_no": "",
                    "qp_no": "-",
                    "paper_name": "TIMEOUT ERROR",
                    "reval_marks": "-",
                    "remarks": "Request Timed Out",
                    "status": "ERROR"
                }], "error"
        except Exception as e:
            if attempt < retry:
                time.sleep(1.0)
            else:
                return [{
                    "enrollment": enrollment,
                    "dob": dob,
                    "roll_no": "",
                    "qp_no": "-",
                    "paper_name": "NETWORK ERROR",
                    "reval_marks": "-",
                    "remarks": str(e)[:100],
                    "status": "ERROR"
                }], "error"
    return [], "error"


def fetch_reval_batch(
    students: list[dict],
    skip_enrollments: set = None,
    progress_callback=None,
    max_workers: int = 5,
    stop_checker=None
) -> tuple[list[dict], dict]:
    """
    Batch fetch REVAL results for a list of students using concurrent worker threads.
    
    students: list of dicts with 'enrollment' and 'dob' (and optional 'name', 'branch', 'institute')
    skip_enrollments: set of enrollments to skip
    progress_callback: callable(completed, total, enrollment, status, row_count)
    stop_checker: callable() returning bool to stop early
    
    Returns: (all_rows, stats)
    """
    skip_enrollments = skip_enrollments or set()
    to_fetch = [s for s in students if s["enrollment"] not in skip_enrollments]
    skipped_count = len(students) - len(to_fetch)

    all_rows = []
    stats = {
        "total": len(students),
        "fetched": 0,
        "found": 0,
        "not_found": 0,
        "skipped": skipped_count,
        "error": 0,
        "subject_count": 0
    }

    if not to_fetch:
        return all_rows, stats

    completed_count = 0
    total_to_fetch = len(to_fetch)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_student = {
            executor.submit(fetch_single_reval, s["enrollment"], s.get("dob", "")): s
            for s in to_fetch
        }

        for future in concurrent.futures.as_completed(future_to_student):
            if stop_checker and stop_checker():
                executor.shutdown(wait=False, cancel_futures=True)
                break

            s_meta = future_to_student[future]
            completed_count += 1
            stats["fetched"] += 1

            try:
                rows, status = future.result()
                # Attach extra student metadata
                for r in rows:
                    if "student_name" not in r or not r["student_name"]:
                        r["student_name"] = s_meta.get("name", s_meta.get("student_name", ""))
                    if "branch" not in r or not r["branch"]:
                        r["branch"] = s_meta.get("branch", "")
                    if "institute" not in r or not r["institute"]:
                        r["institute"] = s_meta.get("institute", "")
                    if "roll_no" not in r or not r["roll_no"]:
                        r["roll_no"] = s_meta.get("rollno", s_meta.get("roll_no", ""))

                all_rows.extend(rows)

                if status == "ok":
                    stats["found"] += 1
                    stats["subject_count"] += len([r for r in rows if r["status"] == "FOUND"])
                elif status == "not_found":
                    stats["not_found"] += 1
                else:
                    stats["error"] += 1

                if progress_callback:
                    progress_callback(completed_count, total_to_fetch, s_meta["enrollment"], status, len(rows))
            except Exception:
                stats["error"] += 1
                if progress_callback:
                    progress_callback(completed_count, total_to_fetch, s_meta["enrollment"], "error", 0)

    return all_rows, stats
