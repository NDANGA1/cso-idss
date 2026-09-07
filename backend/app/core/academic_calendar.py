# academic_calendar.py
# I wrote this to figure out whether we're in a teaching period or a break.
# The university calendar is hardcoded based on IFM's academic schedule.
# I use this in the occupancy engine to suppress timetable bookings during holidays.

from datetime import date

# Each tuple is an inclusive (start, end) range of a TEACHING or EXAM period.
# Only during these windows do recurring timetable bookings count as occupying a venue.
TEACHING_PERIODS = [
    # Semester 1 Teaching 2025/2026
    (date(2025, 11, 24), date(2026, 2, 27)),
    # Exam prep + Semester 1 Final Exams
    (date(2026, 3, 1),   date(2026, 3, 22)),
    # Semester 2 Teaching 2025/2026
    (date(2026, 4, 20),  date(2026, 7, 24)),
    # Exam prep + Semester 2 Final Exams
    (date(2026, 7, 27),  date(2026, 8, 16)),
    # Supplementary / Special / Carry Exams (UG & PG Diploma)
    (date(2026, 9, 28),  date(2026, 10, 16)),
    # Semester 1 2026/2027 (estimated — update when next almanac is issued)
    (date(2026, 11, 23), date(2027, 3, 31)),
]

def is_teaching_active(check_date: date = None) -> bool:
    """
    Return True if the given date falls inside a teaching / exam period,
    meaning timetable (recurring) bookings should be respected.
    Returns False during holidays and inter-semester breaks.
    """
    d = check_date or date.today()
    return any(start <= d <= end for start, end in TEACHING_PERIODS)

def academic_period_label(check_date: date = None) -> str:
    """Human-readable label for the current academic period (for UI hints)."""
    d = check_date or date.today()
    if date(2025, 11, 24) <= d <= date(2026, 2, 27):
        return "Semester 1 Teaching 2025/2026"
    if date(2026, 3, 1) <= d <= date(2026, 3, 22):
        return "Semester 1 Examinations 2025/2026"
    if date(2026, 4, 20) <= d <= date(2026, 7, 24):
        return "Semester 2 Teaching 2025/2026"
    if date(2026, 7, 27) <= d <= date(2026, 8, 16):
        return "Semester 2 Examinations 2025/2026"
    if date(2026, 8, 17) <= d <= date(2026, 9, 27):
        return "Long Break (Post-Examination) 2025/2026"
    if date(2026, 9, 28) <= d <= date(2026, 10, 16):
        return "Supplementary Examinations 2025/2026"
    if date(2026, 10, 17) <= d <= date(2026, 11, 22):
        return "Inter-Semester Break 2025/2026"
    if date(2026, 11, 23) <= d:
        return "Semester 1 Teaching 2026/2027"
    return "Break / Holiday"
