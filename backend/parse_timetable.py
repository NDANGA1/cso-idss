# parse_timetable.py — CLI wrapper for timetable PDF parsing

import pdfplumber
import os
import re
from datetime import datetime, time
from app.db.database import SessionLocal
from app.models.venue import Venue
from app.models.user import User
from app.models.booking import Booking

db = SessionLocal()

def get_or_create_venue(name: str):
    venue = db.query(Venue).filter(Venue.name == name).first()
    if not venue:
        venue = Venue(name=name, capacity=50, total_seats=50, data_mode="TIMETABLE_ONLY")
        db.add(venue)
        db.commit()
        db.refresh(venue)
    return venue

def get_or_create_user(name: str):
    user = db.query(User).filter(User.name == name).first()
    if not user:
        user = User(
            name=name,
            email=f"{name.lower().replace(' ', '').replace(',', '')}@ifm.ac.tz",
            password_hash="hashed_temp",
            role="LECTURER"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

def process_file(file_path):
    print(f"\n=== Processing {os.path.basename(file_path)} ===")
    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if not text:
                continue
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            for line in lines:
                # Detect venue
                venue_match = re.search(r'(TH_[A-Z]|LAB_[0-9]+|[0-9]{3})', line)
                if not venue_match:
                    continue
                    
                venue_name = venue_match.group(0)
                print(f"  Venue: {venue_name} | Line: {line[:120]}")
                
                # Try to detect time range
                time_match = re.search(r'(\d{1,2}:\d{2})\s*-?\s*(\d{1,2}:\d{2})', line)
                if time_match:
                    start_str = time_match.group(1)
                    end_str = time_match.group(2)
                    print(f"    TIME FOUND → {start_str} - {end_str}")
                    
                    try:
                        venue = get_or_create_venue(venue_name)
                        # Simple lecturer fallback for now
                        lecturer_match = re.search(r'([A-Za-z][A-Za-z\s\.,()]+?)(?=\s|$)', line)
                        lecturer_name = lecturer_match.group(1).strip() if lecturer_match else "Unknown Lecturer"
                        user = get_or_create_user(lecturer_name)
                        
                        # Create booking (you can later map days properly)
                        booking = Booking(
                            venue_id=venue.id,
                            user_id=user.id,
                            booking_type="TIMETABLE",
                            start_time=datetime.combine(datetime.now().date(), datetime.strptime(start_str, "%H:%M").time()),
                            end_time=datetime.combine(datetime.now().date(), datetime.strptime(end_str, "%H:%M").time()),
                            status="ACTIVE"
                        )
                        db.add(booking)
                        db.commit()
                        print(f"    → Booking created for {venue_name}")
                    except Exception as e:
                        print(f"    Error creating booking: {e}")
                        db.rollback()

if __name__ == "__main__":
    folder = r"C:\Users\Administrator\Desktop\TIMETABLE PDFS"
    for filename in os.listdir(folder):
        if filename.endswith(".pdf"):
            process_file(os.path.join(folder, filename))
    db.close()
    print("\n Done processing all files.")