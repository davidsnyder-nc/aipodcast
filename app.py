import os
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
import json

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Initialize database
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET" # Add your key here)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Upload folder for cover art
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # type: ignore
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    import models
    return models.User.query.get(int(user_id))

# Add template context processors
@app.context_processor
def utility_processor():
    def now():
        return datetime.now()
        
    # Get system status variables
    # API Keys
    openai_key = os.environ.get("OPENAI_API_KEY" # Add your key here, '')
    elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY" # Add your key here, '')
    github_token = os.environ.get("GITHUB_TOKEN" # Add your key here, '')
    github_username = os.environ.get('GITHUB_USERNAME', '')
    github_repo = os.environ.get('GITHUB_REPO', '')
    
    # If not in environment, check database
    # Skip if no models available yet (early app initialization)
    try:
        import models
        if not openai_key:
            openai_key_db = models.ApiKey.query.filter_by(name='OPENAI_API_KEY').first()
            if openai_key_db:
                openai_key = openai_key_db.value
                
        if not elevenlabs_key:
            elevenlabs_key_db = models.ApiKey.query.filter_by(name='ELEVENLABS_API_KEY').first()
            if elevenlabs_key_db:
                elevenlabs_key = elevenlabs_key_db.value
                
        if not github_token:
            github_token_db = models.ApiKey.query.filter_by(name='GITHUB_TOKEN').first()
            if github_token_db:
                github_token = github_token_db.value
                
        if not github_username:
            github_username_db = models.ApiKey.query.filter_by(name='GITHUB_USERNAME').first()
            if github_username_db:
                github_username = github_username_db.value
                
        if not github_repo:
            github_repo_db = models.ApiKey.query.filter_by(name='GITHUB_REPO').first()
            if github_repo_db:
                github_repo = github_repo_db.value
        
        # Check GitHub configuration
        github_configured = all([github_token, github_username, github_repo])
        
        # Check voice settings
        voice_settings = models.ElevenLabsVoice.query.first()
        
        # Count active feeds
        active_feeds_count = models.RssFeed.query.filter_by(active=True).count()
    except Exception:
        # If models not ready, set default values
        github_configured = False
        voice_settings = None
        active_feeds_count = 0
        
    return dict(
        now=now,
        openai_key=openai_key,
        elevenlabs_key=elevenlabs_key,
        github_configured=github_configured,
        voice_settings=voice_settings,
        active_feeds_count=active_feeds_count
    )

# Configure database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
db.init_app(app)

# Import modules after initializing DB to avoid circular imports
with app.app_context():
    import models
    from rss import fetch_rss_feeds, get_feed_data
    from gpt import generate_podcast_script
    from tts import convert_to_speech
    from gitpush import publish_to_github
    
    # Create tables if they don't exist
    db.create_all()
    
    # Initialize default settings if not present
    if not models.Settings.query.first():
        default_settings = models.Settings()
        default_settings.podcast_title = "Daily Tech Insights"
        default_settings.podcast_description = "An AI-generated daily tech news podcast covering the latest in technology and startups."
        default_settings.podcast_author = "AI Podcast Generator"
        db.session.add(default_settings)
        
        # Add default RSS feeds
        default_feeds = []
        
        feed1 = models.RssFeed()
        feed1.name = "Hacker News"
        feed1.url = "https://news.ycombinator.com/rss"
        feed1.active = True
        default_feeds.append(feed1)
        
        feed2 = models.RssFeed()
        feed2.name = "TechCrunch"
        feed2.url = "https://techcrunch.com/feed/"
        feed2.active = True
        default_feeds.append(feed2)
        
        feed3 = models.RssFeed()
        feed3.name = "The Verge"
        feed3.url = "https://www.theverge.com/rss/index.xml"
        feed3.active = True
        default_feeds.append(feed3)
        
        feed4 = models.RssFeed()
        feed4.name = "Wired"
        feed4.url = "https://www.wired.com/feed/rss"
        feed4.active = True
        default_feeds.append(feed4)
        for feed in default_feeds:
            db.session.add(feed)
            
        db.session.commit()
        logging.info("Initialized default settings and RSS feeds")

# Create storage directory if it doesn't exist
os.makedirs('storage', exist_ok=True)

# Helper function for file uploads
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'
        
        user = models.User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user, remember=remember)
            flash('Login successful!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check if username already exists
        if models.User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return render_template('register.html')
        
        # Check if email already exists
        if email and models.User.query.filter_by(email=email).first():
            flash('Email already in use.', 'danger')
            return render_template('register.html')
        
        # Create new user
        user = models.User()
        user.username = username
        user.email = email
        user.set_password(password)
        
        db.session.add(user)
        
        # Create default podcast settings for the user
        settings = models.Settings()
        settings.podcast_title = f"{username}'s Podcast"
        settings.podcast_description = "An AI-generated daily tech news podcast."
        settings.podcast_author = username
        settings.user_id = user.id  # Will be set after commit
        
        db.session.add(settings)
        db.session.commit()
        
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Profile management
@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    user = current_user
    
    # Only update email if it's provided
    email = request.form.get('email')
    if email and email != user.email:
        if models.User.query.filter_by(email=email).first() and email != user.email:
            flash('Email already in use.', 'danger')
            return redirect(url_for('profile'))
        user.email = email
    
    # Update password if provided
    password = request.form.get('password')
    if password and len(password) >= 6:
        user.set_password(password)
    
    # Handle avatar upload
    if 'avatar' in request.files:
        file = request.files['avatar']
        if file and file.filename and file.filename != '':
            if allowed_file(file.filename):
                # Create avatars directory if it doesn't exist
                avatars_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'avatars')
                os.makedirs(avatars_dir, exist_ok=True)
                
                # Save the file with a unique name
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                filename = f"{timestamp}_{filename}"
                filepath = os.path.join(avatars_dir, filename)
                file.save(filepath)
                
                # Update the user's avatar path (store relative path)
                user.avatar_path = f"uploads/avatars/{filename}"
            else:
                flash('Invalid file type. Please upload an image file (png, jpg, jpeg, gif).', 'danger')
    
    db.session.commit()
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('profile'))

# Routes
@app.route('/')
def index():
    # Redirect to login if not authenticated
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    
    # Get podcasts for current user
    user_id = current_user.id
    settings = models.Settings.query.filter_by(user_id=user_id).all()
    
    episodes = models.Episode.query.order_by(models.Episode.date.desc()).all()
    
    # Check API keys in environment variables first
    openai_key = os.environ.get("OPENAI_API_KEY" # Add your key here, False)
    elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY" # Add your key here, False)
    github_token = os.environ.get("GITHUB_TOKEN" # Add your key here, False)
    github_username = os.environ.get('GITHUB_USERNAME', False)
    github_repo = os.environ.get('GITHUB_REPO', False)
    
    # Check database for API keys if not found in environment
    if not openai_key:
        openai_key_db = models.ApiKey.query.filter_by(name='OPENAI_API_KEY').first()
        if openai_key_db:
            openai_key = openai_key_db.value
            
    if not elevenlabs_key:
        elevenlabs_key_db = models.ApiKey.query.filter_by(name='ELEVENLABS_API_KEY').first()
        if elevenlabs_key_db:
            elevenlabs_key = elevenlabs_key_db.value
            
    if not github_token:
        github_token_db = models.ApiKey.query.filter_by(name='GITHUB_TOKEN').first()
        if github_token_db:
            github_token = github_token_db.value
            
    if not github_username:
        github_username_db = models.ApiKey.query.filter_by(name='GITHUB_USERNAME').first()
        if github_username_db:
            github_username = github_username_db.value
            
    if not github_repo:
        github_repo_db = models.ApiKey.query.filter_by(name='GITHUB_REPO').first()
        if github_repo_db:
            github_repo = github_repo_db.value
    
    # Check GitHub configuration
    github_configured = all([github_token, github_username, github_repo])
    
    # Check voice settings
    voice_settings = models.ElevenLabsVoice.query.first()
    
    # Count active feeds
    active_feeds_count = models.RssFeed.query.filter_by(active=True).count()
    
    return render_template('index.html', 
                          episodes=episodes,
                          podcasts=settings,
                          openai_key=openai_key,
                          elevenlabs_key=elevenlabs_key,
                          github_configured=github_configured,
                          voice_settings=voice_settings,
                          active_feeds_count=active_feeds_count)

@app.route('/episode/<int:id>')
@login_required
def episode(id):
    episode = models.Episode.query.get_or_404(id)
    return render_template('episode.html', episode=episode)

@app.route('/settings')
@login_required
def settings():
    # Get all podcasts for the current user
    user_podcasts = models.Settings.query.filter_by(user_id=current_user.id).all()
    
    # API Keys data
    openai_key = os.environ.get("OPENAI_API_KEY" # Add your key here, '')
    elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY" # Add your key here, '')
    github_token = os.environ.get("GITHUB_TOKEN" # Add your key here, '')
    github_username = os.environ.get('GITHUB_USERNAME', '')
    github_repo = os.environ.get('GITHUB_REPO', '')
    
    # If not in environment, check database
    if not openai_key:
        openai_key_db = models.ApiKey.query.filter_by(name='OPENAI_API_KEY').first()
        if openai_key_db:
            openai_key = openai_key_db.value
            
    if not elevenlabs_key:
        elevenlabs_key_db = models.ApiKey.query.filter_by(name='ELEVENLABS_API_KEY').first()
        if elevenlabs_key_db:
            elevenlabs_key = elevenlabs_key_db.value
            
    if not github_token:
        github_token_db = models.ApiKey.query.filter_by(name='GITHUB_TOKEN').first()
        if github_token_db:
            github_token = github_token_db.value
            
    if not github_username:
        github_username_db = models.ApiKey.query.filter_by(name='GITHUB_USERNAME').first()
        if github_username_db:
            github_username = github_username_db.value
            
    if not github_repo:
        github_repo_db = models.ApiKey.query.filter_by(name='GITHUB_REPO').first()
        if github_repo_db:
            github_repo = github_repo_db.value
    
    # Voice settings data
    voice_settings = models.ElevenLabsVoice.query.first()
    try:
        # Get available voices from ElevenLabs API if API key is available
        available_voices = []
        if elevenlabs_key:
            import requests
            headers = {"xi-api-key": elevenlabs_key}
            response = requests.get("https://api.elevenlabs.io/v1/voices", headers=headers)
            if response.status_code == 200:
                voices_data = response.json().get("voices", [])
                available_voices = [{"voice_id": v["voice_id"], "name": v["name"]} for v in voices_data]
    except Exception as e:
        print(f"Error fetching voices: {e}")
        available_voices = []
    
    # Schedule data
    scheduled_podcasts = models.Settings.query.filter(
        models.Settings.user_id == current_user.id,
        models.Settings.auto_generate == True
    ).all()
    
    # Check if scheduler is running
    try:
        import subprocess
        result = subprocess.run(["pgrep", "-f", "run_scheduler.sh"], capture_output=True, text=True)
        scheduler_running = result.returncode == 0
    except Exception:
        scheduler_running = False
    
    # Count active RSS feeds
    active_feeds_count = models.RssFeed.query.filter_by(active=True).count()
    
    return render_template('settings.html', 
                          podcasts=user_podcasts,
                          openai_key=openai_key,
                          elevenlabs_key=elevenlabs_key,
                          github_token=github_token,
                          github_username=github_username,
                          github_repo=github_repo,
                          default_voice=voice_settings,
                          available_voices=available_voices,
                          scheduled_podcasts=scheduled_podcasts,
                          scheduler_running=scheduler_running,
                          active_feeds_count=active_feeds_count)

@app.route('/settings/<int:id>')
@login_required
def edit_podcast(id):
    # Get specific podcast settings
    podcast = models.Settings.query.get_or_404(id)
    
    # Check if the podcast belongs to the current user
    if podcast.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to edit this podcast.', 'danger')
        return redirect(url_for('settings'))
    
    return render_template('edit_podcast.html', podcast=podcast)

@app.route('/settings/new', methods=['GET', 'POST'])
@login_required
def new_podcast():
    if request.method == 'POST':
        # Create new podcast settings
        podcast = models.Settings()
        podcast.podcast_title = request.form.get('podcast_title', f"{current_user.username}'s Podcast")
        podcast.podcast_description = request.form.get('podcast_description', "An AI-generated daily tech news podcast.")
        podcast.podcast_author = request.form.get('podcast_author', current_user.username)
        podcast.podcast_language = request.form.get('podcast_language', 'en-us')
        podcast.podcast_category = request.form.get('podcast_category', 'Technology')
        podcast.podcast_explicit = True  # All podcasts are marked as explicit
        podcast.time_frame = request.form.get('time_frame', 'today')
        podcast.ai_instructions = request.form.get('ai_instructions')
        
        # Initialize RSS slug based on podcast title
        podcast_title = request.form.get('podcast_title', f"{current_user.username}'s Podcast")
        podcast.rss_slug = podcast_title.lower().replace(' ', '-').replace('.', '').replace('&', 'and')
        
        # Get podcast duration (default to 10 minutes if not provided or invalid)
        try:
            podcast_duration = int(request.form.get('podcast_duration', 10))
            if podcast_duration < 1 or podcast_duration > 60:
                podcast_duration = 10  # Set back to default if out of range
        except ValueError:
            podcast_duration = 10
            
        podcast.podcast_duration = podcast_duration
        podcast.user_id = current_user.id
        
        # Add voice settings
        podcast.voice_id = request.form.get('voice_id', '')
        
        # Handle voice stability and similarity boost as floats
        try:
            voice_stability = float(request.form.get('voice_stability', 0.5))
            if voice_stability < 0 or voice_stability > 1:
                voice_stability = 0.5  # Default if out of range
        except (ValueError, TypeError):
            voice_stability = 0.5
            
        try:
            voice_similarity_boost = float(request.form.get('voice_similarity_boost', 0.5))
            if voice_similarity_boost < 0 or voice_similarity_boost > 1:
                voice_similarity_boost = 0.5  # Default if out of range
        except (ValueError, TypeError):
            voice_similarity_boost = 0.5
        
        podcast.voice_stability = voice_stability
        podcast.voice_similarity_boost = voice_similarity_boost
        
        # Handle cover art upload
        if 'cover_art' in request.files:
            file = request.files['cover_art']
            if file and file.filename and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)  # type: ignore
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                filename = f"{timestamp}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                podcast.cover_art_path = f"uploads/{filename}"
        
        db.session.add(podcast)
        db.session.commit()
        
        flash('New podcast created successfully!', 'success')
        return redirect(url_for('settings'))
        
    return render_template('new_podcast.html')

@app.route('/settings/update/<int:id>', methods=['POST'])
@login_required
def update_settings(id):
    podcast = models.Settings.query.get_or_404(id)
    
    # Check if the podcast belongs to the current user
    if podcast.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to edit this podcast.', 'danger')
        return redirect(url_for('settings'))
    
    # Update podcast settings
    podcast.podcast_title = request.form.get('podcast_title')
    podcast.podcast_description = request.form.get('podcast_description')
    podcast.podcast_author = request.form.get('podcast_author')
    podcast.podcast_language = request.form.get('podcast_language')
    podcast.podcast_category = request.form.get('podcast_category')
    podcast.podcast_explicit = True  # All podcasts are marked as explicit
    podcast.time_frame = request.form.get('time_frame', 'today')
    podcast.ai_instructions = request.form.get('ai_instructions')
    
    # Update RSS feed settings
    podcast.rss_slug = request.form.get('rss_slug')
    # If rss_slug is empty, generate one from the podcast title
    if not podcast.rss_slug or podcast.rss_slug.strip() == '':
        if podcast.podcast_title:
            podcast.rss_slug = podcast.podcast_title.lower().replace(' ', '-').replace('.', '').replace('&', 'and')
        else:
            podcast.rss_slug = f"podcast-{podcast.id}"
    
    # Get podcast duration (default to 10 minutes if not provided or invalid)
    try:
        podcast_duration = int(request.form.get('podcast_duration', 10))
        if podcast_duration < 1 or podcast_duration > 60:
            podcast_duration = 10  # Set back to default if out of range
    except ValueError:
        podcast_duration = 10
        
    podcast.podcast_duration = podcast_duration
    
    # Handle cover art upload
    if 'cover_art' in request.files:
        file = request.files['cover_art']
        if file and file.filename and file.filename != '' and allowed_file(file.filename):
            # Delete old cover art if it exists
            if podcast.cover_art_path and os.path.exists(os.path.join('static', podcast.cover_art_path)):
                os.remove(os.path.join('static', podcast.cover_art_path))
            
            # Save new cover art
            filename = secure_filename(file.filename)  # type: ignore
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            filename = f"{timestamp}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            podcast.cover_art_path = f"uploads/{filename}"
    
    # Update voice settings
    podcast.voice_id = request.form.get('voice_id', '')
    
    # Handle voice stability and similarity boost as floats
    try:
        voice_stability = float(request.form.get('voice_stability', 0.5))
        if voice_stability < 0 or voice_stability > 1:
            voice_stability = 0.5  # Default if out of range
    except (ValueError, TypeError):
        voice_stability = 0.5
        
    try:
        voice_similarity_boost = float(request.form.get('voice_similarity_boost', 0.5))
        if voice_similarity_boost < 0 or voice_similarity_boost > 1:
            voice_similarity_boost = 0.5  # Default if out of range
    except (ValueError, TypeError):
        voice_similarity_boost = 0.5
    
    podcast.voice_stability = voice_stability
    podcast.voice_similarity_boost = voice_similarity_boost
    
    db.session.commit()
    flash('Podcast settings updated successfully!', 'success')
    return redirect(url_for('edit_podcast', id=id))

@app.route('/settings/delete/<int:id>')
@login_required
def delete_podcast(id):
    podcast = models.Settings.query.get_or_404(id)
    
    # Check if the podcast belongs to the current user
    if podcast.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to delete this podcast.', 'danger')
        return redirect(url_for('settings'))
    
    # Delete cover art file if it exists
    if podcast.cover_art_path and os.path.exists(os.path.join('static', podcast.cover_art_path)):
        os.remove(os.path.join('static', podcast.cover_art_path))
    
    db.session.delete(podcast)
    db.session.commit()
    
    flash('Podcast deleted successfully!', 'success')
    return redirect(url_for('settings'))

@app.route('/feeds')
@login_required
def feeds():
    # Get podcasts for the user to filter feeds
    podcasts = models.Settings.query.filter_by(user_id=current_user.id).all()
    
    # Get all feeds for the current user's podcasts
    if current_user.is_admin:
        feeds = models.RssFeed.query.all()
    else:
        podcast_ids = [p.id for p in podcasts]
        feeds = models.RssFeed.query.filter(models.RssFeed.podcast_id.in_(podcast_ids)).all()
    
    return render_template('feeds.html', feeds=feeds, podcasts=podcasts)

@app.route('/feeds/add', methods=['POST'])
@login_required
def add_feed():
    name = request.form['name']
    url = request.form['url']
    podcast_id = request.form.get('podcast_id')
    
    if not name or not url:
        flash('Feed name and URL are required!', 'danger')
        return redirect(url_for('feeds'))
    
    # Verify podcast belongs to the current user
    if podcast_id:
        podcast = models.Settings.query.get(podcast_id)
        if not podcast or (podcast.user_id != current_user.id and not current_user.is_admin):
            flash('Invalid podcast selected!', 'danger')
            return redirect(url_for('feeds'))
    
    new_feed = models.RssFeed()
    new_feed.name = name
    new_feed.url = url
    new_feed.active = True
    new_feed.podcast_id = podcast_id
    db.session.add(new_feed)
    db.session.commit()
    flash('Feed added successfully!', 'success')
    return redirect(url_for('feeds'))

@app.route('/feeds/delete/<int:id>')
@login_required
def delete_feed(id):
    feed = models.RssFeed.query.get_or_404(id)
    db.session.delete(feed)
    db.session.commit()
    flash('Feed deleted successfully!', 'success')
    return redirect(url_for('feeds'))

@app.route('/feeds/toggle/<int:id>')
@login_required
def toggle_feed(id):
    feed = models.RssFeed.query.get_or_404(id)
    feed.active = not feed.active
    db.session.commit()
    flash(f'Feed {"activated" if feed.active else "deactivated"} successfully!', 'success')
    return redirect(url_for('feeds'))

@app.route('/api_keys')
@login_required
def api_keys():
    # Redirect to the settings page with the API Keys tab active
    return redirect(url_for('settings', _anchor='nav-api-keys'))

@app.route('/api_keys/update', methods=['POST'])
@login_required
def update_api_keys():
    # Get API keys from form
    openai_key = request.form.get('openai_api_key', '')
    elevenlabs_key = request.form.get('elevenlabs_api_key', '')
    github_token = request.form.get('github_token', '')
    github_username = request.form.get('github_username', '')
    github_repo = request.form.get('github_repo', '')
    
    # Save API keys to database
    # OpenAI API Key
    if openai_key:
        openai_api_key = models.ApiKey.query.filter_by(name='OPENAI_API_KEY').first()
        if openai_api_key:
            openai_api_key.value = openai_key
        else:
            new_key = models.ApiKey()
            new_key.name = 'OPENAI_API_KEY'
            new_key.value = openai_key
            db.session.add(new_key)
    
    # ElevenLabs API Key
    if elevenlabs_key:
        elevenlabs_api_key = models.ApiKey.query.filter_by(name='ELEVENLABS_API_KEY').first()
        if elevenlabs_api_key:
            elevenlabs_api_key.value = elevenlabs_key
        else:
            new_key = models.ApiKey()
            new_key.name = 'ELEVENLABS_API_KEY'
            new_key.value = elevenlabs_key
            db.session.add(new_key)
    
    # GitHub API Key
    if github_token:
        github_api_key = models.ApiKey.query.filter_by(name='GITHUB_TOKEN').first()
        if github_api_key:
            github_api_key.value = github_token
        else:
            new_key = models.ApiKey()
            new_key.name = 'GITHUB_TOKEN'
            new_key.value = github_token
            db.session.add(new_key)
    
    # GitHub Username
    if github_username:
        github_user = models.ApiKey.query.filter_by(name='GITHUB_USERNAME').first()
        if github_user:
            github_user.value = github_username
        else:
            new_key = models.ApiKey()
            new_key.name = 'GITHUB_USERNAME'
            new_key.value = github_username
            db.session.add(new_key)
    
    # GitHub Repo
    if github_repo:
        github_repository = models.ApiKey.query.filter_by(name='GITHUB_REPO').first()
        if github_repository:
            github_repository.value = github_repo
        else:
            new_key = models.ApiKey()
            new_key.name = 'GITHUB_REPO'
            new_key.value = github_repo
            db.session.add(new_key)
    
    db.session.commit()
    flash('API keys updated successfully!', 'success')
    return redirect(url_for('settings', _anchor='nav-api-keys'))

@app.route('/voices')
@login_required
def voices():
    # Redirect to the settings page with the voices tab active
    return redirect(url_for('settings', _anchor='nav-voices'))

@app.route('/voices/update', methods=['POST'])
@login_required
def update_voice():
    voice_id = request.form.get('voice_id', '')
    stability = request.form.get('stability', 0.5)
    similarity_boost = request.form.get('similarity_boost', 0.5)
    
    voice = models.ElevenLabsVoice.query.first()
    if voice:
        voice.voice_id = voice_id
        voice.stability = stability
        voice.similarity_boost = similarity_boost
    else:
        new_voice = models.ElevenLabsVoice()
        new_voice.voice_id = voice_id
        new_voice.stability = float(stability)
        new_voice.similarity_boost = float(similarity_boost)
        db.session.add(new_voice)
    
    db.session.commit()
    flash('Voice settings updated successfully!', 'success')
    return redirect(url_for('settings', _anchor='nav-voices'))

@app.route('/generate_podcast', methods=['GET', 'POST'])
@login_required
def generate_podcast():
    # Get all podcasts for selection
    user_podcasts = models.Settings.query.filter_by(user_id=current_user.id).all()
    
    if request.method == 'POST':
        podcast_id = request.form.get('podcast_id')
        if not podcast_id:
            flash('Please select a podcast to generate content for.', 'warning')
            return redirect(url_for('generate_podcast'))
        
        try:
            # Get the selected podcast settings
            podcast = models.Settings.query.get_or_404(podcast_id)
            
            # Check if the podcast belongs to the current user
            if podcast.user_id != current_user.id and not current_user.is_admin:
                flash('You do not have permission to generate content for this podcast.', 'danger')
                return redirect(url_for('index'))
            
            # Create directory for today's date
            today = datetime.now().strftime('%Y%m%d')
            storage_dir = f'storage/{today}'
            os.makedirs(storage_dir, exist_ok=True)
            
            # Step 1: Fetch RSS feeds - only for this podcast
            active_feeds = models.RssFeed.query.filter_by(
                active=True, 
                podcast_id=podcast.id
            ).all()
            
            if not active_feeds:
                flash('No active RSS feeds found for this podcast! Please add feeds to this podcast.', 'danger')
                return redirect(url_for('feeds'))
                
            feed_urls = [feed.url for feed in active_feeds]
            # Use the podcast's time_frame setting when fetching articles
            # Increase max_articles_per_feed to 15 to get more content
            articles = fetch_rss_feeds(feed_urls, max_articles_per_feed=15, time_frame=podcast.time_frame)
            
            # Save fetched data to JSON
            with open(f'{storage_dir}/data.json', 'w') as f:
                json.dump(articles, f)
                
            # Step 2: Generate podcast script
            podcast_title = podcast.podcast_title
            podcast_description = podcast.podcast_description
            podcast_author = podcast.podcast_author
            ai_instructions = podcast.ai_instructions
            podcast_duration = podcast.podcast_duration
            
            # Pass all relevant podcast settings to the script generator
            script = generate_podcast_script(
                articles, 
                podcast_title=podcast_title,
                podcast_description=podcast_description,
                podcast_author=podcast_author,
                ai_instructions=ai_instructions,
                podcast_duration=podcast_duration
            )
            
            # Save script to file
            script_path = f'{storage_dir}/script.txt'
            with open(script_path, 'w') as f:
                f.write(script)
            
            # Create episode record
            episode = models.Episode()
            episode.title = f"{podcast_title} - {datetime.now().strftime('%Y-%m-%d')}"
            episode.date = datetime.now()
            episode.script = script
            episode.script_path = script_path
            episode.status = "script_generated"
            episode.podcast_id = podcast.id  # Associate the episode with the podcast
            db.session.add(episode)
            db.session.commit()
            
            flash('Podcast script generated successfully!', 'success')
            return redirect(url_for('episode', id=episode.id))
        
        except Exception as e:
            logging.error(f"Error generating podcast: {str(e)}")
            flash(f'Error generating podcast: {str(e)}', 'danger')
            return redirect(url_for('index'))
            
    # GET request - show podcast selection form
    return render_template('generate_podcast.html', podcasts=user_podcasts)

@app.route('/generate_audio/<int:id>')
@login_required
def generate_audio(id):
    try:
        episode = models.Episode.query.get_or_404(id)
        if not episode.script:
            flash('No script found for this episode!', 'danger')
            return redirect(url_for('episode', id=id))
        
        # Get the podcast associated with this episode
        podcast = None
        if episode.podcast_id:
            podcast = models.Settings.query.get(episode.podcast_id)
        
        # Check if the podcast has specific voice settings
        use_podcast_voice = False
        if podcast and podcast.voice_id and podcast.voice_id.strip() != '':
            use_podcast_voice = True
            
            # Create a voice settings object using podcast settings
            class PodcastVoiceSettings:
                def __init__(self, voice_id, stability, similarity_boost):
                    self.voice_id = voice_id
                    self.stability = stability
                    self.similarity_boost = similarity_boost
            
            voice = PodcastVoiceSettings(
                podcast.voice_id,
                podcast.voice_stability or 0.5,
                podcast.voice_similarity_boost or 0.5
            )
        else:
            # Fall back to global voice settings
            voice = models.ElevenLabsVoice.query.first()
            if not voice:
                flash('No voice settings found! Please set up ElevenLabs voice first.', 'danger')
                return redirect(url_for('settings', _anchor='nav-voices'))
        
        # Generate audio
        today = episode.date.strftime('%Y%m%d')
        storage_dir = f'storage/{today}'
        os.makedirs(storage_dir, exist_ok=True)
        
        audio_path = f'{storage_dir}/podcast.mp3'
        audio_url = convert_to_speech(episode.script, voice, audio_path)
        
        # Update episode record
        episode.audio_path = audio_path
        episode.status = "audio_generated"
        db.session.commit()
        
        flash('Podcast audio generated successfully!', 'success')
        return redirect(url_for('episode', id=id))
    
    except Exception as e:
        logging.error(f"Error generating audio: {str(e)}")
        flash(f'Error generating audio: {str(e)}', 'danger')
        return redirect(url_for('episode', id=id))

@app.route('/audio/<path:date>/<filename>')
@login_required
def serve_audio(date, filename):
    """Serve audio files from storage directories"""
    return send_from_directory(f'storage/{date}', filename)

@app.route('/publish/<int:id>')
@login_required
def publish(id):
    try:
        episode = models.Episode.query.get_or_404(id)
        if not episode.audio_path:
            flash('No audio found for this episode! Generate audio first.', 'danger')
            return redirect(url_for('episode', id=id))
        
        # Get GitHub settings from environment variables or database
        github_token = os.environ.get("GITHUB_TOKEN" # Add your key here)
        github_username = os.environ.get('GITHUB_USERNAME')
        github_repo = os.environ.get('GITHUB_REPO')
        
        # If not found in environment variables, check database
        if not github_token:
            github_token_db = models.ApiKey.query.filter_by(name='GITHUB_TOKEN').first()
            if github_token_db:
                github_token = github_token_db.value
                
        if not github_username:
            github_username_db = models.ApiKey.query.filter_by(name='GITHUB_USERNAME').first()
            if github_username_db:
                github_username = github_username_db.value
                
        if not github_repo:
            github_repo_db = models.ApiKey.query.filter_by(name='GITHUB_REPO').first()
            if github_repo_db:
                github_repo = github_repo_db.value
        
        if not github_token or not github_username or not github_repo:
            flash('GitHub settings not found! Please configure GitHub integration first.', 'danger')
            return redirect(url_for('settings', _anchor='nav-api-keys'))
        
        # Publish to GitHub
        success, url = publish_to_github(
            episode, 
            github_token, 
            github_username, 
            github_repo
        )
        
        if success:
            # Update episode record
            episode.publish_url = url
            episode.status = "published"
            episode.publish_date = datetime.now()
            db.session.commit()
            
            flash('Podcast published to GitHub Pages successfully!', 'success')
        else:
            flash(f'Error publishing to GitHub: {url}', 'danger')
            
        return redirect(url_for('episode', id=id))
    
    except Exception as e:
        logging.error(f"Error publishing podcast: {str(e)}")
        flash(f'Error publishing podcast: {str(e)}', 'danger')
        return redirect(url_for('episode', id=id))


@app.route('/schedule')
@login_required
def schedule():
    # Redirect to the settings page with the schedule tab active
    return redirect(url_for('settings', _anchor='nav-schedule'))


@app.route('/schedule/<int:id>/edit')
@login_required
def edit_schedule(id):
    podcast = models.Settings.query.get_or_404(id)
    
    # Check if the podcast belongs to the current user
    if podcast.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to edit this podcast schedule.', 'danger')
        return redirect(url_for('settings', _anchor='nav-schedule'))
        
    return render_template('edit_schedule.html', podcast=podcast)


@app.route('/schedule/<int:id>/update', methods=['POST'])
@login_required
def update_schedule(id):
    podcast = models.Settings.query.get_or_404(id)
    
    # Check if the podcast belongs to the current user
    if podcast.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to update this podcast schedule.', 'danger')
        return redirect(url_for('settings', _anchor='nav-schedule'))
    
    # Update schedule settings
    podcast.auto_generate = 'auto_generate' in request.form
    podcast.schedule_type = request.form.get('schedule_type', 'daily')
    podcast.schedule_hour = int(request.form.get('schedule_hour', 8))
    podcast.schedule_minute = int(request.form.get('schedule_minute', 0))
    podcast.schedule_day = int(request.form.get('schedule_day', 1))
    podcast.auto_publish = 'auto_publish' in request.form
    
    db.session.commit()
    flash('Schedule settings updated successfully!', 'success')
    return redirect(url_for('settings', _anchor='nav-schedule'))


@app.route('/schedule/<int:id>/run-now')
@login_required
def run_scheduler_now(id):
    podcast = models.Settings.query.get_or_404(id)
    
    # Check if the podcast belongs to the current user
    if podcast.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to generate this podcast.', 'danger')
        return redirect(url_for('settings', _anchor='nav-schedule'))
    
    try:
        # Import the scheduler script functions
        from scheduler import generate_scheduled_podcasts
        
        # Set auto_generate to True temporarily to force generation
        original_auto_generate = podcast.auto_generate
        podcast.auto_generate = True
        podcast.last_auto_generated = None  # Reset to force generation
        db.session.commit()
        
        # Run the scheduler
        generate_scheduled_podcasts()
        
        # Restore original auto_generate value
        podcast.auto_generate = original_auto_generate
        db.session.commit()
        
        flash('Podcast generation started!', 'success')
    except Exception as e:
        flash(f'Error generating podcast: {str(e)}', 'danger')
    
    return redirect(url_for('settings', _anchor='nav-schedule'))

@app.route('/scheduler/start')
@login_required
def start_scheduler():
    """Start the scheduler process"""
    try:
        import subprocess
        subprocess.Popen(['bash', 'run_scheduler.sh'])
        flash('Scheduler started successfully!', 'success')
    except Exception as e:
        flash(f'Failed to start scheduler: {str(e)}', 'danger')
    
    return redirect(url_for('settings', _anchor='nav-schedule'))

@app.route('/scheduler/stop')
@login_required
def stop_scheduler():
    """Stop the scheduler process"""
    try:
        import subprocess
        subprocess.run(['bash', 'stop_scheduler.sh'])
        flash('Scheduler stopped successfully!', 'success')
    except Exception as e:
        flash(f'Failed to stop scheduler: {str(e)}', 'danger')
    
    return redirect(url_for('settings', _anchor='nav-schedule'))


@app.route('/podcast/<slug>/rss.xml')
def podcast_rss(slug):
    """Generate and serve podcast-specific RSS feed"""
    from podcast_rss import generate_podcast_rss
    
    # Find the podcast by slug
    podcast = models.Settings.query.filter_by(rss_slug=slug).first()
    if not podcast:
        return "Podcast not found", 404
    
    # Get published episodes for this podcast
    episodes = models.Episode.query.filter_by(
        podcast_id=podcast.id, 
        status="published"
    ).order_by(models.Episode.date.desc()).all()
    
    # Generate the RSS feed
    rss_content = generate_podcast_rss(podcast, episodes)
    
    # Serve the XML with correct content type
    response = app.response_class(
        response=rss_content,
        status=200,
        mimetype='application/rss+xml'
    )
    return response
