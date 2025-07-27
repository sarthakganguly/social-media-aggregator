# File: frontend/run.py

import logging
from flask import Flask, render_template, request, redirect, url_for, flash, session
import requests  # This is for making API calls
import os
import jwt # We need this to decode the token for the username
from dotenv import load_dotenv

project_root = os.path.join(os.path.dirname(__file__), '..')  # This goes one directory up from frontend/
dotenv_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
# It's crucial for the frontend to have its own secret key for its session
# This keeps the user's browser session secure
BACKEND_INTERNAL_URL = "http://127.0.0.1:5000"
BACKEND_PUBLIC_URL = os.environ.get("BACKEND_PUBLIC_URL")

app.config['SECRET_KEY'] = os.environ.get('FRONTEND_SECRET_KEY')

# Check if the key was loaded, and provide a fallback if not
if not app.config['SECRET_KEY']:
    raise ValueError("No FRONTEND_SECRET_KEY set for Flask application")

# --- Helper Functions ---

def get_auth_headers():
    if 'token' in session:
        return {'Authorization': session['token']}
    return {}

# --- Page Rendering Routes ---

@app.route("/")
def index():
    """
    The landing page. If the user is logged in, it redirects to their dashboard,
    otherwise, it sends them to the login page.
    """
    if 'token' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route("/login", methods=['GET', 'POST'])
def login():
    """Handles the user login page (both showing the form and processing it)."""
    # If user is already logged in, send them to the dashboard
    if 'token' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Make a request to the backend API's login endpoint
        api_response = requests.post(
            f"{BACKEND_INTERNAL_URL}/api/auth/login",
            json={'email': email, 'password': password}
        )

        if api_response.status_code == 200:
            # Login was successful, store the JWT from the backend in the user's session
            session['token'] = api_response.json().get('token')
            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Login failed. Please check your credentials.", "danger")

    return render_template('login.html', title="Login")


@app.route("/register", methods=['GET', 'POST'])
def register():
    """Handles the user registration page."""
    # If user is already logged in, send them to the dashboard
    if 'token' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        # Make a request to the backend API's register endpoint
        api_response = requests.post(
            f"{BACKEND_API_URL}/api/auth/register",
            json={'username': username, 'email': email, 'password': password}
        )

        if api_response.status_code == 201:
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('login'))
        else:
            # Display the error message from the backend API
            error_msg = api_response.json().get('msg', 'An unknown error occurred.')
            flash(f"Registration failed: {error_msg}", "danger")
            
    return render_template('register.html', title="Register")

@app.route("/dashboard", methods=['GET', 'POST']) # Add 'POST' to methods
def dashboard():
    if 'token' not in session:
        return redirect(url_for('login')) # Redirect if not logged in
    
    headers = get_auth_headers()


    if request.method == 'POST':
        content = request.form.get('content')
        platform = 'linkedin'
        # --- NEW: Get the schedule time from the form ---
        schedule_time = request.form.get('schedule_time')

        # Prepare the JSON payload for the backend API
        payload = {
            'content': content,
            'platform': platform,
            'schedule_time': schedule_time # Add the schedule time to the payload
         }

        api_response = requests.post(
            f"{BACKEND_INTERNAL_URL}/api/posts/create",
            headers=headers,
            json=payload # Send the whole payload
        )
    
        # ... (the rest of the success/error handling is the same)
        if api_response.status_code in [200, 201, 202]:
            success_msg = api_response.json().get('message', 'Post submitted successfully!')
            flash(success_msg, "success")
        else:
            error_msg = api_response.json().get('message', 'An unknown error occurred.')
            flash(f"Failed to create post: {error_msg}", "danger")
    
        return redirect(url_for('dashboard'))

    # --- The GET request logic remains the same ---
    username = 'User'
    try:
        raw_token = session['token'].split(" ")[1]
        unverified_payload = jwt.decode(raw_token, options={"verify_signature": False})
        username = unverified_payload.get('username', 'User')
    except (jwt.PyJWTError, IndexError):
        return redirect(url_for('logout'))

    backend_linkedin_auth_url = f"{BACKEND_PUBLIC_URL}/oauth/linkedin/authorize?jwt={raw_token}"
    
    channels_response = requests.get(f"{BACKEND_INTERNAL_URL}/api/channels", headers=headers)
    connected_channels = channels_response.json() if channels_response.status_code == 200 else []

    return render_template(
        'dashboard.html',
        title="Dashboard",
        username=username,
        linkedin_auth_url=backend_linkedin_auth_url,
        channels=connected_channels
    )
@app.route("/logout")
def logout():
    """Logs the user out by clearing the token from the session."""
    session.pop('token', None)
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))


if __name__ == '__main__':
    # Run the frontend server on port 8000 and make it accessible on the network
    # Debug=True gives us helpful error pages and auto-reloading
    app.run(port=8000, debug=True, host='0.0.0.0')
