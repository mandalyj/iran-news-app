import os
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import logging
import streamlit as st
import base64
from io import BytesIO
import json
from bs4 import BeautifulSoup
import feedparser

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Store logs in memory for display in the UI
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
NEWSAPI_API_URL = "https://newsapi.org/v2/everything"
NEWSAPI_API_KEY = os.environ.get("NEWSAPI_API_KEY", "YOUR_NEWSAPI_API_KEY")
CRYPTOCOMPARE_API_URL = "https://min-api.cryptocompare.com/data/v2/news/"
CRYPTOCOMPARE_API_KEY = os.environ.get("CRYPTOCOMPARE_API_KEY", "YOUR_CRYPTOCOMPARE_API_KEY")
FMP_API_URL = "https://financialmodelingprep.com/api/v3"
FMP_API_KEY = os.environ.get("FMP_API_KEY", "YOUR_FMP_API_KEY")
AVALAI_API_URL_DEFAULT = "https://api.avalapis.ir/v1"
AVALAI_API_KEY = os.environ.get("AVALAI_API_KEY", "YOUR_AVALAI_API_KEY")
CURRENTSAPI_API_URL = "https://api.currentsapi.services/v1/search"
CURRENTSAPI_API_KEY = os.environ.get("CURRENTSAPI_API_KEY", "YOUR_CURRENTSAPI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
GOOGLE_AI_API_URL = "https://generativelanguage.googleapis.com/v1beta"
GOOGLE_AI_API_KEY = os.environ.get("GOOGLE_AI_API_KEY", "YOUR_GOOGLE_AI_API_KEY")

TEMP_FILE = "/tmp/iran_news_articles.json"
CHAT_IDS_FILE = "/tmp/iran_news_chat_ids.json"
SCRAPE_SOURCES_FILE = "/tmp/scrape_sources.json"

# بارگذاری منابع اسکرپ از فایل
def load_scrape_sources():
    try:
        if os.path.exists(SCRAPE_SOURCES_FILE):
            with open(SCRAPE_SOURCES_FILE, "r") as f:
                data = json.load(f)
                logger.info(f"Loaded {len(data)} scrape sources from {SCRAPE_SOURCES_FILE}")
                return data
        logger.info(f"File {SCRAPE_SOURCES_FILE} does not exist")
        return []
    except Exception as e:
        logger.error(f"Error loading scrape sources: {str(e)}")
        return []

def save_scrape_sources(sources):
    try:
        with open(SCRAPE_SOURCES_FILE, "w") as f:
            json.dump(sources, f)
        logger.info(f"Saved {len(sources)} scrape sources to {SCRAPE_SOURCES_FILE}")
    except Exception as e:
        logger.error(f"Error saving scrape sources: {str(e)}")

# Streamlit page configuration
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
    .title-link { font-size: 20px !important; font-weight: bold !important; color: #1a73e8 !important; margin-bottom: 2px !important; direction: ltr !important; text-decoration: none !important; font-family: "Arial", sans-serif !important; }
    .source-date { font-size: 14px !important; color: #555 !important; margin-bottom: 10px !important; }
    .description { margin-top: 10px !important; line-height: 1.5 !important; }
    </style>
    """,
    unsafe_allow_html=True
)

def send_error_email(error_message):
    logger.info(f"Error email sending is disabled: {error_message}")

def load_articles_from_file():
    try:
        if os.path.exists(TEMP_FILE):
            with open(TEMP_FILE, "r") as f:
                data = json.load(f)
                logger.info(f"Loaded {len(data)} articles from {TEMP_FILE}")
                return data
        logger.info(f"File {TEMP_FILE} does not exist")
        return []
    except Exception as e:
        logger.error(f"Error loading articles: {str(e)}")
        send_error_email(f"Error loading articles: {str(e)}")
        return []

def save_articles_to_file(articles):
    try:
        with open(TEMP_FILE, "w") as f:
            json.dump(articles, f)
        logger.info(f"Saved {len(articles)} articles to {TEMP_FILE}")
    except Exception as e:
        logger.error(f"Error saving articles: {str(e)}")
        send_error_email(f"Error saving articles: {str(e)}")

def load_chat_ids():
    try:
        if os.path.exists(CHAT_IDS_FILE):
            with open(CHAT_IDS_FILE, "r") as f:
                data = json.load(f)
                logger.info(f"Loaded chat IDs: {data}")
                return data
        logger.info(f"File {CHAT_IDS_FILE} does not exist")
        return {}
    except Exception as e:
        logger.error(f"Error loading chat IDs: {str(e)}")
        send_error_email(f"Error loading chat IDs: {str(e)}")
        return {}

def save_chat_ids(chat_ids):
    try:
        with open(CHAT_IDS_FILE, "w") as f:
            json.dump(chat_ids, f)
        logger.info(f"Saved chat IDs: {chat_ids}")
    except Exception as e:
        logger.error(f"Error saving chat IDs: {str(e)}")
        send_error_email(f"Error saving chat IDs: {str(e)}")

def fetch_gnews(query="Iran", max_records=20, from_date=None, to_date=None):
    if GNEWS_API_KEY == "YOUR_GNEWS_API_KEY":
        logger.error("GNews API key is invalid")
        st.error("GNews API key is invalid")
        return [], "Invalid API key"
    
    params = {
        "q": query, "apikey": GNEWS_API_KEY, "lang": "en", "country": "us",
        "max": min(max_records, 100), "from": from_date, "to": to_date
    }
    headers = {"User-Agent": "IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)"}
    try:
        logger.info(f"Sending request to GNews with params: {params}")
        response = requests.get(GNEWS_API_URL, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        logger.info(f"GNews response: {data}")
        if "errors" in data:
            logger.error(f"GNews API error: {data['errors']}")
            st.error(f"GNews API error: {data['errors']}")
            return [], data['errors']
        articles = data.get("articles", [])
        if not articles:
            logger.warning(f"No articles found for '{query}' on GNews")
            st.warning(f"No articles found for '{query}' on GNews")
            return [], "No articles found"
        formatted_articles = []
        for a in articles:
            title = a.get("title", "No title")
            description = a.get("description", "") or "No description"
            formatted_articles.append({
                "title": title, "url": a.get("url", ""),
                "source": a.get("source", {}).get("name", "Unknown source"),
                "published_at": a.get("publishedAt", ""), "description": description,
                "image_url": a.get("image", ""), "translated_title": title,
                "translated_description": description, "type": "news"
            })
        logger.info(f"Fetched {len(formatted_articles)} articles from GNews")
        return formatted_articles, None
    except Exception as e:
        logger.error(f"Error fetching from GNews: {str(e)}")
        st.error(f"Error fetching from GNews: {str(e)}")
        return [], str(e)

def fetch_worldnews(query="Iran", max_records=20, from_date=None, to_date=None):
    if WORLDNEWS_API_KEY == "YOUR_WORLDNEWS_API_KEY":
        logger.error("World News API key is invalid")
        st.error("World News API key is invalid")
        return [], "Invalid API key"
    
    params = {
        "text": query, "api-key": WORLDNEWS_API_KEY, "language": "en",
        "number": min(max_records, 100), "sort": "publish-time", "sort-direction": "DESC",
        "start-date": from_date, "end-date": to_date
    }
    headers = {"User-Agent": "IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)"}
    try:
        logger.info(f"Sending request to World News with params: {params}")
        response = requests.get(WORLDNEWS_API_URL, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        logger.info(f"World News response: {data}")
        if "error" in data:
            logger.error(f"World News API error: {data.get('error')}")
            st.error(f"World News API error: {data.get('error')}")
            return [], data.get('error')
        articles = data.get("news", [])
        if not articles:
            logger.warning(f"No articles found for '{query}' on World News API")
            st.warning(f"No articles found for '{query}' on World News API")
            return [], "No articles found"
        formatted_articles = []
        for a in articles:
            title = a.get("title", "No title")
            description = a.get("text", "") or "No description"
            formatted_articles.append({
                "title": title, "url": a.get("url", ""),
                "source": a.get("source", "Unknown source"), "published_at": a.get("publish_date", ""),
                "description": description, "image_url": a.get("image", ""),
                "translated_title": title, "translated_description": description,
                "type": "news"
            })
        logger.info(f"Fetched {len(formatted_articles)} articles from World News API")
        return formatted_articles, None
    except Exception as e:
        logger.error(f"Error fetching from World News API: {str(e)}")
        st.error(f"Error fetching from World News API: {str(e)}")
        return [], str(e)

def fetch_newsapi_crypto_news(query="cryptocurrency", max_records=20, from_date=None, to_date=None):
    if NEWSAPI_API_KEY == "YOUR_NEWSAPI_API_KEY":
        logger.error("NewsAPI API key is invalid")
        st.error("NewsAPI API key is invalid")
        return [], "Invalid API key"
    
    params = {
        "q": query,
        "apiKey": NEWSAPI_API_KEY,
        "language": "en",
        "pageSize": min(max_records, 100),
        "sortBy": "publishedAt"
    }
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
    
    headers = {"User-Agent": "IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)"}
    try:
        logger.info(f"Sending request to NewsAPI with params: {params}")
        response = requests.get(NEWSAPI_API_URL, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        logger.info(f"NewsAPI response: {data}")
        if data.get("status") == "error":
            logger.error(f"NewsAPI API error: {data.get('message')}")
            st.error(f"NewsAPI API error: {data.get('message')}")
            return [], data.get('message')
        articles = data.get("articles", [])
        if not articles:
            logger.warning(f"No articles found for '{query}' on NewsAPI")
            st.warning(f"No articles found for '{query}' on NewsAPI")
            return [], "No articles found"
        formatted_articles = []
        for a in articles:
            title = a.get("title", "No title")
            description = a.get("description", "") or "No description"
            formatted_articles.append({
                "title": title, "url": a.get("url", ""),
                "source": a.get("source", {}).get("name", "Unknown source"),
                "published_at": a.get("publishedAt", ""), "description": description,
                "image_url": a.get("urlToImage", ""), "translated_title": title,
                "translated_description": description, "type": "news"
            })
        logger.info(f"Fetched {len(formatted_articles)} articles from NewsAPI")
        return formatted_articles, None
    except Exception as e:
        logger.error(f"Error fetching from NewsAPI: {str(e)}")
        st.error(f"Error fetching from NewsAPI: {str(e)}")
        return [], str(e)

def fetch_cryptocompare_news(query="cryptocurrency", max_records=20, from_date=None, to_date=None):
    if CRYPTOCOMPARE_API_KEY == "YOUR_CRYPTOCOMPARE_API_KEY":
        logger.error("CryptoCompare API key is invalid")
        st.error("CryptoCompare API key is invalid")
        return [], "Invalid API key"
    
    endpoint = CRYPTOCOMPARE_API_URL
    headers = {"User-Agent": "IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)"}
    params = {
        "lang": "EN",
        "api_key": CRYPTOCOMPARE_API_KEY,
        "feeds": "cryptocompare",
    }
    try:
        logger.info(f"Sending request to CryptoCompare with params: {params}")
        response = requests.get(endpoint, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        logger.info(f"CryptoCompare response: {data}")
        if data.get("Response") == "Error":
            logger.error(f"CryptoCompare API error: {data.get('Message')}")
            st.error(f"CryptoCompare API error: {data.get('Message')}")
            return [], data.get('Message')
        articles = data.get("Data", [])
        if not articles:
            logger.warning(f"No articles found for '{query}' on CryptoCompare")
            st.warning(f"No articles found for '{query}' on CryptoCompare")
            return [], "No articles found"
        formatted_articles = []
        for a in articles:
            title = a.get("title", "No title")
            description = a.get("body", "") or "No description"
            formatted_articles.append({
                "title": title, "url": a.get("url", ""),
                "source": a.get("source", "CryptoCompare"),
                "published_at": datetime.fromtimestamp(a.get("published_on", 0)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "description": description, "image_url": a.get("imageurl", ""),
                "translated_title": title, "translated_description": description,
                "type": "report"
            })
        formatted_articles = formatted_articles[:max_records]
        logger.info(f"Fetched {len(formatted_articles)} reports from CryptoCompare")
        return formatted_articles, None
    except Exception as e:
        logger.error(f"Error fetching from CryptoCompare: {str(e)}")
        st.error(f"Error fetching from CryptoCompare: {str(e)}")
        return [], str(e)

def fetch_financial_report(symbol, max_records=1, from_date=None, to_date=None):
    if FMP_API_KEY == "YOUR_FMP_API_KEY":
        logger.error("FMP API key is invalid")
        st.error("FMP API key is invalid")
        return [], "Invalid API key"
    
    endpoint = f"{FMP_API_URL}/income-statement/{symbol}"
    headers = {"User-Agent": "IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)"}
    params = {"limit": max_records, "apikey": FMP_API_KEY}
    try:
        logger.info(f"Sending request to FMP with params: {params}")
        response = requests.get(endpoint, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        logger.info(f"FMP response: {data}")
        if not isinstance(data, list):
            logger.error(f"Unexpected response from FMP: {data}")
            st.error("Unexpected response from FMP")
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
        logger.error(f"Error fetching from FMP: {str(e)}")
        st.error(f"Error fetching from FMP: {str(e)}")
        return [], str(e)

def fetch_currentsapi_news(query="Iran", max_records=20, from_date=None, to_date=None):
    if CURRENTSAPI_API_KEY == "YOUR_CURRENTSAPI_API_KEY":
        logger.error("CurrentsAPI API key is invalid")
        st.error("CurrentsAPI API key is invalid")
        return [], "Invalid API key"
    
    params = {"keywords": query, "apiKey": CURRENTSAPI_API_KEY, "language": "en", "limit": min(max_records, 100)}
    if from_date:
        params["start_date"] = from_date
    if to_date:
        params["end_date"] = to_date
    headers = {"User-Agent": "IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)"}
    try:
        logger.info(f"Sending request to CurrentsAPI with params: {params}")
        response = requests.get(CURRENTSAPI_API_URL, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        logger.info(f"CurrentsAPI response: {data}")
        if data.get("status") == "error":
            logger.error(f"CurrentsAPI API error: {data.get('message')}")
            st.error(f"CurrentsAPI API error: {data.get('message')}")
            return [], data.get('message')
        news = data.get("news", [])
        if not news:
            logger.warning(f"No articles found for '{query}' on CurrentsAPI")
            st.warning(f"No articles found for '{query}' on CurrentsAPI")
            return [], "No articles found"
        formatted_articles = []
        for article in news:
            title = article.get("title", "No title")
            description = article.get("description", "") or "No description"
            formatted_articles.append({
                "title": title, "url": article.get("url", ""),
                "source": article.get("source", {}).get("name", "Unknown source"),
                "published_at": article.get("published", ""), "description": description,
                "image_url": article.get("image", ""), "translated_title": title,
                "translated_description": description, "type": "news"
            })
        logger.info(f"Fetched {len(formatted_articles)} articles from CurrentsAPI")
        return formatted_articles, None
    except Exception as e:
        logger.error(f"Error fetching from CurrentsAPI: {str(e)}")
        st.error(f"Error fetching from CurrentsAPI: {str(e)}")
        return [], str(e)

def fetch_custom_scraped_news(max_records=20):
    scrape_sources = st.session_state.scrape_sources
    news_items = []
    for source in scrape_sources:
        logger.info(f"Processing source: {source['name']} ({source['url']}, type: {source['type']})")
        try:
            if source["type"] == "rss":
                logger.info(f"Attempting to parse RSS feed from {source['url']}")
                feed = feedparser.parse(source["url"])
                if feed.bozo:
                    logger.error(f"RSS feed error for {source['name']}: {feed.bozo_exception}")
                    continue
                if not feed.entries:
                    logger.warning(f"No entries found in RSS feed for {source['name']}")
                    continue
                for entry in feed.entries[:max_records]:
                    title = entry.get("title", "No title")
                    description = entry.get("summary", "") or entry.get("description", "") or "No description"
                    news_items.append({
                        "title": title, "url": entry.get("link", ""),
                        "published_at": entry.get("published", datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")),
                        "description": description, "image_url": entry.get("media_thumbnail", [{}])[0].get("url", ""),
                        "translated_title": title, "translated_description": description,
                        "source": source["name"], "type": "news"
                    })
                    logger.info(f"Successfully parsed RSS entry: {entry.get('title')}")
            elif source["type"] == "web":
                logger.info(f"Attempting to scrape web content from {source['url']}")
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                response = requests.get(source["url"], timeout=10, headers=headers)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                articles = soup.find_all("article")
                if not articles:
                    logger.warning(f"No articles found in {source['url']} with current selectors")
                    continue
                logger.info(f"Found {len(articles)} potential articles")
                for article in articles[:max_records]:
                    title_elem = article.find("h2")
                    title = title_elem.text.strip() if title_elem else "No title"
                    description_elem = article.find("p")
                    description = description_elem.text.strip() if description_elem else "No description"
                    link_elem = article.find("a", href=True)
                    article_url = (
                        link_elem["href"] if link_elem and link_elem["href"].startswith("http") else
                        source["url"].rstrip("/") + "/" + link_elem["href"].lstrip("/") if link_elem else
                        source["url"]
                    )
                    image_elem = article.find("img", src=True)
                    image_url = image_elem["src"] if image_elem else ""
                    news_items.append({
                        "title": title, "url": article_url,
                        "published_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "description": description, "image_url": image_url,
                        "translated_title": title, "translated_description": description,
                        "source": source["name"], "type": "news"
                    })
                    logger.info(f"Successfully scraped article: {title}")
        except Exception as e:
            logger.error(f"Error scraping {source['name']} ({source['url']}): {str(e)}")
    return news_items[:max_records]

def fetch_news(selected_api, query="Iran", max_records=20, from_date=None, to_date=None):
    try:
        logger.info(f"Fetching from {selected_api}: query={query}, max_records={max_records}, from_date={from_date}, to_date={to_date}")
        api_functions = {
            "GNews": fetch_gnews,
            "World News API": fetch_worldnews,
            "NewsAPI (Crypto News)": fetch_newsapi_crypto_news,
            "CryptoCompare (Crypto Reports)": fetch_cryptocompare_news,
            "Financial Report (FMP)": fetch_financial_report,
            "CurrentsAPI": fetch_currentsapi_news,
            "Custom Scraped News": fetch_custom_scraped_news
        }
        fetch_function = api_functions.get(selected_api)
        if not fetch_function:
            logger.error(f"Invalid API: {selected_api}")
            st.error(f"Invalid API: {selected_api}")
            return []
        fetch_query = query if selected_api not in ["Financial Report (FMP)", "CryptoCompare (Crypto Reports)"] else query.upper()
        items, error = fetch_function(fetch_query, max_records, from_date, to_date) if selected_api != "Custom Scraped News" else (fetch_function(max_records), None)
        if not isinstance(items, list):
            logger.error(f"Did not receive a list: {items}")
            st.error("Did not receive a list")
            return []
        if error:
            logger.error(f"Error in {selected_api}: {error}")
            st.error(f"{selected_api}: {error}")
        if items:
            if selected_api not in ["Financial Report (FMP)", "CryptoCompare (Crypto Reports)"]:
                seen_urls = set()
                unique_items = [item for item in items if item["url"] not in seen_urls and not seen_urls.add(item["url"])]
                items = unique_items[:max_records]
            logger.info(f"Fetched {len(items)} items from {selected_api}")
            st.success(f"Fetched {len(items)} items from {selected_api}")
        else:
            logger.warning(f"No items fetched from {selected_api}")
            st.warning(f"No items fetched from {selected_api}")
        return items
    except Exception as e:
        logger.error(f"Error in fetch_news: {str(e)}")
        st.error(f"Error in fetch_news: {str(e)}")
        return []

def translate_with_avalai(text, source_lang="en", target_lang="fa", avalai_api_url=AVALAI_API_URL_DEFAULT, model="gpt-4.1-nano", retries=3, backoff_factor=2):
    if not text:
        return text
    if AVALAI_API_KEY == "YOUR_AVALAI_API_KEY":
        logger.error("Avalai API key is invalid")
        st.error("Avalai API key is invalid. Please set the AVALAI_API_KEY environment variable.")
        return text
    endpoint = f"{avalai_api_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {AVALAI_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)"
    }
    if model == "cohere.rerank-v3-5:0":
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": f"Rank the following documents based on the query: {text}"}]
        }
    else:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": f"Translate this text from {source_lang} to {target_lang}: {text}"}]
        }
    for attempt in range(retries):
        try:
            logger.info(f"Sending request to Avalai with model {model} (Attempt {attempt + 1}/{retries}): {text[:100]}...")
            response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Avalai response: {data}")
            if "choices" in data and data["choices"]:
                translated_text = data["choices"][0]["message"]["content"]
                logger.info(f"Processed text with {model}: {translated_text[:100]}...")
                return translated_text
            logger.warning(f"Avalai API response has no choices: {data}")
            st.warning("Issue with Avalai API response: No result returned.")
            return text
        except requests.exceptions.RequestException as e:
            if attempt == retries - 1:
                logger.error(f"Error in processing with Avalai after {retries} attempts: {str(e)}")
                st.error(f"Error in processing with Avalai: {str(e)}. Falling back to original text.")
                return text
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {backoff_factor ** attempt} seconds...")
            time.sleep(backoff_factor ** attempt)

def summarize_with_gemini(text, max_length=100):
    if not text:
        logger.warning("No text provided for summarization")
        return "No content to summarize"
    if GOOGLE_AI_API_KEY == "YOUR_GOOGLE_AI_API_KEY":
        logger.error("Google AI API key is invalid")
        st.error("Google AI API key is invalid. Please set the GOOGLE_AI_API_KEY environment variable.")
        return text

    endpoint = f"{GOOGLE_AI_API_URL}/models/gemini-1.5-flash:generateContent?key={GOOGLE_AI_API_KEY}"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)"
    }
    prompt = f"Summarize the following article in {max_length} words or less, focusing on the main points:\n\n{text}"
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "maxOutputTokens": max_length * 2,
            "temperature": 0.7
        }
    }
    try:
        logger.info(f"Sending summarization request to Gemini API with model gemini-1.5-flash")
        response = requests.post(endpoint, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Gemini API response: {data}")
        if "candidates" in data and data["candidates"]:
            summary = data["candidates"][0]["content"]["parts"][0]["text"]
            logger.info(f"Generated summary: {summary[:100]}...")
            return summary
        logger.warning(f"Gemini API response has no candidates: {data}")
        st.warning("Issue with Gemini API response: No summary returned.")
        return text
    except Exception as e:
        logger.error(f"Error in summarization with Gemini: {str(e)}")
        st.error(f"Error in summarization with Gemini: {str(e)}. Falling back to original text.")
        return text

def extract_article_content(url):
    try:
        headers = {"User-Agent": "IranNewsAggregator/1.0 (Contact: avestaparsavic@gmail.com)"}
        logger.info(f"Extracting content from URL: {url}")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        paragraphs = soup.find_all('p')
        content = " ".join([para.get_text(strip=True) for para in paragraphs if para.get_text(strip=True)])
        if not content:
            logger.warning(f"No content extracted from {url}")
            return "Content not available"
        summary = summarize_with_gemini(content, max_length=100)
        logger.info(f"Extracted and summarized content: {summary[:100]}...")
        return summary
    except Exception as e:
        logger.error(f"Error extracting content from {url}: {str(e)}")
        return "Unable to extract content"

def rerank_articles_with_avalai(query, items):
    if not items or not isinstance(items, list):
        logger.warning("No articles to rerank")
        return items
    if AVALAI_API_KEY == "YOUR_AVALAI_API_KEY":
        logger.error("Avalai API key is invalid")
        st.error("Avalai API key is invalid. Please set the AVALAI_API_KEY environment variable.")
        return items

    try:
        documents = [f"{item['title']} {item['description']}" for item in items]
        logger.info(f"Sending {len(documents)} documents to Avalai for reranking with query: {query}")
        response_text = translate_with_avalai(json.dumps({"query": query, "documents": documents}), model="cohere.rerank-v3-5:0")
        try:
            response_data = json.loads(response_text)
            reranked_indices = response_data.get("indices", list(range(len(items))))
            reranked_items = [items[i] for i in reranked_indices]
            logger.info(f"Reranked {len(reranked_items)} articles using Avalai with cohere.rerank-v3-5:0")
            return reranked_items
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON response from Avalai for reranking: {response_text}")
            return items
    except Exception as e:
        logger.error(f"Error in reranking with Avalai: {str(e)}")
        st.error(f"Error in reranking with Avalai: {str(e)}. Falling back to original order.")
        return items

def parse_to_tehran_time(utc_time_str):
    if not utc_time_str:
        logger.warning("UTC time is empty")
        return None
    time_formats = [
        "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%d"
    ]
    for time_format in time_formats:
        try:
            utc_time = datetime.strptime(utc_time_str, time_format)
            tehran_time = utc_time + timedelta(hours=3, minutes=30)
            logger.info(f"UTC time ({utc_time_str}) converted to Tehran time: {tehran_time}")
            return tehran_time
        except ValueError:
            continue
    logger.warning(f"Error parsing time: {utc_time_str}")
    return None

def format_tehran_time(tehran_time):
    return tehran_time.strftime("%Y/%m/%d - %H:%M")

def truncate_text(text, max_length=100):
    try:
        text_str = str(text)
        if len(text_str) > max_length:
            return text_str[:max_length].rsplit(" ", 1)[0] + "..."
        return text_str
    except Exception as e:
        logger.error(f"Error truncating text: {str(e)}")
        return str(text)

def filter_articles_by_time(items, time_range_hours, start_date=None, end_date=None, disable_filter=False):
    if not items or not isinstance(items, list):
        logger.warning("Article list is empty or invalid")
        return []
    if items[0].get("type") == "report":
        logger.info("Articles are reports, time filter not applied")
        return items
    if disable_filter:
        logger.info("Time filter is disabled")
        return items
    filtered_items = []
    current_tehran_time = datetime.utcnow() + timedelta(hours=3, minutes=30)
    logger.info(f"Current Tehran time: {current_tehran_time}")
    try:
        if time_range_hours == float("inf"):
            start_datetime = datetime.combine(start_date, datetime.min.time()) + timedelta(hours=3, minutes=30)
            end_datetime = datetime.combine(end_date, datetime.max.time()) + timedelta(hours=3, minutes=30)
            logger.info(f"Time filter: from {start_datetime} to {end_datetime}")
            for item in items:
                published_time = parse_to_tehran_time(item["published_at"])
                if published_time and start_datetime <= published_time <= end_datetime:
                    filtered_items.append(item)
                else:
                    logger.info(f"Article filtered (outside time range): {item.get('title', 'No title')}")
        else:
            cutoff_time = current_tehran_time - timedelta(hours=time_range_hours)
            logger.info(f"Time filter: articles after {cutoff_time}")
            for item in items:
                published_time = parse_to_tehran_time(item["published_at"])
                if published_time and published_time >= cutoff_time:
                    filtered_items.append(item)
                else:
                    logger.info(f"Article filtered (older than time range): {item.get('title', 'No title')}")
        logger.info(f"Filtered {len(filtered_items)} items out of {len(items)}")
        return filtered_items
    except Exception as e:
        logger.error(f"Error filtering articles: {str(e)}")
        st.error(f"Error filtering articles: {str(e)}")
        return items

def pre_process_articles(items, query, avalai_api_url, enable_translation=False, num_items_to_translate=1, enable_reranking=True):
    if not items or not isinstance(items, list):
        logger.warning("Article list for preprocessing is empty")
        return []
    if items[0].get("type") == "report":
        logger.info("Articles are reports, preprocessing not applied")
        return items
    try:
        if enable_reranking:
            logger.info("Reranking articles with Avalai")
            items = rerank_articles_with_avalai(query, items)
        else:
            items = sorted(items, key=lambda x: parse_to_tehran_time(x["published_at"]) or datetime.min, reverse=True)
            logger.info(f"Sorted articles by time: {len(items)} items")

        if enable_translation:
            for i, item in enumerate(items[:num_items_to_translate]):
                item["translated_title"] = translate_with_avalai(item["title"], "en", "fa", avalai_api_url)
                item["translated_description"] = translate_with_avalai(item["description"], "en", "fa", avalai_api_url)

        logger.info(f"Preprocessed articles: {len(items)} items")
        return items
    except Exception as e:
        logger.error(f"Error preprocessing articles: {str(e)}")
        st.error(f"Error preprocessing articles: {str(e)}")
        return items

def update_selected_items(action, item=None):
    if not hasattr(st.session_state, 'selected_items') or not isinstance(st.session_state.selected_items, list):
        st.session_state.selected_items = []
        logger.info("Initialized selected_items as an empty list")
    if action == "add" and item:
        st.session_state.selected_items.append(item)
        logger.info(f"Adding item: {item.get('title', item.get('symbol'))}")
    elif action == "remove" and item:
        st.session_state.selected_items = [x for x in st.session_state.selected_items if x.get('url') != item['url']]
        logger.info(f"Removing item: {item.get('title', item.get('symbol'))}")
    elif action == "clear":
        st.session_state.selected_items = []
        logger.info("Cleared selected items")

def display_items(items):
    try:
        if not items or not isinstance(items, list):
            logger.warning("No items to display: list is empty")
            st.warning("No items to display")
            return
        logger.info(f"Displaying {len(items)} items")
        item_type = items[0].get("type", "news")
        if item_type == "news":
            st.subheader("News Statistics")
            sources = pd.DataFrame([item["source"] for item in items]).value_counts().reset_index()
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
            if not hasattr(st.session_state, 'selected_items') or not isinstance(st.session_state.selected_items, list):
                st.session_state.selected_items = []
                logger.info("Re-initialized selected_items as an empty list")
            st.write(f"You have selected {len(st.session_state.selected_items)} articles for Telegram")
            
            st.subheader("News Articles")
            col1, col2 = st.columns(2)
            for i, item in enumerate(items):
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
                    st.markdown(f'<div class="article-section">', unsafe_allow_html=True)
                    st.markdown(f'<h3 class="title-link"><a href="{item["url"]}" target="_blank">{item["title"]}</a></h3>', unsafe_allow_html=True)
                    st.markdown(f'<div class="source-date">**Source:** {item["source"]} | **Published:** {tehran_time_str}</div>', unsafe_allow_html=True)
                    if item.get("translated_title"):
                        st.markdown(f'<div class="persian-text">**تیتر (فارسی):** {item["translated_title"]}</div>', unsafe_allow_html=True)
                    if item.get("translated_description"):
                        st.markdown(f'<div class="persian-text description">**توضیحات (فارسی):** {truncate_text(item["translated_description"], max_length=100)}</div>', unsafe_allow_html=True)
                    if "relevance_score" in item:
                        st.markdown(f'<div class="source-date">**Relevance Score:** {item["relevance_score"]:.2f}</div>', unsafe_allow_html=True)
                    if item["image_url"]:
                        try:
                            st.image(item["image_url"], width=300)
                        except Exception:
                            st.info("Image failed to load")
                    st.markdown(f'<div class="english-text description">**Description (English):** {truncated_description}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.subheader("Financial Reports")
            for report in items:
                st.markdown('<div class="report-section">', unsafe_allow_html=True)
                st.markdown(f"**Company Symbol:** {report['symbol']}")
                st.markdown(f"**Report Date:** {report['date']}")
                st.markdown(f"**Reported Currency:** {report['reportedCurrency']}")
                st.markdown(f"**Revenue:** {report['revenue']:,} {report['reportedCurrency']}")
                st.markdown(f"**Net Income:** {report['netIncome']:,} {report['reportedCurrency']}")
                st.markdown(f"**Earnings Per Share (EPS):** {report['eps']}")
                st.markdown(f"**Gross Profit:** {report['grossProfit']:,} {report['reportedCurrency']}")
                st.markdown(f"**Operating Income:** {report['operatingIncome']:,} {report['reportedCurrency']}")
                st.markdown('</div>', unsafe_allow_html=True)
    except Exception as e:
        logger.error(f"Error displaying items: {str(e)}")
        st.error(f"Error displaying items: {str(e)}")

def save_items_to_file_for_download(items, format="csv"):
    try:
        if not items or not isinstance(items, list):
            logger.warning("No items to save")
            return None
        df = pd.DataFrame(items)
        if format == "csv":
            buffer = BytesIO()
            df.to_csv(buffer, index=False)
            return buffer.getvalue()
        elif format == "json":
            return json.dumps(items, indent=2).encode()
        return None
    except Exception as e:
        logger.error(f"Error saving items for download: {str(e)}")
        return None

def clean_markdown_text(text):
    text = text.replace("*", "\\*").replace("_", "\\_").replace("[", "\\[").replace("]", "\\]")
    return text

def send_telegram_message(chat_id, message, disable_web_page_preview=False):
    try:
        if len(message) > 4096:
            message = message[:4093] + "..."
        message = clean_markdown_text(message)
        url = f"{TELEGRAM_API_URL}/sendMessage"
        data = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": disable_web_page_preview}
        logger.info(f"Sending message to Telegram: {chat_id}")
        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        logger.info(f"Telegram response: {result}")
        if result.get("ok"):
            logger.info(f"Message sent to {chat_id}")
            return True, "Message sent"
        logger.error(f"Telegram error: {result.get('description')}")
        return False, result.get('description')
    except Exception as e:
        logger.error(f"Error sending Telegram message: {str(e)}")
        return False, str(e)

def get_chat_id_from_username(username, chat_ids):
    try:
        if not username.startswith("@"):
            return None, "Username must start with @"
        username = username[1:].lower()
        if username in chat_ids:
            return chat_ids[username], None
        url = f"{TELEGRAM_API_URL}/getUpdates"
        logger.info(f"Fetching Telegram updates to find chat ID")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Telegram updates response: {data}")
        if not data.get("ok"):
            return None, "Error fetching Telegram updates"
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
        return None, f"Chat ID for @{username} not found"
    except Exception as e:
        logger.error(f"Error fetching chat ID for {username}: {str(e)}")
        return None, str(e)

def main():
    port = int(os.environ.get("PORT", 8501))
    st.write(f"Running on port {port}")  # برای دیباگ

    # Health check
    if st.experimental_get_query_params().get("health") == ["1"]:
        st.write(json.dumps({"status": "healthy"}))
        st.stop()

    try:
        st.title("Iran News Aggregator")
        
        # Initialize session state
        if not hasattr(st.session_state, 'selected_items') or not isinstance(st.session_state.selected_items, list):
            st.session_state.selected_items = []
            logger.info("Initialized selected_items as an empty list")
        
        if not hasattr(st.session_state, 'articles') or not isinstance(st.session_state.articles, list):
            st.session_state.articles = load_articles_from_file()
            logger.info(f"Initialized st.session_state.articles: {len(st.session_state.articles)} items")
        
        if not hasattr(st.session_state, 'chat_ids'):
            st.session_state.chat_ids = load_chat_ids()
        
        if not hasattr(st.session_state, 'avalai_api_url'):
            st.session_state.avalai_api_url = AVALAI_API_URL_DEFAULT

        # Initialize scrape sources
        if not hasattr(st.session_state, 'scrape_sources'):
            st.session_state.scrape_sources = load_scrape_sources()
            logger.info(f"Initialized st.session_state.scrape_sources: {len(st.session_state.scrape_sources)} sources")

        # Add section for adding custom scrape sources
        st.header("Add Custom Scrape Sources")
        with st.form(key="scrape_form"):
            source_name = st.text_input("Source Name", value="")
            source_url = st.text_input("Source URL", value="")
            source_type = st.selectbox("Source Type", options=["web", "rss"], index=0)
            submit_button = st.form_submit_button(label="Add Source")
            if submit_button and source_name and source_url:
                new_source = {"name": source_name, "url": source_url, "type": source_type}
                st.session_state.scrape_sources.append(new_source)
                save_scrape_sources(st.session_state.scrape_sources)
                st.success(f"Added {source_name} to scrape sources")
                st.rerun()

        st.subheader("Current Scrape Sources")
        if st.session_state.scrape_sources:
            for i, source in enumerate(st.session_state.scrape_sources):
                st.write(f"{i + 1}. {source['name']} - {source['url']} ({source['type']})")
                if st.button("Remove", key=f"remove_source_{i}"):
                    st.session_state.scrape_sources.pop(i)
                    save_scrape_sources(st.session_state.scrape_sources)
                    st.rerun()
        else:
            st.info("No scrape sources added yet.")

        with st.sidebar:
            st.header("Search Settings")
            query = st.text_input("Search query (or company symbol for financial reports)", value="Iran")
            today = datetime.now()
            one_year_ago = today - timedelta(days=365)
            start_date = st.date_input("Start date", value=one_year_ago, min_value=one_year_ago, max_value=today)
            end_date = st.date_input("End date", value=today, min_value=one_year_ago, max_value=today)
            max_items = st.slider("Maximum number of items", min_value=1, max_value=100, value=20)
            api_options = ["GNews", "World News API", "NewsAPI (Crypto News)", "CryptoCompare (Crypto Reports)", "Financial Report (FMP)", "CurrentsAPI", "Custom Scraped News"]
            selected_api = st.selectbox("Select API", options=api_options, index=0)
            time_range_options = {
                "Last 30 minutes": 0.5, "Last 1 hour": 1, "Last 4 hours": 4,
                "Last 12 hours": 12, "Last 24 hours": 24, "All articles": float("inf")
            }
            selected_time_range = st.selectbox("Time range (for news)", options=list(time_range_options.keys()), index=4)
            time_range_hours = time_range_options[selected_time_range]
            disable_time_filter = st.checkbox("Disable time filter", value=True)
            
            st.header("Translation Settings (for news)")
            avalai_api_url_options = ["https://api.avalapis.ir/v1", "https://api.avalai.ir/v1"]
            st.session_state.avalai_api_url = st.selectbox("Avalai API URL", options=avalai_api_url_options, index=0)
            enable_translation = st.checkbox("Enable translation", value=False)
            num_items_to_translate = st.slider("Number of articles to translate", min_value=1, max_value=max_items, value=1) if enable_translation else 1
            
            st.header("Ranking Settings")
            enable_reranking = st.checkbox("Enable article reranking with Avalai", value=True)
            
            search_button = st.button("Search for news/reports")
            clear_button = st.button("Clear results")
            
            st.header("Telegram Settings")
            telegram_chat_id = st.text_input("Telegram chat ID", value="5013104607")
            telegram_user_or_group_id = st.text_input("Send to user/group", value="", help="Enter @username or @groupname")
            st.markdown(f"[Start chat with bot](https://t.me/YourBotUsername)", unsafe_allow_html=True)
            if st.session_state.chat_ids:
                st.subheader("Known Users/Groups")
                for username, chat_id in st.session_state.chat_ids.items():
                    st.write(f"@{username}: {chat_id}")
            
            st.header("Download Options")
            download_format = st.selectbox("Download format", ["CSV", "JSON"])
        
        if clear_button:
            st.session_state.articles = []
            update_selected_items("clear")
            if os.path.exists(TEMP_FILE):
                os.remove(TEMP_FILE)
            logger.info("Cleared results")
            st.rerun()
        
        if search_button:
            with st.spinner(f"Searching using {selected_api}..."):
                from_date = start_date.strftime("%Y-%m-%d")
                to_date = end_date.strftime("%Y-%m-%d")
                fetch_query = "cryptocurrency" if selected_api == "NewsAPI (Crypto News)" else query
                items = fetch_news(selected_api, query=fetch_query, max_records=max_items, from_date=from_date, to_date=to_date)
                logger.info(f"After fetch_news, number of items: {len(items)}")
                if items:
                    items = filter_articles_by_time(items, time_range_hours, start_date, end_date, disable_time_filter)
                    logger.info(f"After filter_articles_by_time, number of items: {len(items)}")
                    items = pre_process_articles(items, query, st.session_state.avalai_api_url, enable_translation, num_items_to_translate, enable_reranking)
                    logger.info(f"After pre_process_articles, number of items: {len(items)}")
                    st.session_state.articles = list(items) if isinstance(items, (list, tuple)) else []
                    logger.info(f"Assigned to st.session_state.articles: {len(st.session_state.articles)} items")
                    save_articles_to_file(st.session_state.articles)
                    update_selected_items("clear")
                else:
                    st.session_state.articles = []
                    logger.warning("No items fetched, st.session_state.articles cleared")
        
        if not hasattr(st.session_state, 'articles') or not isinstance(st.session_state.articles, list):
            logger.error(f"st.session_state.articles is not a list: {getattr(st.session_state, 'articles', None)}")
            st.session_state.articles = []
        
        if st.session_state.articles:
            logger.info(f"st.session_state.articles before display: {len(st.session_state.articles)} items")
            display_items(st.session_state.articles)
        else:
            logger.warning("st.session_state.articles is empty, nothing to display")
            st.warning("No items to display")
        
        with st.sidebar:
            st.header("Telegram Actions")
            if st.button("Reset selection"):
                update_selected_items("clear")
                st.success("Selection reset")
            
            if not hasattr(st.session_state, 'selected_items') or not isinstance(st.session_state.selected_items, list):
                st.session_state.selected_items = []
                logger.info("Re-initialized selected_items as an empty list")
            selected_items_len = len(st.session_state.selected_items)
            
            if st.button("Send selected items to Telegram", disabled=selected_items_len == 0):
                with st.spinner("Sending to Telegram..."):
                    success_count = 0
                    fail_count = 0
                    target_chat_id = telegram_user_or_group_id if telegram_user_or_group_id else telegram_chat_id
                    if target_chat_id.startswith("@"):
                        chat_id, error = get_chat_id_from_username(target_chat_id, st.session_state.chat_ids)
                        if chat_id is None:
                            st.error(f"Error resolving username: {error}")
                            fail_count = len(st.session_state.selected_items)
                        else:
                            target_chat_id = chat_id
                    for item in st.session_state.selected_items:
                        try:
                            if item.get("type") == "news":
                                tehran_time = parse_to_tehran_time(item["published_at"])
                                tehran_time_str = format_tehran_time(tehran_time) if tehran_time else item["published_at"]
                                translated_title = translate_with_avalai(item["title"], "en", "fa", st.session_state.avalai_api_url)
                                translated_description = translate_with_avalai(item["description"], "en", "fa", st.session_state.avalai_api_url)
                                if not translated_title or translated_title == item["title"]:
                                    logger.warning(f"Translation failed for title: {item['title']}, using original")
                                    translated_title = item["title"]
                                if not translated_description or translated_description == item["description"]:
                                    logger.warning(f"Translation failed for description: {item['description']}, using original")
                                    translated_description = item["description"]
                                truncated_description = truncate_text(translated_description, max_length=100)
                                article_summary = extract_article_content(item["url"])
                                translated_summary = translate_with_avalai(article_summary, "en", "fa", st.session_state.avalai_api_url)
                                message = (
                                    f"*{translated_title}*\n\n"
                                    f"{truncated_description}\n\n"
                                    f"**انتشار:** {tehran_time_str}\n\n"
                                    f"**خلاصه خبر:**\n{translated_summary}\n\n"
                                    f"[بیشتر بخوانید]({item['url']})"
                                )
                            else:
                                message = (
                                    f"**گزارش مالی برای {item['symbol']}**\n\n"
                                    f"**تاریخ گزارش:** {item['date']}\n"
                                    f"**واحد پول گزارش‌شده:** {item['reportedCurrency']}\n"
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
                                st.error(f"Error sending {item.get('title', item.get('symbol'))}: {result}")
                            time.sleep(1)
                        except Exception as e:
                            fail_count += 1
                            st.error(f"Error sending item: {str(e)}")
                    if success_count > 0:
                        st.success(f"{success_count} آیتم به تلگرام ارسال شد")
                    if fail_count > 0:
                        st.warning(f"ارسال {fail_count} آیتم ناموفق بود")
            else:
                st.info(f"{selected_items_len} آیتم برای ارسال به تلگرام انتخاب شده است")
        
        if st.session_state.articles:
            with st.sidebar:
                if download_format == "CSV":
                    csv_data = save_items_to_file_for_download(st.session_state.articles, format="csv")
                    st.download_button(
                        label="Download as CSV", data=csv_data or b"",
                        file_name=f"iran_news_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv"
                    )
                else:
                    json_data = save_items_to_file_for_download(st.session_state.articles, format="json")
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
        if not hasattr(st.session_state, 'selected_items') or not isinstance(st.session_state.selected_items, list):
            st.session_state.selected_items = []
            logger.info("Re-initialized selected_items as an empty list")

if __name__ == "__main__":
    main()
