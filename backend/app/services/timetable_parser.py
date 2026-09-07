# timetable_parser.py
# Parses the IFM timetable PDF into structured booking entries.
# This was the hardest part to get right — the PDF format is inconsistent.
# I used pdfplumber + a bunch of regex to handle all the edge cases.

import re
import pdfplumber
from datetime import time
from typing import List, Dict, Optional, Tuple, Set
from sqlalchemy.orm import Session

from app.models.venue import Venue
from app.models.user import User
from app.models.booking import Booking

# ── Constants ────────────────────────────────────────────────────────────────

# Maps reversed day-name fragments → canonical day
_REVERSED_DAYS: Dict[str, str] = {
    "yadnom": "MONDAY",
    "yadseu": "TUESDAY",
    "yadsend": "WEDNESDAY",
    "yadrsuht": "THURSDAY",
    "yadirf": "FRIDAY",
    "yadrutas": "SATURDAY",
    "yadnus": "SUNDAY",
    # Short reversed forms
    "nom": "MONDAY",
    "eut": "TUESDAY",
    "dew": "WEDNESDAY",
    "uht": "THURSDAY",
    "irf": "FRIDAY",
    "tas": "SATURDAY",
    "nus": "SUNDAY",
}

VENUE_PATTERN = re.compile(
    r'\b(TH_[A-Z]{1,2}|LAB_\d+|IFM_MK\d+|\d{3})\b', re.IGNORECASE
)

COURSE_CODE_PATTERN = re.compile(
    r'\b([A-Z]{2,4}[_\s]?\d{3,5}(?:\s*,\s*[A-Z]{2,4}[_\s]?\d{3,5})*)\b'
)

LECTURER_PATTERN = re.compile(
    r'(?:^|\n)([A-Z][a-z]+(?:,\s*[A-Z][a-z]*)?(?:\s+\([A-Z][a-z]+\.?\))?)\s*$',
    re.MULTILINE
)

# Typical venue capacities by type
VENUE_CAPACITIES = {
    "TH": 150,
    "LAB": 40,
    "IFM_MK": 120,   # IFM MK halls (medium lecture halls)
    "default": 60,   # Numbered rooms (110-350 range) — ~60 seats
}

# ── Time handling ─────────────────────────────────────────────────────────────

def _to_24h(hour: int) -> int:
    """Convert 12-hour timetable column hour to 24-hour. Slots <7 are afternoon."""
    if hour < 7:
        return hour + 12
    return hour

def _parse_header_times(header_row: List[Optional[str]]) -> Dict[int, Tuple[time, time]]:
    """
    Parse the header row to get column_index → (start_time, end_time).

    Header cells look like: '07:00 08:00', '12:00 01:00', '01:00 02:00'
    """
    col_times: Dict[int, Tuple[time, time]] = {}
    time_re = re.compile(r'(\d{1,2}):(\d{2})\s+(\d{1,2}):(\d{2})')

    for col_idx, cell in enumerate(header_row):
        if not cell:
            continue
        m = time_re.search(str(cell))
        if m:
            sh, sm, eh, em = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
            start = time(_to_24h(sh), sm)
            end_h = _to_24h(eh)
            # Handle midnight wrap: end should always be > start
            if end_h <= _to_24h(sh) and eh != 0:
                end_h = _to_24h(sh) + 1
            end = time(end_h if end_h < 24 else 23, 59)
            col_times[col_idx] = (start, end)

    return col_times

def _detect_day(cell_text: str) -> Optional[str]:
    """Detect if a cell is a day marker (text written backwards)."""
    if not cell_text:
        return None
    lower = cell_text.lower().strip()
    for fragment, day in _REVERSED_DAYS.items():
        if lower.startswith(fragment) or lower == fragment:
            return day
    return None

def _infer_span(row: List, col_idx: int, col_times: Dict) -> int:
    """
    Count how many hours this session spans by checking consecutive None cells.
    Capped at 3 hours (longest realistic IFM class block).
    Stops if a cell has actual content (a new booking starts).
    """
    span = 1
    for offset in range(1, 4):   # max 3-hour cap
        next_col = col_idx + offset
        if next_col >= len(row):
            break
        cell = row[next_col]
        # A genuine None (merged) vs an empty string (truly empty) vs content
        if cell is None:
            span += 1
        else:
            break
    return span

def _extract_venue_and_booking_info(cell_text: str) -> Optional[Dict]:
    """
    Parse cell text into structured booking info.

    Cell format (lines separated by \\n):
      Line 0: Session type (Lecture / Tutorial / Lab / …) [optional]
      Line 1: Course code(s)
      Line 2: Venue code
      Line 3: Lecturer name
      Line 4+: Programme codes [ignored]

    Returns None if no venue code found.
    """
    if not cell_text or not cell_text.strip():
        return None

    venue_match = VENUE_PATTERN.search(cell_text)
    if not venue_match:
        return None

    venue_code = venue_match.group(0).upper()

    # Course code: first match before venue
    course_match = COURSE_CODE_PATTERN.search(cell_text)
    course_code = None
    if course_match:
        raw = course_match.group(1).strip()
        # Take only the first code if multiple listed
        course_code = re.split(r'\s*,\s*', raw)[0].replace(" ", "").upper()

    # Lecturer: line immediately after venue line (title-cased word with optional (Title))
    lines = [l.strip() for l in cell_text.split("\n") if l.strip()]
    venue_line_idx = next((i for i, l in enumerate(lines) if VENUE_PATTERN.search(l)), None)
    lecturer = None
    if venue_line_idx is not None and venue_line_idx + 1 < len(lines):
        candidate = lines[venue_line_idx + 1]
        # Lecturer lines look like: "Mushi, A (Dr)" or "Mchembe,S (Dr)" or "Mapendo,J. (Dr)"
        if re.search(r'[A-Z][a-z]+', candidate) and not VENUE_PATTERN.search(candidate):
            lecturer = candidate.strip().rstrip(",.")

    # Session type
    session_type = None
    if lines and lines[0] in ("Lecture", "Tutorial", "Lab", "Seminar", "Practical"):
        session_type = lines[0]

    return {
        "venue_code": venue_code,
        "course_code": course_code,
        "lecturer": lecturer,
        "session_type": session_type,
    }

# ── DB helpers ────────────────────────────────────────────────────────────────

def _default_capacity(venue_code: str) -> int:
    if venue_code.startswith("TH"):
        return VENUE_CAPACITIES["TH"]
    if venue_code.startswith("LAB"):
        return VENUE_CAPACITIES["LAB"]
    if venue_code.startswith("IFM_MK"):
        return VENUE_CAPACITIES["IFM_MK"]
    return VENUE_CAPACITIES["default"]

def _get_or_create_venue(db: Session, code: str) -> Venue:
    code = code.upper().strip()
    venue = db.query(Venue).filter(Venue.name == code).first()
    if not venue:
        cap = _default_capacity(code)
        venue = Venue(
            name=code,
            capacity=cap,
            total_seats=cap,
            data_mode="TIMETABLE_ONLY",
        )
        db.add(venue)
        db.commit()
        db.refresh(venue)
    return venue

def _get_or_create_lecturer(db: Session, name: str) -> Optional[User]:
    name = name.strip()
    if not name or len(name) < 3 or name.lower() in ("tba", "n/a", "-", "unknown"):
        return None
    user = db.query(User).filter(User.name == name).first()
    if not user:
        safe_email = re.sub(r'[^a-z0-9]', '', name.lower())[:30] + "@ifm.ac.tz"
        # Avoid email collision
        existing_email = db.query(User).filter(User.email == safe_email).first()
        if existing_email:
            safe_email = re.sub(r'[^a-z0-9]', '', name.lower())[:25] + str(hash(name))[-4:] + "@ifm.ac.tz"
        user = User(
            name=name,
            email=safe_email,
            password_hash="timetable_import_placeholder",
            role="LECTURER",
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
        except Exception:
            db.rollback()
            user = db.query(User).filter(User.name == name).first()
    return user

def _create_booking(
    db: Session,
    venue: Venue,
    lecturer: Optional[User],
    course_code: Optional[str],
    day: str,
    start: time,
    end: time,
) -> bool:
    """Returns True if created, False if duplicate."""
    existing = db.query(Booking).filter(
        Booking.venue_id == venue.id,
        Booking.day_of_week == day,
        Booking.start_time == start,
        Booking.end_time == end,
    ).first()
    if existing:
        return False

    booking = Booking(
        venue_id=venue.id,
        user_id=lecturer.id if lecturer else None,
        course_code=course_code,
        course_name=None,
        booking_type="TIMETABLE",
        day_of_week=day,
        start_time=start,
        end_time=end,
        status="ACTIVE",
        source="TIMETABLE_PDF",
    )
    db.add(booking)
    try:
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False

# ── Core page parser ──────────────────────────────────────────────────────────

def _parse_table(
    table: List[List[Optional[str]]],
    db: Session,
) -> Tuple[int, int]:
    """Parse one pdfplumber table. Returns (created, skipped)."""
    if not table or len(table) < 2:
        return 0, 0

    # Row 0: time headers
    col_times = _parse_header_times(table[0])
    if not col_times:
        return 0, 0

    current_day: Optional[str] = None
    created = skipped = 0

    # We sometimes need to carry content across rows (split merged cells)
    pending_by_col: Dict[int, str] = {}   # col_idx → partial cell text

    for row in table[1:]:
        # Check column 0 for day marker
        day_cell = str(row[0] or "").strip()
        detected = _detect_day(day_cell)
        if detected:
            current_day = detected
            pending_by_col.clear()
            continue

        if not current_day:
            continue

        for col_idx, raw_cell in enumerate(row):
            if col_idx not in col_times:
                continue

            cell = str(raw_cell or "").strip() if raw_cell is not None else ""

            # Merge with pending from previous row if applicable
            if col_idx in pending_by_col:
                merged = pending_by_col.pop(col_idx)
                if cell:
                    cell = merged + "\n" + cell
                else:
                    cell = merged

            if not cell:
                continue

            # If venue code not yet present, this may be the first half of a split cell
            venue_match = VENUE_PATTERN.search(cell)
            if not venue_match:
                # Store as pending for next row only if it has content worth keeping
                if re.search(r'[A-Z]{2,4}[_\s]?\d{3,5}', cell) or re.search(r'(Lecture|Tutorial|Lab)', cell):
                    pending_by_col[col_idx] = cell
                continue

            info = _extract_venue_and_booking_info(cell)
            if not info:
                continue

            start_t, _ = col_times[col_idx]
            # Span: count consecutive None cells (max 3h cap)
            span = _infer_span(row, col_idx, col_times)
            end_col = col_idx + span - 1
            while end_col >= col_idx and end_col not in col_times:
                end_col -= 1
            _, end_t = col_times[end_col]

            try:
                venue = _get_or_create_venue(db, info["venue_code"])
                lecturer = _get_or_create_lecturer(db, info["lecturer"]) if info["lecturer"] else None
                ok = _create_booking(db, venue, lecturer, info["course_code"], current_day, start_t, end_t)
                if ok:
                    created += 1
                else:
                    skipped += 1
            except Exception as e:
                db.rollback()
                skipped += 1

    return created, skipped

# ── Public API ────────────────────────────────────────────────────────────────

def parse_timetable_pdf(file_path: str, db: Session, filename: str = "") -> Dict:
    """
    Parse one IFM timetable PDF and insert Booking records.
    Returns a summary dict.
    """
    total_created = total_skipped = 0
    errors = []
    pages_processed = 0

    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            try:
                tables = page.extract_tables()
                if not tables:
                    continue
                pages_processed += 1
                for table in tables:
                    c, s = _parse_table(table, db)
                    total_created += c
                    total_skipped += s
            except Exception as e:
                errors.append(f"Page {page_num}: {str(e)}")

    return {
        "filename": filename,
        "pages_processed": pages_processed,
        "bookings_created": total_created,
        "bookings_skipped": total_skipped,
        "errors": errors,
    }
