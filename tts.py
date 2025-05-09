import os
import requests
import logging
from models import ElevenLabsVoice

def get_elevenlabs_api_key():
    """
    Get ElevenLabs API key from environment variables or database
    
    Returns:
        str: ElevenLabs API key
    """
    # First try environment variable
    elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY" # Add your key here)
    
    # If not found in environment, check database
    if not elevenlabs_api_key:
        from app import app, db
        import models
        with app.app_context():
            api_key = models.ApiKey.query.filter_by(name="ELEVENLABS_API_KEY").first()
            if api_key:
                elevenlabs_api_key = api_key.value
        
    if not elevenlabs_api_key:
        logging.error("ElevenLabs API key not found in environment variables or database")
        return None
    
    # Ensure API key doesn't have extra whitespace or unexpected text
    elevenlabs_api_key = elevenlabs_api_key.strip()
    
    # If key has spaces, take only the first part (the actual API key)
    if ' ' in elevenlabs_api_key:
        logging.warning("ElevenLabs API key contains spaces. Using only the first part.")
        elevenlabs_api_key = elevenlabs_api_key.split()[0]
        
    return elevenlabs_api_key

def convert_to_speech(text, voice_settings, output_path):
    """
    Convert text to speech using ElevenLabs API
    
    Args:
        text (str): Text to convert to speech
        voice_settings (ElevenLabsVoice): Voice settings
        output_path (str): Path to save the audio file
        
    Returns:
        str: Path to the generated audio file
    """
    api_key = get_elevenlabs_api_key()
    if not api_key:
        raise Exception("ElevenLabs API key not found")
    
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Set up API request
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_settings.voice_id}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }
        
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": voice_settings.stability,
                "similarity_boost": voice_settings.similarity_boost
            }
        }
        
        logging.debug(f"Sending TTS request to ElevenLabs for text of length {len(text)}")
        
        # Make API request
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 200:
            # Save the audio file
            with open(output_path, 'wb') as f:
                f.write(response.content)
                
            logging.info(f"Successfully generated audio file at {output_path}")
            return output_path
        else:
            error_msg = f"ElevenLabs API request failed with status code {response.status_code}: {response.text}"
            logging.error(error_msg)
            raise Exception(error_msg)
    
    except Exception as e:
        logging.error(f"Error converting text to speech: {str(e)}")
        raise Exception(f"Error converting text to speech: {str(e)}")
