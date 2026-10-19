# CineBook — Premium Cinema Booking & Management Platform

[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1.3-black.svg)](https://flask.palletsprojects.com/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-orange.svg)](https://www.mysql.com/)
[![Status](https://img.shields.io/badge/Status-Complete-emerald.svg)]()

**CineBook** is an enterprise-grade, academic database-driven cinema booking and management web application. Built on **Python (Flask)** and **MySQL 8**, it transforms a standard ticketing workflow into a dark cinematic experience featuring conflict-free interactive seat selection, dynamic concessions ordering, simulated checkout, instant QR entry passes, and a management console with aggregate analytics.

---

## 🌟 Key Features

### 🎬 Customer Experience
1. **Cinematic Landing Page (`/`)**:
   - Atmospheric hero banner with ambient lighting effects and responsive layout.
   - Real-time platform KPI metrics (active movies, operating theatres, daily showtimes).
   - "Now Showing" featured movie cards directly queried from MySQL `MOVIE`.
   - Partner multiplex discovery and scheduled screening previews.
   - 4-step booking process walkthrough and cinema concessions preview.

2. **Movie Catalogue (`/movies`)**:
   - Parameterized SQL search by film title.
   - Dynamic language filter pills (Tamil, Hindi, Telugu, English, Kannada).
   - Multi-mode sorting (Alphabetical A–Z, Z–A, Runtime shortest/longest).
   - Graceful empty state handling and instant filter resetting.

3. **Movie Details Spotlight (`/movie/<id>`)**:
   - Film synopsis, certification (`UA`), IMDb rating, director, and starring cast.
   - Showtimes grouped hierarchically by **Date** and **Theatre**, with screen numbers and direct booking actions.

4. **Theatres & Showtime Discovery (`/theatres`)**:
   - Multiplex discovery with location tagging.
   - Multi-parameter filtering by Theatre, Movie, and Screening Date.
   - Clear display of screen capacity, auditorium number, and runtime.

5. **Multi-Step Interactive Booking Engine (`/booking`)**:
   - **Step 1 — Show Selection**: Pick or switch between any active screening.
   - **Step 2 — Interactive Seating Map**: Curved cinema screen with real-time seat availability reflecting existing `TICKET` reservations. Tier pricing (Standard ₹120, Executive ₹150, VIP Recliner ₹180) with live price updates.
   - **Step 3 — Customer Information**: Name and 10-digit phone number with auto-lookup: returning customers' names are automatically recalled from the `CUSTOMER` table.
   - **Step 4 — Concessions Ordering**: Live menu loaded from the `SNACK` table (Popcorn, Coke, Nachos, Combo Meals, Chocolate) with steppers and subtotal calculations.
   - **Step 5 — Demo Payment Simulation**: UPI (VPA/QR simulation), Debit/Credit Card (masked simulation), and Box Office Cash simulation.
   - **Step 6 — Review & Confirmation**: Full cost breakdown (Tickets + Snacks = Grand Total) committing an atomic database transaction.

6. **Instant Entry Pass (`/booking/confirmation/<id>`)**:
   - Cinema entry pass with perforated border styling, booking reference `#CB-XXXXX`, assigned seats, itemized concessions, and a simulated gate QR code.
   - Print-ready styling (`@media print`) for hard-copy ticket generation.

7. **My Bookings Lookup (`/my-bookings`)**:
   - Dual search by booking reference ID and/or registered customer phone number.
   - Retrieves full historical reservations, seats, and payment modes.

---

### 🛡️ Administrative Portal
1. **Secure Admin Authentication (`/admin/login`)**:
   - Session-based authentication protected by environment-configured credentials and `scrypt` password hashing.
   - Protected server-side routes preventing unauthorized access.

2. **Live Overview Dashboard (`/admin`)**:
   - Aggregate metrics queried via `COUNT`, `SUM`, and `AVG` without Cartesian multiplication:
     - Total Recorded Revenue (`SUM(Total_Amount)` from `BOOKING`)
     - Ticket Revenue (`SUM(Price)` from `TICKET`)
     - Concession Revenue (`SUM(Quantity * Unit_Price)` from `BOOKING_SNACK`)
     - Average Booking Value
     - Total Bookings, Customers, Movies, and Operating Theatres
   - Recent customer reservations table.
   - Popular movie rankings by ticket volume.

3. **CRUD Resource Management**:
   - **Movies (`/admin/movies`)**: Add, edit runtime/language, and safe delete (guarded against foreign key conflicts in `SHOW`).
   - **Theatres (`/admin/theatres`)**: Add, edit locations, and safe delete.
   - **Screens (`/admin/screens`)**: Composite primary key `(Theatre_Id, Screen_No)` management with seating capacity configuration.
   - **Showtimes (`/admin/shows`)**: Schedule showtimes with automatic schedule conflict detection on `(Theatre_Id, Screen_No, Show_Date, Show_Time)`.
   - **Staff (`/admin/employees`)**: Manage employees and theatre assignments.
   - **Concessions (`/admin/snacks`)**: Manage snack items and current pricing.
   - **Bookings (`/admin/bookings`)**: Search and filter all customer transactions.

4. **Visual Analytics & Reporting (`/admin/analytics`)**:
   - Responsive **Chart.js** visualizations powered by real MySQL aggregation:
     - Financial revenue split (Tickets vs Concessions Doughnut chart).
     - Ticket volume by film title (Bar chart).
     - Multiplex distribution (Polar Area chart).
     - Snack items sold (Bar chart).
     - Daily booking revenue trendline.

---

## 🗄️ Database Architecture (All 11 Normalized Tables)

CineBook strictly adheres to the schema of **`CineBookDB`**:

| # | Table Name | Primary Key | Description & Key Relationships |
|---|------------|-------------|---------------------------------|
| 1 | `THEATRE` | `Theatre_Id` | Multiplex venues and physical city locations. |
| 2 | `SCREEN` | `(Theatre_Id, Screen_No)` | Composite PK; auditorium screen capacity per theatre. |
| 3 | `MOVIE` | `Movie_Id` | Film titles, languages, and durations in minutes. |
| 4 | `SHOW` | `Show_Id` | Scheduled screenings; composite FK `(Theatre_Id, Screen_No)` to `SCREEN`, FK `Movie_Id` to `MOVIE`. Unique schedule constraint on `(Theatre_Id, Screen_No, Show_Date, Show_Time)`. |
| 5 | `CUSTOMER` | `Customer_Id` | Customer contact records (`Customer_Name`, `Phone`). |
| 6 | `BOOKING` | `Booking_Id` | Customer booking header; FK `Customer_Id` and `Show_Id`. Unique key on `(Booking_Id, Show_Id)`. |
| 7 | `TICKET` | `Ticket_No` | Individual seat tickets; composite FK `(Booking_Id, Show_Id)` to `BOOKING`. Unique key on `(Show_Id, Seat_No)` guarantees zero duplicate bookings. |
| 8 | `PAYMENT` | `Payment_Id` | Financial transaction linked to booking; unique key on `Booking_Id` (`Amount`, `Mode`). |
| 9 | `EMPLOYEE` | `Employee_Id` | Staff members; FK `Theatre_Id` to `THEATRE`. |
| 10 | `SNACK` | `Snack_Id` | Concession catalog and standard unit prices. |
| 11 | `BOOKING_SNACK` | `(Booking_Id, Snack_Id)` | Bridge table recording ordered snacks and historical `Unit_Price` at time of booking. |

### 🔒 Atomic Booking Transaction Logic
When a customer confirms a reservation, CineBook executes an atomic database transaction:
```sql
START TRANSACTION;
-- 1. Check seat availability for the show with row-level locking
SELECT Seat_No FROM TICKET WHERE Show_Id = ? AND Seat_No IN (?) FOR UPDATE;

-- 2. Lookup or insert customer record
INSERT INTO CUSTOMER (Customer_Name, Phone) VALUES (?, ?);

-- 3. Insert header booking record
INSERT INTO BOOKING (Booking_Date, Total_Amount, Customer_Id, Show_Id) VALUES (NOW(), ?, ?, ?);

-- 4. Insert ticket records for each selected seat
INSERT INTO TICKET (Seat_No, Price, Booking_Id, Show_Id) VALUES (?, ?, ?, ?);

-- 5. Insert snacks with historical snapshot unit prices
INSERT INTO BOOKING_SNACK (Booking_Id, Snack_Id, Quantity, Unit_Price) VALUES (?, ?, ?, ?);

-- 6. Insert payment simulation record
INSERT INTO PAYMENT (Amount, Mode, Booking_Id) VALUES (?, ?, ?);

COMMIT; -- Or ROLLBACK upon conflict/exception
```

---

## 🛠️ Technology Stack

- **Backend**: Python 3.13, Flask 3.1.3, Werkzeug 3.1.9
- **Database**: MySQL 8.0 with `mysql-connector-python`
- **Environment Management**: `python-dotenv`
- **Frontend**: Semantic HTML5, Vanilla CSS3 (Custom Design System with CSS variables), Vanilla JavaScript (ES6+)
- **Charting & Visualizations**: Chart.js (via CDN)
- **Typography**: Google Fonts (*Outfit* and *Plus Jakarta Sans*)

---

## 🚀 Setup & Installation Instructions (Ubuntu / Linux)

### 1. Prerequisites
Ensure Python 3, `pip`, and MySQL 8 are installed and running:
```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip mysql-server
```

### 2. Clone / Open Repository
```bash
cd /home/rishit-bisoyi/CineBook
```

### 3. Activate Virtual Environment
```bash
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables (`.env`)
Create or edit `.env` in the root project folder:
```ini
# Database Configuration
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=qwerty
DB_NAME=CineBookDB
DB_PORT=3306

# Flask Configuration
FLASK_APP=app.py
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=cinebook-ultra-secure-key-2026-production

# Admin Credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=scrypt:32768:8:1$zOLXdvIeZuqpUCxd$fd365302b3d52c1a8d050585e3b88970c464eb2d7c05661741c59f82b0f3264f8d4416bbb8401506dd97b920cb5dbe85e63cc734800b4968266e43f9c56a0d1f
ADMIN_DEFAULT_PASSWORD=admin123
```

---

## 💻 Running the Application

To start the Flask development server:
```bash
python app.py
```
Or with Flask CLI:
```bash
flask run --host=127.0.0.1 --port=5000
```
Open your browser and navigate to:
```
http://127.0.0.1:5000/
```

### Default Credentials
- **Admin Portal URL**: `http://127.0.0.1:5000/admin/login`
- **Username**: `admin`
- **Password**: `admin123`

---

## 🧪 Running the Verification Test Suite

A comprehensive test suite verifies routes, database queries, customer lookups, seat conflict handling, and administrative permissions:
```bash
python test_app.py
```
Expected output:
```
Ran 12 tests in ~3.1s
OK
```

---

## 📂 Project Structure

```
CineBook/
├── .env                     # Private environment configurations (DB, keys, admin creds)
├── .env.example             # Template environment configuration
├── .gitignore               # Excludes secrets, cache, and virtualenvs
├── requirements.txt         # Python package dependencies
├── README.md                # Comprehensive project documentation
├── app.py                   # Flask application factory and error handlers
├── config.py                # Environment configuration loader
├── db.py                    # Database connection helpers and transaction manager
├── poster_meta.py           # Movie metadata and poster fallback generator
├── test_app.py              # Automated unit and integration test suite
├── routes/
│   ├── __init__.py
│   ├── public.py            # Public routes (Home, Movies, Theatres, Booking, Lookup)
│   ├── admin.py             # Admin controller and CRUD handlers
│   └── api.py               # REST API endpoints (Seats, Conflict checking, Analytics)
├── static/
│   ├── css/
│   │   ├── base.css         # Dark cinema design tokens, typography, CSS reset
│   │   ├── components.css   # Buttons, cards, modals, toast notifications, badges
│   │   ├── cinema.css       # Hero banner, movie grid, interactive seat map, ticket pass
│   │   └── admin.css        # Admin sidebar, tables, stat cards, chart containers
│   ├── js/
│   │   ├── main.js          # Mobile nav toggle, toast notifications, modal dialogs
│   │   ├── booking.js       # Interactive 6-step booking flow and seat visualizer
│   │   ├── catalogue.js     # Live search and language/sort filtering
│   │   └── admin.js         # Confirm delete modals and Chart.js reporting
│   └── style.css            # Stylesheet bundle importing modular CSS sheets
└── templates/
    ├── base.html            # Public layout template with navbar and footer
    ├── index.html           # Home landing page with hero, movies, theatres, and guide
    ├── movies.html          # Movie catalogue browsing page
    ├── movie_detail.html    # Movie spotlight with grouped showtimes
    ├── theatres.html        # Theatre and showtime discovery page
    ├── booking.html         # Interactive multi-step booking experience
    ├── booking_success.html # Print-friendly ticket pass with QR code
    ├── my_bookings.html     # Booking lookup by phone and reference ID
    ├── 404.html             # Custom 404 page
    ├── 500.html             # Custom 500 page
    └── admin/
        ├── base_admin.html  # Admin console sidebar layout
        ├── login.html       # Admin authentication sign-in
        ├── dashboard.html   # Live metrics overview and recent bookings
        ├── movies.html      # Movie CRUD management
        ├── theatres.html    # Theatre CRUD management
        ├── screens.html     # Screen capacity CRUD management
        ├── shows.html       # Show schedule CRUD management
        ├── employees.html   # Staff management
        ├── snacks.html      # Concessions management
        ├── bookings.html    # Booking records inspection
        └── analytics.html   # Chart.js visual analytics reports
```

## 🏆 Competitive UX Enhancements (BookMyShow & IMDb Inspired)

Following an in-depth competitive UX review of **BookMyShow** (ticketing flow, seat locking, concession ordering, showtime discovery) and **IMDb** (title intelligence, dual ratings, trailer modals, cast roles, watchlists), CineBook incorporates:

### 1. 🎟️ BookMyShow-Inspired Discovery & Ticketing
- **Horizontal Date Selector Strip (`/theatres`)**: Day-of-week, calendar date, and month pills (`date-strip`, `date-pill`) for quick day-based scheduling.
- **Time Slot Categorization**: Categorizes showtimes into Morning (< 12 PM), Afternoon (12–4 PM), Evening (4–8 PM), and Night (> 8 PM) with interactive filter chips.
- **10-Minute Seat Hold Window**: Displays a live animated countdown timer badge (`booking-countdown-badge`) during the checkout flow to prevent seat squatting and simulate live reservation holding.
- **Persistent Sticky Order Summary Sidebar**: Desktop sticky sidebar maintaining visibility over selected seats, ticket totals, snacks subtotal, and grand total across all checkout steps.
- **Mobile Floating Bottom Sheet**: Compact sticky bottom action bar displaying seat count, live total, and a 1-tap "Continue" button on mobile viewports.
- **Concession Category Filter Pills**: Interactive pills (`All`, `🍿 Popcorn`, `🥤 Beverages`, `🍱 Combos & Sides`) to quickly navigate cinema refreshments.
- **Calendar (.ics) Export**: One-click download of standard iCalendar files directly from the confirmed ticket pass.

### 2. 🎬 IMDb-Inspired Movie Intelligence & Title Pages
- **Global Header Quick Search Auto-Suggest**: Debounced real-time search popover in the top navigation bar with movie poster thumbnails, runtimes, languages, and ratings.
- **Grid vs. List Catalogue Viewing Modes (`/movies`)**: User toggle between modern grid cards and detailed list rows with rich metadata.
- **Dual Ratings Presentation**: Side-by-side display of the verified **IMDb Reference Score** (e.g. `8.1/10` with vote count) and the **CineBook Community Rating** (e.g. `8.5/10` with verified review count).
- **Verified Cast & Crew Breakdown**: Full credit cards presenting actor names and character roles (e.g. *Thalapathy Vijay as Parthiban / Leo Das*).
- **Official Embedded Video Trailers**: Integrated 16:9 responsive video modal (`playTrailer()`) embedding official YouTube trailers with zero layout shift.
- **User Reviews & 1–10 Star Rating Modal**: Interactive feedback modal allowing guests to rate films and post community reviews, dynamically calculating real-time community averages.
- **Session-Persisted Watchlist**: "+ Add to Watchlist" toggle across movie cards, catalogue list rows, and detail pages with an animated live navbar counter badge.
- **Optional TMDB API Enrichment**: Extensible metadata provider in `poster_meta.py` supporting TMDB API keys via `.env` with safe, non-blocking 1.8s timeout fallbacks.

---

## 📌 Demonstration Notes & Academic Scope
- **Concessions Pricing Integrity**: Snacks purchased preserve their historical `Unit_Price` in `BOOKING_SNACK` even if current prices change in `SNACK`.
- **Composite Key Handling**: Audited to support composite primary keys in `SCREEN(Theatre_Id, Screen_No)` and composite foreign keys in `SHOW` and `TICKET`.
- **Zero Schema Alterations**: All 11 normalized MySQL tables (`THEATRE`, `SCREEN`, `MOVIE`, `SHOW`, `CUSTOMER`, `BOOKING`, `TICKET`, `PAYMENT`, `EMPLOYEE`, `SNACK`, `BOOKING_SNACK`) are 100% preserved. Metadata and community reviews leverage maintainable JSON layers without corrupting database integrity.
- **Payment Gateway Simulation**: To maintain academic focus and avoid collecting real financial credentials, payment modes (UPI, Card, Cash) are simulated and write valid records to `PAYMENT`.
- **Graceful Asset Fallback**: Movie posters fall back to SVG representations if external internet connectivity is unavailable.
