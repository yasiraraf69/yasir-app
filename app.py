# ============================================================
# YASIR-APP V1.0 - Complete Flask Application
# ============================================================

# ============================================================
# 1. IMPORTS
# ============================================================
import os
import sqlite3
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)
from werkzeug.utils import secure_filename


# ============================================================
# 2. APP CONFIGURATION
# ============================================================
app = Flask(__name__)
app.secret_key = "my_super_secret_key_change_this_later"

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ============================================================
# 3. HELPER FUNCTIONS
# ============================================================

def allowed_file(filename):
    """Check if uploaded file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db_connection():
    """Open SQLite database connection."""
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


# ============================================================
# 4. ROUTES
# ============================================================

# ---------------- WELCOME ----------------
@app.route('/')
def welcome():
    if 'user_id' in session:
        return redirect(url_for('profile_view'))
    return render_template('welcome.html')


# ---------------- SIGNUP ----------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email_phone = request.form.get('email_phone')
        password = request.form.get('password')
        re_password = request.form.get('re_password')
        terms_agree = request.form.get('terms_agree')

        if password != re_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('signup'))

        if not terms_agree:
            flash('You must agree to the Terms and Conditions.', 'error')
            return redirect(url_for('signup'))

        conn = get_db_connection()
        try:
            conn.execute(
                'INSERT INTO users (email_phone, password) VALUES (?, ?)',
                (email_phone, password)
            )
            conn.commit()
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email or phone already registered.', 'error')
        finally:
            conn.close()

    return render_template('signup.html')


# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
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
            session['user_id'] = user['id']
            session.permanent = True

            # Check if profile exists
            conn = get_db_connection()
            try:
                profile = conn.execute(
                    'SELECT * FROM profiles WHERE user_id = ?',
                    (user['id'],)
                ).fetchone()
            finally:
                conn.close()

            if profile:
                return redirect(url_for('profile_view'))
            else:
                return redirect(url_for('profile_setup'))
        else:
            flash('Invalid email/phone or password.', 'error')

    return render_template('login.html')


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('welcome'))


# ---------------- FORGOT PASSWORD ----------------
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email_phone = request.form.get('email_phone')
        new_password = request.form.get('new_password')

        conn = get_db_connection()
        try:
            user = conn.execute(
                'SELECT * FROM users WHERE email_phone = ?',
                (email_phone,)
            ).fetchone()

            if user:
                conn.execute(
                    'UPDATE users SET password = ? WHERE email_phone = ?',
                    (new_password, email_phone)
                )
                conn.commit()
                flash('Password reset successfully! Please log in.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Email or Phone not found.', 'error')
        finally:
            conn.close()

    return render_template('forgot_password.html')


# ---------------- PROFILE SETUP ----------------
@app.route('/profile_setup', methods=['GET', 'POST'])
def profile_setup():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form.get('name')
        bio = request.form.get('bio')
        file = request.files.get('profile_pic')

        # Handle optional profile picture upload
        filename = None
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = get_db_connection()
        try:
            # Check if profile exists
            existing = conn.execute(
                'SELECT * FROM profiles WHERE user_id = ?',
                (session['user_id'],)
            ).fetchone()

            if existing:
                # UPDATE existing
                conn.execute(
                    '''UPDATE profiles 
                       SET name = ?, bio = ?, profile_pic = COALESCE(?, profile_pic)
                       WHERE user_id = ?''',
                    (name, bio, filename, session['user_id'])
                )
            else:
                # INSERT new
                conn.execute(
                    'INSERT INTO profiles (user_id, name, bio, profile_pic) VALUES (?, ?, ?, ?)',
                    (session['user_id'], name, bio, filename)
                )

            conn.commit()
        finally:
            conn.close()

        return redirect(url_for('profile_view'))

    return render_template('profile_setup.html')


# ---------------- PROFILE VIEW ----------------
@app.route('/profile')
def profile_view():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    try:
        profile = conn.execute(
            'SELECT * FROM profiles WHERE user_id = ?',
            (session['user_id'],)
        ).fetchone()
    finally:
        conn.close()

    if not profile:
        return redirect(url_for('profile_setup'))

    return render_template('profile_view.html', profile=profile)


# ---------------- DELETE ACCOUNT ----------------
@app.route('/delete_account')
def delete_account():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    conn = get_db_connection()
    try:
        profile = conn.execute(
            'SELECT * FROM profiles WHERE user_id = ?',
            (user_id,)
        ).fetchone()

        # Delete uploaded image from disk
        if profile and profile['profile_pic']:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], profile['profile_pic'])
            if os.path.exists(image_path):
                os.remove(image_path)

        # Delete profile row
        conn.execute('DELETE FROM profiles WHERE user_id = ?', (user_id,))

        # Delete user row
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))

        conn.commit()
    finally:
        conn.close()

    session.clear()
    flash('Your account has been deleted.', 'success')
    return redirect(url_for('welcome'))


# ============================================================
# 5. RUN THE APP
# ============================================================
if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=3002)