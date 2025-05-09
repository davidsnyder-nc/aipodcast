from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    avatar_path = db.Column(db.String(255), nullable=True)  # Path to user's avatar image
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    podcasts = db.relationship('Settings', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Settings(db.Model):
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True)
    podcast_title = db.Column(db.String(255), nullable=False, default="Daily Tech Insights")
    podcast_description = db.Column(db.Text, nullable=False, default="An AI-generated daily tech news podcast covering the latest in technology and startups.")
    podcast_author = db.Column(db.String(255), nullable=False, default="AI Podcast Generator")
    podcast_language = db.Column(db.String(10), nullable=False, default="en-us")
    podcast_category = db.Column(db.String(100), nullable=False, default="Technology")
    podcast_explicit = db.Column(db.Boolean, default=False)
    time_frame = db.Column(db.String(20), nullable=False, default="today")  # Options: today, week, month
    ai_instructions = db.Column(db.Text, nullable=True, default=None)  # Custom instructions for the AI
    podcast_duration = db.Column(db.Integer, nullable=False, default=10)  # Target duration in minutes
    cover_art_path = db.Column(db.String(255), nullable=True)
    voice_id = db.Column(db.String(255), nullable=True)  # Podcast-specific voice ID
    voice_stability = db.Column(db.Float, default=0.5)  # Voice stability setting
    voice_similarity_boost = db.Column(db.Float, default=0.5)  # Voice similarity boost setting
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Podcast RSS settings
    rss_slug = db.Column(db.String(100), nullable=True)  # URL-friendly slug for podcast RSS feed
    rss_description = db.Column(db.Text, nullable=True)  # RSS-specific description (optional)
    rss_copyright = db.Column(db.String(255), nullable=True)  # Copyright info for RSS
    rss_owner_name = db.Column(db.String(255), nullable=True)  # Owner name for RSS
    rss_owner_email = db.Column(db.String(255), nullable=True)  # Owner email for RSS
    rss_image_url = db.Column(db.String(255), nullable=True)  # Custom image URL for RSS
    
    # Scheduling options
    auto_generate = db.Column(db.Boolean, default=False)  # Enable automatic generation
    schedule_type = db.Column(db.String(20), default="daily")  # daily, weekly, custom
    schedule_hour = db.Column(db.Integer, default=8)  # Hour of the day to generate (0-23)
    schedule_minute = db.Column(db.Integer, default=0)  # Minute of the hour (0-59)
    schedule_day = db.Column(db.Integer, default=1)  # Day of week for weekly (0=Monday, 6=Sunday)
    auto_publish = db.Column(db.Boolean, default=False)  # Auto publish to GitHub
    last_auto_generated = db.Column(db.DateTime, nullable=True)  # Last auto-generation time
    
    # Relationships
    episodes = db.relationship('Episode', backref='podcast', lazy=True, foreign_keys='Episode.podcast_id')
    feeds = db.relationship('RssFeed', backref='podcast', lazy=True, foreign_keys='RssFeed.podcast_id')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RssFeed(db.Model):
    __tablename__ = 'rss_feeds'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, default=True)
    last_fetched = db.Column(db.DateTime, nullable=True)
    podcast_id = db.Column(db.Integer, db.ForeignKey('settings.id'), nullable=True)  # Associate with specific podcast
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Episode(db.Model):
    __tablename__ = 'episodes'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    script = db.Column(db.Text, nullable=True)
    script_path = db.Column(db.String(255), nullable=True)
    audio_path = db.Column(db.String(255), nullable=True)
    publish_url = db.Column(db.String(255), nullable=True)
    publish_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(50), default="draft")  # draft, script_generated, audio_generated, published
    podcast_id = db.Column(db.Integer, db.ForeignKey('settings.id'), nullable=True)  # Associate with specific podcast
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ElevenLabsVoice(db.Model):
    __tablename__ = 'elevenlabs_voices'
    
    id = db.Column(db.Integer, primary_key=True)
    voice_id = db.Column(db.String(255), nullable=False)
    stability = db.Column(db.Float, default=0.5)
    similarity_boost = db.Column(db.Float, default=0.5)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ApiKey(db.Model):
    __tablename__ = 'api_keys'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    value = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
