# ============================================================
# yasir-app - Flask Application
# v1.9 - Final cleanup
# ============================================================
# Changes from v1.8:
#   - SVG icons (was: emoji)
#   - Copy polish
#   - .env.example added for easier onboarding
#   - Image size limit increased to 10 MB
#   - Bio length limit (300 chars)
#   - Name length limit (30 chars)
#   - Password length limit (4-18 chars)
# ============================================================

import os
import uuid
import sqlite3
from datetime import timedelta
from functools import wraps
from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, make_response
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================
load_dotenv()


# ============================================================
# APP CONFIG
# ============================================================
app = Flask(__name__)

app.secret_key = os.environ.get('SECRET_KEY')
if not app.secret_key:
    raise ValueError(
        "SECRET_KEY not set. Copy .env.example to .env and set a value."
    )

app.permanent_session_lifetime = timedelta(days=7)

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ============================================================
# DATABASE HELPERS
# ============================================================
def get_db_connection():
    conn = sqlite3.connect('database.db', timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
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


# ============================================================
# IMAGE VALIDATION
# ============================================================
def is_valid_image(file_stream):
    header = file_stream.read(12)
    file_stream.seek(0)

    if header[:8] == b'\x89PNG\r\n\x1a\n':
        return True
    if header[:3] == b'\xff\xd8\xff':
        return True
    if header[:6] in (b'GIF87a', b'GIF89a'):
        return True
    return False


def save_profile_pic(file):
    if not file or file.filename == '':
        return None

    if not is_valid_image(file):
        return None

    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in {'png', 'jpg', 'jpeg', 'gif'}:
        return None

    unique_name = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
    file.save(save_path)

    return unique_name


# ============================================================
# STATE HELPERS
# ============================================================
def is_logged_in():
    return 'user_id' in session


def user_exists(user_id):
    conn = get_db_connection()
    try:
        result = conn.execute(
            'SELECT 1 FROM users WHERE id = ?', (user_id,)
        ).fetchone()
        return result is not None
    finally:
        conn.close()


def has_profile(user_id):
    conn = get_db_connection()
    try:
        result = conn.execute(
            'SELECT 1 FROM profiles WHERE user_id = ?', (user_id,)
        ).fetchone()
        return result is not None
    finally:
        conn.close()


def where_should_logged_in_user_go():
    if has_profile(session['user_id']):
        return url_for('profile_view')
    return url_for('profile_setup')


def clear_session_and_redirect(target='welcome'):
    session.clear()
    response = make_response(redirect(url_for(target)))
    response.delete_cookie('session')
    return response


# ============================================================
# DECORATORS
# ============================================================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_logged_in():
            flash('Please log in first.', 'error')
            return redirect(url_for('login'))
        if not user_exists(session['user_id']):
            session.clear()
            flash('Session expired. Please log in again.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def guest_only(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if is_logged_in():
            if not user_exists(session['user_id']):
                session.clear()
                return f(*args, **kwargs)
            return redirect(where_should_logged_in_user_go())
        return f(*args, **kwargs)
    return decorated


# ============================================================
# ROUTES
# ============================================================

@app.route('/')
def welcome():
    if is_logged_in():
        if not user_exists(session['user_id']):
            session.clear()
            return render_template('welcome.html')
        return redirect(where_should_logged_in_user_go())
    return render_template('welcome.html')


@app.route('/signup', methods=['GET', 'POST'])
@guest_only
def signup():
    if request.method == 'POST':
        email_phone = request.form.get('email_phone')
        password = request.form.get('password')
        re_password = request.form.get('re_password')
        terms_agree = request.form.get('terms_agree')

        if not email_phone or not password:
            flash('Email and password are required.', 'error')
            return redirect(url_for('signup'))

        if password != re_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('signup'))

        if len(password) < 4:
            flash('Password must be at least 4 characters.', 'error')
            return redirect(url_for('signup'))

        if len(password) > 18:
            flash('Password must be 18 characters or less.', 'error')
            return redirect(url_for('signup'))

        if not terms_agree:
            flash('You must agree to the Terms and Conditions.', 'error')
            return redirect(url_for('signup'))

        hashed = generate_password_hash(password)

        conn = get_db_connection()
        try:
            conn.execute(
                'INSERT INTO users (email_phone, password) VALUES (?, ?)',
                (email_phone, hashed)
            )
            conn.commit()
            flash('Account created.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email or phone already registered.', 'error')
            return redirect(url_for('signup'))
        finally:
            conn.close()

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
@guest_only
def login():
    if request.method == 'POST':
        email_phone = request.form.get('email_phone')
        password = request.form.get('password')

        conn = get_db_connection()
        try:
            user = conn.execute(
                'SELECT * FROM users WHERE email_phone = ?',
                (email_phone,)
            ).fetchone()
        finally:
            conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session.permanent = True
            flash('Welcome back!', 'success')
            return redirect(where_should_logged_in_user_go())
        else:
            flash('Invalid email/phone or password.', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    response = clear_session_and_redirect('welcome')
    flash('You have been logged out.', 'success')
    return response


@app.route('/forgot_password', methods=['GET', 'POST'])
@guest_only
def forgot_password():
    if request.method == 'POST':
        email_phone = request.form.get('email_phone')
        new_password = request.form.get('new_password')

        if not email_phone or not new_password:
            flash('Please fill both fields.', 'error')
            return redirect(url_for('forgot_password'))

        if len(new_password) < 4:
            flash('Password must be at least 4 characters.', 'error')
            return redirect(url_for('forgot_password'))

        if len(new_password) > 18:
            flash('Password must be 18 characters or less.', 'error')
            return redirect(url_for('forgot_password'))

        conn = get_db_connection()
        try:
            user = conn.execute(
                'SELECT * FROM users WHERE email_phone = ?', (email_phone,)
            ).fetchone()

            if user:
                hashed = generate_password_hash(new_password)
                conn.execute(
                    'UPDATE users SET password = ? WHERE email_phone = ?',
                    (hashed, email_phone)
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


@app.route('/profile_setup', methods=['GET', 'POST'])
@login_required
def profile_setup():
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

        if not name or name.strip() == '':
            flash('Name is required.', 'error')
            return redirect(url_for('profile_setup'))

        if len(name) > 30:
            flash('Name must be 30 characters or less.', 'error')
            return redirect(url_for('profile_setup'))

        if bio and len(bio) > 300:
            flash('Bio must be 300 characters or less.', 'error')
            return redirect(url_for('profile_setup'))

        filename = None
        if file and file.filename != '':
            filename = save_profile_pic(file)
            if filename is None:
                flash('Only valid PNG, JPG, or GIF images allowed.', 'error')
                return redirect(url_for('profile_setup'))

        conn = get_db_connection()
        try:
            if existing:
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


@app.route('/profile')
@login_required
def profile_view():
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


@app.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    user_id = session['user_id']
    password = request.form.get('password')

    if not password:
        flash('Password is required to delete account.', 'error')
        return redirect(url_for('profile_view'))

    conn = get_db_connection()
    try:
        user = conn.execute(
            'SELECT * FROM users WHERE id = ?', (user_id,)
        ).fetchone()

        if not user or not check_password_hash(user['password'], password):
            flash('Incorrect password. Account not deleted.', 'error')
            return redirect(url_for('profile_view'))

        profile = conn.execute(
            'SELECT * FROM profiles WHERE user_id = ?', (user_id,)
        ).fetchone()

        if profile and profile['profile_pic']:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], profile['profile_pic'])
            if os.path.exists(image_path):
                os.remove(image_path)

        conn.execute('DELETE FROM profiles WHERE user_id = ?', (user_id,))
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
    finally:
        conn.close()

    response = clear_session_and_redirect('welcome')
    flash('Your account has been deleted.', 'success')
    return response


# ============================================================
# ERROR HANDLERS
# ============================================================
@app.errorhandler(413)
def too_large(e):
    flash('File is too large. Max size is 10 MB.', 'error')
    return redirect(url_for('profile_setup'))


# ============================================================
# RUN
# ============================================================
init_db()

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, port=3002)