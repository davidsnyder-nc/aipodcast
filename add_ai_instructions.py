import os
import logging
from sqlalchemy import create_engine, text

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.environ.get("DATABASE_URL")

def add_ai_instructions_column():
    """Add ai_instructions column to settings table"""
    try:
        # Create engine and connect
        engine = create_engine(DATABASE_URL)
        conn = engine.connect()
        
        # Check if column exists
        result = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'settings' AND column_name = 'ai_instructions'"
        ))
        columns = result.fetchall()
        
        # Add ai_instructions column if not exists
        if not columns:
            logger.info("Adding ai_instructions column to settings table")
            conn.execute(text(
                "ALTER TABLE settings ADD COLUMN ai_instructions TEXT DEFAULT NULL"
            ))
            conn.commit()
            logger.info("Settings table ai_instructions column added successfully")
        else:
            logger.info("ai_instructions column already exists in settings table")
            
        conn.close()
        
    except Exception as e:
        logger.error(f"Error adding ai_instructions to settings table: {str(e)}")
        raise

if __name__ == "__main__":
    add_ai_instructions_column()
    logger.info("Migration completed")