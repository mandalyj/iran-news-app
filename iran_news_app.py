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
from bs4 import BeautifulSoup  # For extracting article content

# Set up logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# In-memory log storage for displaying in UI
log_stream = []
class LogHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        log_stream.append(log_entry)

log_handler = LogHandler()
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(log_handler)

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
CURRENTSAPI_API_URL = "https://api.currentsapi.services/v1/search"
CURRENTSAPI_API_KEY = os.environ.get("CURRENTSAPI_API_KEY", "YOUR_CURRENTSAPI_API_KEY")

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
                data = json.load(f)
                logger.info(f"Loaded {len(data)} articles from file {TEMP_FILE}")
                return data
        logger.info(f"No file found at {TEMP_FILE}, returning empty list")
        return []
    except Exception as e:
        logger.error(f"Failed to load articles from file {TEMP_FILE}: {str(e)}")
        send_error_email(f"Failed to load articles from file: {str(e)}")
        return []

# Save articles/reports to temp file
def save_articles_to_file(articles):
    try:
        with open(TEMP_FILE, "w") as f:
            json.dump(articles, f)
        logger.info(f"Saved {len(articles)} articles to file {TEMP_FILE}")
    except Exception as e:
        logger.error(f"Failed to save articles to file {TEMP_FILE}: {str(e)}")
        send_error_email(f"Failed to save articles to file: {str(e)}")

# Load chat IDs from file
def load_chat_ids():
    try:
        if os.path.exists(CHAT_IDS_FILE):
            with open(CHAT_IDS_FILE, "r") as f:
                data = json.load(f)
                logger.info(f"Loaded chat IDs from file {CHAT_IDS_FILE}: {data}")
                return data
        logger.info(f"No chat IDs file found at {CHAT_IDS_FILE}, returning empty dict")
        return {}
    except Exception as e:
        logger.error(f"Failed to load chat IDs from file {CHAT_IDS_FILE}: {str(e)}")
        send_error_email(f"Failed to load chat IDs from file: {str(e)}")
        return {}

# Save chat IDs to file
def save_chat_ids(chat_ids):
    try:
        with open(CHAT_IDS_FILE, "w") as f:
            json.dump(chat_ids, f)
        logger.info(f"Saved chat IDs to file {CHAT_IDS_FILE}: {chat_ids}")
    except Exception as e:
        logger.error(f"Failed to save chat IDs to file {CHAT_IDS_FILE}: {str(e)}")
        send_error_email(f"Failed to save chat IDs to file: {str(e)}")

# Fetch news from GNews API
def fetch_gnews(query="Iran", max_records=20, from_date=None, to_date=None):
    if not GNEWS_API_KEY or GNEWS_API_KEY == "YOUR_GNEWS_API_KEY":
        error_msg = "Invalid GNews API key. Please set a valid API key in Render environment variables."
        logger.error(error_msg)
        send_error_email(error_msg)
        st.error(error_msg)
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
            st.error(error_msg)
            return [], error_msg
            
        articles = data.get("articles", [])
        if not articles:
            error_msg = f"No articles found for query '{query}' in GNews."
            logger.warning(error_msg)
            st.warning(error_msg)
            return [], error_msg
            
        formatted_articles = [
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
        ]
        logger.info(f"Fetched {len(formatted_articles)} articles from GNews")
        return formatted_articles, None
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to fetch news from GNews: {str(e)}"
        logger.error(error_msg)
        send_error_email(error_msg)
        st.error(error_msg)
        return [], error_msg
    except Exception as e:
        error_msg = f"Unexpected error while fetching news from GNews: {str(e)}"
        logger.error(error_msg)
        send_error_email(error_msg)
        st.error(error_msg)
        return [], error_msg

# Fetch news from World News API
def fetch_worldnews(query="Iran", max_records=20, from_date=None, to_date=None):
    if not WORLDNEWS_API_KEY or WORLDNEWS_API_KEY == "YOUR_WORLDNEWS_API_KEY":
        error_msg = "Invalid World News API key. Please set a valid API key in Render environment variables."
        logger.error(error_msg)
        send_error_email(error_msg)
        st.error(error_msg)
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
            st.error(error_msg)
            return [], error_msg
            
        articles = data.get("news", [])
        if not articles:
            error_msg = f"No articles found for query '{query}' in World News API."
            logger.warning(error_msg)
            st.warning(error_msg)
            return [], error_msg
            
        formatted_articles = [
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
        ]
        logger.info(f"Fetched {len(formatted_articles)} articles from World News API")
        return formatted_articles, None
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to fetch news from World News API: {str(e)}"
        logger.error(error_msg)
        send_error_email(error_msg)
        st.error(error_msg)
        return [], error_msg
    except Exception as e:
        error_msg = f"Unexpected error while fetching news from World News API: {str(e)}"
        logger.error(error_msg)
        send_error_email(error_msg)
        st.error(error_msg)
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
                st.warning(error_msg)
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
                    if not (start_datetime <= article_date <= end_datetime):
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
            
            logger.info(f"Fetched {len(formatted_articles)} articles from CoinGecko")
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
                    st.error(error_msg)
                    return [], error_msg
            else:
                error_msg = f"Failed to fetch news from CoinGecko: {str(e)}"
                logger.error(error_msg)
                send_error_email(error_msg)
                st.error(error_msg)
                return [], error_msg
        except Exception as e:
            error_msg = f"Unexpected error while fetching news from CoinGecko: {str(e)}"
            logger.error(error_msg)
            send_error_email(error_msg)
            st.error(error_msg)
            return [], error_msg

# Fetch financial report from Financial Modeling Prep API
def fetch_financial_report(symbol, max_records=1, from_date=None, to_date=None):
    if not FMP_API_KEY or FMP_API_KEY == "YOUR_FMP_API_KEY":
        error_msg = "Invalid Financial Modeling Prep API key. Please set a valid API key in Render environment variables."
        logger.error(error_msg)
        send_error_email(error_msg)
        st.error(error_msg)
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
            st.error(error_msg)
            return [], error_msg
            
        if not data:
            error_msg = f"No financial reports found for symbol '{symbol}'. Please check the symbol and try again."
            logger.warning(error_msg)
            st.warning(error_msg)
            return [], error_msg
            
        reports = []
        for report in data:
            report_date = report.get("date", "")
            if from_date and to_date:
                try:
                    report_datetime = datetime.strptime(report_date, "%Y-%m-%d")
                    start_datetime = datetime.strptime(from_date, "%Y-%m-%d")
                    end_datetime = datetime.strptime(to_date, "%Y-%m-%d")
                    if not (start_datetime <= report_datetime <= end_datetime):
                        continue
                except ValueError as e:
                    logger.warning(f"Invalid date format in report: {report_date}, error: {str(e)}")
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
        
        logger.info(f"Fetched {len(reports)} financial reports for symbol {symbol}")
        return reports, None
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to fetch financial report from FMP: {str(e)}"
        logger.error(error_msg)
        send_error_email(error_msg)
        st.error(error_msg)
        return [], error_msg
    except Exception as e:
        error_msg = f"Unexpected error while fetching financial report from FMP: {str(e)}"
        logger.error(error_msg)
        send_error_email(error_msg)
        st.error(error_msg)
        return [], error_msg

# Fetch news from CurrentsAPI
def fetch_currentsapi_news(query="Iran", max_records=20, from_date=None, to_date=None):
    if not CURRENTSAPI_API_KEY or CURRENTSAPI_API_KEY == "YOUR_CURRENTSAPI_API_KEY":
        error_msg = "Invalid CurrentsAPI key. Please set a valid API key in Render environment variables."
        logger.error(error_msg)
        send_error_email(error_msg)
        st.error(error_msg)
        return [], error_msg
    
    params = {
        "keywords": query,
        "apiKey": CURRENTSAPI_API_KEY,
        "language": "en",
        "limit": min(max_records, 100)
    }
    if from_date:
        params["start_date"] = from_date
    if to_date:
        params["end_date"] = to_date
    
    headers = {
        "User-Agent": f"IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)"
    }
    logger.info(f"Sending CurrentsAPI request with params: {params}")
    
    try:
        response = requests.get(CURRENTSAPI_API_URL, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        logger.info(f"CurrentsAPI response: {data}")
        
        if "status" in data and data["status"] == "error":
            error_msg = f"CurrentsAPI error: {data.get('message', 'Unknown error')}"
            logger.error(error_msg)
            send_error_email(error_msg)
            st.error(error_msg)
            return [], error_msg
            
        news = data.get("news", [])
        if not news:
            error_msg = f"No articles found for query '{query}' in CurrentsAPI."
            logger.warning(error_msg)
            st.warning(error_msg)
            return [], error_msg
            
        formatted_articles = [
            {
                "title": article.get("title", "No title"),
                "url": article.get("url", ""),
                "source": article.get("source", {}).get("name", "Unknown Source"),
                "published_at": article.get("published", ""),
                "description": article.get("description", "") or "No description available",
                "image_url": article.get("image", ""),
                "translated_title": "",
                "translated_description": "",
                "type": "news"
            }
            for article in news
        ]
        logger.info(f"Fetched {len(formatted_articles)} articles from CurrentsAPI")
        return formatted_articles, None
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to fetch news from CurrentsAPI: {str(e)}"
        logger.error(error_msg)
        send_error_email(error_msg)
        st.error(error_msg)
        return [], error_msg
    except Exception as e:
        error_msg = f"Unexpected error while fetching news from CurrentsAPI: {str(e)}"
        logger.error(error_msg)
        send_error_email(error_msg)
        st.error(error_msg)
        return [], error_msg

# Fetch news or reports from the selected API
def fetch_news(selected_api, query="Iran", max_records=20, from_date=None, to_date=None):
    try:
        st.write(f"Starting fetch process from {selected_api}...")
        logger.info(f"Fetching from {selected_api} for query: {query}, max_records: {max_records}, from_date: {from_date}, to_date: {to_date}")
        
        all_items = []
        errors = []
        
        api_functions = {
            "GNews": fetch_gnews,
            "World News API": fetch_worldnews,
            "CoinGecko (Crypto News)": fetch_coingecko_news,
            "Financial Report (FMP)": fetch_financial_report,
            "CurrentsAPI": fetch_currentsapi_news
        }
        
        fetch_function = api_functions.get(selected_api)
        if not fetch_function:
            error_msg = f"Invalid API selected: {selected_api}"
            logger.error(error_msg)
            st.error(error_msg)
            return []
        
        fetch_query = query if selected_api != "Financial Report (FMP)" else query.upper()
        result = fetch_function(fetch_query, max_records, from_date, to_date)
        
        # Ensure the result is a tuple (items, error)
        if not isinstance(result, tuple) or len(result) != 2:
            error_msg = f"Unexpected return format from {selected_api}: {result}"
            logger.error(error_msg)
            st.error(error_msg)
            return []
        
        items, error = result
        logger.info(f"Raw fetch result from {selected_api}: items={items}, error={error}")
        
        if not isinstance(items, list):
            error_msg = f"Fetch function {selected_api} did not return a list: {items}"
            logger.error(error_msg)
            st.error(error_msg)
            return []
        
        st.write(f"Fetched {len(items)} items from {selected_api}")
        logger.info(f"Fetched {len(items)} items from {selected_api}")
        if items:
            all_items.extend(items)
        if error:
            errors.append(f"{selected_api}: {error}")
        
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
    except Exception as e:
        error_msg = f"Unexpected error in fetch_news: {str(e)}"
        logger.error(error_msg)
        st.error(error_msg)
        send_error_email(error_msg)
        return []

# Function to translate text using Avalai API with /chat/completions
def translate_with_avalai(text, source_lang="en", target_lang="fa", avalai_api_url=AVALAI_API_URL_DEFAULT):
    if not text:
        logger.warning("Empty text provided for translation")
        return text
    
    if not AVALAI_API_KEY or AVALAI_API_KEY == "YOUR_AVALAI_API_KEY":
        error_msg = "Invalid Avalai API key. Please set a valid API key in Render environment variables."
        logger.error(error_msg)
        send_error_email(error_msg)
        st.error(error_msg)
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
            logger.info(f"Translated text: {translated_text}")
            return translated_text
        else:
            error_msg = f"Avalai API response missing choices: {data}"
            logger.warning(error_msg)
            send_error_email(error_msg)
            st.warning(error_msg)
            return text
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to translate with Avalai: {str(e)}"
        logger.error(error_msg)
        send_error_email(error_msg)
        st.error(error_msg)
        return text
    except Exception as e:
        error_msg = f"Unexpected error while translating with Avalai: {str(e)}"
        logger.error(error_msg)
        send_error_email(error_msg)
        st.error(error_msg)
        return text

# Function to convert UTC time to Tehran time and return as datetime object
def parse_to_tehran_time(utc_time_str):
    if not utc_time_str:
        logger.warning("Empty time string provided")
        return None
    
    time_formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d"  # For financial reports (just date)
    ]
    
    for time_format in time_formats:
        try:
            utc_time = datetime.strptime(utc_time_str, time_format)
            tehran_time = utc_time + timedelta(hours=3, minutes=30)
            logger.info(f"Successfully parsed time: {utc_time_str} -> {tehran_time}")
            return tehran_time
        except ValueError:
            continue
    
    error_msg = f"Failed to convert time: Invalid format - Input: {utc_time_str}"
    logger.warning(error_msg)
    send_error_email(error_msg)
    return None

# Function to format Tehran time for display
def format_tehran_time(tehran_time):
    return tehran_time.strftime("%Y/%m/%d - %H:%M")

# Function to truncate text to a specified length
def truncate_text(text, max_length=100):
    try:
        text_str = str(text)
        if len(text_str) > max_length:
            return text_str[:max_length].rsplit(" ", 1)[0] + "..."
        return text_str
    except Exception as e:
        logger.error(f"Failed to truncate text: {str(e)}")
        return str(text)

# Function to extract article content for Instant View
def extract_article_content(url):
    try:
        headers = {
            "User-Agent": f"IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        paragraphs = soup.find_all('p')
        content = " ".join([para.get_text(strip=True) for para in paragraphs if para.get_text(strip=True)])
        
        if not content:
            logger.warning(f"No content extracted from URL: {url}")
            return "No content available."
        
        content = truncate_text(content, max_length=500)
        logger.info(f"Extracted content (length: {len(content)}): {content}")
        return content
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to extract content from {url}: {str(e)}"
        logger.error(error_msg)
        send_error_email(error_msg)
        return "Unable to extract content."
    except Exception as e:
        error_msg = f"Unexpected error while extracting content from {url}: {str(e)}"
        logger.error(error_msg)
        send_error_email(error_msg)
        return "Unable to extract content."

# Function to filter items by time range (for news only)
def filter_articles_by_time(items, time_range_hours, start_date=None, end_date=None, disable_filter=False):
    if not items or not isinstance(items, list):
        logger.info("No items or invalid items to filter")
        return []
    
    if items and items[0].get("type") == "report":
        logger.info("Skipping time filter for financial reports")
        return items
    
    if disable_filter:
        logger.info("Time filter disabled. Returning all articles.")
        return items
    
    filtered_items = []
    current_utc_time = datetime.utcnow()
    current_tehran_time = current_utc_time + timedelta(hours=3, minutes=30)
    
    try:
        if time_range_hours == float("inf"):
            start_datetime = datetime.combine(start_date, datetime.min.time()) + timedelta(hours=3, minutes=30)
            end_datetime = datetime.combine(end_date, datetime.max.time()) + timedelta(hours=3, minutes=30)
            
            for item in items:
                published_time = parse_to_tehran_time(item["published_at"])
                if published_time:
                    logger.info(f"Article time: {published_time}, Start: {start_datetime}, End: {end_datetime}")
                    if start_datetime <= published_time <= end_datetime:
                        filtered_items.append(item)
                else:
                    logger.warning(f"Skipping article due to unparseable time: {item['published_at']}")
        else:
            cutoff_time = current_tehran_time - timedelta(hours=time_range_hours)
            for item in items:
                published_time = parse_to_tehran_time(item["published_at"])
                if published_time:
                    logger.info(f"Article time: {published_time}, Cutoff: {cutoff_time}")
                    if published_time >= cutoff_time:
                        filtered_items.append(item)
                else:
                    logger.warning(f"Skipping article due to unparseable time: {item['published_at']}")
        
        logger.info(f"After filtering: {len(filtered_items)} items remain out of {len(items)}")
        return filtered_items
    except Exception as e:
        error_msg = f"Unexpected error while filtering articles: {str(e)}"
        logger.error(error_msg)
        st.error(error_msg)
        return items

# Function to pre-process articles (translations only, skip for reports)
def pre_process_articles(items, avalai_api_url, enable_translation=False, num_items_to_translate=1):
    if not items or not isinstance(items, list):
        logger.info("No items or invalid items to preprocess")
        return []
    
    if items and items[0].get("type") == "report":
        logger.info("Skipping translation for financial reports")
        return items
    
    try:
        sorted_items = sorted(
            items,
            key=lambda x: parse_to_tehran_time(x["published_at"]) or datetime.min,
            reverse=True
        )
        logger.info(f"Sorted {len(sorted_items)} items for translation processing")
        
        for i, item in enumerate(sorted_items):
            try:
                if enable_translation and i < num_items_to_translate:
                    logger.info(f"Translating item {i+1}: {item['title']}")
                    translated_title = translate_with_avalai(item["title"], source_lang="en", target_lang="fa", avalai_api_url=avalai_api_url)
                    logger.info(f"Translated title for item {i+1}: {translated_title}")
                    item["translated_title"] = translated_title
                    
                    translated_description = translate_with_avalai(item["description"], source_lang="en", target_lang="fa", avalai_api_url=avalai_api_url)
                    logger.info(f"Translated description for item {i+1}: {translated_description}")
                    item["translated_description"] = translated_description
                    
                    if translated_description == item["description"]:
                        st.warning(f"Translation failed for description of item {i+1}: {item['title']}")
                        logger.warning(f"Translation failed for description of item {i+1}: {item['title']}")
                else:
                    item["translated_title"] = item["title"]
                    item["translated_description"] = item["description"]
                    if enable_translation and i >= num_items_to_translate:
                        logger.info(f"Skipping translation for item {i+1}: {item['title']} (beyond limit of {num_items_to_translate})")
                        st.info(f"Item {i+1} ({item['title']}) skipped for translation (beyond limit of {num_items_to_translate})")
            except Exception as e:
                error_msg = f"Failed to process item {item['title']}: {str(e)}"
                st.error(error_msg)
                logger.error(error_msg)
                send_error_email(error_msg)
        return sorted_items
    except Exception as e:
        error_msg = f"Unexpected error in pre_process_articles: {str(e)}"
        logger.error(error_msg)
        st.error(error_msg)
        return items

# Function to display items (news or reports) in a nice format
def display_items(items):
    try:
        if not items or not isinstance(items, list):
            st.warning("No items to display or invalid items format.")
            logger.warning("No items or invalid items format to display")
            return
        
        st.write(f"Attempting to display {len(items)} items...")
        logger.info(f"Displaying {len(items)} items: {items}")
        
        item_type = items[0].get("type", "news") if items else "news"
        
        if item_type == "news":
            sorted_items = sorted(
                items,
                key=lambda x: parse_to_tehran_time(x["published_at"]) or datetime.min,
                reverse=True
            )
            logger.info(f"Sorted articles: {len(sorted_items)} articles after sorting")
            
            st.subheader("News Statistics")
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
            
            st.subheader("Selected Articles")
            selected_count = len(st.session_state.selected_items)
            st.write(f"You have selected {selected_count} article(s) to send to Telegram")
            logger.info(f"Current selected items: {st.session_state.selected_items}")
            
            st.subheader("News Articles")
            col1, col2 = st.columns(2)
            for i, item in enumerate(sorted_items):
                current_col = col1 if i % 2 == 0 else col2
                
                with current_col:
                    st.markdown(f'<div class="neon-line-top"></div>', unsafe_allow_html=True)
                    logger.info(f"Rendering article {i+1}: {item['title']}")
                    
                    is_selected = any(a.get('url') == item['url'] for a in st.session_state.selected_items)
                    checkbox_key = f"article_{i}"
                    if st.checkbox("Select for Telegram", key=checkbox_key, value=is_selected):
                        if not is_selected:
                            st.session_state.selected_items.append(item)
                            logger.info(f"Added article to selected: {item['title']}")
                    else:
                        if is_selected:
                            st.session_state.selected_items = [a for a in st.session_state.selected_items if a.get('url') != item['url']]
                            logger.info(f"Removed article from selected: {item['title']}")
                    
                    tehran_time = parse_to_tehran_time(item["published_at"])
                    tehran_time_str = format_tehran_time(tehran_time) if tehran_time else item["published_at"]
                    truncated_description = truncate_text(item["description"], max_length=100)
                    truncated_translated_description = truncate_text(item["translated_description"], max_length=100)
                    
                    st.markdown(f'<div class="article-section">', unsafe_allow_html=True)
                    st.markdown(f'<h3 class="title-link"><a href="{item["url"]}" target="_blank">{item["translated_title"]}</a></h3>', unsafe_allow_html=True)
                    st.markdown(f'<div class="source-date">**Source:** {item["source"]} | **انتشار:** {tehran_time_str}</div>', unsafe_allow_html=True)
                    if item["image_url"]:
                        try:
                            st.image(item["image_url"], width=300)
                        except Exception as e:
                            logger.warning(f"Failed to load image for article {item['title']}: {str(e)}")
                            st.info("Image could not be loaded")
                    st.markdown(f'<div class="english-text description">**Description (English):** {truncated_description}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="persian-text description">**توضیحات (فارسی):** {truncated_translated_description}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
        else:
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
    except Exception as e:
        error_msg = f"Failed to display items: {str(e)}"
        logger.error(error_msg)
        st.error(error_msg)
        send_error_email(error_msg)

# Function to save items to a file for download
def save_items_to_file_for_download(items, format="csv"):
    try:
        if not items or not isinstance(items, list):
            logger.info("No items or invalid items to save for download")
            return None
        df = pd.DataFrame(items)
        if format == "csv":
            buffer = BytesIO()
            df.to_csv(buffer, index=False)
            return buffer.getvalue()
        elif format == "json":
            return json.dumps(items, indent=2)
        return None
    except Exception as e:
        logger.error(f"Failed to save items for download: {str(e)}")
        return None

# Function to send a message to Telegram (include title, description, time, and Instant View for news; financial data for reports)
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
            logger.info(f"Telegram message sent successfully to chat_id {chat_id}")
            return True, "Message sent successfully"
        error_msg = f"Error: {result.get('description', 'Unknown error')}"
        logger.error(error_msg)
        return False, error_msg
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to send message to Telegram: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error while sending message to Telegram: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

# Function to get Chat ID from Telegram username
def get_chat_id_from_username(username, chat_ids):
    try:
        if not username.startswith("@"):
            error_msg = "Username must start with @ (e.g., @username)"
            logger.error(error_msg)
            return None, error_msg
        
        username = username[1:].lower()
        
        if username in chat_ids:
            logger.info(f"Found chat_id for username @{username}: {chat_ids[username]}")
            return chat_ids[username], None
        
        url = f"{TELEGRAM_API_URL}/getUpdates"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("ok"):
            error_msg = "Failed to fetch updates from Telegram"
            logger.error(error_msg)
            return None, error_msg
        
        for update in data.get("result", []):
            if "message" in update and "chat" in update["message"]:
                chat = update["message"]["chat"]
                if chat.get("username", "").lower() == username:
                    chat_id = chat["id"]
                    chat_ids[username] = chat_id
                    save_chat_ids(chat_ids)
                    logger.info(f"Resolved chat_id for username @{username}: {chat_id}")
                    return chat_id, None
                if chat.get("type") == "group" or chat.get("type") == "supergroup":
                    if chat.get("title", "").lower().find(username.lower()) != -1:
                        chat_id = chat["id"]
                        chat_ids[username] = chat_id
                        save_chat_ids(chat_ids)
                        logger.info(f"Resolved chat_id for group @{username}: {chat_id}")
                        return chat_id, None
        
        error_msg = f"Chat ID not found for username @{username}. Make sure the user/group has interacted with the bot."
        logger.warning(error_msg)
        return None, error_msg
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to fetch Chat ID for username {username}: {str(e)}"
        logger.error(error_msg)
        send_error_email(error_msg)
        return None, error_msg
    except Exception as e:
        error_msg = f"Unexpected error while fetching Chat ID for username {username}: {str(e)}"
        logger.error(error_msg)
        send_error_email(error_msg)
        return None, error_msg

# Main Streamlit app
def main():
    try:
        st.title("Iran News Aggregator")
        
        # Initialize session state variables
        if 'selected_items' not in st.session_state:
            st.session_state.selected_items = []
        if 'items' not in st.session_state or not isinstance(st.session_state.items, list):
            st.session_state.items = load_articles_from_file()
        if 'chat_ids' not in st.session_state:
            st.session_state.chat_ids = load_chat_ids()
        if 'avalai_api_url' not in st.session_state:
            st.session_state.avalai_api_url = AVALAI_API_URL_DEFAULT
        
        # Ensure items is always a list
        if not isinstance(st.session_state.items, list):
            logger.warning("st.session_state.items is not a list, resetting to empty list")
            st.session_state.items = []
        
        logger.info(f"Session state items at start: {st.session_state.items}")
        if not st.session_state.items:
            st.info("No items in session state. Please search for news/reports or check if data was loaded from file.")
            logger.info("No items in session state at start.")
        else:
            st.info(f"Found {len(st.session_state.items)} items in session state.")
            logger.info(f"Found {len(st.session_state.items)} items in session state at start.")
        
        with st.sidebar:
            st.header("Query Settings")
            query = st.text_input("Search Query (or Company Symbol for Financial Report)", value="Iran", key="search_query").strip()
            today = datetime(2025, 5, 15)
            default_start_date = today - timedelta(days=7)
            start_date = st.date_input("Start Date", value=default_start_date, min_value=today - timedelta(days=30), max_value=today, key="start_date")
            end_date = st.date_input("End Date", value=today, min_value=start_date, max_value=today, key="end_date")
            max_items = st.slider(label="Maximum number of items", min_value=1, max_value=100, value=20, key="max_items")
            
            api_options = ["GNews", "World News API", "CoinGecko (Crypto News)", "Financial Report (FMP)", "CurrentsAPI"]
            selected_api = st.selectbox("Select API", options=api_options, index=0, key="selected_api")
            
            time_range_options = {
                "Last 30 minutes": 0.5,
                "Last 1 hour": 1,
                "Last 4 hours": 4,
                "Last 12 hours": 12,
                "Last 24 hours": 24,
                "All articles": float("inf")
            }
            selected_time_range = st.selectbox("Time Range (for News)", options=list(time_range_options.keys()), index=4, key="time_range")
            time_range_hours = time_range_options[selected_time_range]
            
            disable_time_filter = st.checkbox("Disable Time Filter (Show All Articles)", value=False, key="disable_time_filter")
            
            st.header("Translation Settings (for News)")
            avalai_api_url_options = ["https://api.avalai.ir/v1", "https://api.avalapis.ir/v1"]
            st.session_state.avalai_api_url = st.selectbox(
                "Avalai API URL",
                options=avalai_api_url_options,
                index=avalai_api_url_options.index(st.session_state.avalai_api_url),
                help="Choose the Avalai API URL. Use https://api.avalai.ir/v1 for global access, or https://api.avalapis.ir/v1 for better performance inside Iran (only accessible from Iran)."
            )
            
            enable_translation = st.checkbox("Enable Translation (May cause 403 error)", value=False, key="enable_translation")
            
            num_items_to_translate = 1
            if enable_translation:
                num_items_to_translate = st.slider(
                    label="Number of articles to translate (newest first)",
                    min_value=1,
                    max_value=max_items,
                    value=1,
                    key="num_items_to_translate"
                )
            
            search_button = st.button("Search for News/Report")
            clear_button = st.button("Clear Results")
            
            st.header("Telegram Settings")
            telegram_chat_id = st.text_input("Telegram Chat ID", value="5013104607", key="telegram_chat_id")
            telegram_user_or_group_id = st.text_input("Send to User/Group", value="", key="telegram_user_or_group_id", help="Enter the @username or @groupname to send selected items to (leave blank to use default Chat ID)")
            
            bot_username = "YourBotUsername"
            st.markdown(f"[Start a chat with the bot](https://t.me/{bot_username}) to allow sending messages.", unsafe_allow_html=True)
            
            if st.session_state.chat_ids:
                st.subheader("Known Users/Groups")
                for username, chat_id in st.session_state.chat_ids.items():
                    st.write(f"@{username}: {chat_id}")
            
            st.header("Download Options")
            download_format = st.selectbox("Download Format", ["CSV", "JSON"], key="download_format")
        
        if clear_button:
            st.session_state.items = []
            st.session_state.selected_items = []
            if os.path.exists(TEMP_FILE):
                os.remove(TEMP_FILE)
            logger.info("Cleared session state and removed temp file")
            st.experimental_rerun()

        if search_button:
            with st.spinner(f"Searching for items using {selected_api}..."):
                logger.info(f"Search button clicked. Query: {query}, API: {selected_api}, Start Date: {start_date}, End Date: {end_date}, Max Items: {max_items}")
                from_date = start_date.strftime("%Y-%m-%d")
                to_date = end_date.strftime("%Y-%m-%d")
                fetch_query = "cryptocurrency" if selected_api == "CoinGecko (Crypto News)" else query
                items = fetch_news(selected_api, query=fetch_query, max_records=max_items, from_date=from_date, to_date=to_date)
                
                logger.info(f"Items returned from fetch_news: {items}, Type: {type(items)}")
                
                if not isinstance(items, list):
                    logger.error(f"fetch_news did not return a list: {items}")
                    st.error(f"Failed to fetch items: fetch_news did not return a list, got {type(items)} instead.")
                    items = []
                
                if items:
                    logger.info(f"Before filtering: {len(items)} items")
                    filtered_items = filter_articles_by_time(items, time_range_hours, start_date, end_date, disable_filter=disable_time_filter)
                    if not filtered_items and selected_api != "Financial Report (FMP)":
                        if time_range_hours != float("inf"):
                            st.warning(f"مقاله‌ای در {selected_time_range} گذشته پیدا نشد. لطفاً بازه زمانی را تغییر دهید یا فیلتر زمانی را غیرفعال کنید.")
                        else:
                            st.warning(f"No articles found within the selected date range ({start_date} to {end_date}). Try adjusting the date range or disabling the time filter.")
                    else:
                        items = filtered_items
                    logger.info(f"After filtering: {len(items)} items")
                    items = pre_process_articles(items, st.session_state.avalai_api_url, enable_translation=enable_translation, num_items_to_translate=num_items_to_translate)
                    logger.info(f"After preprocessing: {len(items)} items")
                    st.session_state.items = items
                    save_articles_to_file(items)
                    st.session_state.selected_items = []
                    st.success("Items fetched successfully!")
                else:
                    st.warning(f"No items fetched from {selected_api}. Check the error messages above or try a different query or API.")
                    logger.warning(f"No items fetched after fetch_news call from {selected_api}.")
                    st.session_state.items = []
        
        if st.session_state.items and isinstance(st.session_state.items, list):
            st.write(f"Found {len(st.session_state.items)} items in session state. Displaying now...")
            display_items(st.session_state.items)
        else:
            st.info("No items to display in session state.")
            logger.info("No items to display in session state after search.")

        with st.sidebar:
            st.header("Telegram Actions")
            if st.button("Reset Selection"):
                st.session_state.selected_items = []
                st.success("Selection reset successfully!")
                logger.info("Selection reset by user.")
            
            if st.button("Send Selected Items to Telegram", disabled=len(st.session_state.selected_items) == 0):
                with st.spinner("Sending to Telegram..."):
                    success_count = 0
                    fail_count = 0
                    target_chat_id = telegram_user_or_group_id if telegram_user_or_group_id else telegram_chat_id
                    
                    if target_chat_id.startswith("@"):
                        chat_id, error = get_chat_id_from_username(target_chat_id, st.session_state.chat_ids)
                        if chat_id is None:
                            st.error(f"Failed to resolve username: {error}")
                            fail_count = len(st.session_state.selected_items)
                        else:
                            target_chat_id = chat_id
                    
                    st.info(f"Sending to Chat ID: {target_chat_id}")
                    logger.info(f"Sending {len(st.session_state.selected_items)} items to {target_chat_id}")
                    
                    for item in st.session_state.selected_items:
                        try:
                            if item.get("type") == "news":
                                tehran_time = parse_to_tehran_time(item["published_at"])
                                tehran_time_str = format_tehran_time(tehran_time) if tehran_time else item["published_at"]
                                
                                final_title = item["translated_title"] or item["title"]
                                final_description = item["translated_description"] or item["description"]
                                
                                if not final_title or final_title == item["title"]:
                                    final_title = translate_with_avalai(item["title"], source_lang="en", target_lang="fa", avalai_api_url=st.session_state.avalai_api_url)
                                    logger.info(f"Translated title for Telegram: {final_title}")
                                    item["translated_title"] = final_title
                                
                                if not final_description or final_description == item["description"]:
                                    final_description = translate_with_avalai(item["description"], source_lang="en", target_lang="fa", avalai_api_url=st.session_state.avalai_api_url)
                                    logger.info(f"Translated description for Telegram: {final_description}")
                                    item["translated_description"] = final_description
                                
                                truncated_description = truncate_text(final_description, max_length=100)
                                article_content = extract_article_content(item["url"])
                                translated_content = translate_with_avalai(article_content, source_lang="en", target_lang="fa", avalai_api_url=st.session_state.avalai_api_url)
                                logger.info(f"Translated Instant View content (length: {len(translated_content)}): {translated_content}")
                                
                                message = (
                                    f"*{final_title}*\n\n"
                                    f"{truncated_description}\n\n"
                                    f"**زمان انتشار:** {tehran_time_str}\n\n"
                                    f"**پیش‌نمایش مقاله (Instant View):**\n{translated_content}\n\n"
                                    f"[ادامه مطلب]({item['url']})"
                                )
                            else:
                                message = (
                                    f"**گزارش مالی شرکت {item['symbol']}**\n\n"
                                    f"**تاریخ گزارش:** {item['date']}\n"
                                    f"**ارز گزارش:** {item['reportedCurrency']}\n"
                                    f"**درآمد:** {item['revenue']:,} {item['reportedCurrency']}\n"
                                    f"**سود خالص:** {item['netIncome']:,} {item['reportedCurrency']}\n"
                                    f"**سود هر سهم (EPS):** {item['eps']}\n"
                                    f"**سود ناخالص:** {item['grossProfit']:,} {item['reportedCurrency']}\n"
                                    f"**درآمد عملیاتی:** {item['operatingIncome']:,} {item['reportedCurrency']}"
                                )
                            
                            logger.info(f"Sending message (length: {len(message)}): {message}")
                            success, result = send_telegram_message(target_chat_id, message, disable_web_page_preview=(item.get("type") != "news"))
                            if success:
                                success_count += 1
                            else:
                                fail_count += 1
                                st.error(f"Failed to send to {target_chat_id}: {item.get('title', item.get('symbol'))} - {result}")
                            time.sleep(1)
                        except Exception as e:
                            fail_count += 1
                            st.error(f"Error sending item to Telegram: {str(e)}")
                            logger.error(f"Error sending item to Telegram: {str(e)}")
                    if success_count > 0:
                        st.success(f"Successfully sent {success_count} item(s) to Telegram")
                    if fail_count > 0:
                        st.warning(f"Failed to send {fail_count} item(s) to Telegram")
            else:
                st.info(f"Select {len(st.session_state.selected_items)} item(s) to send to Telegram")
                logger.info(f"No items selected for sending. Current count: {len(st.session_state.selected_items)}")

        if st.session_state.items and isinstance(st.session_state.items, list):
            with st.sidebar:
                st.header("Download Options")
                if download_format == "CSV":
                    csv_data = save_items_to_file_for_download(st.session_state.items, format="csv")
                    st.download_button(
                        label="Download as CSV",
                        data=csv_data if csv_data else b"",
                        file_name=f"iran_news_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
                else:
                    json_data = save_items_to_file_for_download(st.session_state.items, format="json")
                    st.download_button(
                        label="Download as JSON",
                        data=json_data if json_data else b"",
                        file_name=f"iran_news_{datetime.now().strftime('%Y%m%d')}.json",
                        mime="application/json"
                    )

        # Display logs in sidebar
        st.sidebar.header("Recent Logs")
        for log in log_stream[-10:]:  # Show last 10 logs
            st.sidebar.text(log)
    except Exception as e:
        error_msg = f"Failed in main app: {str(e)}"
        logger.error(error_msg)
        st.error(error_msg)
        send_error_email(error_msg)

if __name__ == "__main__":
    main()
