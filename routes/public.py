from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from datetime import datetime, date, timedelta
from db import query_db
from poster_meta import enrich_movies, enrich_movie
from services.user_features import get_watchlist, is_in_watchlist, get_movie_reviews

public_bp = Blueprint('public', __name__)

def format_show_time(val):
    if val is None:
        return ""
    if isinstance(val, timedelta):
        total_seconds = int(val.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        t = datetime.strptime(f"{hours:02d}:{minutes:02d}", "%H:%M")
        return t.strftime("%I:%M %p")
    if hasattr(val, 'strftime'):
        return val.strftime("%I:%M %p")
    return str(val)

def format_show_date(val):
    if val is None:
        return ""
    if hasattr(val, 'strftime'):
        return val.strftime("%a, %b %d, %Y")
    return str(val)

@public_bp.app_template_filter('time_fmt')
def jinja_time_fmt(val):
    return format_show_time(val)

@public_bp.app_template_filter('date_fmt')
def jinja_date_fmt(val):
    return format_show_date(val)

@public_bp.app_template_filter('currency')
def jinja_currency(val):
    try:
        return f"₹{float(val):,.2f}"
    except (ValueError, TypeError):
        return f"₹{val}"

def get_time_slot_category(val):
    """Categorizes showtime into Morning, Afternoon, Evening, or Night for BookMyShow-style filtering."""
    if val is None:
        return "all"
    hrs = 0
    if isinstance(val, timedelta):
        hrs = int(val.total_seconds()) // 3600
    elif hasattr(val, 'hour'):
        hrs = val.hour
    
    if hrs < 12:
        return "morning"
    elif 12 <= hrs < 16:
        return "afternoon"
    elif 16 <= hrs < 20:
        return "evening"
    else:
        return "night"

# --------------------------------------------------------------------------
# Home Page
# --------------------------------------------------------------------------
@public_bp.route('/')
def home():
    # 1. Fetch all movies from MOVIE table
    movies_raw = query_db("""
        SELECT Movie_Id, Movie_Name, Language, Duration
        FROM MOVIE
        ORDER BY Movie_Name
    """)
    movies = enrich_movies(movies_raw)

    # 2. Fetch theatres with screen count
    theatres = query_db("""
        SELECT t.Theatre_Id, t.Theatre_Name, t.Location, COUNT(s.Screen_No) AS screen_count
        FROM THEATRE t
        LEFT JOIN SCREEN s ON t.Theatre_Id = s.Theatre_Id
        GROUP BY t.Theatre_Id, t.Theatre_Name, t.Location
        ORDER BY t.Theatre_Name
    """)

    # 3. Fetch upcoming shows
    upcoming_shows = query_db("""
        SELECT s.Show_Id, s.Show_Date, s.Show_Time, s.Screen_No,
               m.Movie_Id, m.Movie_Name, m.Language, m.Duration,
               t.Theatre_Id, t.Theatre_Name, t.Location,
               sc.Capacity
        FROM `SHOW` s
        JOIN MOVIE m ON s.Movie_Id = m.Movie_Id
        JOIN THEATRE t ON s.Theatre_Id = t.Theatre_Id
        JOIN SCREEN sc ON s.Theatre_Id = sc.Theatre_Id AND s.Screen_No = sc.Screen_No
        ORDER BY s.Show_Date, s.Show_Time
        LIMIT 8
    """)

    # Aggregate stats for hero section
    stats = {
        "movies_count": len(movies),
        "theatres_count": len(theatres),
        "shows_count": len(upcoming_shows)
    }

    # Spotlight Hero movie
    spotlight = movies[0] if movies else None
    watchlist_ids = get_watchlist()

    return render_template('index.html',
                           movies=movies,
                           theatres=theatres,
                           upcoming_shows=upcoming_shows,
                           stats=stats,
                           spotlight=spotlight,
                           watchlist_ids=watchlist_ids)

# --------------------------------------------------------------------------
# Movie Catalogue
# --------------------------------------------------------------------------
@public_bp.route('/movies')
def movies_catalogue():
    search_q = request.args.get('q', '').strip()
    lang_q = request.args.get('lang', '').strip()
    theatre_id = request.args.get('theatre_id', type=int)
    sort_q = request.args.get('sort', 'title_asc').strip()
    watchlist_only = request.args.get('watchlist', type=int)
    view_mode = request.args.get('view', 'grid').strip() # grid or list

    conditions = []
    params = []

    if search_q:
        conditions.append("LOWER(m.Movie_Name) LIKE %s")
        params.append(f"%{search_q.lower()}%")

    if lang_q:
        conditions.append("m.Language = %s")
        params.append(lang_q)

    join_theatre_sql = ""
    if theatre_id:
        join_theatre_sql = "JOIN `SHOW` sh ON m.Movie_Id = sh.Movie_Id"
        conditions.append("sh.Theatre_Id = %s")
        params.append(theatre_id)

    watchlist_ids = get_watchlist()
    if watchlist_only and watchlist_ids:
        placeholders = ', '.join(['%s'] * len(watchlist_ids))
        conditions.append(f"m.Movie_Id IN ({placeholders})")
        params.extend(watchlist_ids)
    elif watchlist_only and not watchlist_ids:
        # User requested watchlist but has none
        conditions.append("1 = 0")

    order_clause = "ORDER BY m.Movie_Name ASC"
    if sort_q == 'title_desc':
        order_clause = "ORDER BY m.Movie_Name DESC"
    elif sort_q == 'duration_asc':
        order_clause = "ORDER BY m.Duration ASC"
    elif sort_q == 'duration_desc':
        order_clause = "ORDER BY m.Duration DESC"

    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"""
        SELECT DISTINCT m.Movie_Id, m.Movie_Name, m.Language, m.Duration
        FROM MOVIE m
        {join_theatre_sql}
        {where_sql}
        {order_clause}
    """

    movies_raw = query_db(sql, params)
    movies = enrich_movies(movies_raw)

    languages = query_db("SELECT DISTINCT Language FROM MOVIE ORDER BY Language")
    theatres = query_db("SELECT Theatre_Id, Theatre_Name, Location FROM THEATRE ORDER BY Theatre_Name")

    # Build active filter chips for user feedback
    active_filters = []
    if search_q:
        active_filters.append({"type": "q", "label": f"Title: '{search_q}'"})
    if lang_q:
        active_filters.append({"type": "lang", "label": f"Language: {lang_q}"})
    if theatre_id:
        t_name = next((t['Theatre_Name'] for t in theatres if t['Theatre_Id'] == theatre_id), "Selected Venue")
        active_filters.append({"type": "theatre_id", "label": f"Theatre: {t_name}"})
    if watchlist_only:
        active_filters.append({"type": "watchlist", "label": "Watchlist Only"})

    return render_template('movies.html',
                           movies=movies,
                           languages=[l['Language'] for l in languages],
                           theatres=theatres,
                           selected_lang=lang_q,
                           selected_theatre=theatre_id,
                           search_q=search_q,
                           sort_q=sort_q,
                           view_mode=view_mode,
                           watchlist_only=watchlist_only,
                           watchlist_ids=watchlist_ids,
                           active_filters=active_filters)

# --------------------------------------------------------------------------
# Movie Details View
# --------------------------------------------------------------------------
@public_bp.route('/movie/<int:movie_id>')
def movie_details(movie_id):
    movie_raw = query_db("""
        SELECT Movie_Id, Movie_Name, Language, Duration
        FROM MOVIE
        WHERE Movie_Id = %s
    """, (movie_id,), one=True)

    if not movie_raw:
        flash("Movie not found.", "danger")
        return redirect(url_for('public.movies_catalogue'))

    movie = enrich_movie(movie_raw)

    # Fetch all shows for this movie with theatre info
    shows = query_db("""
        SELECT s.Show_Id, s.Show_Date, s.Show_Time, s.Screen_No,
               t.Theatre_Id, t.Theatre_Name, t.Location,
               sc.Capacity
        FROM `SHOW` s
        JOIN THEATRE t ON s.Theatre_Id = t.Theatre_Id
        JOIN SCREEN sc ON s.Theatre_Id = sc.Theatre_Id AND s.Screen_No = sc.Screen_No
        WHERE s.Movie_Id = %s
        ORDER BY s.Show_Date, s.Show_Time
    """, (movie_id,))

    # Group shows by Date and Theatre with time slot categorization
    grouped_shows = {}
    for s in shows:
        d = s['Show_Date']
        if d not in grouped_shows:
            grouped_shows[d] = {}
        t_id = s['Theatre_Id']
        if t_id not in grouped_shows[d]:
            grouped_shows[d][t_id] = {
                "theatre_name": s['Theatre_Name'],
                "location": s['Location'],
                "shows": []
            }
        s['time_slot'] = get_time_slot_category(s['Show_Time'])
        grouped_shows[d][t_id]["shows"].append(s)

    # Fetch community reviews and rating
    reviews_data = get_movie_reviews(movie_id)
    in_user_watchlist = is_in_watchlist(movie_id)

    return render_template('movie_detail.html',
                           movie=movie,
                           grouped_shows=grouped_shows,
                           total_shows=len(shows),
                           reviews=reviews_data['reviews'],
                           community_rating=reviews_data['average_rating'],
                           review_count=reviews_data['count'],
                           in_watchlist=in_user_watchlist)

# --------------------------------------------------------------------------
# Theatres & Showtime Discovery
# --------------------------------------------------------------------------
@public_bp.route('/theatres')
def theatres_discovery():
    theatre_id = request.args.get('theatre_id', type=int)
    movie_id = request.args.get('movie_id', type=int)
    date_str = request.args.get('date', '').strip()
    time_slot = request.args.get('time_slot', '').strip()

    all_theatres = query_db("SELECT Theatre_Id, Theatre_Name, Location FROM THEATRE ORDER BY Theatre_Name")
    all_movies = query_db("SELECT Movie_Id, Movie_Name FROM MOVIE ORDER BY Movie_Name")
    available_dates = query_db("SELECT DISTINCT Show_Date FROM `SHOW` ORDER BY Show_Date")

    conditions = []
    params = []

    if theatre_id:
        conditions.append("s.Theatre_Id = %s")
        params.append(theatre_id)
    if movie_id:
        conditions.append("s.Movie_Id = %s")
        params.append(movie_id)
    if date_str:
        conditions.append("s.Show_Date = %s")
        params.append(date_str)

    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    shows_raw = query_db(f"""
        SELECT s.Show_Id, s.Show_Date, s.Show_Time, s.Screen_No,
               m.Movie_Id, m.Movie_Name, m.Language, m.Duration,
               t.Theatre_Id, t.Theatre_Name, t.Location,
               sc.Capacity
        FROM `SHOW` s
        JOIN MOVIE m ON s.Movie_Id = m.Movie_Id
        JOIN THEATRE t ON s.Theatre_Id = t.Theatre_Id
        JOIN SCREEN sc ON s.Theatre_Id = sc.Theatre_Id AND s.Screen_No = sc.Screen_No
        {where_sql}
        ORDER BY s.Show_Date, s.Show_Time, t.Theatre_Name
    """, params)

    shows = []
    for s in shows_raw:
        slot = get_time_slot_category(s['Show_Time'])
        if time_slot and slot != time_slot:
            continue
        s['time_slot'] = slot
        shows.append(s)

    # Format structured date pills for BookMyShow-style horizontal strip
    date_pills = []
    for row in available_dates:
        d = row['Show_Date']
        d_str = str(d)
        is_selected = (date_str == d_str)
        date_pills.append({
            "date_str": d_str,
            "day_name": d.strftime("%a").upper(),
            "day_num": d.strftime("%d"),
            "month_name": d.strftime("%b").upper(),
            "selected": is_selected
        })

    return render_template('theatres.html',
                           theatres=all_theatres,
                           movies=all_movies,
                           date_pills=date_pills,
                           shows=shows,
                           selected_theatre=theatre_id,
                           selected_movie=movie_id,
                           selected_date=date_str,
                           selected_slot=time_slot)

# --------------------------------------------------------------------------
# Interactive Multi-step Booking Experience
# --------------------------------------------------------------------------
@public_bp.route('/booking')
def booking_flow():
    show_id = request.args.get('show_id', type=int)

    available_shows = query_db("""
        SELECT s.Show_Id, s.Show_Date, s.Show_Time, s.Screen_No,
               m.Movie_Name, m.Language,
               t.Theatre_Name, t.Location
        FROM `SHOW` s
        JOIN MOVIE m ON s.Movie_Id = m.Movie_Id
        JOIN THEATRE t ON s.Theatre_Id = t.Theatre_Id
        ORDER BY s.Show_Date, s.Show_Time
    """)

    snacks = query_db("SELECT Snack_Id, Snack_Name, Price FROM SNACK ORDER BY Snack_Id")

    # Add category tags to snacks
    for s in snacks:
        name = s['Snack_Name'].lower()
        if 'popcorn' in name:
            s['category'] = 'Popcorn'
        elif 'coke' in name or 'drink' in name or 'water' in name:
            s['category'] = 'Beverages'
        elif 'combo' in name or 'meal' in name:
            s['category'] = 'Combos'
        else:
            s['category'] = 'Snacks & Bites'

    return render_template('booking.html',
                           show_id=show_id,
                           available_shows=available_shows,
                           snacks=snacks)

# --------------------------------------------------------------------------
# Booking Confirmation Ticket Pass
# --------------------------------------------------------------------------
@public_bp.route('/booking/confirmation/<int:booking_id>')
def booking_confirmation(booking_id):
    booking = query_db("""
        SELECT b.Booking_Id, b.Booking_Date, b.Total_Amount,
               c.Customer_Id, c.Customer_Name, c.Phone,
               s.Show_Id, s.Show_Date, s.Show_Time, s.Screen_No,
               m.Movie_Name, m.Language, m.Duration,
               t.Theatre_Name, t.Location,
               p.Amount AS Payment_Amount, p.Mode AS Payment_Mode
        FROM BOOKING b
        JOIN CUSTOMER c ON b.Customer_Id = c.Customer_Id
        JOIN `SHOW` s ON b.Show_Id = s.Show_Id
        JOIN MOVIE m ON s.Movie_Id = m.Movie_Id
        JOIN THEATRE t ON s.Theatre_Id = t.Theatre_Id
        LEFT JOIN PAYMENT p ON b.Booking_Id = p.Booking_Id
        WHERE b.Booking_Id = %s
    """, (booking_id,), one=True)

    if not booking:
        flash("Booking reference not found.", "danger")
        return redirect(url_for('public.home'))

    tickets = query_db("""
        SELECT Ticket_No, Seat_No, Price
        FROM TICKET
        WHERE Booking_Id = %s
        ORDER BY Seat_No
    """, (booking_id,))

    snacks = query_db("""
        SELECT bs.Quantity, bs.Unit_Price, (bs.Quantity * bs.Unit_Price) AS Subtotal,
               s.Snack_Name
        FROM BOOKING_SNACK bs
        JOIN SNACK s ON bs.Snack_Id = s.Snack_Id
        WHERE bs.Booking_Id = %s
    """, (booking_id,))

    ticket_subtotal = sum(t['Price'] for t in tickets)
    snack_subtotal = sum(s['Subtotal'] for s in snacks)

    return render_template('booking_success.html',
                           booking=booking,
                           tickets=tickets,
                           snacks=snacks,
                           ticket_subtotal=ticket_subtotal,
                           snack_subtotal=snack_subtotal)

# --------------------------------------------------------------------------
# My Bookings Lookup
# --------------------------------------------------------------------------
@public_bp.route('/my-bookings', methods=['GET', 'POST'])
def my_bookings():
    booking_id = request.values.get('booking_id', '').strip()
    phone = request.values.get('phone', '').strip()

    bookings_result = []
    searched = False

    if booking_id or phone:
        searched = True
        params = []
        conditions = []

        if booking_id:
            conditions.append("b.Booking_Id = %s")
            params.append(booking_id)

        if phone:
            conditions.append("c.Phone = %s")
            params.append(phone)

        sql = f"""
            SELECT b.Booking_Id, b.Booking_Date, b.Total_Amount,
                   c.Customer_Name, c.Phone,
                   s.Show_Date, s.Show_Time, s.Screen_No,
                   m.Movie_Name, m.Language,
                   t.Theatre_Name, t.Location,
                   p.Mode AS Payment_Mode
            FROM BOOKING b
            JOIN CUSTOMER c ON b.Customer_Id = c.Customer_Id
            JOIN `SHOW` s ON b.Show_Id = s.Show_Id
            JOIN MOVIE m ON s.Movie_Id = m.Movie_Id
            JOIN THEATRE t ON s.Theatre_Id = t.Theatre_Id
            LEFT JOIN PAYMENT p ON b.Booking_Id = p.Booking_Id
            WHERE {" AND ".join(conditions)}
            ORDER BY b.Booking_Date DESC
        """
        raw_list = query_db(sql, params)

        for item in raw_list:
            b_id = item['Booking_Id']
            tickets = query_db("SELECT Seat_No, Price FROM TICKET WHERE Booking_Id = %s", (b_id,))
            snacks = query_db("""
                SELECT bs.Quantity, bs.Unit_Price, s.Snack_Name
                FROM BOOKING_SNACK bs
                JOIN SNACK s ON bs.Snack_Id = s.Snack_Id
                WHERE bs.Booking_Id = %s
            """, (b_id,))
            item['tickets'] = tickets
            item['seats_str'] = ", ".join([t['Seat_No'] for t in tickets])
            item['snacks'] = snacks
            bookings_result.append(item)

        if not bookings_result:
            flash("No bookings found matching your search details.", "warning")

    return render_template('my_bookings.html',
                           searched=searched,
                           booking_id=booking_id,
                           phone=phone,
                           bookings=bookings_result)
