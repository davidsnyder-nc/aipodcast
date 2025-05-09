import os
import logging
from sqlalchemy import create_engine, text

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.environ.get("DATABASE_URL")

def add_time_frame_column():
    """Add time_frame column to settings table"""
    try:
        # Create engine and connect
        engine = create_engine(DATABASE_URL)
        conn = engine.connect()
        
        # Check if column exists
        result = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'settings' AND column_name = 'time_frame'"
        ))
        columns = result.fetchall()
        
        # Add time_frame column if not exists
        if not columns:
            logger.info("Adding time_frame column to settings table")
            conn.execute(text(
                "ALTER TABLE settings ADD COLUMN time_frame VARCHAR(20) DEFAULT 'today' NOT NULL"
            ))
            conn.commit()
            logger.info("Settings table time_frame column added successfully")
        else:
            logger.info("time_frame column already exists in settings table")
            
        conn.close()
        
    except Exception as e:
        logger.error(f"Error adding time_frame to settings table: {str(e)}")
        raise

if __name__ == "__main__":
    add_time_frame_column()
    logger.info("Migration completed")