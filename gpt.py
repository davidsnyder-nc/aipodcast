import os
import logging
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

def generate_podcast_introduction(podcast_title, style_guidance="", host_info="", custom_instructions=None):
    """
    Generate podcast introduction
    
    Args:
        podcast_title (str): Podcast title
        style_guidance (str): Optional style guidance based on podcast description
        host_info (str): Optional host information
        custom_instructions (str): Optional custom AI instructions
        
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
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # do not change this unless explicitly requested by the user
        response = client.chat.completions.create(
            model="gpt-4o",
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

def summarize_article(article, podcast_duration=10):
    """
    Summarize article using OpenAI
    
    Args:
        article (dict): Article dictionary
        podcast_duration (int): Target podcast duration in minutes
        
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
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # do not change this unless explicitly requested by the user
        response = client.chat.completions.create(
            model="gpt-4o",
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

def generate_conclusion():
    """
    Generate podcast conclusion
    
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
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # do not change this unless explicitly requested by the user
        response = client.chat.completions.create(
            model="gpt-4o",
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

def generate_podcast_script(articles, podcast_title="Daily Tech Insights", podcast_description=None, podcast_author=None, ai_instructions=None, podcast_duration=10):
    """
    Generate full podcast script
    
    Args:
        articles (list): List of article dictionaries
        podcast_title (str): Podcast title
        podcast_description (str): Podcast description to use as style guidance
        podcast_author (str): Podcast author/host name
        ai_instructions (str): Custom AI instructions
        podcast_duration (int): Target podcast duration in minutes
        
    Returns:
        str: Generated podcast script
    """
    logging.info(f"Generating podcast script for {podcast_title} with {len(articles)} articles")
    
    script_parts = []
    
    # Introduction with custom guidance if available
    style_guidance = ""
    if podcast_description:
        style_guidance = f"\nPodcast description: {podcast_description}"
    
    host_info = ""
    if podcast_author:
        host_info = f"\nHost: {podcast_author}"
        
    intro = generate_podcast_introduction(podcast_title, style_guidance, host_info, ai_instructions)
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
        article_summary = summarize_article(article, podcast_duration)
        script_parts.append(article_summary)
        script_parts.append("\n\n")
        
        # Add transition between articles, but not after the last one
        if i < max_articles - 1:
            script_parts.append(generate_transition())
            script_parts.append("\n\n")
    
    # Conclusion
    conclusion = generate_conclusion()
    script_parts.append(conclusion)
    
    return "".join(script_parts)
