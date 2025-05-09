import os
import logging
import base64
import requests
from io import BytesIO
from openai import OpenAI
from datetime import datetime

def get_openai_client():
    """
    Get OpenAI client with API key from environment variables or database
    
    Returns:
        OpenAI: OpenAI client
    """
    # First try environment variable
    openai_api_key = os.environ.get("OPENAI_API_KEY" # Add your key here)
    
    # If not found in environment, check database
    if not openai_api_key:
        from app import app, db
        import models
        with app.app_context():
            api_key = models.ApiKey.query.filter_by(name="OPENAI_API_KEY").first()
            if api_key:
                openai_api_key = api_key.value
        
    if not openai_api_key:
        logging.error("OpenAI API key not found in environment variables or database")
        return None
        
    return OpenAI(api_key=openai_api_key)

def generate_podcast_introduction(podcast_title, style_guidance="", host_info="", custom_instructions=None, model="gpt-3.5-turbo"):
    """
    Generate podcast introduction
    
    Args:
        podcast_title (str): Podcast title
        style_guidance (str): Optional style guidance based on podcast description
        host_info (str): Optional host information
        custom_instructions (str): Optional custom AI instructions
        model (str): OpenAI model to use
        
    Returns:
        str: Generated introduction
    """
    client = get_openai_client()
    if not client:
        return "Welcome to today's podcast. Let's dive into the latest tech news."
    
    today = datetime.now().strftime("%B %d, %Y")
    
    # Default prompt
    prompt = (
        f"Write a brief but engaging introduction for a podcast episode titled '{podcast_title}' "
        f"for today, {today}. The podcast covers the latest technology news and trends. "
        f"Keep it under 100 words, conversational, and welcoming."
    )
    
    # Add style guidance if provided
    if style_guidance:
        prompt += style_guidance
    
    # Add host info if provided
    if host_info:
        prompt += host_info
    
    # System message
    system_message = "You are a professional podcast host specializing in technology news."
    
    # Override with custom instructions if provided
    if custom_instructions:
        system_message = custom_instructions
    
    try:
        # Use the specified model or fall back to gpt-3.5-turbo if invalid
        ai_model = model if model else "gpt-3.5-turbo"
        logging.info(f"Using OpenAI model: {ai_model} for introduction generation")
        
        response = client.chat.completions.create(
            model=ai_model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            max_tokens=250,
            temperature=0.7
        )
        
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Error generating podcast introduction: {str(e)}")
        return f"Welcome to {podcast_title} for {today}. Let's dive into the latest tech news."

def summarize_article(article, podcast_duration=10, model="gpt-3.5-turbo"):
    """
    Summarize article using OpenAI
    
    Args:
        article (dict): Article dictionary
        podcast_duration (int): Target podcast duration in minutes
        model (str): OpenAI model to use
        
    Returns:
        str: Summarized article
    """
    client = get_openai_client()
    if not client:
        return f"An article titled '{article['title']}' was published by {article['source']}."
    
    title = article.get('title', 'Untitled article')
    source = article.get('source', 'Unknown source')
    content = article.get('summary', '')
    
    # Adjust summary length based on podcast duration
    # Increase word count to create more detailed summaries
    if podcast_duration < 5:
        word_count = "80-120"  # More detailed for short podcasts
    elif podcast_duration <= 15:
        word_count = "150-200"  # Significantly more detailed for medium podcasts
    else:
        word_count = "250-350"  # Very detailed for longer podcasts
    
    # Calculate max_tokens based on word count to ensure we get full summaries
    max_tokens = int(word_count.split('-')[1]) * 2  # Rough estimate: 1 word ≈ 1.5-2 tokens
    
    prompt = (
        f"Summarize the following article for a tech podcast, highlighting key points, insights, and implications:\n\n"
        f"Title: {title}\n"
        f"Source: {source}\n\n"
        f"{content}\n\n"
        f"Provide a comprehensive yet engaging summary ({word_count} words) that would sound natural when read aloud in a podcast. "
        f"Start with 'From {source}' and then dive into the content. Include specific details, quotes if relevant, and explain "
        f"why this news matters to listeners. Make it informative and conversational."
    )
    
    try:
        # Use the specified model or fall back to gpt-3.5-turbo if invalid
        ai_model = model if model else "gpt-3.5-turbo"
        logging.info(f"Using OpenAI model: {ai_model} for article summarization")
        
        response = client.chat.completions.create(
            model=ai_model,
            messages=[
                {"role": "system", "content": "You are a technology podcast host summarizing news articles. Your audience values detailed analysis and comprehensive coverage."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,  # Increased token limit for longer summaries
            temperature=0.7
        )
        
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Error summarizing article: {str(e)}")
        return f"From {source}: An article titled '{title}' was published recently."

def generate_transition():
    """
    Generate transition between articles
    
    Returns:
        str: Generated transition
    """
    transitions = [
        "Moving on to our next story...",
        "In other tech news...",
        "Shifting gears to another interesting development...",
        "Next up in today's tech headlines...",
        "Another noteworthy story today...",
        "Let's turn our attention to another tech update...",
        "On a different note...",
        "Here's another story that caught our attention...",
        "Switching topics...",
        "And now for something different..."
    ]
    
    import random
    return random.choice(transitions)

def generate_conclusion(model="gpt-3.5-turbo"):
    """
    Generate podcast conclusion
    
    Args:
        model (str): OpenAI model to use
        
    Returns:
        str: Generated conclusion
    """
    client = get_openai_client()
    if not client:
        return "That's all for today's episode. Thanks for listening, and we'll be back tomorrow with more tech news!"
    
    prompt = (
        "Write a brief, friendly conclusion for a daily tech news podcast episode. "
        "Thank the listeners and mention that we'll be back tomorrow with more news. "
        "Keep it under 70 words and conversational."
    )
    
    try:
        # Use the specified model or fall back to gpt-3.5-turbo if invalid
        ai_model = model if model else "gpt-3.5-turbo"
        logging.info(f"Using OpenAI model: {ai_model} for conclusion generation")
        
        response = client.chat.completions.create(
            model=ai_model,
            messages=[
                {"role": "system", "content": "You are a professional podcast host concluding a technology news episode."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7
        )
        
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Error generating podcast conclusion: {str(e)}")
        return "That's all for today's episode. Thanks for listening, and we'll be back tomorrow with more tech news!"

def generate_podcast_artwork(podcast_title, podcast_description=None, podcast_category="Technology", size="1024x1024"):
    """
    Generate podcast cover art using DALL-E
    
    Args:
        podcast_title (str): Podcast title
        podcast_description (str): Podcast description for context
        podcast_category (str): Category for styling the image
        size (str): Size of the generated image (1024x1024, 1792x1024, or 1024x1792)
        
    Returns:
        tuple: (success, filepath_or_error_message)
    """
    client = get_openai_client()
    if not client:
        return False, "OpenAI API key not configured"
    
    # Create prompt based on podcast information
    base_prompt = f"Create a professional podcast cover art for '{podcast_title}'"
    
    # Add category context
    category_context = {
        "Technology": "with modern tech elements, circuit patterns, and a clean digital aesthetic",
        "Business": "with professional business imagery, charts, or sleek office elements",
        "News": "with journalism themes, newspaper elements, and information graphics",
        "Science": "with scientific imagery, atoms, lab equipment, or space elements",
        "Education": "with academic imagery, books, graduation caps, or learning elements",
        "Arts": "with artistic elements, paint splashes, or creative visual metaphors",
        "Comedy": "with fun, vibrant colors and playful visual elements",
        "Health": "with wellness imagery, medical symbols, or healthy lifestyle elements",
        "Entertainment": "with media elements, spotlights, or entertainment industry symbols"
    }
    
    # Build the complete prompt
    style_instructions = category_context.get(podcast_category, "with a professional, clean design")
    prompt = f"{base_prompt} {style_instructions}. "
    
    # Add description context if available
    if podcast_description and len(podcast_description) > 5:
        # Extract key themes from description to inform the artwork
        prompt += f"The podcast is about: {podcast_description[:100]}. "
    
    # Add design requirements
    prompt += "Include the title prominently. Use a modern color palette. Make it visually appealing and professional. No text other than the title."
    
    try:
        logging.info(f"Generating podcast artwork for '{podcast_title}'")
        
        # Generate image with DALL-E
        # Handle size parameter to make it compatible with DALL-E requirements
        valid_sizes = ["1024x1024", "1792x1024", "1024x1792"]
        if size not in valid_sizes:
            size = "1024x1024"  # Default to square format if invalid
            
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=size,
            quality="standard",
            n=1,
        )
        
        # Get the image URL
        if response and hasattr(response, 'data') and response.data and len(response.data) > 0:
            image_url = response.data[0].url
        else:
            return False, "Failed to generate image: No image data in response"
        
        # Download the image
        if not image_url:
            return False, "No image URL was generated"
            
        try:
            image_response = requests.get(image_url)
            if image_response.status_code != 200:
                return False, f"Failed to download generated image: HTTP {image_response.status_code}"
        except Exception as e:
            return False, f"Error downloading image: {str(e)}"
        
        # Create storage directory if it doesn't exist
        os.makedirs('static/podcast_covers', exist_ok=True)
        
        # Save the image
        # Create a filename based on the podcast title
        filename = f"cover_{podcast_title.lower().replace(' ', '_')[:30]}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        
        # Create a consistent path format - just the relative path inside static
        relative_path = os.path.join('podcast_covers', filename)
        
        # Full filepath for saving the file
        filepath = os.path.join('static', relative_path)
        
        # Log what we're doing
        logging.warning(f"COVER ART DEBUG - Saving podcast cover to: {filepath}")
        
        try:
            with open(filepath, 'wb') as f:
                f.write(image_response.content)
                
            # Verify the file was created
            if os.path.exists(filepath):
                file_size = os.path.getsize(filepath)
                logging.warning(f"COVER ART DEBUG - Cover art file created successfully at: {filepath} (size: {file_size} bytes)")
            else:
                logging.warning(f"COVER ART DEBUG - ERROR: File not created at {filepath} despite no exceptions")
                
            # Return the path that should be saved in the database (relative to static/)
            db_path = relative_path
            logging.warning(f"COVER ART DEBUG - Path to save in DB: {db_path}")
        except Exception as inner_e:
            logging.error(f"COVER ART DEBUG - ERROR writing cover art file: {str(inner_e)}")
            raise inner_e  # Re-raise to be caught by outer exception handler
        
        return True, db_path
        
    except Exception as e:
        logging.error(f"Error generating podcast artwork: {str(e)}")
        return False, f"Error generating podcast artwork: {str(e)}"

def generate_podcast_script(articles, podcast_title="Daily Tech Insights", podcast_description=None, podcast_author=None, host_name=None, ai_instructions=None, podcast_duration=10, openai_model="gpt-3.5-turbo"):
    """
    Generate full podcast script
    
    Args:
        articles (list): List of article dictionaries
        podcast_title (str): Podcast title
        podcast_description (str): Podcast description to use as style guidance
        podcast_author (str): Podcast author for metadata
        host_name (str): Name of the podcast host to mention in the script
        ai_instructions (str): Custom AI instructions
        podcast_duration (int): Target podcast duration in minutes
        openai_model (str): OpenAI model to use for generation
        
    Returns:
        str: Generated podcast script
    """
    logging.info(f"Generating podcast script for {podcast_title} with {len(articles)} articles using model {openai_model}")
    
    script_parts = []
    
    # Introduction with custom guidance if available
    style_guidance = ""
    if podcast_description:
        style_guidance = f"\nPodcast description: {podcast_description}"
    
    host_info = ""
    if host_name:
        host_info = f"\nHost: {host_name}"
    elif podcast_author:
        host_info = f"\nHost: {podcast_author}"
        
    intro = generate_podcast_introduction(podcast_title, style_guidance, host_info, ai_instructions, openai_model)
    script_parts.append(intro)
    script_parts.append("\n\n")
    
    # Calculate appropriate number of articles based on podcast duration
    # Use more articles for longer podcasts while ensuring each gets sufficient coverage
    if podcast_duration < 5:
        max_articles = min(5, len(articles))  # 5 articles for short podcasts
    elif podcast_duration <= 15:
        max_articles = min(10, len(articles))  # 10 articles for medium podcasts
    else:
        max_articles = min(15, len(articles))  # 15 articles for longer podcasts
        
    # Always include at least 5 articles if available, regardless of duration
    max_articles = max(min(5, len(articles)), max_articles)
    
    logging.info(f"Using {max_articles} articles for a {podcast_duration} minute podcast")
    
    # Process all available articles up to max_articles
    for i, article in enumerate(articles[:max_articles]):
        article_summary = summarize_article(article, podcast_duration, openai_model)
        script_parts.append(article_summary)
        script_parts.append("\n\n")
        
        # Add transition between articles, but not after the last one
        if i < max_articles - 1:
            script_parts.append(generate_transition())
            script_parts.append("\n\n")
    
    # Conclusion
    conclusion = generate_conclusion(openai_model)
    script_parts.append(conclusion)
    
    return "".join(script_parts)
