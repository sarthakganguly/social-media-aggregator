# File: backend/app.py

# --- Core Imports ---
import os
import requests
import jwt
import datetime
from functools import wraps
from urllib.parse import urlencode

# --- Flask and Extension Imports ---
from flask import Flask, request, jsonify, redirect, session
from dotenv import load_dotenv

# --- Redis and RQ Imports for Background Jobs ---
import redis
from rq import Queue

# --- Explicitly find and load the .env file from the project root ---
project_root = os.path.join(os.path.dirname(__file__), '..')
dotenv_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path)

# --- Application Module Imports ---
# These are imported now, after the environment is loaded.
from config import Config
from models import db, bcrypt, User, SocialChannel
from tasks import post_to_linkedin # Import from the local tasks.py

# --- App Initialization ---
app = Flask(__name__)
app.config.from_object(Config)

# --- Direct Configuration Loading (for keys not in config.py) ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Logging Setup ---
import logging
logging.basicConfig(level=logging.INFO)

if not app.config['SECRET_KEY']:
    app.logger.critical("FATAL ERROR: SECRET_KEY not found in environment.")
else:
    app.logger.info("Secret key loaded successfully.")

# --- Database and Bcrypt Initialization ---
db.init_app(app)
bcrypt.init_app(app)

# --- Redis Queue Connection ---
try:
    redis_conn = redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379'))
    q = Queue(connection=redis_conn)
    app.logger.info("Successfully connected to Redis and created task queue.")
except Exception as e:
    app.logger.critical(f"FATAL ERROR: Could not connect to Redis. {e}")
    q = None # Set queue to None if connection fails


# --- Helper Functions / Decorators ---

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user_id = data['sub']
        except Exception as e:
            return jsonify({'message': 'Token is invalid!', 'error': str(e)}), 401
        return f(current_user_id, *args, **kwargs)
    return decorated


# --- API Routes ---

@app.route('/api/auth/register', methods=['POST'])
def register():
    # ... (code is unchanged)
    data = request.get_json()
    if User.query.filter((User.email == data['email']) | (User.username == data['username'])).first(): return jsonify({'msg': 'User exists'}), 400
    new_user = User(username=data['username'], email=data['email']); new_user.set_password(data['password'])
    db.session.add(new_user); db.session.commit()
    return jsonify({'msg': 'User registered'}), 201


@app.route('/api/auth/login', methods=['POST'])
def login():
    # ... (code is unchanged, but ensuring str(user.id) is used)
    data = request.get_json()
    user = User.query.filter_by(email=data.get('email')).first()
    if user and user.check_password(data.get('password')):
        payload = {
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1),
            'iat': datetime.datetime.utcnow(),
            'sub': str(user.id),  # Ensure subject is a string
            'role': user.role,
            'username': user.username
        }
        token = jwt.encode(payload, app.config.get('SECRET_KEY'), algorithm='HS256')
        return jsonify({'token': f'Bearer {token}'}), 200
    return jsonify({'msg': 'Invalid credentials'}), 401


@app.route('/api/channels', methods=['GET'])
@token_required
def get_channels(current_user_id):
    # ... (code is unchanged)
    channels = SocialChannel.query.filter_by(user_id=current_user_id).all()
    return jsonify([{'platform': c.platform} for c in channels]), 200


@app.route('/api/posts/create', methods=['POST'])
@token_required
def create_post(current_user_id):
    """Handles both immediate and scheduled posts."""
    if not q: # Check if Redis connection was successful
        return jsonify({'message': 'Background worker is not available.'}), 503

    data = request.get_json()
    content = data.get('content')
    platform = data.get('platform')
    schedule_time_str = data.get('schedule_time')

    if not all([content, platform]):
        return jsonify({'message': 'Missing content or platform'}), 400

    channel = SocialChannel.query.filter_by(user_id=current_user_id, platform=platform).first()
    if not channel or not channel.access_token or not channel.channel_user_id:
        return jsonify({'message': f'Channel for {platform} not fully configured.'}), 404

    if schedule_time_str: # If a schedule time is provided
        try:
            schedule_datetime = datetime.datetime.fromisoformat(schedule_time_str)
            job = q.enqueue_at(
                schedule_datetime,
                post_to_linkedin,
                args=(channel.access_token, channel.channel_user_id, content)
            )
            human_readable_time = schedule_datetime.strftime('%B %d, %Y at %I:%M %p')
            app.logger.info(f"Post for user {current_user_id} scheduled for {human_readable_time}. Job ID: {job.id}")
            return jsonify({'message': f'Post successfully scheduled for {human_readable_time}!'}), 202
        except ValueError:
            return jsonify({'message': 'Invalid datetime format.'}), 400
    else: # If no schedule time, post immediately
        job = q.enqueue(
            post_to_linkedin,
            args=(channel.access_token, channel.channel_user_id, content)
        )
        app.logger.info(f"Submitting immediate post job for user {current_user_id}. Job ID: {job.id}")
        return jsonify({'message': 'Post has been queued for immediate delivery!'}), 202


# --- OAuth Routes ---
# ... (These are unchanged from our last working version) ...
@app.route('/oauth/linkedin/authorize')
def linkedin_authorize():
    user_jwt = request.args.get('jwt')
    if not user_jwt: return "Error: Auth token not provided.", 400
    redirect_uri = f"{os.environ.get('PUBLIC_SERVER_URL')}/oauth/linkedin/callback"
    params = {'response_type': 'code','client_id': os.environ.get('LINKEDIN_CLIENT_ID'),'redirect_uri': redirect_uri,'scope': 'openid profile w_member_social','state': user_jwt}
    linkedin_auth_url = 'https://www.linkedin.com/oauth/v2/authorization?' + urlencode(params)
    return redirect(linkedin_auth_url)


@app.route('/oauth/linkedin/callback')
def linkedin_callback():
    auth_code = request.args.get('code')
    user_jwt = request.args.get('state')
    if not auth_code or not user_jwt: return "Error: Missing params.", 400
    try:
        payload = jwt.decode(user_jwt, app.config['SECRET_KEY'], algorithms=["HS256"])
        user_id = payload['sub']
    except (jwt.PyJWTError) as e:
        return "Error: Invalid state token.", 400

    token_url = 'https://www.linkedin.com/oauth/v2/accessToken'
    redirect_uri = f"{os.environ.get('PUBLIC_SERVER_URL')}/oauth/linkedin/callback"
    token_params = {'grant_type': 'authorization_code','code': auth_code,'redirect_uri': redirect_uri,'client_id': os.environ.get('LINKEDIN_CLIENT_ID'),'client_secret': os.environ.get('LINKEDIN_CLIENT_SECRET')}
    response = requests.post(token_url, data=token_params)
    if response.status_code != 200: return "Error fetching access token.", 400
    access_token = response.json().get('access_token')

    profile_headers = {'Authorization': f'Bearer {access_token}'}
    profile_response = requests.get('https://api.linkedin.com/v2/userinfo', headers=profile_headers)
    linkedin_user_id = profile_response.json().get('sub') if profile_response.ok else None
    
    channel = SocialChannel.query.filter_by(user_id=user_id, platform='linkedin').first()
    if channel:
        channel.access_token = access_token
        channel.channel_user_id = linkedin_user_id
    else:
        channel = SocialChannel(user_id=user_id, platform='linkedin', access_token=access_token, channel_user_id=linkedin_user_id)
        db.session.add(channel)
    db.session.commit()
    return redirect(f"{os.environ.get('FRONTEND_URL')}/dashboard")


if __name__ == '__main__':
    # Not used by 'flask run', but useful for direct execution
    app.run(debug=True)
