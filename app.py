import os
import time
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
@app.route('/help')
@login_required
def help():
    """Help and documentation page"""
    return render_template('help.html')

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
        podcast.host_name = request.form.get('host_name')
        podcast.podcast_language = request.form.get('podcast_language', 'en-us')
        podcast.podcast_category = request.form.get('podcast_category', 'Technology')
        podcast.podcast_explicit = True  # All podcasts are marked as explicit
        podcast.time_frame = request.form.get('time_frame', 'today')
        podcast.ai_instructions = request.form.get('ai_instructions')
        podcast.blocked_terms = request.form.get('blocked_terms')
        podcast.openai_model = request.form.get('openai_model', 'gpt-3.5-turbo')
        
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
        
        # Handle cover art upload or use AI-generated cover
        if 'cover_art' in request.files:
            file = request.files['cover_art']
            if file and file.filename and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)  # type: ignore
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                filename = f"{timestamp}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                podcast.cover_art_path = f"uploads/{filename}"
        elif request.form.get('generated_cover_path'):
            # Use the AI-generated cover art
            generated_path = request.form.get('generated_cover_path', '')
            import logging
            logging.warning(f"COVER ART DEBUG - New podcast - Generated cover path from form: {generated_path}")
            
            if generated_path:
                # The path should already be correct (relative to static)
                # But let's ensure it doesn't have any 'static/' prefix 
                db_path = generated_path
                if db_path.startswith('static/'):
                    db_path = db_path.replace('static/', '')
                
                logging.warning(f"COVER ART DEBUG - New podcast - Path for DB storage: {db_path}")
                
                # Set the new cover art path
                podcast.cover_art_path = db_path
                logging.warning(f"COVER ART DEBUG - New podcast - Updated podcast cover art path to: {db_path}")
                
                # Verify the file exists
                full_path = os.path.join('static', db_path)
                if os.path.exists(full_path):
                    logging.warning(f"COVER ART DEBUG - New podcast - Cover art file exists at: {full_path}")
                else:
                    logging.warning(f"COVER ART DEBUG - New podcast - WARNING: Cover art file does not exist at: {full_path}")
        
        # Handle RSS feed sources
        feed_sources = request.form.getlist('feed_sources[]')
        
        db.session.add(podcast)
        db.session.commit()
        
        # Create RSS feed associations for the selected sources
        if feed_sources:
            rss_feed_mapping = {
                'hacker_news': 'https://news.ycombinator.com/rss',
                'tech_crunch': 'https://techcrunch.com/feed/',
                'the_verge': 'https://www.theverge.com/rss/index.xml',
                'wired': 'https://www.wired.com/feed/rss',
                'openai_blog': 'https://openai.com/blog/rss/',
                'dev_to': 'https://dev.to/feed',
                'github_blog': 'https://github.blog/feed/',
                'huggingface_blog': 'https://huggingface.co/blog/feed.xml',
                'forbes': 'https://www.forbes.com/business/feed/',
                'bloomberg': 'https://www.bloomberg.com/feed/technology/feed.xml',
                'wsj': 'https://feeds.a.dj.com/rss/RSSWSJD.xml',
                'vc': 'https://news.crunchbase.com/feed/',
                'saastr': 'https://www.saastr.com/feed/',
                'product_hunt': 'https://www.producthunt.com/feed'
            }
            
            for source_id in feed_sources:
                if source_id in rss_feed_mapping:
                    feed = models.RssFeed()
                    feed.name = source_id.replace('_', ' ').title()  # Transform id to readable name
                    feed.url = rss_feed_mapping[source_id]
                    feed.active = True
                    feed.podcast_id = podcast.id  # Associate with the newly created podcast
                    feed.user_id = current_user.id
                    db.session.add(feed)
            
            db.session.commit()
            flash(f'Added {len(feed_sources)} RSS feeds to your podcast.', 'success')
        
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
    podcast.host_name = request.form.get('host_name')
    podcast.podcast_language = request.form.get('podcast_language')
    podcast.podcast_category = request.form.get('podcast_category')
    podcast.podcast_explicit = True  # All podcasts are marked as explicit
    podcast.time_frame = request.form.get('time_frame', 'today')
    podcast.ai_instructions = request.form.get('ai_instructions')
    podcast.blocked_terms = request.form.get('blocked_terms')
    podcast.openai_model = request.form.get('openai_model', 'gpt-3.5-turbo')
    
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
    
    # Handle cover art upload or use AI-generated cover
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
    elif request.form.get('generated_cover_path'):
        # Use the AI-generated cover art
        generated_path = request.form.get('generated_cover_path', '')
        import logging
        logging.info(f"Edit podcast - Generated cover path from form: {generated_path}")
            
        if generated_path:
            # The path should already be correct (relative to static)
            # But let's ensure it doesn't have any 'static/' prefix 
            db_path = generated_path
            if db_path.startswith('static/'):
                db_path = db_path.replace('static/', '')
                
            logging.info(f"Edit podcast - Path for DB storage: {db_path}")
            
            # Check if the file exists
            full_path = os.path.join('static', db_path)
            logging.info(f"Edit podcast - Full file path to check: {full_path}")
            
            # SIMPLIFIED APPROACH: Trust the path we received and assign it directly
            # Delete old cover art if it exists and it's different from what we're saving
            if podcast.cover_art_path and podcast.cover_art_path != db_path and os.path.exists(os.path.join('static', podcast.cover_art_path)):
                try:
                    logging.warning(f"COVER ART DEBUG - Deleting old cover art: {podcast.cover_art_path}")
                    os.remove(os.path.join('static', podcast.cover_art_path))
                except Exception as e:
                    logging.warning(f"COVER ART DEBUG - Failed to delete old cover art: {str(e)}")
            
            # Set the new cover art path
            podcast.cover_art_path = db_path
            logging.warning(f"COVER ART DEBUG - Updated podcast cover art path to: {db_path}")
            
            # Verify the file exists
            if os.path.exists(full_path):
                logging.warning(f"COVER ART DEBUG - Cover art file exists at: {full_path}")
            else:
                logging.warning(f"COVER ART DEBUG - WARNING: Cover art file does not exist at: {full_path}")
    
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

@app.route('/generate_cover_art', methods=['POST'])
@login_required
def generate_cover_art():
    """
    Generate podcast cover art using DALL-E
    """
    import logging
    from gpt import generate_podcast_artwork
    
    try:
        data = request.json
        podcast_title = data.get('podcast_title', 'My Podcast')
        podcast_description = data.get('podcast_description', '')
        podcast_category = data.get('category', 'Technology')
        
        # Call the function to generate artwork
        success, result = generate_podcast_artwork(
            podcast_title=podcast_title,
            podcast_description=podcast_description,
            podcast_category=podcast_category
        )
        
        if success:
            # The result from generate_podcast_artwork is now standardized
            # It returns just the relative path within static/ folder
            relative_path = result.replace('\\', '/')
            logging.warning(f"COVER ART DEBUG - Generated art path from DALL-E (relative to static/): {relative_path}")
            
            # Verify the file exists
            full_path = os.path.join('static', relative_path)
            if os.path.exists(full_path):
                logging.warning(f"COVER ART DEBUG - Generated cover art file exists at: {full_path}")
            else:
                logging.warning(f"COVER ART DEBUG - WARNING: Generated cover art file does not exist at: {full_path}")
            
            # Return both the file path and URL for the image
            return jsonify({
                "success": True, 
                "file_path": relative_path,
                "image_url": url_for('static', filename=relative_path),
                "message": "Cover art generated successfully!"
            })
        else:
            return jsonify({"success": False, "error": result}), 500
            
    except Exception as e:
        logging.error(f"Error generating cover art: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/generate_podcast', methods=['GET', 'POST'])
@login_required
def generate_podcast():
    # Get all podcasts for selection
    user_podcasts = models.Settings.query.filter_by(user_id=current_user.id).all()
    
    if request.method == 'POST':
        podcast_ids = request.form.getlist('podcast_ids[]')
        if not podcast_ids:
            flash('Please select at least one podcast to generate content for.', 'warning')
            return redirect(url_for('generate_podcast'))
        
        # We'll track which podcasts were processed successfully
        successful_podcasts = []
        failed_podcasts = []
        
        for podcast_id in podcast_ids:
            try:
                # Get the selected podcast settings
                podcast = models.Settings.query.get(podcast_id)
                if not podcast:
                    failed_podcasts.append(f"Podcast ID {podcast_id} not found")
                    continue
                
                # Check if the podcast belongs to the current user
                if podcast.user_id != current_user.id and not current_user.is_admin:
                    failed_podcasts.append(f"No permission for podcast: {podcast.podcast_title}")
                    continue
                
                # Create directory for today's date
                today = datetime.now().strftime('%Y%m%d')
                storage_dir = f'storage/{today}/{podcast.id}'  # Add podcast ID to path to avoid conflicts
                os.makedirs(storage_dir, exist_ok=True)
                
                # Step 1: Fetch RSS feeds - only for this podcast
                active_feeds = models.RssFeed.query.filter_by(
                    active=True, 
                    podcast_id=podcast.id
                ).all()
                
                if not active_feeds:
                    failed_podcasts.append(f"No active RSS feeds for: {podcast.podcast_title}")
                    continue
                    
                feed_urls = [feed.url for feed in active_feeds]
                logging.info(f"Fetching articles from {len(feed_urls)} RSS feeds for podcast '{podcast.podcast_title}'")
                
                try:
                    # Use the podcast's time_frame setting and blocked_terms when fetching articles
                    # Increase max_articles_per_feed to 15 to get more content
                    articles = fetch_rss_feeds(
                        feed_urls,
                        max_articles_per_feed=15, 
                        time_frame=podcast.time_frame,
                        blocked_terms=podcast.blocked_terms
                    )
                    
                    if not articles:
                        failed_podcasts.append(f"No articles found for: {podcast.podcast_title}")
                        continue
                        
                    logging.info(f"Found {len(articles)} articles from RSS feeds for '{podcast.podcast_title}'")
                    
                    # Save fetched data to JSON
                    with open(f'{storage_dir}/data.json', 'w') as f:
                        json.dump(articles, f)
                    
                    # Step 2: Generate podcast script
                    podcast_title = podcast.podcast_title
                    podcast_description = podcast.podcast_description
                    podcast_author = podcast.podcast_author
                    host_name = podcast.host_name
                    ai_instructions = podcast.ai_instructions
                    podcast_duration = podcast.podcast_duration
                    openai_model = podcast.openai_model
                    
                    logging.info(f"Generating podcast script for '{podcast_title}' using model {openai_model}")
                    
                    # Pass all relevant podcast settings to the script generator including the AI model
                    script = generate_podcast_script(
                        articles, 
                        podcast_title=podcast_title,
                        podcast_description=podcast_description,
                        podcast_author=podcast_author,
                        host_name=host_name,
                        ai_instructions=ai_instructions,
                        podcast_duration=podcast_duration,
                        openai_model=openai_model
                    )
                    
                    if not script or len(script.strip()) < 100:  # Basic validation
                        failed_podcasts.append(f"Generated script too short for: {podcast.podcast_title}")
                        continue
                    
                    # Save script to file
                    script_path = f'{storage_dir}/script.txt'
                    with open(script_path, 'w') as f:
                        f.write(script)
                    
                    logging.info(f"Script generated successfully for '{podcast.podcast_title}', length: {len(script)} characters")
                    
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
                    
                    # Add to successful podcasts list
                    successful_podcasts.append({"title": podcast.podcast_title, "episode_id": episode.id})
                    
                except Exception as e:
                    error_msg = str(e)
                    logging.error(f"Error generating podcast '{podcast.podcast_title}': {error_msg}")
                    failed_podcasts.append(f"Error for {podcast.podcast_title}: {error_msg[:100]}...")
            
            except Exception as e:
                error_msg = str(e)
                logging.error(f"Error processing podcast ID {podcast_id}: {error_msg}")
                failed_podcasts.append(f"Error processing podcast ID {podcast_id}: {error_msg[:100]}...")
        
        # After processing all podcasts, show summary
        if successful_podcasts:
            if len(successful_podcasts) == 1:
                # If only one podcast was processed successfully, redirect to its episode page
                flash(f"Successfully generated podcast: {successful_podcasts[0]['title']}", 'success')
                return redirect(url_for('episode', id=successful_podcasts[0]['episode_id']))
            else:
                # If multiple podcasts were processed, redirect to the episodes list with a summary
                flash(f"Successfully generated {len(successful_podcasts)} podcasts: " + 
                      ", ".join(p['title'] for p in successful_podcasts), 'success')
                return redirect(url_for('index'))
        
        # If no podcasts were processed successfully, show errors
        if failed_podcasts:
            for error in failed_podcasts:
                flash(error, 'danger')
        
        return redirect(url_for('generate_podcast'))
    
    # GET request - show podcast selection form
    return render_template('generate_podcast.html', podcasts=user_podcasts)

@app.route('/generate_audio/<int:id>')
@login_required
def generate_audio(id):
    """
    Generate audio for an episode - SIMPLE DIRECT VERSION
    No background tasks or progress tracking, just a direct call to generate audio
    """
    try:
        # Get the episode
        logging.info(f"Starting direct audio generation for episode ID {id}")
        episode = models.Episode.query.get_or_404(id)
        
        if not episode.script:
            logging.error(f"No script found for episode ID {id}")
            flash('No script found for this episode!', 'danger')
            return redirect(url_for('episode', id=id))
        
        # Get the podcast
        podcast = None
        if episode.podcast_id:
            podcast = models.Settings.query.get(episode.podcast_id)
        
        # Get voice settings - either from podcast or fallback to global
        if podcast and podcast.voice_id and podcast.voice_id.strip():
            # Create voice settings from podcast
            class VoiceSettings:
                def __init__(self, voice_id, stability, similarity_boost):
                    self.voice_id = voice_id
                    self.stability = stability
                    self.similarity_boost = similarity_boost
            
            voice = VoiceSettings(
                podcast.voice_id,
                podcast.voice_stability or 0.5,
                podcast.voice_similarity_boost or 0.5
            )
            logging.info(f"Using podcast voice ID: {voice.voice_id}")
        else:
            # Use global voice settings
            voice = models.ElevenLabsVoice.query.first()
            if not voice:
                flash('No voice settings found! Please configure voice settings first.', 'danger')
                return redirect(url_for('voices'))
            logging.info(f"Using global voice ID: {voice.voice_id}")
        
        # Set up audio storage path
        today = episode.date.strftime('%Y%m%d')
        storage_dir = f'storage/{today}'
        os.makedirs(storage_dir, exist_ok=True)
        audio_path = f'{storage_dir}/podcast.mp3'
        
        # Import the TTS module
        from tts import convert_to_speech
        
        # Update episode status
        episode.status = "generating_audio"
        db.session.commit()
        
        # Start a separate thread to generate audio
        def generate_audio_thread():
            try:
                # Import needed modules in thread
                import logging
                import os
                from app import db
                import models
                from tts import convert_to_speech
                
                logging.info(f"Thread started for audio generation of episode {id}")
                
                # Generate the audio file
                audio_result = convert_to_speech(episode.script, voice, audio_path)
                
                # Check if generation was successful
                if audio_result and os.path.exists(audio_result):
                    # Update episode status to success
                    with db.session.begin():
                        episode = models.Episode.query.get(id)
                        if episode:
                            episode.audio_path = audio_path
                            episode.status = "audio_generated"
                            logging.info(f"Audio generation successful for episode {id}")
                        else:
                            logging.error(f"Episode {id} not found after audio generation")
                else:
                    # Update episode status to failure
                    with db.session.begin():
                        episode = models.Episode.query.get(id)
                        if episode:
                            episode.status = "script_generated"  # Revert to previous state
                            logging.error(f"Audio generation failed for episode {id}")
                        else:
                            logging.error(f"Episode {id} not found after audio generation")
            
            except Exception as e:
                # Log the error and update episode status
                error_msg = f"Error generating audio: {str(e)}"
                logging.error(error_msg)
                
                try:
                    with db.session.begin():
                        episode = models.Episode.query.get(id)
                        if episode:
                            episode.status = "script_generated"  # Revert to previous state
                            logging.info(f"Reverted episode {id} status due to error")
                except Exception as db_error:
                    logging.error(f"Database error updating episode status: {str(db_error)}")
        
        # Start generation in a separate thread
        import threading
        thread = threading.Thread(target=generate_audio_thread)
        thread.daemon = True
        thread.start()
        
        # Return to episode page with message
        flash('Audio generation started. This may take a few minutes. Check back soon to see if audio is ready.', 'info')
        return redirect(url_for('episode', id=id))
    
    except Exception as e:
        logging.error(f"Error initiating audio generation: {str(e)}")
        flash(f'Error initiating audio generation: {str(e)}', 'danger')
        
        # Make sure to reset episode status
        try:
            episode = models.Episode.query.get(id)
            if episode:
                episode.status = "script_generated"  # Revert to previous state
                db.session.commit()
        except:
            pass
            
        return redirect(url_for('episode', id=id))

@app.route('/audio_status/<int:id>/<task_id>')
@login_required
def audio_generation_status(id, task_id):
    """Show status of audio generation"""
    episode = models.Episode.query.get_or_404(id)
    
    from background_task import get_task_status, get_task_result
    
    # Get the status of the task
    status = get_task_status(task_id)
    
    # If the task is complete, redirect to the episode page
    if status and status.get('status') == 'completed':
        flash('Podcast audio generated successfully!', 'success')
        return redirect(url_for('episode', id=id))
    
    # If the task failed, show an error
    if status and status.get('status') == 'failed':
        error_message = status.get('error', 'Unknown error')
        flash(f'Audio generation failed: {error_message}', 'danger')
        return redirect(url_for('episode', id=id))
    
    # Otherwise, render a template showing the progress
    return render_template(
        'audio_status.html', 
        episode=episode, 
        task_id=task_id, 
        status=status
    )

@app.route('/api/task_status/<task_id>')
@login_required
def task_status_api(task_id):
    """API endpoint for getting task status"""
    from background_task import get_task_status
    import logging
    
    # Log the request for debugging
    logging.info(f"Task status request received for task_id: {task_id}")
    
    try:
        # Get the status of the task
        status = get_task_status(task_id)
        
        # Log the response for debugging
        logging.info(f"Returning task status for {task_id}: {status}")
        
        # Always return a valid JSON response
        if not status or not isinstance(status, dict):
            logging.warning(f"Invalid status returned for task {task_id}: {status}")
            return jsonify({
                'status': 'unknown',
                'progress': 0,
                'message': 'Task status information not available',
                'error': 'Task status retrieval failed'
            }), 404
        
        return jsonify(status)
    
    except Exception as e:
        # Log the error
        error_msg = f"Error retrieving task status: {str(e)}"
        logging.error(error_msg)
        
        # Return a fallback response
        return jsonify({
            'status': 'error',
            'progress': 0,
            'message': 'Error retrieving task status',
            'error': str(e)
        }), 500

@app.route('/audio/<path:date>/<filename>')
@login_required
def serve_audio(date, filename):
    """Serve audio files from storage directories"""
    return send_from_directory(f'storage/{date}', filename)

@app.route('/delete_audio/<int:id>')
@login_required
def delete_audio(id):
    """Delete audio file for an episode"""
    episode = models.Episode.query.get_or_404(id)
    
    # Check if the episode belongs to the current user's podcasts
    podcast = models.Settings.query.get_or_404(episode.podcast_id)
    if podcast.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to delete this audio file.', 'danger')
        return redirect(url_for('episode', id=id))
    
    if episode.audio_path:
        try:
            # Get audio file path
            date_folder = episode.audio_path.split('/')[1]
            audio_path = os.path.join('storage', date_folder, 'podcast.mp3')
            
            # Delete the audio file if it exists
            if os.path.exists(audio_path):
                os.remove(audio_path)
                logging.info(f"Deleted audio file: {audio_path}")
            
            # Update episode status
            if episode.status == 'published':
                # If published, keep track that it was published but audio is now deleted
                episode.status = 'published_no_audio'
            else:
                # If not published, revert to script_generated status
                episode.status = 'script_generated'
            
            # Clear audio_path
            episode.audio_path = None
            db.session.commit()
            
            flash('Audio file deleted successfully.', 'success')
        except Exception as e:
            logging.error(f"Error deleting audio file: {str(e)}")
            flash(f'Error deleting audio file: {str(e)}', 'danger')
    else:
        flash('No audio file found for this episode.', 'warning')
    
    return redirect(url_for('episode', id=id))

@app.route('/delete_episode/<int:id>')
@login_required
def delete_episode(id):
    """Delete an episode"""
    episode = models.Episode.query.get_or_404(id)
    
    # Check if the episode belongs to the current user's podcasts
    podcast = models.Settings.query.get_or_404(episode.podcast_id)
    if podcast.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to delete this episode.', 'danger')
        return redirect(url_for('index'))
    
    try:
        # If episode has audio, delete the audio file first
        if episode.audio_path:
            try:
                # Get audio file path
                date_folder = episode.audio_path.split('/')[1]
                audio_path = os.path.join('storage', date_folder, 'podcast.mp3')
                
                # Delete the audio file if it exists
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                    logging.info(f"Deleted audio file: {audio_path}")
            except Exception as e:
                logging.error(f"Error deleting audio file: {str(e)}")
                # Continue with episode deletion even if audio file deletion fails
        
        # Store episode title for flash message
        episode_title = episode.title
        
        # Delete the episode
        db.session.delete(episode)
        db.session.commit()
        
        flash(f'Episode "{episode_title}" deleted successfully.', 'success')
    except Exception as e:
        logging.error(f"Error deleting episode: {str(e)}")
        flash(f'Error deleting episode: {str(e)}', 'danger')
    
    return redirect(url_for('index'))

@app.route('/publish/<int:id>')
@login_required
def publish(id):
    """
    Publish a podcast episode to GitHub Pages
    
    Creates an RSS feed and uploads audio files to GitHub repository
    to be served via GitHub Pages.
    """
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
        logging.info(f"Publishing episode {id} to GitHub Pages")
        
        # Get associated podcast settings
        podcast_settings = episode.settings  # This should be accessible through the relationship
        podcast_title = podcast_settings.title if podcast_settings else "Daily Tech Insights"
        
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
            
            flash(f'Podcast "{episode.title}" published successfully! Accessible at: <a href="{url}" target="_blank">{url}</a>', 'success')
            logging.info(f"Episode {id} published successfully to {url}")
        else:
            flash(f'Error publishing to GitHub: {url}', 'danger')
            logging.error(f"Failed to publish episode {id}: {url}")
            
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
