# dryrun_parser.py
# I use this to test timetable PDF parsing without touching the DB.

import sys, re, os
sys.path.insert(0, os.path.dirname(__file__))

import pdfplumber
from datetime import time

_REVERSED_DAYS = {
    'yadnom': 'MONDAY', 'yadseu': 'TUESDAY', 'yadsend': 'WEDNESDAY',
    'yadrsuht': 'THURSDAY', 'yadirf': 'FRIDAY', 'yadrutas': 'SATURDAY',
    'yadnus': 'SUNDAY', 'nom': 'MONDAY', 'eut': 'TUESDAY', 'dew': 'WEDNESDAY',
    'uht': 'THURSDAY', 'irf': 'FRIDAY', 'tas': 'SATURDAY', 'nus': 'SUNDAY',
}

VENUE_PATTERN = re.compile(r'\b(TH_[A-Z]{1,2}|LAB_\d+|IFM_MK\d+|\d{3})\b', re.IGNORECASE)
COURSE_CODE_PATTERN = re.compile(r'\b([A-Z]{2,4}[_\s]?\d{3,5})\b')

def to24h(h):
    return h + 12 if h < 7 else h

def parse_header(row):
    col_times = {}
    tre = re.compile(r'(\d{1,2}):(\d{2})\s+(\d{1,2}):(\d{2})')
    for ci, cell in enumerate(row):
        if not cell:
            continue
        m = tre.search(str(cell))
        if m:
            sh, sm, eh, em = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
            s = time(to24h(sh), sm)
            e_h = to24h(eh)
            if e_h <= to24h(sh):
                e_h = to24h(sh) + 1
            e = time(min(e_h, 23), em)
            col_times[ci] = (s, e)
    return col_times

def detect_day(txt):
    if not txt:
        return None
    low = txt.lower().strip()
    for frag, day in _REVERSED_DAYS.items():
        if low.startswith(frag) or low == frag:
            return day
    return None

def parse_file(fpath, fname):
    results = []
    with pdfplumber.open(fpath) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            if not tables:
                continue
            for table in tables:
                if not table or len(table) < 2:
                    continue
                col_times = parse_header(table[0])
                if not col_times:
                    continue
                current_day = None
                pending = {}
                for row in table[1:]:
                    dc = str(row[0] or '').strip()
                    d = detect_day(dc)
                    if d:
                        current_day = d
                        pending.clear()
                        continue
                    if not current_day:
                        continue
                    for ci, raw in enumerate(row):
                        if ci not in col_times:
                            continue
                        cell = str(raw or '').strip() if raw is not None else ''
                        if ci in pending:
                            merged = pending.pop(ci)
                            cell = (merged + '\n' + cell).strip() if cell else merged
                        if not cell:
                            continue
                        vm = VENUE_PATTERN.search(cell)
                        if not vm:
                            if re.search(r'[A-Z]{2,4}[_\s]?\d{3,5}', cell) or re.search(r'(Lecture|Tutorial)', cell):
                                pending[ci] = cell
                            continue
                        venue = vm.group(0).upper()
                        cm = COURSE_CODE_PATTERN.search(cell)
                        course = cm.group(1).replace(' ', '').upper() if cm else None
                        st, et = col_times[ci]
                        results.append((fname[:22], f'p{page_num}', current_day, str(st)[:5], str(et)[:5], venue, course or ''))
    return results

def main():
    folder = r'C:\Users\JANE KAYANGE\Desktop\FYP PRAYGOD\TIMETABLES'
    files = sorted(os.listdir(folder))
    all_results = []
    venue_set = set()

    for fname in files:
        fpath = os.path.join(folder, fname)
        results = parse_file(fpath, fname)
        all_results.extend(results)
        venue_set.update(r[5] for r in results)
        print(f'{fname}: {len(results)} bookings found')

    print(f'\nTotal bookings extracted: {len(all_results)}')
    print(f'Unique venues: {sorted(venue_set)}')
    print('\nFirst 50 entries:')
    for r in all_results[:50]:
        print(f'  {r[2]:<10} {r[3]}-{r[4]}  {r[5]:<10} {r[6]}')

if __name__ == '__main__':
    main()
