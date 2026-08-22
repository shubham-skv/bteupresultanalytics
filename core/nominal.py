"""
core/nominal.py  —  Parse NOMINAL register from Excel (.xlsx) or PDF
Extracts: enrollment, name, father_name, dob, branch, semester, rollno
"""
import re
import pandas as pd
from datetime import datetime


# ---------------------------------------------------------------------------
# Excel parser
# ---------------------------------------------------------------------------

def _parse_sheet_name(sheet_name: str) -> tuple[str, str]:
    """
    Sheet names follow the pattern like:
       '2 sem ce', '4 sem cse', '6 sem ee lat', '6 sem cse lat'
    Returns: (semester, branch)
    """
    sheet_name = sheet_name.strip().lower()
    # Extract semester number
    sem_match = re.match(r"(\d+)\s*sem\s*(.*)", sheet_name)
    if sem_match:
        semester = sem_match.group(1)
        rest = sem_match.group(2).strip()
        # Normalise branch name
        branch_map = {
            "ce": "Civil Engineering",
            "cse": "Computer Science & Engineering",
            "ee": "Electrical Engineering",
            "me": "Mechanical Engineering",
            "ec": "Electronics Engineering",
            "it": "Information Technology",
        }
        for key, full in branch_map.items():
            if rest.startswith(key):
                suffix = rest[len(key):].strip()
                branch = full + (" (Lateral)" if "lat" in suffix else "")
                return semester, branch
        # Fallback
        return semester, rest.upper()
    return "Unknown", sheet_name.upper()


def _format_dob(val) -> str | None:
    """Convert various date formats to DD/MM/YYYY string."""
    if pd.isnull(val) or str(val).strip() in ("", "nan", "NaT"):
        return None
    if isinstance(val, datetime):
        return val.strftime("%d/%m/%Y")
    s = str(val).strip()
    # Already DD/MM/YYYY
    if re.match(r"\d{2}/\d{2}/\d{4}", s):
        return s
    # YYYY-MM-DD
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    return s


def parse_excel(file_obj, source_label: str = "NOMINAL.xlsx", institute_name: str = "Unknown Institute") -> list[dict]:
    """
    Extract nominal register data from an Excel file (.xlsx)
    Supports multiple sheets (one per branch/semester).
    """
    try:
        xls = pd.ExcelFile(file_obj)
    except Exception as e:
        raise ValueError(f"Could not read Excel file: {e}")
        
    students = []
    
    for sheet_name in xls.sheet_names:
        semester, branch = _parse_sheet_name(sheet_name)
        df = pd.read_excel(xls, sheet_name=sheet_name)
        # Normalise column names
        df.columns = [str(c).strip() for c in df.columns]
        # Find relevant columns (case-insensitive)
        col_map = {}
        for col in df.columns:
            cl = col.lower().replace("'", "").replace('"', "")
            if "enrollment" in cl or "enroll" in cl:
                col_map["enrollment"] = col
            elif "name" in cl and "father" not in cl:
                col_map["name"] = col
            elif "father" in cl:
                col_map["father_name"] = col
            elif "birth" in cl or "dob" in cl:
                col_map["dob"] = col
            elif col.lower().strip() == "rollno":
                col_map["rollno"] = col

        for _, row in df.iterrows():
            enroll = str(row.get(col_map.get("enrollment", ""), "")).strip()
            if not enroll or enroll.lower() in ("nan", "enrollment no", "s. no."):
                continue
            # Must look like an enrollment number (starts with E or letter + digits)
            if not re.match(r"[A-Za-z]\d{10,}", enroll):
                continue

            dob = _format_dob(row.get(col_map.get("dob", ""), None))
            if not dob:
                continue

            students.append({
                "enrollment": enroll,
                "name": str(row.get(col_map.get("name", ""), "")).strip(),
                "father_name": str(row.get(col_map.get("father_name", ""), "")).strip(),
                "dob": dob,
                "branch": branch,
                "semester": semester,
                "rollno": str(row.get(col_map.get("rollno", ""), "")).strip(),
                "source_file": source_label,
                "institute": institute_name,
            })
    return students


# ---------------------------------------------------------------------------
# PDF parser  (pdfplumber + Regex)
# ---------------------------------------------------------------------------

def parse_pdf(file_obj, source_label: str = "NOMINAL.pdf", institute_name: str = None) -> list[dict]:
    """
    Extract nominal register data from a PDF using pdfplumber.
    Uses regex line-by-line parsing which is much more robust against
    table border issues and multi-line rows.
    """
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber is not installed. Run: pip install pdfplumber")

    students = []
    current_branch = "Unknown"
    current_semester = "Unknown"

    branch_keywords = {
        "civil": "Civil Engineering",
        "computer": "Computer Science & Engineering",
        "electrical": "Electrical Engineering",
        "mechanical": "Mechanical Engineering",
        "electronics": "Electronics Engineering",
        "information": "Information Technology",
        "chemical": "Chemical Engineering",
        "agriculture": "Agricultural Engineering",
        "paint": "Paint Technology",
        "textile": "Textile Technology",
    }
    
    current_institute = institute_name or "Unknown Institute"

    # Regex to match: Enrollment (E+14 digits), Roll No (digits), Names, DOB (dd/mm/yyyy)
    student_pattern = re.compile(r'\b(E[A-Za-z0-9]{13,})\s+(\d+)\s+(.+?)\s+(\d{2}/\d{2}/\d{4})\b')

    with pdfplumber.open(file_obj) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            text_upper = text.upper()
            
            # Detect institute if not manually provided
            if not institute_name:
                inst_match = re.search(r"INSTITUTION\s*:\s*(.+)", text_upper)
                if inst_match:
                    current_institute = inst_match.group(1).strip()
            
            # Detect branch & semester
            for kw, branch_full in branch_keywords.items():
                if kw.upper() in text_upper:
                    current_branch = branch_full
                    if "LATERAL" in text_upper:
                        current_branch += " (Lateral)"
                    break
            
            if current_branch == "Unknown":
                # Fallback: Look for "--- [BRANCH NAME]"
                branch_match = re.search(r'\d{3}\s*---\s*([A-Z\s&]+?)(?:(?=\nBRANCH|\nENROLLMENT|\s*$))', text_upper)
                if branch_match:
                    current_branch = branch_match.group(1).strip()
                    if "LATERAL" in text_upper:
                        current_branch += " (Lateral)"

            # Detect semester
            sem_match = re.search(r"(\d)\s*(ST|ND|RD|TH)\s*SEM", text_upper)
            if sem_match:
                current_semester = sem_match.group(1)
            elif "FINAL SEMESTER" in text_upper:
                current_semester = "6"
            elif "FIRST SEMESTER" in text_upper:
                current_semester = "1"
            elif "SECOND SEMESTER" in text_upper:
                current_semester = "2"
            elif "THIRD SEMESTER" in text_upper:
                current_semester = "3"
            elif "FOURTH SEMESTER" in text_upper:
                current_semester = "4"
            elif "FIFTH SEMESTER" in text_upper:
                current_semester = "5"
            elif "SIXTH SEMESTER" in text_upper:
                current_semester = "6"

            # 1. Try table extraction (best for multi-line cells)
            tables = page.extract_tables()
            students_found_on_page = 0
            
            if tables:
                for table in tables:
                    for row in table:
                        if not row or len(row) < 6:
                            continue
                        
                        # Find the column that contains the Enrollment number
                        # Usually it's in column 1, but we'll scan just in case
                        enroll_idx = -1
                        for i, cell in enumerate(row):
                            if cell and re.match(r"^E[A-Za-z0-9]{13,}$", str(cell).strip()):
                                enroll_idx = i
                                break
                                
                        if enroll_idx != -1 and len(row) > enroll_idx + 4:
                            enroll = str(row[enroll_idx]).strip()
                            roll = str(row[enroll_idx + 1]).replace('\n', '').strip()
                            student_name = str(row[enroll_idx + 2]).replace('\n', ' ').strip()
                            father_name = str(row[enroll_idx + 3]).replace('\n', ' ').strip()
                            
                            # DOB might have newlines or extra text, just extract the date
                            dob_raw = str(row[enroll_idx + 4])
                            dob_match = re.search(r"(\d{2}/\d{2}/\d{4})", dob_raw)
                            dob = dob_match.group(1) if dob_match else dob_raw.replace('\n', '').strip()
                            
                            students.append({
                                "enrollment": enroll,
                                "name": student_name,
                                "father_name": father_name,
                                "dob": dob,
                                "branch": current_branch,
                                "semester": current_semester,
                                "rollno": str(roll).strip(),
                                "source_file": source_label,
                                "institute": current_institute,
                            })
                            students_found_on_page += 1

            # 2. Fallback to extract_words if no tables were found
            if students_found_on_page == 0:
                words = page.extract_words()
                if not words:
                    continue
                    
                words.sort(key=lambda w: (w['top'], w['x0']))
                lines = []
                current_line = [words[0]]
                for word in words[1:]:
                    if abs(word['top'] - current_line[-1]['top']) < 5:
                        current_line.append(word)
                    else:
                        lines.append(" ".join([w['text'] for w in current_line]))
                        current_line = [word]
                if current_line:
                    lines.append(" ".join([w['text'] for w in current_line]))

                for line in lines:
                    match = student_pattern.search(line)
                    if match:
                        enroll, roll, names, dob = match.groups()
                        parts = names.strip().split()
                        half = len(parts) // 2
                        student_name = " ".join(parts[:half]) if half > 0 else names.strip()
                        father_name = " ".join(parts[half:]) if half > 0 else ""
                        
                        students.append({
                            "enrollment": enroll,
                            "name": student_name,
                            "father_name": father_name,
                            "dob": dob,
                            "branch": current_branch,
                            "semester": current_semester,
                            "rollno": roll,
                            "source_file": source_label,
                        })

    return students
