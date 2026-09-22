# ============================================================
# MY-FIRST-PROJECT - Flask Application
# v1.5 — Strong logic, all paths covered, no loops
# ============================================================
# Route flow:
#   Visitor → / → [Login] [Signup]
#   Signup → /login
#   Login → check profile → /profile_setup OR /profile
#   Logout → / (cookie cleared)
#   Delete → / (cookie cleared)
# ============================================================

import os
import sqlite3
from datetime import timedelta
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, make_response
)
from werkzeug.utils import secure_filename


# ============================================================
# APP CONFIG
# ============================================================
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'my_super_secret_key_change_later')
app.permanent_session_lifetime = timedelta(days=7)

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ============================================================
# DATABASE HELPERS
# ============================================================
def get_db_connection():
    """Open SQLite connection with timeout (prevents 'database is locked')."""
    conn = sqlite3.connect('database.db', timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_phone TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            bio TEXT,
            profile_pic TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    conn.commit()
    conn.close()


def allowed_file(filename):
    """Check file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ============================================================
# STATE HELPERS — single source of truth
# ============================================================
def is_logged_in():
    """Is there a session with a user_id?"""
    return 'user_id' in session


def user_exists(user_id):
    """Does this user still exist in the DB? (ghost session check)"""
    conn = get_db_connection()
    try:
        result = conn.execute(
            'SELECT 1 FROM users WHERE id = ?', (user_id,)
        ).fetchone()
        return result is not None
    finally:
        conn.close()


def has_profile(user_id):
    """Has this user completed profile setup?"""
    conn = get_db_connection()
    try:
        result = conn.execute(
            'SELECT 1 FROM profiles WHERE user_id = ?', (user_id,)
        ).fetchone()
        return result is not None
    finally:
        conn.close()


def where_should_logged_in_user_go():
    """
    Central function: where should a logged-in user go?
    - No profile → /profile_setup
    - Has profile → /profile
    """
    if has_profile(session['user_id']):
        return url_for('profile_view')
    return url_for('profile_setup')


def clear_session_and_redirect(target='welcome'):
    """
    Fully clear session + delete cookie.
    Used by logout + delete account.
    """
    session.clear()
    response = make_response(redirect(url_for(target)))
    response.delete_cookie('session')
    return response


# ============================================================
# DECORATORS — reusable access control
# ============================================================

def login_required(f):
    """
    Route only accessible if logged in.
    Also handles ghost session (user deleted but cookie remains).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # 1. Not logged in at all → go login
        if not is_logged_in():
            flash('Please log in first.', 'error')
            return redirect(url_for('login'))

        # 2. Ghost session → user missing from DB
        if not user_exists(session['user_id']):
            session.clear()
            flash('Session expired. Please log in again.', 'error')
            return redirect(url_for('login'))

        return f(*args, **kwargs)
    return decorated


def guest_only(f):
    """
    Route only accessible if NOT logged in.
    If logged in → redirect to profile or profile_setup.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if is_logged_in():
            # Ghost session check
            if not user_exists(session['user_id']):
                session.clear()
                return f(*args, **kwargs)
            # Real logged-in user → go where they belong
            return redirect(where_should_logged_in_user_go())
        return f(*args, **kwargs)
    return decorated


# ============================================================
# ROUTES
# ============================================================

# ---------------- WELCOME ----------------
@app.route('/')
def welcome():
    """
    Welcome page — ONLY for visitors.
    Logged-in users auto-redirect to profile/profile_setup.
    """
    if is_logged_in():
        # Ghost session → clear and show welcome
        if not user_exists(session['user_id']):
            session.clear()
            return render_template('welcome.html')
        # Real user → redirect
        return redirect(where_should_logged_in_user_go())

    # Visitor → show welcome
    return render_template('welcome.html')


# ---------------- SIGNUP ----------------
@app.route('/signup', methods=['GET', 'POST'])
@guest_only
def signup():
    """Only for visitors."""
    if request.method == 'POST':
        email_phone = request.form.get('email_phone')
        password = request.form.get('password')
        re_password = request.form.get('re_password')
        terms_agree = request.form.get('terms_agree')

        # Validation
        if not email_phone or not password:
            flash('Email and password are required.', 'error')
            return redirect(url_for('signup'))

        if password != re_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('signup'))

        if not terms_agree:
            flash('You must agree to the Terms and Conditions.', 'error')
            return redirect(url_for('signup'))

        # Save user
        conn = get_db_connection()
        try:
            conn.execute(
                'INSERT INTO users (email_phone, password) VALUES (?, ?)',
                (email_phone, password)
            )
            conn.commit()
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email or phone already registered.', 'error')
            return redirect(url_for('signup'))
        finally:
            conn.close()

    return render_template('signup.html')


# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
@guest_only
def login():
    """Only for visitors."""
    if request.method == 'POST':
        email_phone = request.form.get('email_phone')
        password = request.form.get('password')

        conn = get_db_connection()
        try:
            user = conn.execute(
                'SELECT * FROM users WHERE email_phone = ? AND password = ?',
                (email_phone, password)
            ).fetchone()
        finally:
            conn.close()

        if user:
            # Set session
            session['user_id'] = user['id']
            session.permanent = True
            flash('Welcome back!', 'success')

            # Route to setup OR profile
            return redirect(where_should_logged_in_user_go())
        else:
            flash('Invalid email/phone or password.', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    """Clear session + cookie → welcome."""
    response = clear_session_and_redirect('welcome')
    flash('You have been logged out.', 'success')
    return response


# ---------------- FORGOT PASSWORD ----------------
@app.route('/forgot_password', methods=['GET', 'POST'])
@guest_only
def forgot_password():
    """Only for visitors."""
    if request.method == 'POST':
        email_phone = request.form.get('email_phone')
        new_password = request.form.get('new_password')

        if not email_phone or not new_password:
            flash('Please fill both fields.', 'error')
            return redirect(url_for('forgot_password'))

        conn = get_db_connection()
        try:
            user = conn.execute(
                'SELECT * FROM users WHERE email_phone = ?', (email_phone,)
            ).fetchone()

            if user:
                conn.execute(
                    'UPDATE users SET password = ? WHERE email_phone = ?',
                    (new_password, email_phone)
                )
                conn.commit()
                flash('Password reset! Please log in.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Email or Phone not found.', 'error')
                return redirect(url_for('forgot_password'))
        finally:
            conn.close()

    return render_template('forgot_password.html')


# ---------------- PROFILE SETUP ----------------
@app.route('/profile_setup', methods=['GET', 'POST'])
@login_required
def profile_setup():
    """Logged-in only."""
    # Get existing profile (for edit mode)
    conn = get_db_connection()
    try:
        existing = conn.execute(
            'SELECT * FROM profiles WHERE user_id = ?',
            (session['user_id'],)
        ).fetchone()
    finally:
        conn.close()

    if request.method == 'POST':
        name = request.form.get('name')
        bio = request.form.get('bio')
        file = request.files.get('profile_pic')

        # Name required
        if not name or name.strip() == '':
            flash('Name is required.', 'error')
            return redirect(url_for('profile_setup'))

        # Handle image upload
        filename = None
        if file and file.filename != '':
            if not allowed_file(file.filename):
                flash('Only PNG, JPG, JPEG, GIF allowed.', 'error')
                return redirect(url_for('profile_setup'))
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = get_db_connection()
        try:
            if existing:
                # UPDATE — keep old values if new not provided
                conn.execute(
                    '''UPDATE profiles
                       SET name = ?,
                           bio = COALESCE(NULLIF(?, ''), bio),
                           profile_pic = COALESCE(?, profile_pic)
                       WHERE user_id = ?''',
                    (name, bio, filename, session['user_id'])
                )
            else:
                conn.execute(
                    'INSERT INTO profiles (user_id, name, bio, profile_pic) VALUES (?, ?, ?, ?)',
                    (session['user_id'], name, bio, filename)
                )
            conn.commit()
        finally:
            conn.close()

        flash('Profile saved!', 'success')
        return redirect(url_for('profile_view'))

    return render_template('profile_setup.html', profile=existing)


# ---------------- PROFILE VIEW ----------------
@app.route('/profile')
@login_required
def profile_view():
    """Logged-in only. Requires profile."""
    if not has_profile(session['user_id']):
        flash('Please set up your profile first.', 'error')
        return redirect(url_for('profile_setup'))

    conn = get_db_connection()
    try:
        profile = conn.execute(
            'SELECT * FROM profiles WHERE user_id = ?',
            (session['user_id'],)
        ).fetchone()
    finally:
        conn.close()

    return render_template('profile_view.html', profile=profile)


# ---------------- DELETE ACCOUNT ----------------
@app.route('/delete_account')
@login_required
def delete_account():
    """Logged-in only. Deletes everything."""
    user_id = session['user_id']

    conn = get_db_connection()
    try:
        profile = conn.execute(
            'SELECT * FROM profiles WHERE user_id = ?', (user_id,)
        ).fetchone()

        # Delete uploaded image from disk
        if profile and profile['profile_pic']:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], profile['profile_pic'])
            if os.path.exists(image_path):
                os.remove(image_path)

        # Delete from DB
        conn.execute('DELETE FROM profiles WHERE user_id = ?', (user_id,))
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
    finally:
        conn.close()

    # Clear session + cookie
    response = clear_session_and_redirect('welcome')
    flash('Your account has been deleted.', 'success')
    return response


# ============================================================
# ERROR HANDLERS
# ============================================================
@app.errorhandler(413)
def too_large(e):
    flash('File is too large. Max size is 5 MB.', 'error')
    return redirect(url_for('profile_setup'))


# ============================================================
# RUN
# ============================================================
init_db()

if __name__ == '__main__':
    app.run(debug=True, port=3002)

