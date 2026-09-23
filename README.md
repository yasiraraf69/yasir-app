# yasir-app

A Flask + SQLite web app with user authentication and profile management.

## Features

- User signup and login
- Profile setup with picture upload
- Profile view
- Settings and account deletion
- Session management with cookie clearing

## Tech Stack

- Python (Flask)
- SQLite
- HTML, CSS, JavaScript
- Werkzeug for password hashing

## Setup

1. Install dependencies:
   pip install -r requirements.txt

2. Create a `.env` file:
   SECRET_KEY=your_random_secret_key

3. Run the app:
   python app.py

4. Open: http://127.0.0.1:3002

## Version History

- v1.0: Initial release
- v1.5: Strong logic, no loops, toasts, cookie handling
- v1.8: Security update