from flask import Blueprint, request, jsonify, session
from datetime import datetime, date, timedelta
from decimal import Decimal
from db import get_db_cursor, query_db
from routes.public import format_show_date, format_show_time
from poster_meta import enrich_movies, enrich_movie
from services.user_features import (
    get_watchlist, toggle_watchlist_item, is_in_watchlist,
    get_movie_reviews, add_movie_review
)

api_bp = Blueprint('api', __name__, url_prefix='/api')

def get_seat_tier_price(seat_no):
    """Calculates demo ticket price consistent with database sample tickets."""
    row = seat_no.strip()[:1].upper()
    if row == 'A':
        return Decimal('120.00')
    elif row in ('B', 'C'):
        return Decimal('150.00')
    else:
        return Decimal('180.00')

@api_bp.route('/shows/<int:show_id>/details')
def get_show_details(show_id):
    show = query_db("""
        SELECT s.Show_Id, s.Show_Date, s.Show_Time, s.Screen_No,
               m.Movie_Id, m.Movie_Name, m.Language, m.Duration,
               t.Theatre_Id, t.Theatre_Name, t.Location,
               sc.Capacity
        FROM `SHOW` s
        JOIN MOVIE m ON s.Movie_Id = m.Movie_Id
        JOIN THEATRE t ON s.Theatre_Id = t.Theatre_Id
        JOIN SCREEN sc ON s.Theatre_Id = sc.Theatre_Id AND s.Screen_No = sc.Screen_No
        WHERE s.Show_Id = %s
    """, (show_id,), one=True)

    if not show:
        return jsonify({"error": "Show not found"}), 404

    # Fetch booked seats from TICKET
    booked_rows = query_db("""
        SELECT Seat_No FROM TICKET WHERE Show_Id = %s
    """, (show_id,))

    booked_seats = [r['Seat_No'] for r in booked_rows]
    meta = enrich_movie(show)

    return jsonify({
        "show_id": show['Show_Id'],
        "movie_id": show['Movie_Id'],
        "movie_name": show['Movie_Name'],
        "language": show['Language'],
        "duration": show['Duration'],
        "formatted_duration": meta.get('formatted_duration', f"{show['Duration']}m"),
        "formats": meta.get('formats', ["2D", "Dolby Atmos"]),
        "certificate": meta.get('certificate', "UA"),
        "theatre_id": show['Theatre_Id'],
        "theatre_name": show['Theatre_Name'],
        "location": show['Location'],
        "screen_no": show['Screen_No'],
        "capacity": show['Capacity'],
        "formatted_date": format_show_date(show['Show_Date']),
        "formatted_time": format_show_time(show['Show_Time']),
        "booked_seats": booked_seats
    })

@api_bp.route('/customer/lookup')
def lookup_customer():
    phone = request.args.get('phone', '').strip()
    if not phone:
        return jsonify({"exists": False})

    customer = query_db("SELECT Customer_Id, Customer_Name, Phone FROM CUSTOMER WHERE Phone = %s", (phone,), one=True)
    if customer:
        return jsonify({
            "exists": True,
            "customer_id": customer['Customer_Id'],
            "customer_name": customer['Customer_Name']
        })
    return jsonify({"exists": False})

@api_bp.route('/movies/quick-search')
def quick_search_movies():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])

    movies_raw = query_db("""
        SELECT Movie_Id, Movie_Name, Language, Duration
        FROM MOVIE
        WHERE LOWER(Movie_Name) LIKE %s OR LOWER(Language) LIKE %s
        ORDER BY Movie_Name
        LIMIT 6
    """, (f"%{q.lower()}%", f"%{q.lower()}%"))

    enriched = enrich_movies(movies_raw)
    results = []
    for m in enriched:
        results.append({
            "id": m['Movie_Id'],
            "title": m['Movie_Name'],
            "language": m['Language'],
            "duration": m.get('formatted_duration'),
            "rating": m.get('rating'),
            "poster_url": m.get('poster_url'),
            "genre": m.get('genre'),
            "url": f"/movie/{m['Movie_Id']}"
        })
    return jsonify(results)

@api_bp.route('/watchlist', methods=['GET'])
def get_user_watchlist():
    return jsonify({"watchlist": get_watchlist()})

@api_bp.route('/watchlist/toggle', methods=['POST'])
def toggle_watchlist():
    data = request.get_json(silent=True) or {}
    movie_id = data.get('movie_id')
    if not movie_id:
        return jsonify({"error": "Missing movie_id"}), 400

    added, count = toggle_watchlist_item(movie_id)
    return jsonify({
        "in_watchlist": added,
        "count": count,
        "message": "Added to your Watchlist" if added else "Removed from your Watchlist"
    })

@api_bp.route('/reviews/<int:movie_id>', methods=['GET', 'POST'])
def handle_reviews(movie_id):
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        user_name = (data.get('user_name') or '').strip()
        rating = data.get('rating')
        review_text = (data.get('review_text') or '').strip()

        if not rating or not (1 <= int(rating) <= 10):
            return jsonify({"error": "Rating must be an integer between 1 and 10"}), 400
        if not review_text or len(review_text) < 5:
            return jsonify({"error": "Review must be at least 5 characters"}), 400

        # Fetch movie name
        movie = query_db("SELECT Movie_Name FROM MOVIE WHERE Movie_Id = %s", (movie_id,), one=True)
        movie_name = movie['Movie_Name'] if movie else f"Movie #{movie_id}"

        review = add_movie_review(movie_id, movie_name, user_name, rating, review_text)
        summary = get_movie_reviews(movie_id)
        return jsonify({
            "success": True,
            "review": review,
            "average_rating": summary['average_rating'],
            "review_count": summary['count'],
            "message": "Thank you for your review!"
        }), 201

    # GET reviews
    data = get_movie_reviews(movie_id)
    return jsonify(data)

@api_bp.route('/booking/submit', methods=['POST'])
def submit_booking():
    data = request.get_json(silent=True) or {}
    show_id = data.get('show_id')
    seats = data.get('seats', [])
    customer_name = (data.get('customer_name') or '').strip()
    customer_phone = (data.get('customer_phone') or '').strip()
    payment_mode = (data.get('payment_mode') or 'UPI').strip()
    snack_quantities = data.get('snacks', {})

    # Validation
    if not show_id:
        return jsonify({"error": "Missing show identifier"}), 400
    if not seats or not isinstance(seats, list):
        return jsonify({"error": "At least one seat must be selected"}), 400
    if not customer_name or len(customer_name) < 2:
        return jsonify({"error": "Customer name must be at least 2 characters"}), 400
    if not customer_phone or not customer_phone.isdigit() or len(customer_phone) != 10:
        return jsonify({"error": "A valid 10-digit phone number is required"}), 400

    # Start atomic database transaction
    try:
        with get_db_cursor(commit=True, dictionary=True) as (conn, cursor):
            # 1. Verify show exists
            cursor.execute("SELECT Show_Id FROM `SHOW` WHERE Show_Id = %s", (show_id,))
            show_row = cursor.fetchone()
            if not show_row:
                return jsonify({"error": "Show does not exist"}), 404

            # 2. Check for seat conflicts (Lock rows or check uniqueness within this Show_Id)
            placeholders = ', '.join(['%s'] * len(seats))
            check_sql = f"SELECT Seat_No FROM TICKET WHERE Show_Id = %s AND Seat_No IN ({placeholders}) FOR UPDATE"
            cursor.execute(check_sql, [show_id] + seats)
            conflicts = [r['Seat_No'] for r in cursor.fetchall()]

            if conflicts:
                conn.rollback()
                return jsonify({
                    "error": "Seat conflict",
                    "conflicts": conflicts,
                    "message": f"Seat(s) {', '.join(conflicts)} have just been reserved by another customer. Please select other seats."
                }), 409

            # 3. Calculate tickets subtotal
            ticket_records = []
            ticket_subtotal = Decimal('0.00')
            for seat in seats:
                price = get_seat_tier_price(seat)
                ticket_records.append((seat, price))
                ticket_subtotal += price

            # 4. Calculate snacks subtotal with database prices
            snack_records = []
            snack_subtotal = Decimal('0.00')
            for s_id_str, qty in snack_quantities.items():
                try:
                    snack_id = int(s_id_str)
                    qty = int(qty)
                except (ValueError, TypeError):
                    continue

                if qty > 0:
                    cursor.execute("SELECT Snack_Id, Price FROM SNACK WHERE Snack_Id = %s", (snack_id,))
                    s_row = cursor.fetchone()
                    if s_row:
                        u_price = s_row['Price']
                        snack_records.append((snack_id, qty, u_price))
                        snack_subtotal += (Decimal(qty) * u_price)

            # Grand Total
            grand_total = ticket_subtotal + snack_subtotal

            # 5. Customer Handling: lookup or insert
            cursor.execute("SELECT Customer_Id FROM CUSTOMER WHERE Phone = %s", (customer_phone,))
            cust_row = cursor.fetchone()
            if cust_row:
                customer_id = cust_row['Customer_Id']
                cursor.execute("UPDATE CUSTOMER SET Customer_Name = %s WHERE Customer_Id = %s", (customer_name, customer_id))
            else:
                cursor.execute("INSERT INTO CUSTOMER (Customer_Name, Phone) VALUES (%s, %s)", (customer_name, customer_phone))
                customer_id = cursor.lastrowid

            # 6. Insert BOOKING record
            cursor.execute("""
                INSERT INTO BOOKING (Booking_Date, Total_Amount, Customer_Id, Show_Id)
                VALUES (NOW(), %s, %s, %s)
            """, (grand_total, customer_id, show_id))
            booking_id = cursor.lastrowid

            # 7. Insert TICKET records for each seat
            for seat_no, price in ticket_records:
                cursor.execute("""
                    INSERT INTO TICKET (Seat_No, Price, Booking_Id, Show_Id)
                    VALUES (%s, %s, %s, %s)
                """, (seat_no, price, booking_id, show_id))

            # 8. Insert BOOKING_SNACK records
            for snack_id, qty, u_price in snack_records:
                cursor.execute("""
                    INSERT INTO BOOKING_SNACK (Booking_Id, Snack_Id, Quantity, Unit_Price)
                    VALUES (%s, %s, %s, %s)
                """, (booking_id, snack_id, qty, u_price))

            # 9. Insert PAYMENT record
            valid_modes = ('UPI', 'Card', 'Cash')
            mode_clean = payment_mode if payment_mode in valid_modes else 'UPI'
            cursor.execute("""
                INSERT INTO PAYMENT (Amount, Mode, Booking_Id)
                VALUES (%s, %s, %s)
            """, (grand_total, mode_clean, booking_id))

        return jsonify({
            "success": True,
            "booking_id": booking_id,
            "total_amount": float(grand_total)
        })

    except Exception as e:
        return jsonify({"error": "Failed to process booking", "message": str(e)}), 500

@api_bp.route('/admin/analytics-data')
def get_analytics_data():
    ticket_rev = query_db("SELECT COALESCE(SUM(Price), 0) AS total FROM TICKET", one=True)['total']
    snack_rev = query_db("SELECT COALESCE(SUM(Quantity * Unit_Price), 0) AS total FROM BOOKING_SNACK", one=True)['total']
    booking_rev = query_db("SELECT COALESCE(SUM(Total_Amount), 0) AS total FROM BOOKING", one=True)['total']

    movie_stats = query_db("""
        SELECT m.Movie_Name, COUNT(t.Ticket_No) AS ticket_count
        FROM MOVIE m
        LEFT JOIN `SHOW` s ON m.Movie_Id = s.Movie_Id
        LEFT JOIN TICKET t ON s.Show_Id = t.Show_Id
        GROUP BY m.Movie_Id, m.Movie_Name
        ORDER BY ticket_count DESC
    """)

    theatre_stats = query_db("""
        SELECT th.Theatre_Name, COUNT(b.Booking_Id) AS booking_count
        FROM THEATRE th
        LEFT JOIN `SHOW` s ON th.Theatre_Id = s.Theatre_Id
        LEFT JOIN BOOKING b ON s.Show_Id = b.Show_Id
        GROUP BY th.Theatre_Id, th.Theatre_Name
        ORDER BY booking_count DESC
    """)

    snack_stats = query_db("""
        SELECT sn.Snack_Name, COALESCE(SUM(bs.Quantity), 0) AS total_sold
        FROM SNACK sn
        LEFT JOIN BOOKING_SNACK bs ON sn.Snack_Id = bs.Snack_Id
        GROUP BY sn.Snack_Id, sn.Snack_Name
        ORDER BY total_sold DESC
    """)

    daily_trends = query_db("""
        SELECT DATE(Booking_Date) AS b_date, SUM(Total_Amount) AS daily_rev
        FROM BOOKING
        GROUP BY DATE(Booking_Date)
        ORDER BY b_date ASC
    """)

    return jsonify({
        "ticket_revenue": float(ticket_rev),
        "snack_revenue": float(snack_rev),
        "total_revenue": float(booking_rev),
        "movies": [{"name": m['Movie_Name'], "tickets": m['ticket_count']} for m in movie_stats],
        "theatres": [{"name": t['Theatre_Name'], "bookings": t['booking_count']} for t in theatre_stats],
        "snacks": [{"name": s['Snack_Name'], "sold_quantity": int(s['total_sold'])} for s in snack_stats],
        "daily_trends": [{"date": str(d['b_date']), "revenue": float(d['daily_rev'])} for d in daily_trends]
    })
