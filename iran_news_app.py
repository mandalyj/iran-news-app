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
from bs4 import BeautifulSoup  # For extracting article content

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration - API keys are fetched from environment variables
GNEWS_API_URL = "https://gnews.io/api/v4/search"
GNEWS_API_KEY = os.environ.get("GNEWS_API_KEY", "YOUR_GNEWS_API_KEY")
WORLDNEWS_API_URL = "https://api.worldnewsapi.com/search-news"
WORLDNEWS_API_KEY = os.environ.get("WORLDNEWS_API_KEY", "YOUR_WORLDNEWS_API_KEY")
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"
FMP_API_URL = "https://financialmodelingprep.com/api/v3"
FMP_API_KEY = os.environ.get("FMP_API_KEY", "YOUR_FMP_API_KEY")
AVALAI_API_URL_DEFAULT = "https://api.avalai.ir/v1"
AVALAI_API_KEY = os.environ.get("AVALAI_API_KEY", "YOUR_AVALAI_API_KEY")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Temporary file to store articles/reports and chat IDs
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
    .report-section {
        margin-bottom: 20px;
        padding: 10px;
        background-color: #e6f3ff;
        border-radius: 5px;
    }
    .neon-line-top {
        height: 4px;
        background: linear-gradient(90deg, rgba(255, 0, 0, 0.8), rgba(255, 100, 100, 0.8), rgba(255, 0, 0, 0.8));
        box-shadow: 0 0 10px rgba(255, 0, 0, 0.7), 0 0 20px rgba(255, 0, 0, 0.5), 0 0 30px rgba(255, 100, 100, 0.3);
        margin: 10px 0;
    }
    .title-link {
        font-size: 20px !important;
        font-weight: bold !important;
        color: #1a73e8 !important;
        margin-bottom: 2px !important;
        direction: rtl !important;
        text-decoration: none !important;
        font-family: "B Nazanin", "B Lotus", "Arial Unicode MS", sans-serif !important;
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
    logger.info(f"Error email sending is disabled. Error message: {error_message}")

# Load articles/reports from temp file if exists
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

# Save articles/reports to temp file
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
        logger.warning(f"Error saving chat IDs from file: {str(e)}")
        send_error_email(f"Error saving chat IDs from file: {str(e)}")

# Fetch news from GNews API
def fetch_gnews(query="Iran", max_records=20, from_date=None, to_date=None):
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
                "translated_description": "",
                "type": "news"
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
                "translated_description": "",
                "type": "news"
            }
            for a in articles
        ], None
    except Exception as e:
        error_msg = f"Error fetching World News API: {str(e)}"
        logger.error(error_msg)
        send_error_email(error_msg)
        return [], error_msg

# Fetch crypto news from CoinGecko API with delay and retry
def fetch_coingecko_news(query="cryptocurrency", max_records=20, from_date=None, to_date=None):
    endpoint = f"{COINGECKO_API_URL}/news"
    headers = {
        "User-Agent": f"IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)"
    }
    params = {
        "limit": min(max_records, 100),
    }
    logger.info(f"Sending CoinGecko news request with params: {params}")

    retries = 3
    delay = 5
    for attempt in range(retries):
        try:
            logger.info(f"Adding a {delay}-second delay before CoinGecko request (Attempt {attempt + 1}/{retries}) to avoid rate limiting...")
            time.sleep(delay)

            response = requests.get(endpoint, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            logger.info(f"CoinGecko news response: {data}")

            articles = data.get("data", [])
            if not articles:
                error_msg = f"No articles found for query '{query}' in CoinGecko."
                logger.warning(error_msg)
                return [], error_msg

            formatted_articles = []
            for a in articles:
                published_at = a.get("published_at", "")
                if from_date and to_date:
                    article_date = parse_to_tehran_time(published_at)
                    if not article_date:
                        continue
                    start_datetime = datetime.strptime(from_date, "%Y-%m-%d")
                    end_datetime = datetime.strptime(to_date, "%Y-%m-%d")
                    # Adjusting for timezone difference for date comparison
                    start_datetime_tehran = start_datetime - timedelta(hours=3, minutes=30)
                    end_datetime_tehran = end_datetime - timedelta(hours=3, minutes=30) + timedelta(days=1) # Include the whole end day

                    if not (start_datetime_tehran <= article_date <= end_datetime_tehran):
                        continue
                formatted_articles.append({
                    "title": a.get("title", "No title"),
                    "url": a.get("url", ""),
                    "source": a.get("source", "CoinGecko"),
                    "published_at": published_at,
                    "description": a.get("description", "") or "No description available",
                    "image_url": a.get("thumb", ""),
                    "translated_title": "",
                    "translated_description": "",
                    "type": "news"
                })

            return formatted_articles, None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.warning(f"Rate limit exceeded (429), retrying in {delay} seconds... (Attempt {attempt + 1}/{retries})")
                if attempt < retries - 1:
                    time.sleep(delay)
                    delay *= 2
                else:
                    error_msg = "Max retries exceeded for CoinGecko news due to rate limiting."
                    logger.error(error_msg)
                    send_error_email(error_msg)
                    return [], error_msg
            else:
                error_msg = f"Error fetching CoinGecko news: {str(e)}"
                logger.error(error_msg)
                send_error_email(error_msg)
                return [], error_msg
        except Exception as e:
            error_msg = f"Error fetching CoinGecko news: {str(e)}"
            logger.error(error_msg)
            send_error_email(error_msg)
            return [], error_msg
    # Fallback if all retries fail
    error_msg = "Failed to fetch CoinGecko news after multiple retries."
    logger.error(error_msg)
    send_error_email(error_msg)
    return [], error_msg


# Fetch financial report from Financial Modeling Prep API
def fetch_financial_report(symbol, max_records=1, from_date=None, to_date=None):
    if not FMP_API_KEY or FMP_API_KEY == "YOUR_FMP_API_KEY":
        error_msg = "Invalid Financial Modeling Prep API key. Please set a valid API key in Render environment variables."
        logger.error(error_msg)
        send_error_email(error_msg)
        return [], error_msg

    endpoint = f"{FMP_API_URL}/income-statement/{symbol}"
    headers = {
        "User-Agent": f"IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)",
        "Content-Type": "application/json"
    }
    params = {
        "limit": max_records,
        "apikey": FMP_API_KEY
    }
    logger.info(f"Sending Financial Modeling Prep request for symbol {symbol} with params: {params}")

    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Financial Modeling Prep response: {data}")

        if not isinstance(data, list):
            error_msg = f"Unexpected response format from Financial Modeling Prep: {data}"
            logger.error(error_msg)
            send_error_email(error_msg)
            return [], error_msg

        if not data:
            error_msg = f"No financial reports found for symbol '{symbol}'."
            logger.warning(error_msg)
            return [], error_msg

        reports = []
        for report in data:
            report_date = report.get("date", "")
            if from_date and to_date:
                report_datetime = datetime.strptime(report_date, "%Y-%m-%d")
                start_datetime = datetime.strptime(from_date, "%Y-%m-%d")
                end_datetime = datetime.strptime(to_date, "%Y-%m-%d")
                if not (start_datetime <= report_datetime <= end_datetime):
                    continue
            reports.append({
                "symbol": report.get("symbol", symbol),
                "date": report_date,
                "revenue": report.get("revenue", 0),
                "netIncome": report.get("netIncome", 0),
                "eps": report.get("eps", 0),
                "grossProfit": report.get("grossProfit", 0),
                "operatingIncome": report.get("operatingIncome", 0),
                "reportedCurrency": report.get("reportedCurrency", "USD"),
                "type": "report"
            })

        return reports, None
    except Exception as e:
        error_msg = f"Error fetching Financial Modeling Prep report: {str(e)}"
        logger.error(error_msg)
        send_error_email(error_msg)
        return [], error_msg

# Fetch news or reports from the selected API
def fetch_news(selected_api, query="Iran", max_records=20, from_date=None, to_date=None):
    st.write(f"Starting fetch process from {selected_api}...")
    logger.info(f"Fetching from {selected_api} for query: {query}, max_records: {max_records}, from_date: {from_date}, to_date: {to_date}")

    all_items = []
    errors = []

    api_functions = {
        "GNews": fetch_gnews,
        "World News API": fetch_worldnews,
        "CoinGecko (Crypto News)": fetch_coingecko_news,
        "Financial Report (FMP)": fetch_financial_report
    }

    fetch_function = api_functions.get(selected_api)
    if not fetch_function:
        error_msg = f"Invalid API selected: {selected_api}"
        logger.error(error_msg)
        st.error(error_msg)
        return []

    try:
        fetch_query = query if selected_api != "Financial Report (FMP)" else query.upper()
        items, error = fetch_function(fetch_query, max_records, from_date, to_date)
        st.write(f"Fetched {len(items)} items from {selected_api}")
        logger.info(f"Fetched {len(items)} items from {selected_api}")
        if items:
            all_items.extend(items)
        if error:
            errors.append(f"{selected_api}: {error}")
    except Exception as e:
        error_msg = f"Error fetching from {selected_api}: {str(e)}"
        errors.append(error_msg)
        st.error(error_msg)
        send_error_email(error_msg)

    if selected_api != "Financial Report (FMP)":
        seen_urls = set()
        unique_items = []
        for item in all_items:
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                unique_items.append(item)
        all_items = unique_items[:max_records]
    else:
        all_items = all_items[:max_records]

    logger.info(f"After processing: {len(all_items)} items")

    for error in errors:
        st.error(error)
        send_error_email(error)

    if all_items:
        st.write(f"Successfully fetched {len(all_items)} items from {selected_api}!")
    else:
        st.warning(f"No items fetched from {selected_api}. This might be due to API indexing delays or invalid query. Try adjusting the date range or query.")

    return all_items

# Function to translate text using Avalai API with /chat/completions
def translate_with_avalai(text, source_lang="en", target_lang="fa", avalai_api_url=AVALAI_API_URL_DEFAULT):
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
        "model": "gpt-4.1-nano", # Using a potentially faster/cheaper model for translation
        "messages": [
            {
                "role": "system",
                "content": f"You are a helpful translator. Translate the following text from {source_lang} to {target_lang}."
            },
            {
                "role": "user",
                "content": text
            }
        ],
        "max_tokens": 1000 # Limit response length for translation
    }

    try:
        logger.info(f"Sending translation request to Avalai endpoint: {endpoint}")
        response = requests.post(endpoint, headers=headers, json=payload, timeout=20) # Increased timeout
        response.raise_for_status()
        data = response.json()
        logger.info(f"Avalai API response status: {response.status_code}")
        logger.debug(f"Avalai API full response: {data}")

        if "choices" in data and len(data["choices"]) > 0:
            translated_text = data["choices"][0]["message"]["content"].strip()
            logger.info(f"Translation successful. Translated text snippet: {translated_text[:50]}...")
            return translated_text
        else:
            error_msg = f"Avalai API response missing choices or choices is empty: {data}"
            logger.warning(error_msg)
            send_error_email(error_msg)
            return text # Return original text if translation fails
    except requests.exceptions.RequestException as e:
        error_msg = f"Network or API error during Avalai translation: {str(e)}"
        logger.error(error_msg)
        send_error_email(error_msg)
        return text # Return original text on error
    except Exception as e:
        error_msg = f"Unexpected error during Avalai translation: {str(e)}"
        logger.error(error_msg)
        send_error_email(error_msg)
        return text # Return original text on error


# Function to convert UTC time to Tehran time and return as datetime object
def parse_to_tehran_time(utc_time_str):
    if not utc_time_str:
        logger.warning("Empty time string provided")
        return None

    time_formats = [
        "%Y-%m-%dT%H:%M:%SZ", # GNews
        "%Y-%m-%d %H:%M:%S", # World News API (sometimes)
        "%Y-%m-%dT%H:%M:%S", # World News API (sometimes)
        "%Y-%m-%dT%H:%M:%S.%fZ", # GNews (sometimes)
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d",  # For financial reports (just date) or APIs with only date
        "%Y-%m-%dT%H:%M:%S+00:00", # CoinGecko
    ]

    utc_time = None
    for time_format in time_formats:
        try:
            # Handle timezone info if present
            if '%' in time_format and 'z' in time_format:
                utc_time = datetime.strptime(utc_time_str, time_format)
                # Convert to UTC if a timezone is parsed
                if utc_time.tzinfo is not None:
                    import pytz
                    utc_time = utc_time.astimezone(pytz.utc).replace(tzinfo=None)
            else:
                utc_time = datetime.strptime(utc_time_str, time_format)

            # If only date is parsed, assume midnight UTC
            if len(utc_time_str.split('T')) == 1 and '-' in utc_time_str and ':' not in utc_time_str:
                utc_time = datetime.strptime(utc_time_str, "%Y-%m-%d")

            tehran_time = utc_time + timedelta(hours=3, minutes=30)
            logger.info(f"Successfully parsed time: {utc_time_str} -> {tehran_time} (Tehran Time)")
            return tehran_time
        except ValueError:
            continue
        except Exception as e:
            logger.error(f"Unexpected error parsing time {utc_time_str} with format {time_format}: {str(e)}")
            continue

    error_msg = f"Error converting time: Invalid format or parsing error - Input: {utc_time_str}"
    logger.warning(error_msg)
    send_error_email(error_msg)
    return None


# Function to format Tehran time for display
def format_tehran_time(tehran_time):
    if not isinstance(tehran_time, datetime):
        logger.warning(f"Invalid input for format_tehran_time: {tehran_time}")
        return str(tehran_time) # Return as is if not a datetime object
    return tehran_time.strftime("%Y/%m/%d - %H:%M")

# Function to truncate text to a specified length
def truncate_text(text, max_length=100):
    if not isinstance(text, str):
        return str(text)
    if len(text) > max_length:
        return text[:max_length].rsplit(" ", 1)[0] + "..."
    return text

# Function to extract article content for Instant View (Simplified)
def extract_article_content(url):
    try:
        headers = {
            "User-Agent": f"IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)"
        }
        logger.info(f"Attempting to extract content from: {url}")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Attempt to find common article content containers
        possible_containers = [
            'article',
            '.article-content',
            '.entry-content',
            '.post-content',
            '.story-body',
            'main',
            'body' # Fallback
        ]

        content_element = None
        for selector in possible_containers:
            content_element = soup.select_one(selector)
            if content_element:
                break

        content = ""
        if content_element:
            paragraphs = content_element.find_all('p')
            content = " ".join([para.get_text(strip=True) for para in paragraphs if para.get_text(strip=True)])
        else:
            # If no specific container found, just get all paragraphs in the body
            paragraphs = soup.find_all('p')
            content = " ".join([para.get_text(strip=True) for para in paragraphs if para.get_text(strip=True)])


        if not content or len(content.split()) < 20: # Minimum word count check
            logger.warning(f"Insufficient content extracted from URL: {url}. Length: {len(content)}")
            return "No significant content available or extraction failed."

        # Basic cleaning
        content = content.replace('\n', ' ').strip()
        content = ' '.join(content.split()) # Remove multiple spaces

        logger.info(f"Extracted content (length: {len(content)}): {content[:200]}...")
        return content
    except Exception as e:
        error_msg = f"Error extracting content from {url}: {str(e)}"
        logger.error(error_msg)
        send_error_email(error_msg)
        return "Unable to extract content."


# Function to filter items by time range (for news only)
def filter_articles_by_time(items, time_range_hours, start_date=None, end_date=None, disable_filter=False):
    if not items:
        return []

    # Do not filter financial reports by time range
    if items and items[0].get("type") == "report":
        return items

    if disable_filter:
        logger.info("Time filter disabled. Returning all articles.")
        return items

    filtered_items = []
    current_utc_time = datetime.utcnow()
    tehran_timezone_offset = timedelta(hours=3, minutes=30)
    current_tehran_time = current_utc_time + tehran_timezone_offset

    if time_range_hours == float("inf"): # Custom date range
        if start_date and end_date:
            try:
                # Convert start/end dates (from UI) to datetime objects for comparison
                # Note: parse_to_tehran_time now returns Tehran time. We compare Tehran times.
                start_datetime_tehran = datetime.combine(start_date, datetime.min.time()) + tehran_timezone_offset
                end_datetime_tehran = datetime.combine(end_date, datetime.max.time()) + tehran_timezone_offset

                for item in items:
                    published_time_tehran = parse_to_tehran_time(item["published_at"]) # Already Tehran time

                    if published_time_tehran:
                        logger.info(f"Article Tehran time: {published_time_tehran}, Start Tehran: {start_datetime_tehran}, End Tehran: {end_datetime_tehran}")
                        if start_datetime_tehran <= published_time_tehran <= end_datetime_tehran:
                            filtered_items.append(item)
                    else:
                        logger.warning(f"Skipping article due to unparseable time: {item['published_at']}")
            except Exception as e:
                logger.error(f"Error filtering by custom date range: {str(e)}")
                send_error_email(f"Error filtering by custom date range: {str(e)}")
                # If filtering fails, return all items to be safe
                return items
    else: # Relative time range
        cutoff_time_tehran = current_tehran_time - timedelta(hours=time_range_hours)
        for item in items:
            published_time_tehran = parse_to_tehran_time(item["published_at"])
            if published_time_tehran:
                logger.info(f"Article Tehran time: {published_time_tehran}, Cutoff Tehran time: {cutoff_time_tehran}")
                if published_time_tehran >= cutoff_time_tehran:
                    filtered_items.append(item)
            else:
                logger.warning(f"Skipping article due to unparseable time: {item['published_at']}")

    logger.info(f"After filtering: {len(filtered_items)} items remain out of {len(items)}")
    return filtered_items


# Function to pre-process articles (translations only, skip for reports)
def pre_process_articles(items, avalai_api_url, enable_translation=False, num_items_to_translate=1):
    if not items:
        return items

    # Do not translate financial reports
    if items and items[0].get("type") == "report":
        return items

    # Sort items by date before translating the latest ones
    sorted_items = sorted(
        items,
        key=lambda x: parse_to_tehran_time(x["published_at"]) or datetime.min,
        reverse=True
    )
    logger.info(f"Sorted {len(sorted_items)} items for translation processing")

    processed_items = []
    for i, item in enumerate(sorted_items):
        processed_item = item.copy() # Work on a copy to avoid modifying original list during iteration

        try:
            if enable_translation and i < num_items_to_translate:
                logger.info(f"Translating item {i+1}: {processed_item['title']}")
                translated_title = translate_with_avalai(processed_item["title"], source_lang="en", target_lang="fa", avalai_api_url=avalai_api_url)
                logger.info(f"Translated title for item {i+1}: {translated_title[:50]}...")
                processed_item["translated_title"] = translated_title

                translated_description = translate_with_avalai(processed_item["description"], source_lang="en", target_lang="fa", avalai_api_url=avalai_api_url)
                logger.info(f"Translated description for item {i+1}: {translated_description[:50]}...")
                processed_item["translated_description"] = translated_description

                if translated_description == processed_item["description"] and processed_item["description"]:
                    # This check might be too simple, as a short text might translate to itself
                    # Consider adding a more robust check or just log a warning.
                    logger.info(f"Translation for description of item {i+1} returned original text.")
            else:
                processed_item["translated_title"] = processed_item["title"]
                processed_item["translated_description"] = processed_item["description"]
                if enable_translation and i >= num_items_to_translate:
                    logger.info(f"Skipping translation for item {i+1}: {processed_item['title']} (beyond limit of {num_items_to_translate})")
                    # st.info(f"Item {i+1} ({processed_item['title']}) skipped for translation (beyond limit of {num_items_to_translate})")

            processed_items.append(processed_item)

        except Exception as e:
            st.error(f"Error processing item {processed_item.get('title', 'Unknown Title')}: {str(e)}")
            logger.error(f"Error in pre_process_articles for item {processed_item.get('title', 'Unknown Title')}: {str(e)}")
            send_error_email(f"Error in pre_process_articles: {str(e)} - Item: {processed_item.get('title', 'Unknown Title')}")
            processed_items.append(processed_item) # Append original item if processing fails

    return processed_items


# Function to display items (news or reports) in a nice format
def display_items(items):
    st.write(f"Attempting to display {len(items)} items...")
    logger.info(f"Displaying {len(items)} items")

    if not items:
        st.warning("No items to display. This might be due to filtering or no items being fetched.")
        return

    item_type = items[0].get("type", "news")

    if item_type == "news":
        sorted_items = sorted(
            items,
            key=lambda x: parse_to_tehran_time(x["published_at"]) or datetime.min,
            reverse=True
        )
        logger.info(f"Sorted articles: {len(sorted_items)} articles after sorting")

        st.subheader("News Statistics")
        if sorted_items:
            sources = pd.DataFrame([item["source"] for item in sorted_items]).value_counts().reset_index()
            sources.columns = ["Source", "Count"]
            if len(sources) > 1:
                col1, col2 = st.columns(2)
                with col1:
                    st.bar_chart(sources.set_index("Source"))
                with col2:
                    st.dataframe(sources)
            else:
                st.write(f"All articles from: {sources.iloc[0, 0]}")
        else:
            st.info("No news items to display statistics.")


        st.subheader("Selected Articles")
        # Use item URL as a unique identifier for selection state
        selected_urls = {a.get('url') for a in st.session_state.selected_items}
        selected_count = len(selected_urls)
        st.write(f"You have selected {selected_count} article(s) to send to Telegram")
        logger.info(f"Current selected items (by URL): {selected_urls}")


        st.subheader("News Articles")
        col1, col2 = st.columns(2)
        for i, item in enumerate(sorted_items):
            current_col = col1 if i % 2 == 0 else col2

            with current_col:
                st.markdown(f'<div class="neon-line-top"></div>', unsafe_allow_html=True)
                logger.info(f"Rendering article {i+1}: {item['title']}")

                item_url = item.get('url')
                is_selected = item_url in selected_urls
                checkbox_key = f"article_select_{item_url}_{i}" # Unique key including URL and index

                if st.checkbox("Select for Telegram", key=checkbox_key, value=is_selected):
                    if not is_selected:
                        st.session_state.selected_items.append(item)
                        logger.info(f"Added article to selected: {item['title']}")
                        # Update the selected_urls set immediately
                        selected_urls.add(item_url)
                else:
                    if is_selected:
                        # Remove the item based on URL
                        st.session_state.selected_items = [a for a in st.session_state.selected_items if a.get('url') != item_url]
                        logger.info(f"Removed article from selected: {item['title']}")
                        # Update the selected_urls set immediately
                        selected_urls.discard(item_url)

                tehran_time = parse_to_tehran_time(item["published_at"])
                tehran_time_str = format_tehran_time(tehran_time) if tehran_time else item["published_at"]
                truncated_description = truncate_text(item["description"], max_length=200) # Increased description truncate
                truncated_translated_description = truncate_text(item["translated_description"], max_length=200) # Increased description truncate

                st.markdown(f'<div class="article-section">', unsafe_allow_html=True)
                st.markdown(f'<h3 class="title-link"><a href="{item["url"]}" target="_blank">{item["translated_title"]}</a></h3>', unsafe_allow_html=True)
                st.markdown(f'<div class="source-date">**Source:** {item["source"]} | **انتشار:** {tehran_time_str}</div>', unsafe_allow_html=True)
                if item["image_url"]:
                    try:
                        # Add a caption or descriptive text for the image if available
                        st.image(item["image_url"], width=300, caption=item.get("title", "Article Image"))
                    except Exception as e:
                        logger.warning(f"Could not load image from {item['image_url']}: {str(e)}")
                        st.info("Image could not be loaded")
                st.markdown(f'<div class="english-text description">**Description (English):** {truncated_description}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="persian-text description">**توضیحات (فارسی):** {truncated_translated_description}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
    else: # Financial Reports
        st.subheader("Financial Reports")
        for i, report in enumerate(items):
            st.markdown(f'<div class="report-section">', unsafe_allow_html=True)
            st.markdown(f"**نماد شرکت:** {report['symbol']}", unsafe_allow_html=True)
            st.markdown(f"**تاریخ گزارش:** {report['date']}", unsafe_allow_html=True)
            st.markdown(f"**ارز گزارش:** {report['reportedCurrency']}", unsafe_allow_html=True)
            st.markdown(f"**درآمد:** {report['revenue']:,} {report['reportedCurrency']}", unsafe_allow_html=True)
            st.markdown(f"**سود خالص:** {report['netIncome']:,} {report['reportedCurrency']}", unsafe_allow_html=True)
            st.markdown(f"**سود هر سهم (EPS):** {report['eps']}", unsafe_allow_html=True)
            st.markdown(f"**سود ناخالص:** {report['grossProfit']:,} {report['reportedCurrency']}", unsafe_allow_html=True)
            st.markdown(f"**درآمد عملیاتی:** {report['operatingIncome']:,} {report['reportedCurrency']}", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

# Function to save items to a file for download
def save_items_to_file_for_download(items, format="csv"):
    if not items:
        return None
    df = pd.DataFrame(items)
    if format == "csv":
        buffer = BytesIO()
        df.to_csv(buffer, index=False)
        return buffer.getvalue()
    elif format == "json":
        return json.dumps(items, indent=2, ensure_ascii=False).encode('utf-8') # Ensure proper encoding
    return None

# Function to send a message to Telegram (include title, description, time, and Instant View for news; financial data for reports)
def send_telegram_message(chat_id, message, disable_web_page_preview=False):
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        error_msg = "Telegram bot token is not set. Cannot send messages."
        logger.error(error_msg)
        st.error(error_msg)
        send_error_email(error_msg)
        return False

    try:
        # Telegram message limit is 4096 characters. Split into multiple messages if needed.
        max_chars = 4000 # Keep a buffer
        messages_to_send = [message[i:i + max_chars] for i in range(0, len(message), max_chars)]

        success = True
        for msg_part in messages_to_send:
            url = f"{TELEGRAM_API_URL}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": msg_part,
                "parse_mode": "Markdown",
                "disable_web_page_preview": disable_web_page_preview
            }
            logger.info(f"Sending message to chat ID {chat_id}: {msg_part[:100]}...")

            response = requests.post(url, json=data, timeout=10)
            response_data = response.json()
            logger.info(f"Telegram API response for sendMessage: {response_data}")

            if response.status_code != 200 or not response_data.get("ok"):
                error_msg = f"Error sending message to Telegram chat ID {chat_id}: {response_data.get('description', 'Unknown error')}"
                logger.error(error_msg)
                st.error(error_msg)
                send_error_email(error_msg)
                success = False # Mark as failed but try sending other parts

        return success

    except Exception as e:
        error_msg = f"Exception during Telegram message sending to chat ID {chat_id}: {str(e)}"
        logger.error(error_msg)
        st.error(error_msg)
        send_error_email(error_msg)
        return False


# --- Streamlit App Layout ---

st.title("Iran News and Financial Report Aggregator")

# Sidebar for API keys, settings, and Telegram
with st.sidebar:
    st.header("Configuration")

    st.warning("API keys are read from environment variables. If you see 'YOUR_API_KEY' placeholders, please set the environment variables (GNEWS_API_KEY, WORLDNEWS_API_KEY, FMP_API_KEY, AVALAI_API_KEY, TELEGRAM_BOT_TOKEN) on your hosting platform (e.g., Render.com).")

    st.header("Data Sources")
    selected_api = st.selectbox(
        "Select API:",
        ["GNews", "World News API", "CoinGecko (Crypto News)", "Financial Report (FMP)"]
    )

    query = st.text_input(
        f"Enter Query/Symbol for {selected_api}:",
        value="Iran" if selected_api != "Financial Report (FMP)" else "AAPL" # Default query
    )

    max_records = st.slider(
        "Maximum number of records:",
        min_value=1,
        max_value=100,
        value=20,
        step=1
    )

    st.header("Time Filtering")
    time_filter_option = st.radio(
        "Select time range:",
        ["Last Hour", "Last 24 Hours", "Last 7 Days", "Custom Date Range", "Disable Filter"]
    )

    from_date, to_date = None, None
    date_range = None # Initialize date_range to None
    if time_filter_option == "Custom Date Range":
        # Ensure date_input always returns a tuple, even if only one date is selected initially
        date_range_input = st.date_input("Select date range", value=(datetime.now() - timedelta(days=7)).date(), key='date_range')
        if isinstance(date_range_input, tuple) and len(date_range_input) == 2:
            date_range = date_range_input
            from_date = date_range[0].strftime("%Y-%m-%d")
            to_date = date_range[1].strftime("%Y-%m-%d")
        elif isinstance(date_range_input, datetime):
            date_range = (date_range_input, date_range_input) # Treat single date as a range
            from_date = date_range[0].strftime("%Y-%m-%d")
            to_date = date_range[1].strftime("%Y-%m-%d")


        logger.info(f"Custom date range selected: From {from_date} to {to_date}")
    else:
        from_date, to_date = None, None # Reset date range inputs if not in custom mode
        date_range = None


    time_range_hours = {
        "Last Hour": 1,
        "Last 24 Hours": 24,
        "Last 7 Days": 7 * 24,
        "Custom Date Range": float("inf"), # Use infinity to indicate custom date range
        "Disable Filter": None # None indicates no time filter
    }.get(time_filter_option)

    disable_time_filter = (time_filter_option == "Disable Filter")

    st.header("Translation Settings (News Only)")
    enable_translation = st.checkbox("Enable Translation (English to Persian)", value=False)
    num_items_to_translate = st.slider(
        "Number of latest items to translate:",
        min_value=0,
        max_value=max_records,
        value=1,
        step=1,
        disabled=not enable_translation
    )
    avalai_api_url = st.text_input("Avalai API URL", value=AVALAI_API_URL_DEFAULT, disabled=not enable_translation)


    st.header("Telegram Settings")
    chat_ids = load_chat_ids()
    current_chat_id = chat_ids.get("default_chat_id", "")
    telegram_chat_id = st.text_input("Telegram Chat ID (e.g., -1001234567890)", value=current_chat_id)

    # Save chat ID when input changes
    if telegram_chat_id and telegram_chat_id != current_chat_id:
        chat_ids["default_chat_id"] = telegram_chat_id
        save_chat_ids(chat_ids)
        logger.info(f"Saved default Telegram Chat ID: {telegram_chat_id}")


# --- Main Content Area ---

if 'fetched_items' not in st.session_state:
    st.session_state.fetched_items = []

if 'selected_items' not in st.session_state:
    st.session_state.selected_items = []

# Fetch Button
if st.button(f"Fetch from {selected_api}"):
    st.session_state.selected_items = [] # Clear selected items on new fetch
    with st.spinner(f"Fetching data from {selected_api}..."):
        fetched_items = fetch_news(selected_api, query, from_date=from_date, to_date=to_date, max_records=max_records) # Pass dates and max_records to fetch_news

        if selected_api != "Financial Report (FMP)":
            # Apply time filter before translation and display for news
            filtered_items = filter_articles_by_time(fetched_items, time_range_hours, date_range[0] if time_filter_option == "Custom Date Range" and date_range else None, date_range[1] if time_filter_option == "Custom Date Range" and date_range else None, disable_time_filter)
            # Pre-process (translate) filtered news items
            processed_items = pre_process_articles(filtered_items, avalai_api_url, enable_translation, num_items_to_translate)
        else:
            # No time filter or translation for financial reports displayed here, they are filtered by date in fetch_financial_report
            processed_items = fetched_items # Financial reports are already filtered by date in fetch_financial_report if dates are provided

        st.session_state.fetched_items = processed_items # Store processed items
        # Corrected line: Check the length of fetched_items, not a non-existent 'items'
        st.info(f"Found {len(st.session_state.fetched_items)} items in session state!")


# Display fetched items
if st.session_state.fetched_items:
    display_items(st.session_state.fetched_items)

# Send to Telegram Button
if st.session_state.selected_items:
    st.subheader("Send to Telegram")
    if not telegram_chat_id:
        st.warning("Please enter a Telegram Chat ID in the sidebar to send messages.")
    elif st.button(f"Send {len(st.session_state.selected_items)} Selected Item(s) to Telegram"):
        with st.spinner(f"Sending {len(st.session_state.selected_items)} item(s) to Telegram..."):
            all_successful = True
            for item in st.session_state.selected_items:
                if item["type"] == "news":
                    tehran_time = parse_to_tehran_time(item["published_at"])
                    tehran_time_str = format_tehran_time(tehran_time) if tehran_time else item["published_at"]

                    # Consider extracting full content for Telegram message if needed
                    # extracted_content = extract_article_content(item["url"])
                    # message = f"*{item['translated_title']}*\n\nSource: {item['source']} | Published: {tehran_time_str}\n\n{extracted_content}\n\n[Read More]({item['url']})"

                    # Using the translated description and linking to the original article
                    message = f"*{item['translated_title']}*\n\n**منبع:** {item['source']} | **انتشار:** {tehran_time_str}\n\n{item['translated_description']}\n\n[Read More]({item['url']})"

                    # Disable web page preview for news articles to avoid duplicate display in Telegram
                    if not send_telegram_message(telegram_chat_id, message, disable_web_page_preview=True):
                        all_successful = False
                        logger.error(f"Failed to send article: {item['title']}")
                else: # Financial Reports
                    message = f"**گزارش مالی:** {item['symbol']}\n\n**تاریخ گزارش:** {item['date']}\n**ارز گزارش:** {item['reportedCurrency']}\n**درآمد:** {item['revenue']:,} {item['reportedCurrency']}\n**سود خالص:** {item['netIncome']:,} {item['reportedCurrency']}\n**سود هر سهم (EPS):** {item['eps']}\n**سود ناخالص:** {item['grossProfit']:,} {item['reportedCurrency']}\n**درآمد عملیاتی:** {item['operatingIncome']:,} {item['reportedCurrency']}"

                    if not send_telegram_message(telegram_chat_id, message):
                        all_successful = False
                        logger.error(f"Failed to send report for symbol: {item['symbol']}")

                time.sleep(0.5) # Add a small delay between sending messages

        if all_successful:
            st.success("Selected item(s) sent to Telegram successfully!")
            # Optional: Clear selected items after sending
            # st.session_state.selected_items = []
            # st.rerun() # Rerun to update the UI and remove checkboxes
        else:
            st.error("Some items failed to send to Telegram.")

# Download Button
if st.session_state.fetched_items:
    st.subheader("Download Data")
    download_format = st.selectbox("Select download format:", ["csv", "json"])
    download_data = save_items_to_file_for_download(st.session_state.fetched_items, download_format)
    if download_data is not None: # Check if download_data is not None
        file_extension = download_format
        mime_type = "text/csv" if download_format == "csv" else "application/json"
        st.download_button(
            label=f"Download Data as .{file_extension}",
            data=download_data,
            file_name=f"iran_news_and_reports.{file_extension}",
            mime=mime_type,
        )
    else:
        st.info("No data available to download.")


# Optional: Clear Fetched Items Button
if st.session_state.fetched_items or st.session_state.selected_items:
    if st.button("Clear All Fetched and Selected Items"):
        st.session_state.fetched_items = []
        st.session_state.selected_items = []
        # Optional: Clear the temporary file
        # if os.path.exists(TEMP_FILE):
        #     os.remove(TEMP_FILE)
        st.success("Cleared all fetched and selected items.")
        st.rerun() # Rerun to update the UI


# Optional: Info about the app
st.markdown("---")
st.info("This app aggregates news and financial reports using various APIs. News articles can be translated to Persian and sent to a specified Telegram chat.")

st.markdown("Developed by [Your Name/Contact Info or GitHub Link]") # Replace with actual info
