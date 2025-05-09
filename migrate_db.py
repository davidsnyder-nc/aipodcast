import os
import logging
from app import app, db
from sqlalchemy import text

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_tables():
    """Create all tables"""
    from app import app, db
    from models import User, Settings, RssFeed, Episode, ElevenLabsVoice, ApiKey
    
    with app.app_context():
        # Create tables
        db.create_all()
        
        # Check if admin user exists, create if not
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User()
            admin.username = 'admin'
            admin.set_password('mindless')
            admin.is_admin = True
            db.session.add(admin)
            db.session.commit()
            print("Admin user created: admin/mindless")
        
        print("Database tables created successfully")
        
def drop_and_recreate_settings():
    """Drop and recreate settings table to add new columns"""
    with app.app_context():
        try:
            # Check if columns exist
            conn = db.engine.connect()
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('settings')]
            
            # Add podcast_language column if not exists
            if 'podcast_language' not in columns:
                logger.info("Adding podcast_language column to settings table")
                conn.execute(text(
                    "ALTER TABLE settings ADD COLUMN podcast_language VARCHAR(50) DEFAULT 'en-us' NOT NULL"
                ))
            
            # Add podcast_category column if not exists
            if 'podcast_category' not in columns:
                logger.info("Adding podcast_category column to settings table")
                conn.execute(text(
                    "ALTER TABLE settings ADD COLUMN podcast_category VARCHAR(100) DEFAULT 'Technology' NOT NULL"
                ))
            
            # Add podcast_explicit column if not exists
            if 'podcast_explicit' not in columns:
                logger.info("Adding podcast_explicit column to settings table")
                conn.execute(text(
                    "ALTER TABLE settings ADD COLUMN podcast_explicit BOOLEAN DEFAULT FALSE"
                ))
            
            # Add cover_art_path column if not exists
            if 'cover_art_path' not in columns:
                logger.info("Adding cover_art_path column to settings table")
                conn.execute(text(
                    "ALTER TABLE settings ADD COLUMN cover_art_path VARCHAR(255) NULL"
                ))
                
            # Commit the transaction
            conn.commit()
            logger.info("Settings table migration completed successfully")
            
        except Exception as e:
            logger.error(f"Error migrating settings table: {str(e)}")
            raise

def add_user_id_to_settings():
    """Add user_id column to settings table"""
    from app import app, db
    
    with app.app_context():
        try:
            conn = db.engine.connect()
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('settings')]
            
            # Add user_id column if not exists
            if 'user_id' not in columns:
                logger.info("Adding user_id column to settings table")
                conn.execute(text(
                    "ALTER TABLE settings ADD COLUMN user_id INTEGER NULL"
                ))
                conn.commit()
            
            # Add foreign key if possible (may require dropping constraints first)
            logger.info("Settings table user_id column added successfully")
                
        except Exception as e:
            logger.error(f"Error adding user_id to settings table: {str(e)}")
            raise
            
def add_time_frame_to_settings():
    """Add time_frame column to settings table"""
    from app import app, db
    
    with app.app_context():
        try:
            conn = db.engine.connect()
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('settings')]
            
            # Add time_frame column if not exists
            if 'time_frame' not in columns:
                logger.info("Adding time_frame column to settings table")
                conn.execute(text(
                    "ALTER TABLE settings ADD COLUMN time_frame VARCHAR(20) DEFAULT 'today' NOT NULL"
                ))
                conn.commit()
                logger.info("Settings table time_frame column added successfully")
                
        except Exception as e:
            logger.error(f"Error adding time_frame to settings table: {str(e)}")
            raise

def migrate_database():
    """Run all migration steps"""
    from app import app, db
    
    with app.app_context():
        try:
            # Create all tables (including new ones like users)
            create_tables()
            
            # Add new columns to existing tables
            drop_and_recreate_settings()
            add_user_id_to_settings()
            add_time_frame_to_settings()
            
            logger.info("Database migration completed successfully")
        except Exception as e:
            logger.error(f"Error migrating database: {str(e)}")
            raise

if __name__ == "__main__":
    migrate_database()
    logger.info("Database migration completed")