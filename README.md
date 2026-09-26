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
- python-dotenv for environment variables

## Setup

Follow these steps to run the app locally.

### 1. Clone the repository

git clone https://github.com/yasiraraf69/yasir-app.git
cd yasir-app

### 2. Install dependencies

Make sure Python 3.8 or higher is installed. Then run:

pip install -r requirements.txt

### 3. Create your environment file

The app needs a `.env` file with a secret key. Copy the example file:

On Windows:
copy .env.example .env

On Mac or Linux:
cp .env.example .env

Now open `.env` and replace the placeholder with a random string. You can use any random text. Longer is better.

### 4. Run the app

python app.py

### 5. Open in browser

http://127.0.0.1:3002

## Notes

- The `database.db` file is created automatically on first run.
- The `.env` file should never be committed to Git. It contains your secret key.
- Uploaded profile pictures are stored in `static/uploads/`.

## Version History

- v1.0: Initial release
- v1.5: Strong logic, no loops, toasts, cookie handling
- v1.8: Security update - password hashing, env secret key, POST delete, image validation