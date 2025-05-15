import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import logging
import streamlit as st
import base64
from io import BytesIO
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration - API keys are fetched from environment variables
GNEWS_API_URL = "https://gnews.io/api/v4/search"
GNEWS_API_KEY = os.environ.get("GNEWS_API_KEY", "YOUR_GNEWS_API_KEY")
WORLDNEWS_API_URL = "https://api.worldnewsapi.com/search-news"
WORLDNEWS_API_KEY = os.environ.get("WORLDNEWS_API_KEY", "YOUR_WORLDNEWS_API_KEY")
AVALAI_API_URL_DEFAULT = "https://api.avalai.ir/v1"
AVALAI_API_KEY = os.environ.get("AVALAI_API_KEY", "YOUR_AVALAI_API_KEY")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Temporary file to store articles and chat IDs
TEMP_FILE = "/tmp/iran_news_articles.json"
CHAT_IDS_FILE = "/tmp/iran_news_chat_ids.json"

# Initialize Streamlit page with custom CSS
st.set_page_config(
    page_title="Iran News Aggregator",
    page_icon="📰",
    layout="wide"
)

# Add custom CSS to adjust text alignment, font, and size
st.markdown(
    """
    <style>
    .persian-text {
        direction: rtl;
        text-align: right;
        font-family: "B Nazanin", "Arial Unicode MS", "Tahoma", sans-serif;
        font-size: 16px !important;
    }
    .english-text {
        direction: ltr;
        text-align: left;
        font-size: 14px !important;
    }
    .article-section {
        margin-bottom: 20px;
        padding: 0px;
        background-color: #f9f9f9;
    }
    .neon-line-top {
        height: 4px;
        background: linear-gradient(90deg, rgba(255, 0, 0, 0.8), rgba(255, 100, 100, 0.8), rgba(255, 0, 0, 0.8));
        box-shadow: 0 0 10px rgba(255, 0, 0, 0.7), 0 0 20px rgba(255, 0, 0, 0.5), 0 0 30px rgba(255, 100, 100, 0.3);
        margin: 10px 0;
    }
    .title-link {
        font-size: 18px !important;
        font-weight: bold !important;
        color: #1a73e8 !important;
        margin-bottom: 2px !important; /* Reduced margin to bring checkbox closer */
    }
    .source-date {
        font-size: 14px !important;
        color: #555 !important;
        margin-bottom: 10px !important;
    }
    .description {
        margin-top: 10px !important;
        line-height: 1.5 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Function to send error email (disabled as per user request)
def send_error_email(error_message):
    # Email sending is disabled as per user request
    logger.info(f"Error email sending is disabled. Error message: {error_message}")

# Load articles from temp file if exists
def load_articles_from_file():
    try:
        if os.path.exists(TEMP_FILE):
            with open(TEMP_FILE, "r") as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.warning(f"Error loading articles from file: {str(e)}")
        send_error_email(f"Error loading articles from file: {str(e)}")
        return []

# Save articles to temp file
def save_articles_to_file(articles):
    try:
        with open(TEMP_FILE, "w") as f:
            json.dump(articles, f)
    except Exception as e:
        logger.warning(f"Error saving articles to file: {str(e)}")
        send_error_email(f"Error saving articles to file: {str(e)}")

# Load chat IDs from file
def load_chat_ids():
    try:
        if os.path.exists(CHAT_IDS_FILE):
            with open(CHAT_IDS_FILE, "r") as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.warning(f"Error loading chat IDs from file: {str(e)}")
        send_error_email(f"Error loading chat IDs from file: {str(e)}")
        return {}

# Save chat IDs to file
def save_chat_ids(chat_ids):
    try:
        with open(CHAT_IDS_FILE, "w") as f:
            json.dump(chat_ids, f)
    except Exception as e:
        logger.warning(f"Error saving chat IDs to file: {str(e)}")
        send_error_email(f"Error saving chat IDs to file: {str(e)}")

# Fetch news from GNews API
def fetch_gnews(query="Iran", max_records=20, from_date=None, to_date=None):
    """
    Fetch news articles from GNews API
    """
    if not GNEWS_API_KEY or GNEWS_API_KEY == "YOUR_GNEWS_API_KEY":
        error_msg = "Invalid GNews API key. Please set a valid API key in Render environment variables."
        logger.error(error_msg)
        send_error_email(error_msg)
        return [], error_msg
    
    params = {
        "q": query,
        "apikey": GNEWS_API_KEY,
        "lang": "en",
        "country": "us",
        "max": min(max_records, 100),
        "from": from_date,
        "to": to_date
    }
    headers = {
        "User-Agent": f"IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)"
    }
    logger.info(f"Sending GNews request with params: {params}")
    
    try:
        response = requests.get(GNEWS_API_URL, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        logger.info(f"GNews response: {data}")
        
        if "errors" in data:
            error_msg = f"GNews API error: {data['errors']}"
            logger.error(error_msg)
            send_error_email(error_msg)
            return [], error_msg
            
        articles = data.get("articles", [])
        if not articles:
            error_msg = f"No articles found for query '{query}' in GNews."
            logger.warning(error_msg)
            return [], error_msg
            
        return [
            {
                "title": a.get("title", "No title"),
                "url": a.get("url", ""),
                "source": a.get("source", {}).get("name", "Unknown Source"),
                "published_at": a.get("publishedAt", ""),
                "description": a.get("description", "") or "No description available",
                "image_url": a.get("image", ""),
                "translated_title": "",
                "translated_description": ""
            }
            for a in articles
        ], None
    except Exception as e:
        error_msg = f"Error fetching GNews: {str(e)}"
        logger.error(error_msg)
        send_error_email(error_msg)
        return [], error_msg

# Fetch news from World News API
def fetch_worldnews(query="Iran", max_records=20, from_date=None, to_date=None):
    """
    Fetch news articles from World News API
    """
    if not WORLDNEWS_API_KEY or WORLDNEWS_API_KEY == "YOUR_WORLDNEWS_API_KEY":
        error_msg = "Invalid World News API key. Please set a valid API key in Render environment variables."
        logger.error(error_msg)
        send_error_email(error_msg)
        return [], error_msg
    
    params = {
        "text": query,
        "api-key": WORLDNEWS_API_KEY,
        "language": "en",
        "number": min(max_records, 100),
        "sort": "publish-time",
        "sort-direction": "DESC",
        "start-date": from_date,
        "end-date": to_date
    }
    headers = {
        "User-Agent": f"IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)"
    }
    logger.info(f"Sending World News API request with params: {params}")
    
    try:
        response = requests.get(WORLDNEWS_API_URL, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        logger.info(f"World News API response: {data}")
        
        if "error" in data:
            error_msg = f"World News API error: {data.get('error', 'Unknown error')}"
            logger.error(error_msg)
            send_error_email(error_msg)
            return [], error_msg
            
        articles = data.get("news", [])
        if not articles:
            error_msg = f"No articles found for query '{query}' in World News API."
            logger.warning(error_msg)
            return [], error_msg
            
        return [
            {
                "title": a.get("title", "No title"),
                "url": a.get("url", ""),
                "source": a.get("source", "Unknown Source"),
                "published_at": a.get("publish_date", ""),
                "description": a.get("text", "") or "No description available",
                "image_url": a.get("image", ""),
                "translated_title": "",
                "translated_description": ""
            }
            for a in articles
        ], None
    except Exception as e:
        error_msg = f"Error fetching World News API: {str(e)}"
        logger.error(error_msg)
        send_error_email(error_msg)
        return [], error_msg

# Fetch news from all APIs in parallel using ThreadPoolExecutor
def fetch_news(query="Iran", max_records=20, from_date=None, to_date=None):
    """
    Fetch news from all APIs in parallel and combine results
    """
    st.write("Starting news fetch process (parallel)...")
    logger.info(f"Fetching news for query: {query}, max_records: {max_records}, from_date: {from_date}, to_date: {to_date}")
    fetch_functions = [
        (fetch_gnews, "GNews"),
        (fetch_worldnews, "World News API")
    ]
    
    all_articles = []
    errors = []
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_to_api = {
            executor.submit(func, query, max_records, from_date, to_date): name
            for func, name in fetch_functions
        }
        
        for future in as_completed(future_to_api):
            api_name = future_to_api[future]
            try:
                articles, error = future.result()
                st.write(f"Fetched {len(articles)} articles from {api_name}")
                logger.info(f"Fetched {len(articles)} articles from {api_name}")
                if articles:
                    all_articles.extend(articles)
                if error:
                    errors.append(f"{api_name}: {error}")
            except Exception as e:
                error_msg = f"Error fetching from {api_name}: {str(e)}"
                errors.append(error_msg)
                st.error(error_msg)
                send_error_email(error_msg)
    
    # Remove duplicates based on URL
    seen_urls = set()
    unique_articles = []
    for article in all_articles:
        if article["url"] not in seen_urls:
            seen_urls.add(article["url"])
            unique_articles.append(article)
    
    # Limit the total number of articles to max_records
    unique_articles = unique_articles[:max_records]
    logger.info(f"After removing duplicates and limiting: {len(unique_articles)} articles")
    
    for error in errors:
        st.error(error)
        send_error_email(error)
    
    if unique_articles:
        st.write(f"Successfully fetched {len(unique_articles)} unique articles from all APIs!")
    else:
        st.warning("No articles fetched from any API. This might be due to API indexing delays. Try adjusting the date range (e.g., search for articles from a few days ago).")
    
    return unique_articles

# Function to translate text using Avalai API with /chat/completions
def translate_with_avalai(text, source_lang="en", target_lang="fa", avalai_api_url=AVALAI_API_URL_DEFAULT):
    """
    Translate text using Avalai API's /chat/completions endpoint
    """
    if not text:
        logger.warning("Empty text provided for translation")
        return text
    
    if not AVALAI_API_KEY or AVALAI_API_KEY == "YOUR_AVALAI_API_KEY":
        error_msg = "Invalid Avalai API key. Please set a valid API key in Render environment variables."
        logger.error(error_msg)
        send_error_email(error_msg)
        return text
    
    endpoint = f"{avalai_api_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {AVALAI_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": f"IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)"
    }
    payload = {
        "model": "gpt-4.1-nano",
        "messages": [
            {
                "role": "user",
                "content": f"Translate this text from {source_lang} to {target_lang}: {text}"
            }
        ]
    }
    
    try:
        logger.info(f"Sending translation request to Avalai: {payload}")
        response = requests.post(endpoint, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Avalai API response: {data}")
        
        if "choices" in data and len(data["choices"]) > 0:
            translated_text = data["choices"][0]["message"]["content"]
            return translated_text
        else:
            error_msg = f"Avalai API response missing choices: {data}"
            logger.warning(error_msg)
            send_error_email(error_msg)
            return text
    except Exception as e:
        error_msg = f"Error translating with Avalai: {str(e)}"
        logger.error(error_msg)
        send_error_email(error_msg)
        return text

# Function to convert UTC time to Tehran time and return as datetime object
def parse_to_tehran_time(utc_time_str):
    """
    Convert UTC time string to Tehran time (UTC+3:30) and return as datetime object
    """
    if not utc_time_str:
        logger.warning("Empty time string provided")
        return None
    
    # Expanded list of possible time formats
    time_formats = [
        "%Y-%m-%dT%H:%M:%SZ",           # 2025-05-14T12:34:56Z
        "%Y-%m-%d %H:%M:%S",            # 2025-05-14 12:34:56
        "%Y-%m-%dT%H:%M:%S",            # 2025-05-14T12:34:56
        "%Y-%m-%dT%H:%M:%S.%fZ",        # 2025-05-14T12:34:56.789Z
        "%Y-%m-%d %H:%M:%S.%f",         # 2025-05-14 12:34:56.789
        "%Y-%m-%dT%H:%M:%S%z",          # 2025-05-14T12:34:56+0000
    ]
    
    for time_format in time_formats:
        try:
            utc_time = datetime.strptime(utc_time_str, time_format)
            tehran_time = utc_time + timedelta(hours=3, minutes=30)
            logger.info(f"Successfully parsed time: {utc_time_str} -> {tehran_time}")
            return tehran_time
        except ValueError:
            continue
    
    error_msg = f"Error converting time: Invalid format - Input: {utc_time_str}"
    logger.warning(error_msg)
    send_error_email(error_msg)
    return None

# Function to format Tehran time for display
def format_tehran_time(tehran_time):
    """
    Format Tehran time for display
    """
    return tehran_time.strftime("%Y/%m/%d - %H:%M")

# Function to truncate text to a specified length
def truncate_text(text, max_length=100):
    """
    Truncate text to a specified length and add ellipsis if necessary
    """
    if len(text) > max_length:
        return text[:max_length].rsplit(" ", 1)[0] + "..."
    return text

# Function to filter articles by time range
def filter_articles_by_time(articles, time_range_hours, start_date=None, end_date=None, disable_filter=False):
    """
    Filter articles based on the selected time range or date range
    """
    if not articles:
        return []
    
    if disable_filter:
        logger.info("Time filter disabled. Returning all articles.")
        return articles
    
    filtered_articles = []
    
    current_utc_time = datetime.utcnow()
    current_tehran_time = current_utc_time + timedelta(hours=3, minutes=30)
    
    if time_range_hours == float("inf"):
        start_datetime = datetime.combine(start_date, datetime.min.time()) + timedelta(hours=3, minutes=30)
        end_datetime = datetime.combine(end_date, datetime.max.time()) + timedelta(hours=3, minutes=30)
        
        for article in articles:
            published_time = parse_to_tehran_time(article["published_at"])
            if published_time:
                logger.info(f"Article time: {published_time}, Start: {start_datetime}, End: {end_datetime}")
                if start_datetime <= published_time <= end_datetime:
                    filtered_articles.append(article)
            else:
                logger.warning(f"Skipping article due to unparseable time: {article['published_at']}")
    else:
        cutoff_time = current_tehran_time - timedelta(hours=time_range_hours)
        for article in articles:
            published_time = parse_to_tehran_time(article["published_at"])
            if published_time:
                logger.info(f"Article time: {published_time}, Cutoff: {cutoff_time}")
                if published_time >= cutoff_time:
                    filtered_articles.append(article)
            else:
                logger.warning(f"Skipping article due to unparseable time: {article['published_at']}")
    
    logger.info(f"After filtering: {len(filtered_articles)} articles remain out of {len(articles)}")
    return filtered_articles

# Function to pre-process articles (translations only)
def pre_process_articles(articles, avalai_api_url, enable_translation=False, num_articles_to_translate=1):
    """
    Pre-process articles by translating with Avalai, only for the specified number of newest articles
    """
    if not articles:
        return articles
    
    # Sort articles by publication time (newest first)
    sorted_articles = sorted(
        articles,
        key=lambda x: parse_to_tehran_time(x["published_at"]) or datetime.min,
        reverse=True
    )
    logger.info(f"Sorted {len(sorted_articles)} articles for translation processing")
    
    for i, article in enumerate(sorted_articles):
        try:
            # Only translate the specified number of newest articles
            if enable_translation and i < num_articles_to_translate:
                logger.info(f"Translating article {i+1}: {article['title']}")
                article["translated_title"] = translate_with_avalai(article["title"], source_lang="en", target_lang="fa", avalai_api_url=avalai_api_url)
                article["translated_description"] = translate_with_avalai(article["description"], source_lang="en", target_lang="fa", avalai_api_url=avalai_api_url)
            else:
                article["translated_title"] = article["title"]
                article["translated_description"] = article["description"]
                if enable_translation and i >= num_articles_to_translate:
                    logger.info(f"Skipping translation for article {i+1}: {article['title']} (beyond limit of {num_articles_to_translate})")
        except Exception as e:
            st.error(f"Error processing article {article['title']}: {str(e)}")
            logger.error(f"Error in pre_process_articles: {str(e)}")
            send_error_email(f"Error in pre_process_articles: {str(e)} - Article: {article['title']}")
    return sorted_articles

# Function to display news articles in a nice format (two columns)
def display_news_articles(articles):
    """Display news articles in a structured format with two columns"""
    st.write(f"Attempting to display {len(articles)} articles...")
    logger.info(f"Displaying {len(articles)} articles: {articles}")
    
    if not articles:
        st.warning("No news articles to display. This might be due to filtering or no articles being fetched.")
        return
    
    sorted_articles = sorted(
        articles,
        key=lambda x: parse_to_tehran_time(x["published_at"]) or datetime.min,
        reverse=True
    )
    logger.info(f"Sorted articles: {len(sorted_articles)} articles after sorting")
    
    st.subheader("News Statistics")
    sources = pd.DataFrame([article["source"] for article in sorted_articles]).value_counts().reset_index()
    sources.columns = ["Source", "Count"]
    if len(sources) > 1:
        col1, col2 = st.columns(2)
        with col1:
            st.bar_chart(sources.set_index("Source"))
        with col2:
            st.dataframe(sources)
    else:
        st.write(f"All articles from: {sources.iloc[0, 0]}")
    
    st.subheader("Selected Articles")
    selected_count = len(st.session_state.selected_articles)
    st.write(f"You have selected {selected_count} article(s) to send to Telegram")
    logger.info(f"Current selected articles: {st.session_state.selected_articles}")
    
    st.subheader("News Articles")
    # Create two columns for displaying articles
    col1, col2 = st.columns(2)
    for i, article in enumerate(sorted_articles):
        # Alternate between columns
        current_col = col1 if i % 2 == 0 else col2
        
        with current_col:
            # Neon line above the article title
            st.markdown(f'<div class="neon-line-top"></div>', unsafe_allow_html=True)
            logger.info(f"Rendering article {i+1}: {article['title']}")
            
            is_selected = any(a.get('url') == article['url'] for a in st.session_state.selected_articles)
            checkbox_key = f"article_{i}"
            if st.checkbox("Select for Telegram", key=checkbox_key, value=is_selected):
                if not is_selected:
                    st.session_state.selected_articles.append(article)
                    logger.info(f"Added article to selected: {article['title']}")
            else:
                if is_selected:
                    st.session_state.selected_articles = [a for a in st.session_state.selected_articles if a.get('url') != article['url']]
                    logger.info(f"Removed article from selected: {article['title']}")
            
            tehran_time = parse_to_tehran_time(article["published_at"])
            tehran_time_str = format_tehran_time(tehran_time) if tehran_time else article["published_at"]
            truncated_description = truncate_text(article["description"], max_length=100)
            truncated_translated_description = truncate_text(article["translated_description"], max_length=100)
            
            st.markdown(f'<div class="article-section">', unsafe_allow_html=True)
            st.markdown(f'<h3 class="title-link"><a href="{article["url"]}" target="_blank">{article["translated_title"]}</a></h3>', unsafe_allow_html=True)
            st.markdown(f'<div class="source-date">**Source:** {article["source"]} | **انتشار:** {tehran_time_str}</div>', unsafe_allow_html=True)
            if article["image_url"]:
                try:
                    st.image(article["image_url"], width=300)
                except:
                    st.info("Image could not be loaded")
            st.markdown(f'<div class="english-text description">**Description (English):** {truncated_description}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="persian-text description">**توضیحات (فارسی):** {truncated_translated_description}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

# Function to save articles to a file for download
def save_articles_to_file_for_download(articles, format="csv"):
    if not articles:
        return None
    df = pd.DataFrame(articles)
    if format == "csv":
        buffer = BytesIO()
        df.to_csv(buffer, index=False)
        return buffer.getvalue()
    elif format == "json":
        return json.dumps(articles, indent=2)
    return None

# Function to send a message to Telegram (include both original and translated text)
def send_telegram_message(chat_id, message, disable_web_page_preview=False):
    try:
        if len(message) > 4096:
            message = message[:4093] + "..."
        
        url = f"{TELEGRAM_API_URL}/sendMessage"
        data = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": disable_web_page_preview}
        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        if result.get("ok"):
            return True, "Message sent successfully"
        return False, f"Error: {result.get('description', 'Unknown error')}"
    except requests.exceptions.RequestException as e:
        return False, f"Error sending message: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"

# Function to get Chat ID from Telegram username
def get_chat_id_from_username(username, chat_ids):
    """
    Get Chat ID from Telegram username using stored chat IDs or getUpdates
    """
    try:
        if not username.startswith("@"):
            return None, "Username must start with @ (e.g., @username)"
        
        username = username[1:].lower()
        
        if username in chat_ids:
            return chat_ids[username], None
        
        url = f"{TELEGRAM_API_URL}/getUpdates"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("ok"):
            return None, "Failed to fetch updates from Telegram"
        
        for update in data.get("result", []):
            if "message" in update and "chat" in update["message"]:
                chat = update["message"]["chat"]
                if chat.get("username", "").lower() == username:
                    chat_id = chat["id"]
                    chat_ids[username] = chat_id
                    save_chat_ids(chat_ids)
                    return chat_id, None
                if chat.get("type") == "group" or chat.get("type") == "supergroup":
                    if chat.get("title", "").lower().find(username.lower()) != -1:
                        chat_id = chat["id"]
                        chat_ids[username] = chat_id
                        save_chat_ids(chat_ids)
                        return chat_id, None
        
        return None, f"Chat ID not found for username @{username}. Make sure the user/group has interacted with the bot."
    except Exception as e:
        logger.warning(f"Error fetching Chat ID for username {username}: {str(e)}")
        send_error_email(f"Error fetching Chat ID for username {username}: {str(e)}")
        return None, str(e)

# Main Streamlit app
def main():
    st.title("Iran News Aggregator")
    
    if 'selected_articles' not in st.session_state:
        st.session_state.selected_articles = []
    if 'articles' not in st.session_state:
        st.session_state.articles = load_articles_from_file()
    if 'chat_ids' not in st.session_state:
        st.session_state.chat_ids = load_chat_ids()
    if 'avalai_api_url' not in st.session_state:
        st.session_state.avalai_api_url = AVALAI_API_URL_DEFAULT
    
    if not st.session_state.articles:
        st.info("No articles in session state. Please search for news or check if data was loaded from file.")
        logger.info("No articles in session state at start.")
    else:
        st.info(f"Found {len(st.session_state.articles)} articles in session state.")
        logger.info(f"Found {len(st.session_state.articles)} articles in session state at start.")
    
    with st.sidebar:
        st.header("Query Settings")
        query = st.text_input("Search Query", value="Iran", key="search_query").strip()
        today = datetime(2025, 5, 14)
        default_start_date = today - timedelta(days=7)
        start_date = st.date_input("Start Date", value=default_start_date, min_value=today - timedelta(days=30), max_value=today, key="start_date")
        end_date = st.date_input("End Date", value=today, min_value=start_date, max_value=today, key="end_date")
        max_articles = st.slider(label="Maximum number of articles per API", min_value=5, max_value=100, value=20, key="max_articles")
        
        time_range_options = {
            "Last 30 minutes": 0.5,
            "Last 1 hour": 1,
            "Last 4 hours": 4,
            "Last 12 hours": 12,
            "Last 24 hours": 24,
            "All articles": float("inf")
        }
        selected_time_range = st.selectbox("Time Range", options=list(time_range_options.keys()), index=4, key="time_range")
        time_range_hours = time_range_options[selected_time_range]
        
        disable_time_filter = st.checkbox("Disable Time Filter (Show All Articles)", value=False, key="disable_time_filter")
        
        st.header("Translation Settings")
        avalai_api_url_options = ["https://api.avalai.ir/v1", "https://api.avalapis.ir/v1"]
        st.session_state.avalai_api_url = st.selectbox(
            "Avalai API URL",
            options=avalai_api_url_options,
            index=avalai_api_url_options.index(st.session_state.avalai_api_url),
            help="Choose the Avalai API URL. Use https://api.avalai.ir/v1 for global access, or https://api.avalapis.ir/v1 for better performance inside Iran (only accessible from Iran)."
        )
        
        enable_translation = st.checkbox("Enable Translation (May cause 403 error)", value=False, key="enable_translation")
        
        # Add a slider for selecting the number of articles to translate
        num_articles_to_translate = 1
        if enable_translation:
            num_articles_to_translate = st.slider(
                label="Number of articles to translate (newest first)",
                min_value=1,
                max_value=max_articles,
                value=1,
                key="num_articles_to_translate"
            )
        
        search_button = st.button("Search for News")
        clear_button = st.button("Clear Results")
        
        st.header("Telegram Settings")
        telegram_chat_id = st.text_input("Telegram Chat ID", value="5013104607", key="telegram_chat_id")
        telegram_user_or_group_id = st.text_input("Send to User/Group", value="", key="telegram_user_or_group_id", help="Enter the @username or @groupname to send selected news to (leave blank to use default Chat ID)")
        
        bot_username = "YourBotUsername"
        st.markdown(f"[Start a chat with the bot](https://t.me/{bot_username}) to allow sending messages.", unsafe_allow_html=True)
        
        if st.session_state.chat_ids:
            st.subheader("Known Users/Groups")
            for username, chat_id in st.session_state.chat_ids.items():
                st.write(f"@{username}: {chat_id}")
        
        st.header("Download Options")
        download_format = st.selectbox("Download Format", ["CSV", "JSON"], key="download_format")
    
    if clear_button:
        st.session_state.articles = []
        st.session_state.selected_articles = []
        if os.path.exists(TEMP_FILE):
            os.remove(TEMP_FILE)
        st.experimental_rerun()

    if search_button:
        with st.spinner(f"Searching for news about {query}..."):
            logger.info(f"Search button clicked. Query: {query}, Start Date: {start_date}, End Date: {end_date}, Max Articles: {max_articles}")
            from_date = start_date.strftime("%Y-%m-%d")
            to_date = end_date.strftime("%Y-%m-%d")
            articles = fetch_news(query=query, max_records=max_articles, from_date=from_date, to_date=to_date)
            if articles:
                logger.info(f"Before filtering: {len(articles)} articles")
                filtered_articles = filter_articles_by_time(articles, time_range_hours, start_date, end_date, disable_filter=disable_time_filter)
                if not filtered_articles:
                    if time_range_hours != float("inf"):
                        st.warning(f"مقاله‌ای در {selected_time_range} گذشته پیدا نشد. لطفاً بازه زمانی را تغییر دهید یا فیلتر زمانی را غیرفعال کنید.")
                    else:
                        st.warning(f"No articles found within the selected date range ({start_date} to {end_date}). Try adjusting the date range or disabling the time filter.")
                else:
                    articles = filtered_articles
                logger.info(f"After filtering: {len(articles)} articles")
                articles = pre_process_articles(articles, st.session_state.avalai_api_url, enable_translation=enable_translation, num_articles_to_translate=num_articles_to_translate)
                logger.info(f"After preprocessing: {len(articles)} articles")
                st.session_state.articles = articles
                save_articles_to_file(articles)
                st.session_state.selected_articles = []
                st.success("Articles fetched successfully!")
            else:
                st.warning("No articles fetched. Check the error messages above or try a different query.")
                logger.warning("No articles fetched after fetch_news call.")
    
    if st.session_state.articles:
        st.write(f"Found {len(st.session_state.articles)} articles in session state. Displaying now...")
        display_news_articles(st.session_state.articles)
    else:
        st.info("No articles to display in session state.")
        logger.info("No articles to display in session state after search.")

    with st.sidebar:
        st.header("Telegram Actions")
        if st.button("Reset Selection"):
            st.session_state.selected_articles = []
            st.success("Selection reset successfully!")
            logger.info("Selection reset by user.")
        
        if st.button("Send Selected News to Telegram", disabled=len(st.session_state.selected_articles) == 0):
            with st.spinner("Sending to Telegram..."):
                success_count = 0
                fail_count = 0
                target_chat_id = telegram_user_or_group_id if telegram_user_or_group_id else telegram_chat_id
                
                if target_chat_id.startswith("@"):
                    chat_id, error = get_chat_id_from_username(target_chat_id, st.session_state.chat_ids)
                    if chat_id is None:
                        st.error(f"Failed to resolve username: {error}")
                        fail_count = len(st.session_state.selected_articles)
                    else:
                        target_chat_id = chat_id
                
                st.info(f"Sending to Chat ID: {target_chat_id}")
                logger.info(f"Sending {len(st.session_state.selected_articles)} articles to {target_chat_id}")
                
                for article in st.session_state.selected_articles:
                    message = (
                        f"*{article['title']}*\n\n"
                        f"{article['description']}\n\n"
                        f"*عنوان (فارسی):* {article['translated_title']}\n\n"
                        f"*توضیحات (فارسی):* {article['translated_description']}\n\n"
                        f"[Read more]({article['url']})"
                    )
                    st.info(f"Message: {message}")
                    success, result = send_telegram_message(target_chat_id, message, disable_web_page_preview=False)
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1
                        st.error(f"Failed to send to {target_chat_id}: {article['title']} - {result}")
                    time.sleep(1)
                if success_count > 0:
                    st.success(f"Successfully sent {success_count} article(s) to Telegram")
                if fail_count > 0:
                    st.warning(f"Failed to send {fail_count} article(s) to Telegram")
        else:
            st.info(f"Select {len(st.session_state.selected_articles)} article(s) to send to Telegram")
            logger.info(f"No articles selected for sending. Current count: {len(st.session_state.selected_articles)}")

    if st.session_state.articles:
        with st.sidebar:
            st.header("Download Options")
            if download_format == "CSV":
                csv_data = save_articles_to_file_for_download(st.session_state.articles, format="csv")
                st.download_button(
                    label="Download as CSV",
                    data=csv_data if csv_data else b"",
                    file_name=f"iran_news_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                json_data = save_articles_to_file_for_download(st.session_state.articles, format="json")
                st.download_button(
                    label="Download as JSON",
                    data=json_data if json_data else b"",
                    file_name=f"iran_news_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json"
                )

if __name__ == "__main__":
    main()
