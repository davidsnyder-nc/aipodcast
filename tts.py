import os
import io
import time
import requests
import logging
import subprocess
from pydub import AudioSegment
from models import ElevenLabsVoice

# Configure pydub to find ffmpeg
from pydub.utils import which
AudioSegment.converter = which("ffmpeg") or "/usr/bin/ffmpeg"

def get_elevenlabs_api_key():
    """
    Get ElevenLabs API key from environment variables or database
    
    Returns:
        str: ElevenLabs API key
    """
    logging.info("Retrieving ElevenLabs API key")
    
    # First try environment variable
    elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY" # Add your key here)
    if elevenlabs_api_key:
        logging.info("Found ElevenLabs API key in environment variables")
    
    # If not found in environment, check database
    if not elevenlabs_api_key:
        logging.info("ElevenLabs API key not found in environment, checking database")
        from app import app, db
        import models
        with app.app_context():
            api_key = models.ApiKey.query.filter_by(name="ELEVENLABS_API_KEY").first()
            if api_key:
                elevenlabs_api_key = api_key.value
                logging.info("Found ElevenLabs API key in database")
            else:
                logging.error("No ELEVENLABS_API_KEY record found in database")
        
    if not elevenlabs_api_key:
        logging.error("ElevenLabs API key not found in environment variables or database")
        return None
    
    # Log key length for debugging (don't log the actual key)
    original_length = len(elevenlabs_api_key)
    logging.info(f"Original ElevenLabs API key length: {original_length}")
    
    # Ensure API key doesn't have extra whitespace or unexpected text
    elevenlabs_api_key = elevenlabs_api_key.strip()
    
    # If key has quotes, remove them
    if elevenlabs_api_key.startswith('"') and elevenlabs_api_key.endswith('"'):
        elevenlabs_api_key = elevenlabs_api_key[1:-1]
        logging.warning("Removed double quotes from ElevenLabs API key")
    
    if elevenlabs_api_key.startswith("'") and elevenlabs_api_key.endswith("'"):
        elevenlabs_api_key = elevenlabs_api_key[1:-1]
        logging.warning("Removed single quotes from ElevenLabs API key")
    
    # If key has spaces, take only the first part (the actual API key)
    if ' ' in elevenlabs_api_key:
        logging.warning("ElevenLabs API key contains spaces. Using only the first part.")
        elevenlabs_api_key = elevenlabs_api_key.split()[0]
    
    # Remove any remaining quotes
    original_key = elevenlabs_api_key
    elevenlabs_api_key = elevenlabs_api_key.replace("'", "").replace('"', "")
    if elevenlabs_api_key != original_key:
        logging.warning("Removed embedded quotes from ElevenLabs API key")
    
    # Check final key length
    final_length = len(elevenlabs_api_key)
    logging.info(f"Final ElevenLabs API key length: {final_length}")
    if original_length != final_length:
        logging.warning(f"API key length changed from {original_length} to {final_length}")
    
    # Mask the key for logging (show first 4 and last 4 characters)
    if len(elevenlabs_api_key) > 8:
        masked_key = elevenlabs_api_key[:4] + "..." + elevenlabs_api_key[-4:]
    else:
        masked_key = "***"
    logging.info(f"Using ElevenLabs API key: {masked_key}")
    
    # Ensure the key has the expected format
    if not elevenlabs_api_key.startswith("sk_"):
        logging.warning(f"ElevenLabs API key has unexpected format (should start with 'sk_')")
        
    return elevenlabs_api_key

def check_elevenlabs_api_key(api_key):
    """
    Check if the ElevenLabs API key is valid by making a test request
    
    Args:
        api_key (str): ElevenLabs API key to check
        
    Returns:
        tuple: (bool, str) - Success status and error message if failed
    """
    if not api_key:
        logging.error("API key is missing")
        return False, "API key is missing"
    
    # Clean up the key just to be safe
    api_key = api_key.strip().replace('"', '').replace("'", "")
    
    try:
        # Make a simple request to the ElevenLabs API to check the key
        url = "https://api.elevenlabs.io/v1/voices"
        headers = {"xi-api-key": api_key}
        
        logging.info("Making test request to ElevenLabs API to validate key")
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            # Get available voices for logging
            voices_data = response.json()
            voices = voices_data.get("voices", [])
            
            # Create lists of voice names and IDs for logging
            voice_names = []
            voice_ids = []
            
            # Check for Archie/Jeremy's voice specifically
            archie_voice_id = "8Rym4ZbhAhRTh2D03UoX"
            archie_found = False
            
            for voice in voices:
                if "name" in voice and "voice_id" in voice:
                    voice_names.append(voice.get("name"))
                    voice_ids.append(voice.get("voice_id"))
                    
                    # Check if this is the Archie/Jeremy voice
                    if voice.get("voice_id") == archie_voice_id:
                        logging.info(f"Found voice with ID {archie_voice_id}: {voice.get('name')}")
                        archie_found = True
            
            logging.info(f"ElevenLabs API key is valid. Found {len(voices)} voices.")
            logging.info(f"Available voices: {', '.join(voice_names)}")
            
            # Check if Archie/Jeremy's voice is available
            if not archie_found:
                logging.warning(f"Voice with ID {archie_voice_id} (Archie/Jeremy) not found in available voices")
            
            return True, ""
        else:
            error_msg = f"ElevenLabs API key validation failed with status code {response.status_code}: {response.text}"
            logging.error(error_msg)
            return False, error_msg
    
    except requests.exceptions.RequestException as req_error:
        error_msg = f"Network error when connecting to ElevenLabs API: {str(req_error)}"
        logging.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Error checking ElevenLabs API key: {str(e)}"
        logging.error(error_msg)
        return False, error_msg

def chunk_text(text, max_chars=9000):
    """
    Split text into chunks of a maximum size while trying to respect sentence boundaries.
    
    Args:
        text (str): The text to split
        max_chars (int): Maximum characters per chunk
        
    Returns:
        list: List of text chunks
    """
    # If text is already small enough, return it as is
    if len(text) <= max_chars:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    # Split text into sentences (try to break at periods, question marks, exclamation points)
    sentences = []
    current_sentence = ""
    
    for char in text:
        current_sentence += char
        if char in ['.', '!', '?', '\n'] and current_sentence.strip():
            sentences.append(current_sentence)
            current_sentence = ""
    
    # Add any remaining text as a sentence
    if current_sentence.strip():
        sentences.append(current_sentence)
    
    # Group sentences into chunks
    for sentence in sentences:
        # If adding this sentence would exceed the limit, save the current chunk and start a new one
        if len(current_chunk) + len(sentence) > max_chars:
            chunks.append(current_chunk)
            current_chunk = sentence
        else:
            current_chunk += sentence
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk)
    
    logging.info(f"Split text into {len(chunks)} chunks for TTS processing")
    return chunks

def convert_to_speech(text, voice_settings, output_path, task_id=None):
    """
    Convert text to speech using ElevenLabs API
    
    Args:
        text (str): Text to convert to speech
        voice_settings (ElevenLabsVoice): Voice settings
        output_path (str): Path to save the audio file
        
    Returns:
        str: Path to the generated audio file
    """
    
    # Import task progress tracking if task_id was provided
    update_progress = None
    if task_id:
        try:
            from background_task import set_task_progress
            
            def update_progress(progress, message=None):
                set_task_progress(task_id, progress, message)
                logging.info(f"Updated task {task_id} progress to {progress}% - {message}")
        except ImportError:
            logging.warning("Could not import background_task module for progress updates")
    
    # Update progress to show we've started
    if update_progress:
        update_progress(5, "Initializing audio generation...")
        
    api_key = get_elevenlabs_api_key()
    if not api_key:
        error_msg = "ElevenLabs API key not found. Please configure it in the API Keys settings."
        logging.error(error_msg)
        if update_progress:
            update_progress(10, f"Error: {error_msg}")
        raise Exception(error_msg)
    
    # Verify the API key and get available voices
    if update_progress:
        update_progress(10, "Verifying API key and checking available voices...")
        
    valid_key, error_message = check_elevenlabs_api_key(api_key)
    if not valid_key:
        if update_progress:
            update_progress(15, f"Error: Invalid API key - {error_message}")
        raise Exception(f"Invalid ElevenLabs API key: {error_message}")
    
    try:
        # Ensure the directory exists
        if update_progress:
            update_progress(15, "Creating output directories...")
            
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Split text into smaller chunks to avoid ElevenLabs character limit and reduce memory usage
        if update_progress:
            update_progress(20, "Splitting text into manageable chunks...")
            
        text_chunks = chunk_text(text, max_chars=4000)  # Reduced chunk size for better reliability
        logging.info(f"Processing {len(text_chunks)} chunks for text-to-speech conversion")
        
        if update_progress:
            update_progress(25, f"Ready to process {len(text_chunks)} chunks of text...")
        
        # Process each chunk and combine the audio
        combined_audio = None
        
        # Get voice ID from settings
        voice_id = voice_settings.voice_id
        
        # Log voice ID for debugging
        logging.info(f"Using voice ID: {voice_id}")
        
        # Map voice names to their IDs based on the ElevenLabs API
        voice_name_mapping = {
            "archie": "8Rym4ZbhAhRTh2D03UoX",  # Actual ID for "Jermey's Voice" (also called Archie)
            "archie-english": "kmSVBPu7loj4ayNinwWM",  # "Archie - English teen youth"
            "jeremy": "8Rym4ZbhAhRTh2D03UoX",  # Same as Archie
            "jermey": "8Rym4ZbhAhRTh2D03UoX",  # Same as Archie
            "jeremy's voice": "8Rym4ZbhAhRTh2D03UoX"  # Same as Archie
        }
        
        # Check if voice_id is a name that needs to be mapped to an ID
        voice_id_lower = voice_id.lower()
        if voice_id_lower in voice_name_mapping:
            original_voice_id = voice_id
            voice_id = voice_name_mapping[voice_id_lower]
            logging.info(f"Mapped voice name '{original_voice_id}' to ID: {voice_id}")
        
        # Double check if we have a valid voice ID
        if not voice_id or len(voice_id) < 10:
            logging.warning(f"Voice ID '{voice_id}' appears invalid, will try to use anyway")
        
        # Set up API request parameters
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }
        
        voice_settings_dict = {
            "stability": voice_settings.stability,
            "similarity_boost": voice_settings.similarity_boost
        }
        
        for i, chunk in enumerate(text_chunks):
            logging.info(f"Processing chunk {i+1}/{len(text_chunks)} with {len(chunk)} characters")
            
            # Calculate current progress: 25% start + 60% progress spread across chunks
            if update_progress:
                chunk_progress = 25 + int((i / len(text_chunks)) * 60)
                update_progress(chunk_progress, f"Processing chunk {i+1} of {len(text_chunks)}...")
            
            # Skip empty chunks
            if not chunk.strip():
                logging.warning(f"Skipping empty chunk {i+1}")
                continue
                
            data = {
                "text": chunk,
                "model_id": "eleven_multilingual_v2",  # Updated to newer model
                "voice_settings": voice_settings_dict
            }
            
            # Number of retries
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    # Make API request for this chunk with increased timeout
                    if update_progress:
                        update_progress(
                            chunk_progress, 
                            f"Sending chunk {i+1}/{len(text_chunks)} to API (attempt {retry_count+1})..."
                        )
                        
                    logging.info(f"Making API request for chunk {i+1} (attempt {retry_count+1})")
                    # Use a longer timeout for ElevenLabs API which can sometimes take longer
                    response = requests.post(
                        url, 
                        json=data, 
                        headers=headers,
                        timeout=60  # Increased to 60 seconds timeout
                    )
                    
                    if response.status_code != 200:
                        error_msg = f"ElevenLabs API request failed with status code {response.status_code}: {response.text}"
                        logging.error(error_msg)
                        
                        # Specifically check for credit-related errors
                        response_text = response.text.lower()
                        if 'insufficient credit' in response_text or 'character quota' in response_text or 'credits depleted' in response_text or 'reached maximum quota' in response_text:
                            credit_error = "Your ElevenLabs account has insufficient credits. Please add more credits to your ElevenLabs account to continue generating podcast audio."
                            logging.error(credit_error)
                            if update_progress:
                                update_progress(chunk_progress, f"Error: {credit_error}")
                            raise Exception(credit_error)
                        
                        # For some status codes, we should retry
                        if response.status_code in [429, 500, 502, 503, 504]:
                            retry_count += 1
                            if retry_count < max_retries:
                                logging.info(f"Retrying after error (attempt {retry_count+1})")
                                time.sleep(2)  # Wait 2 seconds before retry
                                continue
                            else:
                                raise Exception(error_msg)
                        else:
                            # For other status codes, don't retry
                            raise Exception(error_msg)
                    
                    # Verify that we got actual audio data
                    if len(response.content) < 100:  # An MP3 should be larger than this
                        logging.error(f"Received suspiciously small response: {len(response.content)} bytes")
                        logging.error(f"Response content: {response.content}")
                        retry_count += 1
                        if retry_count < max_retries:
                            logging.info(f"Retrying after small response error (attempt {retry_count+1})")
                            time.sleep(2)
                            continue
                        else:
                            raise Exception("Received invalid audio data from API")
                    
                    # Successful response, process it
                    logging.info(f"Successfully received audio for chunk {i+1} ({len(response.content)} bytes)")
                    
                    # Load audio chunk
                    try:
                        chunk_audio = AudioSegment.from_mp3(io.BytesIO(response.content))
                        
                        # Add to combined audio
                        if combined_audio is None:
                            combined_audio = chunk_audio
                        else:
                            combined_audio += chunk_audio
                        
                        # Break out of retry loop
                        break
                        
                    except Exception as audio_error:
                        error_msg = f"Error processing audio data for chunk {i+1}: {str(audio_error)}"
                        logging.error(error_msg)
                        retry_count += 1
                        if retry_count < max_retries:
                            logging.info(f"Retrying after audio processing error (attempt {retry_count+1})")
                            time.sleep(2)
                            continue
                        else:
                            raise Exception(error_msg)
                        
                except requests.exceptions.Timeout:
                    logging.error(f"Request timeout for chunk {i+1}")
                    retry_count += 1
                    if retry_count < max_retries:
                        logging.info(f"Retrying after timeout (attempt {retry_count+1})")
                        time.sleep(2)
                        continue
                    else:
                        raise Exception(f"Request timeout for chunk {i+1} after {max_retries} attempts")
                        
                except requests.exceptions.RequestException as req_error:
                    error_msg = f"Network error when connecting to ElevenLabs API: {str(req_error)}"
                    logging.error(error_msg)
                    retry_count += 1
                    if retry_count < max_retries:
                        logging.info(f"Retrying after network error (attempt {retry_count+1})")
                        time.sleep(2)
                        continue
                    else:
                        raise Exception(error_msg)
                        
                except Exception as chunk_error:
                    error_msg = f"Error processing chunk {i+1}: {str(chunk_error)}"
                    logging.error(error_msg)
                    retry_count += 1
                    if retry_count < max_retries:
                        logging.info(f"Retrying after general error (attempt {retry_count+1})")
                        time.sleep(2)
                        continue
                    else:
                        raise Exception(error_msg)
            
            # If we get here and retry_count is still max_retries, it means all retries failed
            if retry_count >= max_retries:
                raise Exception(f"Failed to process chunk {i+1} after {max_retries} attempts")
        
        # Save the final combined audio
        if combined_audio:
            try:
                if update_progress:
                    update_progress(85, "Finalizing audio file...")
                
                # Make sure the directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # Save audio to a temporary file first
                temp_path = f"{output_path}.temp"
                logging.info(f"Saving audio to temporary file: {temp_path}")
                combined_audio.export(temp_path, format="mp3")
                
                # Then move to the final path
                if os.path.exists(temp_path):
                    if os.path.exists(output_path):
                        os.remove(output_path)  # Remove existing file if present
                    os.rename(temp_path, output_path)
                    logging.info(f"Successfully generated combined audio file at {output_path}")
                    
                    if update_progress:
                        update_progress(100, "Audio generation completed successfully!")
                        
                    return output_path
                else:
                    if update_progress:
                        update_progress(85, "Error: Failed to save audio file")
                    raise Exception(f"Failed to save temporary audio file at {temp_path}")
            except Exception as save_error:
                logging.error(f"Error saving audio file: {str(save_error)}")
                if update_progress:
                    update_progress(85, f"Error: {str(save_error)}")
                raise Exception(f"Error saving audio file: {str(save_error)}")
        else:
            if update_progress:
                update_progress(85, "Error: No audio content was generated")
            raise Exception("Failed to generate any audio content")
    
    except Exception as e:
        logging.error(f"Error converting text to speech: {str(e)}")
        raise Exception(f"Error converting text to speech: {str(e)}")
