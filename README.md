# CSO-IDSS

**AI-Based Real-Time Campus Space Occupancy & Intelligent Decision Support System**

Final Year Project — Institute of Finance Management (IFM), Dar es Salaam

CSO-IDSS answers a simple question that's hard to answer well: *"Is this venue free right now, and will it be free later?"* It fuses live computer-vision headcounts from campus cameras with the official class timetable and manual bookings, then layers a forecasting model on top so users can see not just current occupancy but predicted occupancy.

## Key Features

- **Real-time occupancy detection** — a YOLOv8-based computer vision pipeline counts people from live camera feeds per venue.
- **Timetable-aware availability** — parses the institute's timetable PDF and merges it with one-off bookings so a lecture hall isn't shown as "free" just because no camera is pointed at it yet.
- **Academic calendar logic** — automatically distinguishes teaching periods from breaks/holidays so recurring class bookings don't falsely block rooms during holidays.
- **Occupancy forecasting** — a Random Forest model trained on historical occupancy readings predicts how busy a venue will be at a future time.
- **Seat-map & live venue dashboard** — visual, per-seat/per-venue views of current status.
- **Booking & alarms** — students/staff can book venues and set alarms for when a venue frees up.
- **Analytics dashboard** — historical trends per venue, with automatic snapshotting every 15 minutes so data never goes stale.
- **Role-based access** — admin and staff views for managing venues and bookings, separate from the general user experience.

## How It Works

1. **Capture** — `camera/inference.py` pulls frames from RTSP camera streams.
2. **Preprocess** — CLAHE contrast enhancement + unsharp masking to compensate for cheap/low-quality camera feeds.
3. **Detect** — YOLOv8 (via Ultralytics, with an OpenCV-DNN ONNX fallback) detects people, with test-time augmentation and temporal smoothing across frames to stabilize the headcount.
4. **Reconcile** — `OccupancyEngine` combines the live headcount with active bookings and the academic calendar to compute each venue's true availability state.
5. **Forecast** — `forecast_service.py` trains a `RandomForestRegressor` on historical readings (grouped by hour/day-of-week) to predict future occupancy once enough data has accumulated.
6. **Serve** — a FastAPI backend exposes all of this over REST + WebSockets to a React frontend.

## Tech Stack

| Layer | Technology |
|---|---|
| Computer Vision | YOLOv8 (Ultralytics / ONNX Runtime), OpenCV |
| Backend | FastAPI, SQLAlchemy, PostgreSQL |
| Forecasting | scikit-learn (Random Forest) |
| Timetable Parsing | pdfplumber + custom regex parsing |
| Frontend | React, Vite, Tailwind CSS |
| Deployment | Railway (backend), Vercel (frontend) |

## Project Structure

```
cso-idss/
├── backend/
│   ├── app/
│   │   ├── routers/        # auth, venues, bookings, alarms, analytics, forecast, seatmap, timetable
│   │   ├── services/       # occupancy_engine, forecast_service, analytics_service, timetable_parser
│   │   ├── models/         # SQLAlchemy models
│   │   └── core/           # security, academic calendar logic
│   └── camera/              # YOLOv8 inference pipeline
└── frontend/
    └── src/
        ├── pages/           # Dashboard, LiveVenues, Analytics, Forecast, VenueDetail, admin & staff views
        └── components/      # SeatGrid, OccupancyGauge, CameraView, AlarmAlert, etc.
```

## Running Locally

**Backend**
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env      # set your DATABASE_URL and SECRET_KEY
uvicorn app.main:app --reload --port 8001
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

The API is self-documented at `/docs` once the backend is running.

## Author

**Praygod Ndanga** — BSc. Information Technology, Institute of Finance Management
