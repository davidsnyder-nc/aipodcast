import os
import shutil
import logging
import tempfile
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urljoin

def publish_to_github(episode, github_token, github_username, github_repo, branch="main"):
    """
    Publish podcast to GitHub Pages
    
    Args:
        episode (Episode): Episode to publish
        github_token (str): GitHub access token
        github_username (str): GitHub username
        github_repo (str): GitHub repository name
        branch (str): GitHub branch name
        
    Returns:
        tuple: (success, url_or_error)
    """
    logging.info(f"Publishing episode {episode.id} to GitHub")
    
    # Check if audio file exists
    if not os.path.exists(episode.audio_path):
        error_msg = f"Audio file not found at {episode.audio_path}"
        logging.error(error_msg)
        return False, error_msg
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Clone repository
            repo_url = f"https://{github_token}@github.com/{github_username}/{github_repo}.git"
            clone_cmd = ["git", "clone", repo_url, "--depth", "1", "--branch", branch, temp_dir]
            
            logging.debug(f"Cloning repository: {github_username}/{github_repo}")
            process = subprocess.run(clone_cmd, capture_output=True, text=True)
            
            if process.returncode != 0:
                error_msg = f"Failed to clone repository: {process.stderr}"
                logging.error(error_msg)
                return False, error_msg
            
            # Create podcast directory if it doesn't exist
            podcast_dir = os.path.join(temp_dir, "podcasts")
            os.makedirs(podcast_dir, exist_ok=True)
            
            # Generate clean filename from title
            date_str = episode.date.strftime('%Y%m%d')
            file_base = f"{date_str}_{episode.title.lower().replace(' ', '_')}"
            
            # Copy audio file
            audio_filename = f"{file_base}.mp3"
            audio_dest = os.path.join(podcast_dir, audio_filename)
            shutil.copy2(episode.audio_path, audio_dest)
            
            # Copy script file
            script_filename = f"{file_base}.txt"
            script_dest = os.path.join(podcast_dir, script_filename)
            shutil.copy2(episode.script_path, script_dest)
            
            # Update podcast RSS feed XML
            rss_path = os.path.join(temp_dir, "podcast.xml")
            
            # Create RSS file if it doesn't exist
            if not os.path.exists(rss_path):
                create_initial_rss_file(rss_path)
            
            # Update RSS file with new episode
            update_rss_file(
                rss_path, 
                episode, 
                audio_filename, 
                f"https://{github_username}.github.io/{github_repo}/podcasts/{audio_filename}"
            )
            
            # Commit and push changes
            git_commands = [
                ["git", "config", "user.name", "AI Podcast Generator"],
                ["git", "config", "user.email", "noreply@example.com"],
                ["git", "add", "."],
                ["git", "commit", "-m", f"Add podcast episode: {episode.title}"],
                ["git", "push", "origin", branch]
            ]
            
            for cmd in git_commands:
                logging.debug(f"Running git command: {cmd}")
                process = subprocess.run(cmd, cwd=temp_dir, capture_output=True, text=True)
                
                if process.returncode != 0:
                    error_msg = f"Git command failed: {process.stderr}"
                    logging.error(error_msg)
                    return False, error_msg
            
            # Return published URL
            published_url = f"https://{github_username}.github.io/{github_repo}/podcasts/{audio_filename}"
            logging.info(f"Successfully published episode to {published_url}")
            return True, published_url
    
    except Exception as e:
        error_msg = f"Error publishing to GitHub: {str(e)}"
        logging.error(error_msg)
        return False, error_msg

def create_initial_rss_file(rss_path):
    """
    Create initial podcast RSS feed file
    
    Args:
        rss_path (str): Path to RSS file
    """
    root = ET.Element("rss", version="2.0")
    root.set("xmlns:itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
    root.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
    
    channel = ET.SubElement(root, "channel")
    
    # Required RSS elements
    ET.SubElement(channel, "title").text = "Daily Tech Insights"
    ET.SubElement(channel, "description").text = "An AI-generated daily tech news podcast covering the latest in technology and startups."
    ET.SubElement(channel, "link").text = "https://example.com"
    ET.SubElement(channel, "language").text = "en-us"
    ET.SubElement(channel, "lastBuildDate").text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
    
    # iTunes specific elements
    ET.SubElement(channel, "itunes:author").text = "AI Podcast Generator"
    ET.SubElement(channel, "itunes:summary").text = "An AI-generated daily tech news podcast covering the latest in technology and startups."
    
    # Write to file
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0)
    tree.write(rss_path, encoding="utf-8", xml_declaration=True)
    
    logging.info(f"Created initial RSS file at {rss_path}")

def update_rss_file(rss_path, episode, audio_filename, audio_url):
    """
    Update podcast RSS feed file with new episode
    
    Args:
        rss_path (str): Path to RSS file
        episode (Episode): Episode to add
        audio_filename (str): Audio filename
        audio_url (str): Audio URL
    """
    try:
        # Parse existing RSS file
        tree = ET.parse(rss_path)
        root = tree.getroot()
        channel = root.find("channel")
        
        # Update lastBuildDate
        lastBuildDate = channel.find("lastBuildDate")
        if lastBuildDate is not None:
            lastBuildDate.text = datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
        
        # Create new item element
        item = ET.SubElement(channel, "item")
        
        # Add item elements
        ET.SubElement(item, "title").text = episode.title
        ET.SubElement(item, "description").text = episode.script[:200] + "..." if len(episode.script) > 200 else episode.script
        ET.SubElement(item, "pubDate").text = episode.date.strftime("%a, %d %b %Y %H:%M:%S GMT")
        ET.SubElement(item, "guid", isPermaLink="false").text = audio_url
        
        # Add enclosure (audio file)
        audio_size = os.path.getsize(episode.audio_path)
        ET.SubElement(item, "enclosure", url=audio_url, length=str(audio_size), type="audio/mpeg")
        
        # Add iTunes specific elements
        ET.SubElement(item, "itunes:duration").text = "00:10:00"  # Placeholder duration
        ET.SubElement(item, "itunes:summary").text = episode.script[:200] + "..." if len(episode.script) > 200 else episode.script
        
        # Write updated RSS to file
        ET.indent(tree, space="  ", level=0)
        tree.write(rss_path, encoding="utf-8", xml_declaration=True)
        
        logging.info(f"Updated RSS file with episode {episode.id}")
    
    except Exception as e:
        logging.error(f"Error updating RSS file: {str(e)}")
        raise
