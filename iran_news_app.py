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
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# In-memory log storage for UI
log_stream = []
class LogHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        log_stream.append(log_entry)

log_handler = LogHandler()
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(log_handler)

# Configuration
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

TEMP_FILE = "/tmp/iran_news_articles.json"
CHAT_IDS_FILE = "/tmp/iran_news_chat_ids.json"

# Streamlit page config
st.set_page_config(page_title="Iran News Aggregator", page_icon="📰", layout="wide")

# Custom CSS
st.markdown(
    """
    <style>
    .persian-text { direction: rtl; text-align: right; font-family: "B Nazanin", "Arial Unicode MS", sans-serif; font-size: 16px !important; }
    .english-text { direction: ltr; text-align: left; font-size: 14px !important; }
    .article-section { margin-bottom: 20px; padding: 0px; background-color: #f9f9f9; }
    .report-section { margin-bottom: 20px; padding: 10px; background-color: #e6f3ff; border-radius: 5px; }
    .neon-line-top { height: 4px; background: linear-gradient(90deg, rgba(255, 0, 0, 0.8), rgba(255, 100, 100, 0.8), rgba(255, 0, 0, 0.8)); box-shadow: 0 0 10px rgba(255, 0, 0, 0.7); margin: 10px 0; }
    .title-link { font-size: 20px !important; font-weight: bold !important; color: #1a73e8 !important; margin-bottom: 2px !important; direction: rtl !important; text-decoration: none !important; font-family: "B Nazanin", sans-serif !important; }
    .source-date { font-size: 14px !important; color: #555 !important; margin-bottom: 10px !important; }
    .description { margin-top: 10px !important; line-height: 1.5 !important; }
    </style>
    """,
    unsafe_allow_html=True
)

def send_error_email(error_message):
    logger.info(f"Error email sending disabled: {error_message}")

def load_articles_from_file():
    try:
        if os.path.exists(TEMP_FILE):
            with open(TEMP_FILE, "r") as f:
                data = json.load(f)
                logger.info(f"Loaded {len(data)} articles from {TEMP_FILE}")
                return data
        return []
    except Exception as e:
        logger.error(f"Failed to load articles: {str(e)}")
        send_error_email(f"Failed to load articles: {str(e)}")
        return []

def save_articles_to_file(articles):
    try:
        with open(TEMP_FILE, "w") as f:
            json.dump(articles, f)
        logger.info(f"Saved {len(articles)} articles to {TEMP_FILE}")
    except Exception as e:
        logger.error(f"Failed to save articles: {str(e)}")
        send_error_email(f"Failed to save articles: {str(e)}")

def load_chat_ids():
    try:
        if os.path.exists(CHAT_IDS_FILE):
            with open(CHAT_IDS_FILE, "r") as f:
                data = json.load(f)
                logger.info(f"Loaded chat IDs: {data}")
                return data
        return {}
    except Exception as e:
        logger.error(f"Failed to load chat IDs: {str(e)}")
        send_error_email(f"Failed to load chat IDs: {str(e)}")
        return {}

def save_chat_ids(chat_ids):
    try:
        with open(CHAT_IDS_FILE, "w") as f:
            json.dump(chat_ids, f)
        logger.info(f"Saved chat IDs: {chat_ids}")
    except Exception as e:
        logger.error(f"Failed to save chat IDs: {str(e)}")
        send_error_email(f"Failed to save chat IDs: {str(e)}")

def fetch_gnews(query="Iran", max_records=20, from_date=None, to_date=None):
    if GNEWS_API_KEY == "YOUR_GNEWS_API_KEY":
        logger.error("Invalid GNews API key")
        st.error("Invalid GNews API key")
        return [], "Invalid GNews API key"
    
    params = {
        "q": query, "apikey": GNEWS_API_KEY, "lang": "en", "country": "us",
        "max": min(max_records, 100), "from": from_date, "to": to_date
    }
    headers = {"User-Agent": "IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)"}
    try:
        response = requests.get(GNEWS_API_URL, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        if "errors" in data:
            logger.error(f"GNews API error: {data['errors']}")
            st.error(f"GNews API error: {data['errors']}")
            return [], data['errors']
        articles = data.get("articles", [])
        if not articles:
            logger.warning(f"No articles found for '{query}' in GNews")
            st.warning(f"No articles found for '{query}' in GNews")
            return [], "No articles found"
        formatted_articles = [
            {
                "title": a.get("title", "No title"), "url": a.get("url", ""),
                "source": a.get("source", {}).get("name", "Unknown Source"),
                "published_at": a.get("publishedAt", ""), "description": a.get("description", "") or "No description",
                "image_url": a.get("image", ""), "translated_title": "", "translated_description": "", "type": "news"
            } for a in articles
        ]
        logger.info(f"Fetched {len(formatted_articles)} articles from GNews")
        return formatted_articles, None
    except Exception as e:
        logger.error(f"Failed to fetch from GNews: {str(e)}")
        st.error(f"Failed to fetch from GNews: {str(e)}")
        return [], str(e)

def fetch_worldnews(query="Iran", max_records=20, from_date=None, to_date=None):
    if WORLDNEWS_API_KEY == "YOUR_WORLDNEWS_API_KEY":
        logger.error("Invalid World News API key")
        st.error("Invalid World News API key")
        return [], "Invalid World News API key"
    
    params = {
        "text": query, "api-key": WORLDNEWS_API_KEY, "language": "en",
        "number": min(max_records, 100), "sort": "publish-time", "sort-direction": "DESC",
        "start-date": from_date, "end-date": to_date
    }
    headers = {"User-Agent": "IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)"}
    try:
        response = requests.get(WORLDNEWS_API_URL, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            logger.error(f"World News API error: {data.get('error')}")
            st.error(f"World News API error: {data.get('error')}")
            return [], data.get('error')
        articles = data.get("news", [])
        if not articles:
            logger.warning(f"No articles found for '{query}' in World News API")
            st.warning(f"No articles found for '{query}' in World News API")
            return [], "No articles found"
        formatted_articles = [
            {
                "title": a.get("title", "No title"), "url": a.get("url", ""),
                "source": a.get("source", "Unknown Source"), "published_at": a.get("publish_date", ""),
                "description": a.get("text", "") or "No description", "image_url": a.get("image", ""),
                "translated_title": "", "translated_description": "", "type": "news"
            } for a in articles
        ]
        logger.info(f"Fetched {len(formatted_articles)} articles from World News API")
        return formatted_articles, None
    except Exception as e:
        logger.error(f"Failed to fetch from World News API: {str(e)}")
        st.error(f"Failed to fetch from World News API: {str(e)}")
        return [], str(e)

def fetch_coingecko_news(query="cryptocurrency", max_records=20, from_date=None, to_date=None):
    endpoint = f"{COINGECKO_API_URL}/news"
    headers = {"User-Agent": "IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)"}
    params = {"limit": min(max_records, 100)}
    retries = 3
    delay = 5
    for attempt in range(retries):
        try:
            time.sleep(delay)
            response = requests.get(endpoint, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            articles = data.get("data", [])
            if not articles:
                logger.warning(f"No articles found for '{query}' in CoinGecko")
                st.warning(f"No articles found for '{query}' in CoinGecko")
                return [], "No articles found"
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
                    "title": a.get("title", "No title"), "url": a.get("url", ""),
                    "source": a.get("source", "CoinGecko"), "published_at": published_at,
                    "description": a.get("description", "") or "No description", "image_url": a.get("thumb", ""),
                    "translated_title": "", "translated_description": "", "type": "news"
                })
            logger.info(f"Fetched {len(formatted_articles)} articles from CoinGecko")
            return formatted_articles, None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429 and attempt < retries - 1:
                logger.warning(f"Rate limit exceeded, retrying in {delay} seconds...")
                delay *= 2
                continue
            logger.error(f"Failed to fetch from CoinGecko: {str(e)}")
            st.error(f"Failed to fetch from CoinGecko: {str(e)}")
            return [], str(e)
        except Exception as e:
            logger.error(f"Failed to fetch from CoinGecko: {str(e)}")
            st.error(f"Failed to fetch from CoinGecko: {str(e)}")
            return [], str(e)

def fetch_financial_report(symbol, max_records=1, from_date=None, to_date=None):
    if FMP_API_KEY == "YOUR_FMP_API_KEY":
        logger.error("Invalid FMP API key")
        st.error("Invalid FMP API key")
        return [], "Invalid FMP API key"
    
    endpoint = f"{FMP_API_URL}/income-statement/{symbol}"
    headers = {"User-Agent": "IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)"}
    params = {"limit": max_records, "apikey": FMP_API_KEY}
    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            logger.error(f"Unexpected response from FMP: {data}")
            st.error(f"Unexpected response from FMP")
            return [], "Unexpected response"
        if not data:
            logger.warning(f"No reports found for '{symbol}'")
            st.warning(f"No reports found for '{symbol}'")
            return [], "No reports found"
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
                except ValueError:
                    continue
            reports.append({
                "symbol": report.get("symbol", symbol), "date": report_date,
                "revenue": report.get("revenue", 0), "netIncome": report.get("netIncome", 0),
                "eps": report.get("eps", 0), "grossProfit": report.get("grossProfit", 0),
                "operatingIncome": report.get("operatingIncome", 0),
                "reportedCurrency": report.get("reportedCurrency", "USD"), "type": "report"
            })
        logger.info(f"Fetched {len(reports)} reports for {symbol}")
        return reports, None
    except Exception as e:
        logger.error(f"Failed to fetch from FMP: {str(e)}")
        st.error(f"Failed to fetch from FMP: {str(e)}")
        return [], str(e)

def fetch_currentsapi_news(query="Iran", max_records=20, from_date=None, to_date=None):
    if CURRENTSAPI_API_KEY == "YOUR_CURRENTSAPI_API_KEY":
        logger.error("Invalid CurrentsAPI key")
        st.error("Invalid CurrentsAPI key")
        return [], "Invalid CurrentsAPI key"
    
    params = {"keywords": query, "apiKey": CURRENTSAPI_API_KEY, "language": "en", "limit": min(max_records, 100)}
    if from_date:
        params["start_date"] = from_date
    if to_date:
        params["end_date"] = to_date
    headers = {"User-Agent": "IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)"}
    try:
        response = requests.get(CURRENTSAPI_API_URL, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "error":
            logger.error(f"CurrentsAPI error: {data.get('message')}")
            st.error(f"CurrentsAPI error: {data.get('message')}")
            return [], data.get('message')
        news = data.get("news", [])
        if not news:
            logger.warning(f"No articles found for '{query}' in CurrentsAPI")
            st.warning(f"No articles found for '{query}' in CurrentsAPI")
            return [], "No articles found"
        formatted_articles = [
            {
                "title": article.get("title", "No title"), "url": article.get("url", ""),
                "source": article.get("source", {}).get("name", "Unknown Source"),
                "published_at": article.get("published", ""), "description": article.get("description", "") or "No description",
                "image_url": article.get("image", ""), "translated_title": "", "translated_description": "", "type": "news"
            } for article in news
        ]
        logger.info(f"Fetched {len(formatted_articles)} articles from CurrentsAPI")
        return formatted_articles, None
    except Exception as e:
        logger.error(f"Failed to fetch from CurrentsAPI: {str(e)}")
        st.error(f"Failed to fetch from CurrentsAPI: {str(e)}")
        return [], str(e)

def fetch_news(selected_api, query="Iran", max_records=20, from_date=None, to_date=None):
    try:
        logger.info(f"Fetching from {selected_api}: query={query}, max_records={max_records}")
        api_functions = {
            "GNews": fetch_gnews, "World News API": fetch_worldnews,
            "CoinGecko (Crypto News)": fetch_coingecko_news, "Financial Report (FMP)": fetch_financial_report,
            "CurrentsAPI": fetch_currentsapi_news
        }
        fetch_function = api_functions.get(selected_api)
        if not fetch_function:
            logger.error(f"Invalid API: {selected_api}")
            st.error(f"Invalid API: {selected_api}")
            return []
        fetch_query = query if selected_api != "Financial Report (FMP)" else query.upper()
        items, error = fetch_function(fetch_query, max_records, from_date, to_date)
        if not isinstance(items, list):
            logger.error(f"Fetch did not return a list: {items}")
            st.error(f"Fetch did not return a list")
            return []
        if error:
            st.error(f"{selected_api}: {error}")
        if items:
            if selected_api != "Financial Report (FMP)":
                seen_urls = set()
                unique_items = [item for item in items if item["url"] not in seen_urls and not seen_urls.add(item["url"])]
                items = unique_items[:max_records]
            logger.info(f"Fetched {len(items)} items from {selected_api}")
            st.success(f"Fetched {len(items)} items from {selected_api}")
        else:
            st.warning(f"No items fetched from {selected_api}")
        return items
    except Exception as e:
        logger.error(f"Error in fetch_news: {str(e)}")
        st.error(f"Error in fetch_news: {str(e)}")
        return []

def translate_with_avalai(text, source_lang="en", target_lang="fa", avalai_api_url=AVALAI_API_URL_DEFAULT):
    if not text:
        return text
    if AVALAI_API_KEY == "YOUR_AVALAI_API_KEY":
        logger.error("Invalid Avalai API key")
        st.error("Invalid Avalai API key")
        return text
    endpoint = f"{avalai_api_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {AVALAI_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)"
    }
    payload = {
        "model": "gpt-4.1-nano",
        "messages": [{"role": "user", "content": f"Translate this text from {source_lang} to {target_lang}: {text}"}]
    }
    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        if "choices" in data and data["choices"]:
            return data["choices"][0]["message"]["content"]
        logger.warning(f"Avalai API response missing choices: {data}")
        st.warning(f"Avalai API response issue")
        return text
    except Exception as e:
        logger.error(f"Failed to translate: {str(e)}")
        st.error(f"Failed to translate: {str(e)}")
        return text

def parse_to_tehran_time(utc_time_str):
    if not utc_time_str:
        return None
    time_formats = [
        "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%d"
    ]
    for time_format in time_formats:
        try:
            utc_time = datetime.strptime(utc_time_str, time_format)
            return utc_time + timedelta(hours=3, minutes=30)
        except ValueError:
            continue
    logger.warning(f"Failed to parse time: {utc_time_str}")
    return None

def format_tehran_time(tehran_time):
    return tehran_time.strftime("%Y/%m/%d - %H:%M")

def truncate_text(text, max_length=100):
    try:
        text_str = str(text)
        if len(text_str) > max_length:
            return text_str[:max_length].rsplit(" ", 1)[0] + "..."
        return text_str
    except Exception:
        return str(text)

def extract_article_content(url):
    try:
        headers = {"User-Agent": "IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)"}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        paragraphs = soup.find_all('p')
        content = " ".join([para.get_text(strip=True) for para in paragraphs if para.get_text(strip=True)])
        if not content:
            logger.warning(f"No content extracted from {url}")
            return "No content available"
        return truncate_text(content, max_length=500)
    except Exception as e:
        logger.error(f"Failed to extract content from {url}: {str(e)}")
        return "Unable to extract content"

def filter_articles_by_time(items, time_range_hours, start_date=None, end_date=None, disable_filter=False):
    if not items or not isinstance(items, list):
        return []
    if items[0].get("type") == "report":
        return items
    if disable_filter:
        return items
    filtered_items = []
    current_tehran_time = datetime.utcnow() + timedelta(hours=3, minutes=30)
    try:
        if time_range_hours == float("inf"):
            start_datetime = datetime.combine(start_date, datetime.min.time()) + timedelta(hours=3, minutes=30)
            end_datetime = datetime.combine(end_date, datetime.max.time()) + timedelta(hours=3, minutes=30)
            for item in items:
                published_time = parse_to_tehran_time(item["published_at"])
                if published_time and start_datetime <= published_time <= end_datetime:
                    filtered_items.append(item)
        else:
            cutoff_time = current_tehran_time - timedelta(hours=time_range_hours)
            for item in items:
                published_time = parse_to_tehran_time(item["published_at"])
                if published_time and published_time >= cutoff_time:
                    filtered_items.append(item)
        logger.info(f"Filtered {len(filtered_items)} items from {len(items)}")
        return filtered_items
    except Exception as e:
        logger.error(f"Error filtering articles: {str(e)}")
        st.error(f"Error filtering articles: {str(e)}")
        return items

def pre_process_articles(items, avalai_api_url, enable_translation=False, num_items_to_translate=1):
    if not items or not isinstance(items, list):
        return []
    if items[0].get("type") == "report":
        return items
    try:
        sorted_items = sorted(items, key=lambda x: parse_to_tehran_time(x["published_at"]) or datetime.min, reverse=True)
        for i, item in enumerate(sorted_items):
            if enable_translation and i < num_items_to_translate:
                item["translated_title"] = translate_with_avalai(item["title"], source_lang="en", target_lang="fa", avalai_api_url=avalai_api_url)
                item["translated_description"] = translate_with_avalai(item["description"], source_lang="en", target_lang="fa", avalai_api_url=avalai_api_url)
            else:
                item["translated_title"] = item["title"]
                item["translated_description"] = item["description"]
        return sorted_items
    except Exception as e:
        logger.error(f"Error in pre_process_articles: {str(e)}")
        st.error(f"Error in pre_process_articles: {str(e)}")
        return items

def update_selected_items(action, item=None):
    if not isinstance(st.session_state.selected_items, list):
        logger.error(f"selected_items is not a list: {st.session_state.selected_items}, Type: {type(st.session_state.selected_items)}")
        st.session_state.selected_items = []
    if action == "add" and item:
        st.session_state.selected_items.append(item)
        logger.info(f"Added item: {item.get('title', item.get('symbol'))}")
    elif action == "remove" and item:
        st.session_state.selected_items = [x for x in st.session_state.selected_items if x.get('url') != item['url']]
        logger.info(f"Removed item: {item.get('title', item.get('symbol'))}")
    elif action == "clear":
        st.session_state.selected_items = []
        logger.info("Cleared selected items")

def display_items(items):
    try:
        if not items or not isinstance(items, list):
            st.warning("No items to display")
            logger.warning("No items to display")
            return
        item_type = items[0].get("type", "news")
        if item_type == "news":
            sorted_items = sorted(items, key=lambda x: parse_to_tehran_time(x["published_at"]) or datetime.min, reverse=True)
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
            if not isinstance(st.session_state.selected_items, list):
                logger.error(f"selected_items is not a list: {st.session_state.selected_items}")
                st.session_state.selected_items = []
            st.write(f"You have selected {len(st.session_state.selected_items)} article(s) to send to Telegram")
            
            st.subheader("News Articles")
            col1, col2 = st.columns(2)
            for i, item in enumerate(sorted_items):
                current_col = col1 if i % 2 == 0 else col2
                with current_col:
                    st.markdown('<div class="neon-line-top"></div>', unsafe_allow_html=True)
                    is_selected = any(a.get('url') == item['url'] for a in st.session_state.selected_items)
                    if st.checkbox("Select for Telegram", key=f"article_{i}", value=is_selected):
                        if not is_selected:
                            update_selected_items("add", item)
                    else:
                        if is_selected:
                            update_selected_items("remove", item)
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
                        except Exception:
                            st.info("Image could not be loaded")
                    st.markdown(f'<div class="english-text description">**Description (English):** {truncated_description}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="persian-text description">**توضیحات (فارسی):** {truncated_translated_description}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.subheader("Financial Reports")
            for report in items:
                st.markdown('<div class="report-section">', unsafe_allow_html=True)
                st.markdown(f"**نماد شرکت:** {report['symbol']}")
                st.markdown(f"**تاریخ گزارش:** {report['date']}")
                st.markdown(f"**ارز گزارش:** {report['reportedCurrency']}")
                st.markdown(f"**درآمد:** {report['revenue']:,} {report['reportedCurrency']}")
                st.markdown(f"**سود خالص:** {report['netIncome']:,} {report['reportedCurrency']}")
                st.markdown(f"**سود هر سهم (EPS):** {report['eps']}")
                st.markdown(f"**سود ناخالص:** {report['grossProfit']:,} {report['reportedCurrency']}")
                st.markdown(f"**درآمد عملیاتی:** {report['operatingIncome']:,} {report['reportedCurrency']}")
                st.markdown('</div>', unsafe_allow_html=True)
    except Exception as e:
        logger.error(f"Failed to display items: {str(e)}")
        st.error(f"Failed to display items: {str(e)}")

def save_items_to_file_for_download(items, format="csv"):
    try:
        if not items or not isinstance(items, list):
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
            logger.info(f"Sent message to {chat_id}")
            return True, "Message sent"
        logger.error(f"Telegram error: {result.get('description')}")
        return False, result.get('description')
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {str(e)}")
        return False, str(e)

def get_chat_id_from_username(username, chat_ids):
    try:
        if not username.startswith("@"):
            return None, "Username must start with @"
        username = username[1:].lower()
        if username in chat_ids:
            return chat_ids[username], None
        url = f"{TELEGRAM_API_URL}/getUpdates"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            return None, "Failed to fetch Telegram updates"
        for update in data.get("result", []):
            if "message" in update and "chat" in update["message"]:
                chat = update["message"]["chat"]
                if chat.get("username", "").lower() == username:
                    chat_id = chat["id"]
                    chat_ids[username] = chat_id
                    save_chat_ids(chat_ids)
                    return chat_id, None
                if chat.get("type") in ["group", "supergroup"]:
                    if chat.get("title", "").lower().find(username.lower()) != -1:
                        chat_id = chat["id"]
                        chat_ids[username] = chat_id
                        save_chat_ids(chat_ids)
                        return chat_id, None
        return None, f"Chat ID not found for @{username}"
    except Exception as e:
        logger.error(f"Failed to fetch chat ID for {username}: {str(e)}")
        return None, str(e)

def main():
    try:
        st.title("Iran News Aggregator")
        
        # Initialize session state
        if 'selected_items' not in st.session_state or not isinstance(st.session_state.selected_items, list):
            st.session_state.selected_items = []
            logger.info("Initialized selected_items")
        if 'items' not in st.session_state or not isinstance(st.session_state.items, list):
            st.session_state.items = load_articles_from_file()
        if 'chat_ids' not in st.session_state:
            st.session_state.chat_ids = load_chat_ids()
        if 'avalai_api_url' not in st.session_state:
            st.session_state.avalai_api_url = AVALAI_API_URL_DEFAULT
        
        with st.sidebar:
            st.header("Query Settings")
            query = st.text_input("Search Query (or Symbol for Financial Report)", value="Iran")
            today = datetime(2025, 5, 15)
            default_start_date = today - timedelta(days=7)
            start_date = st.date_input("Start Date", value=default_start_date, min_value=today - timedelta(days=30), max_value=today)
            end_date = st.date_input("End Date", value=today, min_value=start_date, max_value=today)
            max_items = st.slider("Maximum number of items", min_value=1, max_value=100, value=20)
            api_options = ["GNews", "World News API", "CoinGecko (Crypto News)", "Financial Report (FMP)", "CurrentsAPI"]
            selected_api = st.selectbox("Select API", options=api_options, index=0)
            time_range_options = {
                "Last 30 minutes": 0.5, "Last 1 hour": 1, "Last 4 hours": 4,
                "Last 12 hours": 12, "Last 24 hours": 24, "All articles": float("inf")
            }
            selected_time_range = st.selectbox("Time Range (for News)", options=list(time_range_options.keys()), index=4)
            time_range_hours = time_range_options[selected_time_range]
            disable_time_filter = st.checkbox("Disable Time Filter", value=False)
            
            st.header("Translation Settings (for News)")
            avalai_api_url_options = ["https://api.avalai.ir/v1", "https://api.avalapis.ir/v1"]
            st.session_state.avalai_api_url = st.selectbox("Avalai API URL", options=avalai_api_url_options, index=0)
            enable_translation = st.checkbox("Enable Translation", value=False)
            num_items_to_translate = st.slider("Number of articles to translate", min_value=1, max_value=max_items, value=1) if enable_translation else 1
            
            search_button = st.button("Search for News/Report")
            clear_button = st.button("Clear Results")
            
            st.header("Telegram Settings")
            telegram_chat_id = st.text_input("Telegram Chat ID", value="5013104607")
            telegram_user_or_group_id = st.text_input("Send to User/Group", value="", help="Enter @username or @groupname")
            st.markdown(f"[Start a chat with the bot](https://t.me/YourBotUsername)", unsafe_allow_html=True)
            if st.session_state.chat_ids:
                st.subheader("Known Users/Groups")
                for username, chat_id in st.session_state.chat_ids.items():
                    st.write(f"@{username}: {chat_id}")
            
            st.header("Download Options")
            download_format = st.selectbox("Download Format", ["CSV", "JSON"])
        
        if clear_button:
            st.session_state.items = []
            update_selected_items("clear")
            if os.path.exists(TEMP_FILE):
                os.remove(TEMP_FILE)
            st.experimental_rerun()
        
        if search_button:
            with st.spinner(f"Searching using {selected_api}..."):
                from_date = start_date.strftime("%Y-%m-%d")
                to_date = end_date.strftime("%Y-%m-%d")
                fetch_query = "cryptocurrency" if selected_api == "CoinGecko (Crypto News)" else query
                items = fetch_news(selected_api, query=fetch_query, max_records=max_items, from_date=from_date, to_date=to_date)
                if items:
                    items = filter_articles_by_time(items, time_range_hours, start_date, end_date, disable_time_filter)
                    items = pre_process_articles(items, st.session_state.avalai_api_url, enable_translation, num_items_to_translate)
                    st.session_state.items = items
                    save_articles_to_file(items)
                    update_selected_items("clear")
                else:
                    st.session_state.items = []
        
        if st.session_state.items:
            display_items(st.session_state.items)
        
        with st.sidebar:
            st.header("Telegram Actions")
            if st.button("Reset Selection"):
                update_selected_items("clear")
                st.success("Selection reset")
            
            if not isinstance(st.session_state.selected_items, list):
                logger.error(f"selected_items is not a list: {st.session_state.selected_items}")
                st.session_state.selected_items = []
            selected_items_len = len(st.session_state.selected_items)
            
            if st.button("Send Selected Items to Telegram", disabled=selected_items_len == 0):
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
                    for item in st.session_state.selected_items:
                        try:
                            if item.get("type") == "news":
                                tehran_time = parse_to_tehran_time(item["published_at"])
                                tehran_time_str = format_tehran_time(tehran_time) if tehran_time else item["published_at"]
                                final_title = item["translated_title"] or translate_with_avalai(item["title"], "en", "fa", st.session_state.avalai_api_url)
                                final_description = item["translated_description"] or translate_with_avalai(item["description"], "en", "fa", st.session_state.avalai_api_url)
                                truncated_description = truncate_text(final_description, max_length=100)
                                article_content = extract_article_content(item["url"])
                                translated_content = translate_with_avalai(article_content, "en", "fa", st.session_state.avalai_api_url)
                                message = (
                                    f"*{final_title}*\n\n"
                                    f"{truncated_description}\n\n"
                                    f"**زمان انتشار:** {tehran_time_str}\n\n"
                                    f"**پیش‌نمایش مقاله:**\n{translated_content}\n\n"
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
                            success, result = send_telegram_message(target_chat_id, message, disable_web_page_preview=(item.get("type") != "news"))
                            if success:
                                success_count += 1
                            else:
                                fail_count += 1
                                st.error(f"Failed to send {item.get('title', item.get('symbol'))}: {result}")
                            time.sleep(1)
                        except Exception as e:
                            fail_count += 1
                            st.error(f"Error sending item: {str(e)}")
                    if success_count > 0:
                        st.success(f"Sent {success_count} item(s) to Telegram")
                    if fail_count > 0:
                        st.warning(f"Failed to send {fail_count} item(s)")
            else:
                st.info(f"Select {selected_items_len} item(s) to send to Telegram")
        
        if st.session_state.items:
            with st.sidebar:
                if download_format == "CSV":
                    csv_data = save_items_to_file_for_download(st.session_state.items, format="csv")
                    st.download_button(
                        label="Download as CSV", data=csv_data or b"",
                        file_name=f"iran_news_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv"
                    )
                else:
                    json_data = save_items_to_file_for_download(st.session_state.items, format="json")
                    st.download_button(
                        label="Download as JSON", data=json_data or b"",
                        file_name=f"iran_news_{datetime.now().strftime('%Y%m%d')}.json", mime="application/json"
                    )
        
        st.sidebar.header("Recent Logs")
        for log in log_stream[-10:]:
            st.sidebar.text(log)
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        st.error(f"Error in main: {str(e)}")
        if not isinstance(st.session_state.selected_items, list):
            st.session_state.selected_items = []

if __name__ == "__main__":
    main()
