from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
from werkzeug.security import check_password_hash
from decimal import Decimal
from config import Config
from db import query_db, execute_db

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash("Please sign in to access the CineBook Admin Dashboard.", "warning")
            return redirect(url_for('admin.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# --------------------------------------------------------------------------
# Admin Authentication
# --------------------------------------------------------------------------
@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        # Validate against configured credentials in environment
        is_user_valid = (username == Config.ADMIN_USERNAME)
        is_pw_valid = False

        if Config.ADMIN_PASSWORD_HASH:
            try:
                is_pw_valid = check_password_hash(Config.ADMIN_PASSWORD_HASH, password)
            except Exception:
                is_pw_valid = (password == Config.ADMIN_DEFAULT_PASSWORD)
        else:
            is_pw_valid = (password == Config.ADMIN_DEFAULT_PASSWORD)

        if is_user_valid and is_pw_valid:
            session['admin_logged_in'] = True
            session['admin_user'] = username
            flash(f"Welcome back, Administrator {username}!", "success")
            next_url = request.args.get('next') or url_for('admin.dashboard')
            return redirect(next_url)
        else:
            flash("Invalid administrator username or password.", "danger")

    return render_template('admin/login.html')

@admin_bp.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_user', None)
    flash("You have successfully signed out of the admin panel.", "info")
    return redirect(url_for('admin.login'))

# --------------------------------------------------------------------------
# Dashboard Overview
# --------------------------------------------------------------------------
@admin_bp.route('/')
@admin_required
def dashboard():
    # 1. Real SQL aggregate metrics
    movies_cnt = query_db("SELECT COUNT(*) AS c FROM MOVIE", one=True)['c']
    theatres_cnt = query_db("SELECT COUNT(*) AS c FROM THEATRE", one=True)['c']
    customers_cnt = query_db("SELECT COUNT(*) AS c FROM CUSTOMER", one=True)['c']
    bookings_cnt = query_db("SELECT COUNT(*) AS c FROM BOOKING", one=True)['c']

    # Revenue metrics (avoiding Cartesian multiplication by using dedicated queries)
    ticket_rev = query_db("SELECT COALESCE(SUM(Price), 0) AS total FROM TICKET", one=True)['total']
    snack_rev = query_db("SELECT COALESCE(SUM(Quantity * Unit_Price), 0) AS total FROM BOOKING_SNACK", one=True)['total']
    total_rev = query_db("SELECT COALESCE(SUM(Total_Amount), 0) AS total FROM BOOKING", one=True)['total']
    avg_booking = query_db("SELECT COALESCE(AVG(Total_Amount), 0) AS val FROM BOOKING", one=True)['val']

    # 2. Recent Bookings list
    recent_bookings = query_db("""
        SELECT b.Booking_Id, b.Booking_Date, b.Total_Amount,
               c.Customer_Name, c.Phone,
               m.Movie_Name,
               t.Theatre_Name,
               p.Mode AS Payment_Mode
        FROM BOOKING b
        JOIN CUSTOMER c ON b.Customer_Id = c.Customer_Id
        JOIN `SHOW` s ON b.Show_Id = s.Show_Id
        JOIN MOVIE m ON s.Movie_Id = m.Movie_Id
        JOIN THEATRE t ON s.Theatre_Id = t.Theatre_Id
        LEFT JOIN PAYMENT p ON b.Booking_Id = p.Booking_Id
        ORDER BY b.Booking_Date DESC
        LIMIT 6
    """)

    # 3. Popular Movies by tickets
    top_movies = query_db("""
        SELECT m.Movie_Id, m.Movie_Name, m.Language,
               COUNT(t.Ticket_No) AS tickets_sold,
               COALESCE(SUM(t.Price), 0) AS ticket_revenue
        FROM MOVIE m
        LEFT JOIN `SHOW` s ON m.Movie_Id = s.Movie_Id
        LEFT JOIN TICKET t ON s.Show_Id = t.Show_Id
        GROUP BY m.Movie_Id, m.Movie_Name, m.Language
        ORDER BY tickets_sold DESC
        LIMIT 5
    """)

    metrics = {
        "movies": movies_cnt,
        "theatres": theatres_cnt,
        "customers": customers_cnt,
        "bookings": bookings_cnt,
        "ticket_revenue": ticket_rev,
        "snack_revenue": snack_rev,
        "total_revenue": total_rev,
        "avg_booking": avg_booking
    }

    return render_template('admin/dashboard.html',
                           metrics=metrics,
                           recent_bookings=recent_bookings,
                           top_movies=top_movies)

# --------------------------------------------------------------------------
# Movie Management CRUD
# --------------------------------------------------------------------------
@admin_bp.route('/movies', methods=['GET', 'POST'])
@admin_required
def manage_movies():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('movie_name', '').strip()
            lang = request.form.get('language', '').strip()
            duration = request.form.get('duration', type=int)

            if not name or not lang or not duration or duration <= 0:
                flash("Please provide valid movie name, language, and positive duration.", "danger")
            else:
                execute_db("INSERT INTO MOVIE (Movie_Name, Language, Duration) VALUES (%s, %s, %s)", (name, lang, duration))
                flash(f"Movie '{name}' was added successfully.", "success")

        elif action == 'edit':
            m_id = request.form.get('movie_id', type=int)
            name = request.form.get('movie_name', '').strip()
            lang = request.form.get('language', '').strip()
            duration = request.form.get('duration', type=int)

            if not m_id or not name or not lang or not duration or duration <= 0:
                flash("Invalid movie update parameters.", "danger")
            else:
                execute_db("UPDATE MOVIE SET Movie_Name = %s, Language = %s, Duration = %s WHERE Movie_Id = %s",
                           (name, lang, duration, m_id))
                flash(f"Movie '{name}' updated successfully.", "success")

        return redirect(url_for('admin.manage_movies'))

    # GET: List movies with show count
    movies = query_db("""
        SELECT m.Movie_Id, m.Movie_Name, m.Language, m.Duration,
               COUNT(s.Show_Id) AS show_count
        FROM MOVIE m
        LEFT JOIN `SHOW` s ON m.Movie_Id = s.Movie_Id
        GROUP BY m.Movie_Id, m.Movie_Name, m.Language, m.Duration
        ORDER BY m.Movie_Name
    """)
    return render_template('admin/movies.html', movies=movies)

@admin_bp.route('/movies/delete/<int:movie_id>', methods=['POST'])
@admin_required
def delete_movie(movie_id):
    # Check if movie has existing shows
    existing = query_db("SELECT COUNT(*) AS c FROM `SHOW` WHERE Movie_Id = %s", (movie_id,), one=True)['c']
    if existing > 0:
        flash(f"Cannot delete movie: It has {existing} active showtime(s) scheduled. Remove or reschedule those shows first.", "danger")
    else:
        execute_db("DELETE FROM MOVIE WHERE Movie_Id = %s", (movie_id,))
        flash("Movie deleted successfully.", "success")
    return redirect(url_for('admin.manage_movies'))

# --------------------------------------------------------------------------
# Theatre & Screen Management CRUD
# --------------------------------------------------------------------------
@admin_bp.route('/theatres', methods=['GET', 'POST'])
@admin_required
def manage_theatres():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('theatre_name', '').strip()
            location = request.form.get('location', '').strip()
            if not name or not location:
                flash("Theatre name and location are required.", "danger")
            else:
                execute_db("INSERT INTO THEATRE (Theatre_Name, Location) VALUES (%s, %s)", (name, location))
                flash(f"Theatre '{name}' added successfully.", "success")

        elif action == 'edit':
            t_id = request.form.get('theatre_id', type=int)
            name = request.form.get('theatre_name', '').strip()
            location = request.form.get('location', '').strip()
            if not t_id or not name or not location:
                flash("Invalid theatre update data.", "danger")
            else:
                execute_db("UPDATE THEATRE SET Theatre_Name = %s, Location = %s WHERE Theatre_Id = %s", (name, location, t_id))
                flash(f"Theatre '{name}' updated successfully.", "success")

        return redirect(url_for('admin.manage_theatres'))

    theatres = query_db("""
        SELECT t.Theatre_Id, t.Theatre_Name, t.Location,
               COUNT(DISTINCT s.Screen_No) AS screen_count,
               COUNT(DISTINCT sh.Show_Id) AS show_count,
               COUNT(DISTINCT e.Employee_Id) AS employee_count
        FROM THEATRE t
        LEFT JOIN SCREEN s ON t.Theatre_Id = s.Theatre_Id
        LEFT JOIN `SHOW` sh ON t.Theatre_Id = sh.Theatre_Id
        LEFT JOIN EMPLOYEE e ON t.Theatre_Id = e.Theatre_Id
        GROUP BY t.Theatre_Id, t.Theatre_Name, t.Location
        ORDER BY t.Theatre_Name
    """)
    return render_template('admin/theatres.html', theatres=theatres)

@admin_bp.route('/theatres/delete/<int:theatre_id>', methods=['POST'])
@admin_required
def delete_theatre(theatre_id):
    shows = query_db("SELECT COUNT(*) AS c FROM `SHOW` WHERE Theatre_Id = %s", (theatre_id,), one=True)['c']
    screens = query_db("SELECT COUNT(*) AS c FROM SCREEN WHERE Theatre_Id = %s", (theatre_id,), one=True)['c']
    employees = query_db("SELECT COUNT(*) AS c FROM EMPLOYEE WHERE Theatre_Id = %s", (theatre_id,), one=True)['c']

    if shows > 0 or screens > 0 or employees > 0:
        flash(f"Cannot delete theatre: It still contains {screens} screen(s), {shows} show(s), or {employees} employee(s). Remove related records first.", "danger")
    else:
        execute_db("DELETE FROM THEATRE WHERE Theatre_Id = %s", (theatre_id,))
        flash("Theatre deleted successfully.", "success")
    return redirect(url_for('admin.manage_theatres'))

@admin_bp.route('/screens', methods=['GET', 'POST'])
@admin_required
def manage_screens():
    if request.method == 'POST':
        action = request.form.get('action')
        theatre_id = request.form.get('theatre_id', type=int)
        screen_no = request.form.get('screen_no', type=int)
        capacity = request.form.get('capacity', type=int)

        if not theatre_id or not screen_no or not capacity or capacity <= 0 or screen_no <= 0:
            flash("Valid Theatre, positive Screen Number, and positive Capacity are required.", "danger")
        elif action == 'add':
            # Check duplicate primary key (Theatre_Id, Screen_No)
            dup = query_db("SELECT 1 FROM SCREEN WHERE Theatre_Id = %s AND Screen_No = %s", (theatre_id, screen_no), one=True)
            if dup:
                flash(f"Screen {screen_no} already exists in this theatre.", "danger")
            else:
                execute_db("INSERT INTO SCREEN (Theatre_Id, Screen_No, Capacity) VALUES (%s, %s, %s)",
                           (theatre_id, screen_no, capacity))
                flash(f"Screen {screen_no} added successfully.", "success")
        elif action == 'edit':
            execute_db("UPDATE SCREEN SET Capacity = %s WHERE Theatre_Id = %s AND Screen_No = %s",
                       (capacity, theatre_id, screen_no))
            flash(f"Screen {screen_no} capacity updated to {capacity}.", "success")

        return redirect(url_for('admin.manage_screens'))

    screens = query_db("""
        SELECT s.Theatre_Id, s.Screen_No, s.Capacity,
               t.Theatre_Name, t.Location,
               COUNT(sh.Show_Id) AS show_count
        FROM SCREEN s
        JOIN THEATRE t ON s.Theatre_Id = t.Theatre_Id
        LEFT JOIN `SHOW` sh ON s.Theatre_Id = sh.Theatre_Id AND s.Screen_No = sh.Screen_No
        GROUP BY s.Theatre_Id, s.Screen_No, s.Capacity, t.Theatre_Name, t.Location
        ORDER BY t.Theatre_Name, s.Screen_No
    """)
    theatres = query_db("SELECT Theatre_Id, Theatre_Name FROM THEATRE ORDER BY Theatre_Name")
    return render_template('admin/screens.html', screens=screens, theatres=theatres)

@admin_bp.route('/screens/delete/<int:theatre_id>/<int:screen_no>', methods=['POST'])
@admin_required
def delete_screen(theatre_id, screen_no):
    shows = query_db("SELECT COUNT(*) AS c FROM `SHOW` WHERE Theatre_Id = %s AND Screen_No = %s",
                     (theatre_id, screen_no), one=True)['c']
    if shows > 0:
        flash(f"Cannot delete Screen {screen_no}: It has {shows} scheduled showtime(s).", "danger")
    else:
        execute_db("DELETE FROM SCREEN WHERE Theatre_Id = %s AND Screen_No = %s", (theatre_id, screen_no))
        flash(f"Screen {screen_no} deleted successfully.", "success")
    return redirect(url_for('admin.manage_screens'))

# --------------------------------------------------------------------------
# Show Management CRUD
# --------------------------------------------------------------------------
@admin_bp.route('/shows', methods=['GET', 'POST'])
@admin_required
def manage_shows():
    if request.method == 'POST':
        action = request.form.get('action')
        show_date = request.form.get('show_date')
        show_time = request.form.get('show_time')
        theatre_id = request.form.get('theatre_id', type=int)
        screen_no = request.form.get('screen_no', type=int)
        movie_id = request.form.get('movie_id', type=int)

        # 1. Validate screen belongs to theatre
        screen_ok = query_db("SELECT 1 FROM SCREEN WHERE Theatre_Id = %s AND Screen_No = %s", (theatre_id, screen_no), one=True)
        if not screen_ok:
            flash("Selected screen does not belong to the selected theatre.", "danger")
            return redirect(url_for('admin.manage_shows'))

        if action == 'add':
            # Check unique constraint (Theatre_Id, Screen_No, Show_Date, Show_Time)
            conflict = query_db("""
                SELECT Show_Id FROM `SHOW`
                WHERE Theatre_Id = %s AND Screen_No = %s AND Show_Date = %s AND Show_Time = %s
            """, (theatre_id, screen_no, show_date, show_time), one=True)

            if conflict:
                flash("Schedule conflict: A show is already scheduled for that screen at the exact same date and time.", "danger")
            else:
                execute_db("""
                    INSERT INTO `SHOW` (Show_Date, Show_Time, Theatre_Id, Screen_No, Movie_Id)
                    VALUES (%s, %s, %s, %s, %s)
                """, (show_date, show_time, theatre_id, screen_no, movie_id))
                flash("Showtime scheduled successfully.", "success")

        elif action == 'edit':
            show_id = request.form.get('show_id', type=int)
            execute_db("""
                UPDATE `SHOW`
                SET Show_Date = %s, Show_Time = %s, Theatre_Id = %s, Screen_No = %s, Movie_Id = %s
                WHERE Show_Id = %s
            """, (show_date, show_time, theatre_id, screen_no, movie_id, show_id))
            flash("Showtime updated successfully.", "success")

        return redirect(url_for('admin.manage_shows'))

    shows = query_db("""
        SELECT s.Show_Id, s.Show_Date, s.Show_Time, s.Screen_No, s.Theatre_Id, s.Movie_Id,
               t.Theatre_Name, m.Movie_Name, sc.Capacity,
               COUNT(b.Booking_Id) AS booking_count
        FROM `SHOW` s
        JOIN THEATRE t ON s.Theatre_Id = t.Theatre_Id
        JOIN MOVIE m ON s.Movie_Id = m.Movie_Id
        JOIN SCREEN sc ON s.Theatre_Id = sc.Theatre_Id AND s.Screen_No = sc.Screen_No
        LEFT JOIN BOOKING b ON s.Show_Id = b.Show_Id
        GROUP BY s.Show_Id, s.Show_Date, s.Show_Time, s.Screen_No, s.Theatre_Id, s.Movie_Id, t.Theatre_Name, m.Movie_Name, sc.Capacity
        ORDER BY s.Show_Date DESC, s.Show_Time DESC
    """)
    theatres = query_db("SELECT Theatre_Id, Theatre_Name FROM THEATRE ORDER BY Theatre_Name")
    movies = query_db("SELECT Movie_Id, Movie_Name FROM MOVIE ORDER BY Movie_Name")
    screens = query_db("SELECT Theatre_Id, Screen_No, Capacity FROM SCREEN ORDER BY Theatre_Id, Screen_No")

    return render_template('admin/shows.html', shows=shows, theatres=theatres, movies=movies, screens=screens)

@admin_bp.route('/shows/delete/<int:show_id>', methods=['POST'])
@admin_required
def delete_show(show_id):
    bookings = query_db("SELECT COUNT(*) AS c FROM BOOKING WHERE Show_Id = %s", (show_id,), one=True)['c']
    if bookings > 0:
        flash(f"Cannot delete show: It has {bookings} existing customer booking(s) associated with it.", "danger")
    else:
        execute_db("DELETE FROM `SHOW` WHERE Show_Id = %s", (show_id,))
        flash("Showtime deleted successfully.", "success")
    return redirect(url_for('admin.manage_shows'))

# --------------------------------------------------------------------------
# Employee Management CRUD
# --------------------------------------------------------------------------
@admin_bp.route('/employees', methods=['GET', 'POST'])
@admin_required
def manage_employees():
    if request.method == 'POST':
        action = request.form.get('action')
        name = request.form.get('employee_name', '').strip()
        desig = request.form.get('designation', '').strip()
        theatre_id = request.form.get('theatre_id', type=int)

        if not name or not desig or not theatre_id:
            flash("Employee name, designation, and valid theatre are required.", "danger")
        elif action == 'add':
            execute_db("INSERT INTO EMPLOYEE (Employee_Name, Designation, Theatre_Id) VALUES (%s, %s, %s)",
                       (name, desig, theatre_id))
            flash(f"Employee '{name}' added successfully.", "success")
        elif action == 'edit':
            emp_id = request.form.get('employee_id', type=int)
            execute_db("UPDATE EMPLOYEE SET Employee_Name = %s, Designation = %s, Theatre_Id = %s WHERE Employee_Id = %s",
                       (name, desig, theatre_id, emp_id))
            flash(f"Employee '{name}' updated successfully.", "success")

        return redirect(url_for('admin.manage_employees'))

    employees = query_db("""
        SELECT e.Employee_Id, e.Employee_Name, e.Designation, e.Theatre_Id,
               t.Theatre_Name, t.Location
        FROM EMPLOYEE e
        JOIN THEATRE t ON e.Theatre_Id = t.Theatre_Id
        ORDER BY t.Theatre_Name, e.Employee_Name
    """)
    theatres = query_db("SELECT Theatre_Id, Theatre_Name FROM THEATRE ORDER BY Theatre_Name")
    return render_template('admin/employees.html', employees=employees, theatres=theatres)

@admin_bp.route('/employees/delete/<int:employee_id>', methods=['POST'])
@admin_required
def delete_employee(employee_id):
    execute_db("DELETE FROM EMPLOYEE WHERE Employee_Id = %s", (employee_id,))
    flash("Employee record deleted successfully.", "success")
    return redirect(url_for('admin.manage_employees'))

# --------------------------------------------------------------------------
# Snack Management CRUD
# --------------------------------------------------------------------------
@admin_bp.route('/snacks', methods=['GET', 'POST'])
@admin_required
def manage_snacks():
    if request.method == 'POST':
        action = request.form.get('action')
        name = request.form.get('snack_name', '').strip()
        price = request.form.get('price', type=float)

        if not name or price is None or price < 0:
            flash("Snack name and a non-negative price are required.", "danger")
        elif action == 'add':
            execute_db("INSERT INTO SNACK (Snack_Name, Price) VALUES (%s, %s)", (name, price))
            flash(f"Snack '{name}' added successfully.", "success")
        elif action == 'edit':
            s_id = request.form.get('snack_id', type=int)
            execute_db("UPDATE SNACK SET Snack_Name = %s, Price = %s WHERE Snack_Id = %s", (name, price, s_id))
            flash(f"Snack '{name}' updated successfully.", "success")

        return redirect(url_for('admin.manage_snacks'))

    snacks = query_db("""
        SELECT s.Snack_Id, s.Snack_Name, s.Price,
               COALESCE(SUM(bs.Quantity), 0) AS total_orders
        FROM SNACK s
        LEFT JOIN BOOKING_SNACK bs ON s.Snack_Id = bs.Snack_Id
        GROUP BY s.Snack_Id, s.Snack_Name, s.Price
        ORDER BY s.Snack_Id
    """)
    return render_template('admin/snacks.html', snacks=snacks)

@admin_bp.route('/snacks/delete/<int:snack_id>', methods=['POST'])
@admin_required
def delete_snack(snack_id):
    orders = query_db("SELECT COUNT(*) AS c FROM BOOKING_SNACK WHERE Snack_Id = %s", (snack_id,), one=True)['c']
    if orders > 0:
        flash(f"Cannot delete snack: It is recorded in {orders} past booking snack order(s). Keep it to preserve financial history.", "danger")
    else:
        execute_db("DELETE FROM SNACK WHERE Snack_Id = %s", (snack_id,))
        flash("Snack deleted successfully.", "success")
    return redirect(url_for('admin.manage_snacks'))

# --------------------------------------------------------------------------
# Booking Management & Inspection
# --------------------------------------------------------------------------
@admin_bp.route('/bookings')
@admin_required
def manage_bookings():
    search_q = request.args.get('q', '').strip()
    theatre_filter = request.args.get('theatre_id', type=int)

    conditions = []
    params = []

    if search_q:
        conditions.append("(b.Booking_Id = %s OR LOWER(c.Customer_Name) LIKE %s OR c.Phone LIKE %s)")
        params.extend([search_q if search_q.isdigit() else 0, f"%{search_q.lower()}%", f"%{search_q}%"])

    if theatre_filter:
        conditions.append("s.Theatre_Id = %s")
        params.append(theatre_filter)

    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    bookings = query_db(f"""
        SELECT b.Booking_Id, b.Booking_Date, b.Total_Amount,
               c.Customer_Name, c.Phone,
               m.Movie_Name,
               t.Theatre_Name,
               s.Show_Date, s.Show_Time, s.Screen_No,
               p.Mode AS Payment_Mode
        FROM BOOKING b
        JOIN CUSTOMER c ON b.Customer_Id = c.Customer_Id
        JOIN `SHOW` s ON b.Show_Id = s.Show_Id
        JOIN MOVIE m ON s.Movie_Id = m.Movie_Id
        JOIN THEATRE t ON s.Theatre_Id = t.Theatre_Id
        LEFT JOIN PAYMENT p ON b.Booking_Id = p.Booking_Id
        {where_sql}
        ORDER BY b.Booking_Date DESC
    """, params)

    theatres = query_db("SELECT Theatre_Id, Theatre_Name FROM THEATRE ORDER BY Theatre_Name")
    return render_template('admin/bookings.html', bookings=bookings, theatres=theatres, search_q=search_q)

# --------------------------------------------------------------------------
# Analytics Page
# --------------------------------------------------------------------------
@admin_bp.route('/analytics')
@admin_required
def analytics():
    ticket_rev = query_db("SELECT COALESCE(SUM(Price), 0) AS t FROM TICKET", one=True)['t']
    snack_rev = query_db("SELECT COALESCE(SUM(Quantity * Unit_Price), 0) AS s FROM BOOKING_SNACK", one=True)['s']
    booking_rev = query_db("SELECT COALESCE(SUM(Total_Amount), 0) AS b FROM BOOKING", one=True)['b']
    total_payments = query_db("SELECT COALESCE(SUM(Amount), 0) AS p FROM PAYMENT", one=True)['p']
    avg_ticket = query_db("SELECT COALESCE(AVG(Price), 0) AS a FROM TICKET", one=True)['a']

    return render_template('admin/analytics.html',
                           ticket_rev=ticket_rev,
                           snack_rev=snack_rev,
                           booking_rev=booking_rev,
                           total_payments=total_payments,
                           avg_ticket=avg_ticket)
