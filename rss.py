import os
import json
import feedparser
import logging
from datetime import datetime, timedelta
from time import mktime
from urllib.parse import urlparse

def fetch_rss_feeds(feed_urls, max_articles_per_feed=15, time_frame='today'):
    """
    Fetch articles from multiple RSS feed URLs with time frame filtering
    
    Args:
        feed_urls (list): List of RSS feed URLs
        max_articles_per_feed (int): Maximum number of articles to fetch per feed
        time_frame (str): Time frame for filtering articles ('today', 'week', 'month')
        
    Returns:
        list: List of article dictionaries
    """
    logging.info(f"Fetching RSS feeds: {feed_urls} with time frame: {time_frame} and max_articles_per_feed: {max_articles_per_feed}")
    all_articles = []
    
    # Calculate the cutoff date based on time_frame
    now = datetime.now()
    if time_frame == 'today':
        cutoff_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif time_frame == 'week':
        cutoff_date = now - timedelta(days=7)
    elif time_frame == 'month':
        cutoff_date = now - timedelta(days=30)
    else:
        cutoff_date = now.replace(hour=0, minute=0, second=0, microsecond=0)  # Default to today
    
    logging.info(f"Using cutoff date: {cutoff_date.isoformat()} for time frame: {time_frame}")
    
    for feed_url in feed_urls:
        try:
            feed = feedparser.parse(feed_url)
            
            if feed.bozo:
                logging.warning(f"Error parsing feed {feed_url}: {feed.bozo_exception}")
                continue
                
            domain = urlparse(feed_url).netloc
            feed_title = feed.feed.title if hasattr(feed, 'feed') and hasattr(feed.feed, 'title') else domain
            
            # Get articles from feed
            articles = []
            for entry in feed.entries:
                published_time = None
                
                # Try to get published time in different formats
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published_time = datetime.fromtimestamp(mktime(entry.published_parsed))
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    published_time = datetime.fromtimestamp(mktime(entry.updated_parsed))
                else:
                    # If no date available, use current time but mark it
                    published_time = datetime.now()
                    logging.warning(f"No date found for article: {entry.title if hasattr(entry, 'title') else 'Unknown'}, using current time")
                
                # Apply time frame filter
                if published_time and published_time >= cutoff_date:
                    # Get article content with improved handling
                    content = ''
                    
                    # Try multiple content sources in order of preference
                    if hasattr(entry, 'content') and entry.content:
                        content = entry.content[0].value
                    elif hasattr(entry, 'summary_detail') and entry.summary_detail:
                        content = entry.summary_detail.value
                    elif hasattr(entry, 'summary'):
                        content = entry.summary
                    elif hasattr(entry, 'description'):
                        content = entry.description
                    
                    # If we still have no content, create a minimal entry
                    if not content.strip():
                        content = f"Article titled '{entry.title}' from {feed_title}. Visit {entry.link} for more information."
                    
                    article = {
                        'title': entry.title,
                        'link': entry.link,
                        'published': published_time.isoformat(),
                        'source': feed_title,
                        'summary': content
                    }
                    articles.append(article)
                    
                    # Break if we've reached the maximum articles per feed
                    if len(articles) >= max_articles_per_feed:
                        break
            
            all_articles.extend(articles)
            logging.info(f"Successfully fetched {len(articles)} articles from {feed_url} after time frame filtering")
            
        except Exception as e:
            logging.error(f"Error fetching feed {feed_url}: {str(e)}")
    
    # Only sort if we have articles
    if all_articles:
        # Sort articles by published date (newest first)
        all_articles.sort(
            key=lambda x: datetime.fromisoformat(x['published']) if x['published'] else datetime.min,
            reverse=True
        )
    
    logging.info(f"Total articles fetched from all feeds: {len(all_articles)}")
    return all_articles

def get_feed_data(date_str=None):
    """
    Get saved feed data for a specific date
    
    Args:
        date_str (str): Date string in YYYYMMDD format. If None, use today's date.
        
    Returns:
        list: List of article dictionaries
    """
    if not date_str:
        date_str = datetime.now().strftime('%Y%m%d')
        
    storage_dir = f'storage/{date_str}'
    data_file = f'{storage_dir}/data.json'
    
    if not os.path.exists(data_file):
        logging.warning(f"No feed data found for {date_str}")
        return []
        
    try:
        with open(data_file, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        logging.error(f"Error loading feed data for {date_str}: {str(e)}")
        return []
