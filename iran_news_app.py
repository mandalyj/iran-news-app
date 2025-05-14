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
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration - GNews API and NewsAPI
GNEWS_API_URL = "https://gnews.io/api/v4/search"
GNEWS_API_KEY = os.environ.get("GNEWS_API_KEY", "99cbce3921a97e9454302dc0e15789fa")  # Your GNews API Key
NEWSAPI_URL = "https://newsapi.org/v2/everything"
NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "YOUR_NEWSAPI_KEY")  # Replace with your NewsAPI Key

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "7912415975:AAElta6RTGMYcaMY2cEMyU0Zbfdf_Cm4ZfQ")
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
        font-family: "B Nazanin", "Arial Unicode MS", "Tahoma", sans-serif; /* B Nazanin as Persian font */
        font-size: 18px !important; /* Persian font size */
    }
    .english-text {
        direction: ltr;
        text-align: left;
        font-size: 14px !important; /* English font size */
    }
    .article-section {
        margin-bottom: 20px;
    }
    .title-link {
        font-size: 17px !important; /* Increased by 1 unit */
        font-weight: bold !important; /* Make the title bold */
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Load articles from temp file if exists
def load_articles_from_file():
    try:
        if os.path.exists(TEMP_FILE):
            with open(TEMP_FILE, "r") as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.warning(f"Error loading articles from file: {str(e)}")
        return []

# Save articles to temp file
def save_articles_to_file(articles):
    try:
        with open(TEMP_FILE, "w") as f:
            json.dump(articles, f)
    except Exception as e:
        logger.warning(f"Error saving articles to file: {str(e)}")

# Load chat IDs from file
def load_chat_ids():
    try:
        if os.path.exists(CHAT_IDS_FILE):
            with open(CHAT_IDS_FILE, "r") as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.warning(f"Error loading chat IDs from file: {str(e)}")
        return {}

# Save chat IDs to file
def save_chat_ids(chat_ids):
    try:
        with open(CHAT_IDS_FILE, "w") as f:
            json.dump(chat_ids, f)
    except Exception as e:
        logger.warning(f"Error saving chat IDs to file: {str(e)}")

# Fetch news from GNews API
def fetch_gnews(query="Iran", max_records=20, from_date=None, to_date=None):
    """
    Fetch news articles from GNews API
    """
    if not GNEWS_API_KEY or GNEWS_API_KEY == "YOUR_GNEWS_API_KEY":
        error_msg = "Invalid GNews API key. Please set a valid API key."
        logger.error(error_msg)
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
    logger.info(f"Sending GNews request with params: {params}")
    
    try:
        response = requests.get(GNEWS_API_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        logger.info(f"GNews response: {data}")
        
        if "errors" in data:
            error_msg = f"GNews API error: {data['errors']}"
            logger.error(error_msg)
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
                "stock_price": None
            }
            for a in articles
        ], None
    except Exception as e:
        error_msg = f"Error fetching GNews: {str(e)}"
        logger.error(error_msg)
        return [], error_msg

# Fetch news from NewsAPI
def fetch_newsapi(query="Iran", max_records=20, from_date=None, to_date=None):
    """
    Fetch news articles from NewsAPI
    """
    if not NEWSAPI_KEY or NEWSAPI_KEY == "YOUR_NEWSAPI_KEY":
        error_msg = "Invalid NewsAPI key. Please set a valid API key."
        logger.error(error_msg)
        return [], error_msg
    
    params = {
        "q": query,
        "apiKey": NEWSAPI_KEY,
        "language": "en",
        "from": from_date,
        "to": to_date,
        "pageSize": min(max_records, 100),
        "sortBy": "publishedAt"
    }
    logger.info(f"Sending NewsAPI request with params: {params}")
    
    try:
        response = requests.get(NEWSAPI_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        logger.info(f"NewsAPI response: {data}")
        
        if data.get("status") != "ok":
            error_msg = f"NewsAPI error: {data.get('message', 'Unknown error')}"
            logger.error(error_msg)
            return [], error_msg
            
        articles = data.get("articles", [])
        if not articles:
            error_msg = f"No articles found for query '{query}' in NewsAPI."
            logger.warning(error_msg)
            return [], error_msg
            
        return [
            {
                "title": a.get("title", "No title"),
                "url": a.get("url", ""),
                "source": a.get("source", {}).get("name", "Unknown Source"),
                "published_at": a.get("publishedAt", ""),
                "description": a.get("description", "") or "No description available",
                "image_url": a.get("urlToImage", ""),
                "translated_title": "",
                "translated_description": "",
                "stock_price": None
            }
            for a in articles
        ], None
    except Exception as e:
        error_msg = f"Error fetching NewsAPI: {str(e)}"
        logger.error(error_msg)
        return [], error_msg

# Fetch news from all APIs in parallel using ThreadPoolExecutor
def fetch_news(query="Iran", max_records=20, from_date=None, to_date=None):
    """
    Fetch news from all APIs in parallel and combine results
    """
    st.write("Starting news fetch process (parallel)...")
    fetch_functions = [
        (fetch_gnews, "GNews"),
        (fetch_newsapi, "NewsAPI")
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
                if articles:
                    all_articles.extend(articles)
                if error:
                    errors.append(f"{api_name}: {error}")
            except Exception as e:
                error_msg = f"Error fetching from {api_name}: {str(e)}"
                errors.append(error_msg)
                st.error(error_msg)
    
    # Remove duplicates based on URL
    seen_urls = set()
    unique_articles = []
    for article in all_articles:
        if article["url"] not in seen_urls:
            seen_urls.add(article["url"])
            unique_articles.append(article)
    
    for error in errors:
        st.error(error)
    
    if unique_articles:
        st.write(f"Successfully fetched {len(unique_articles)} unique articles from all APIs!")
    else:
        st.warning("No articles fetched from any API.")
    
    return unique_articles

# Function to convert UTC time to Tehran time
def convert_to_tehran_time(utc_time_str):
    """
    Convert UTC time string to Tehran time (UTC+3:30)
    """
    try:
        utc_time = datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%M:%SZ")
        tehran_time = utc_time + timedelta(hours=3, minutes=30)
        return tehran_time.strftime("%Y/%m/%d - %H:%M")
    except Exception as e:
        logger.warning(f"Error converting time: {str(e)}")
        return utc_time_str

# Function to fetch stock price using yfinance
def fetch_stock_price(company_name):
    """
    Fetch the latest stock price for a company using yfinance
    """
    try:
        # Simple mapping of company names to ticker symbols (you can expand this)
        ticker_map = {
            "apple": "AAPL",
            "microsoft": "MSFT",
            "google": "GOOGL",
            "amazon": "AMZN",
            "tesla": "TSLA"
        }
        
        # Try to find a matching ticker
        ticker_symbol = None
        company_name_lower = company_name.lower()
        for key, value in ticker_map.items():
            if key in company_name_lower:
                ticker_symbol = value
                break
        
        if not ticker_symbol:
            return None, "Ticker not found for this company"
        
        ticker = yf.Ticker(ticker_symbol)
        stock_data = ticker.history(period="1d")
        if not stock_data.empty:
            latest_price = stock_data["Close"].iloc[-1]
            return round(latest_price, 2), None
        return None, "No stock data available"
    except Exception as e:
        logger.warning(f"Error fetching stock price for {company_name}: {str(e)}")
        return None, str(e)

# Function to pre-process articles (stock prices only)
def pre_process_articles(articles):
    """
    Pre-process articles by fetching stock prices
    """
    for i, article in enumerate(articles):
        try:
            # Fetch stock price based on article title
            stock_price, error = fetch_stock_price(article["title"])
            if stock_price is not None:
                article["stock_price"] = stock_price
            else:
                article["stock_price"] = None
                if error:
                    logger.warning(f"Stock price fetch error for {article['title']}: {error}")
            # Set empty translations (disabled for now)
            article["translated_title"] = article["title"]
            article["translated_description"] = article["description"]
        except Exception as e:
            st.error(f"Error processing article {article['title']}: {str(e)}")
            logger.error(f"Error in pre_process_articles: {str(e)}")
    return articles

# Function to display news articles in a nice format
def display_news_articles(articles):
    """Display news articles in a structured format"""
    st.write(f"Attempting to display {len(articles)} articles...")
    if not articles:
        st.warning("No news articles to display")
        return
        
    st.subheader("News Statistics")
    sources = pd.DataFrame([article["source"] for article in articles]).value_counts().reset_index()
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
    
    st.subheader("News Articles")
    for i in range(0, len(articles), 2):
        cols = st.columns(2)
        with cols[0]:
            article = articles[i]
            st.write(f"Displaying article {i+1}: {article['title']}")
            is_selected = any(a.get('url') == article['url'] for a in st.session_state.selected_articles)
            checkbox_key = f"article_{i}"
            if st.checkbox("Select for Telegram", key=checkbox_key, value=is_selected):
                if not is_selected:
                    st.session_state.selected_articles.append(article)
            else:
                if is_selected:
                    st.session_state.selected_articles = [a for a in st.session_state.selected_articles if a.get('url') != article['url']]
            tehran_time = convert_to_tehran_time(article["published_at"])
            st.markdown(f'<div class="article-section">', unsafe_allow_html=True)
            st.markdown(f'<h3 class="title-link"><a href="{article["url"]}" target="_blank">{article["title"]}</a></h3>', unsafe_allow_html=True)
            st.markdown('<div class="persian-text">**عنوان (فارسی):** ' + article["translated_title"] + '</div>', unsafe_allow_html=True)
            st.markdown(f'**Source:** {article["source"]}')
            st.markdown(f'<div class="persian-text">**انتشار:** {tehran_time}</div>', unsafe_allow_html=True)
            if article["stock_price"] is not None:
                st.markdown(f'<div class="english-text">**Latest Stock Price (USD):** {article["stock_price"]}</div>', unsafe_allow_html=True)
            if article["image_url"]:
                try:
                    st.image(article["image_url"], use_column_width=True)
                except:
                    st.info("Image could not be loaded")
            st.markdown('<div class="english-text">**Description (English):** ' + article["description"] + '</div>', unsafe_allow_html=True)
            st.markdown('<div class="persian-text">**توضیحات (فارسی):** ' + article["translated_description"] + '</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        if i + 1 < len(articles):
            with cols[1]:
                article = articles[i + 1]
                st.write(f"Displaying article {i+2}: {article['title']}")
                is_selected = any(a.get('url') == article['url'] for a in st.session_state.selected_articles)
                checkbox_key = f"article_{i+1}"
                if st.checkbox("Select for Telegram", key=checkbox_key, value=is_selected):
                    if not is_selected:
                        st.session_state.selected_articles.append(article)
                else:
                    if is_selected:
                        st.session_state.selected_articles = [a for a in st.session_state.selected_articles if a.get('url') != article['url']]
                tehran_time = convert_to_tehran_time(article["published_at"])
                st.markdown(f'<div class="article-section">', unsafe_allow_html=True)
                st.markdown(f'<h3 class="title-link"><a href="{article["url"]}" target="_blank">{article["title"]}</a></h3>', unsafe_allow_html=True)
                st.markdown('<div class="persian-text">**عنوان (فارسی):** ' + article["translated_title"] + '</div>', unsafe_allow_html=True)
                st.markdown(f'**Source:** {article["source"]}')
                st.markdown(f'<div class="persian-text">**انتشار:** {tehran_time}</div>', unsafe_allow_html=True)
                if article["stock_price"] is not None:
                    st.markdown(f'<div class="english-text">**Latest Stock Price (USD):** {article["stock_price"]}</div>', unsafe_allow_html=True)
                if article["image_url"]:
                    try:
                        st.image(article["image_url"], use_column_width=True)
                    except:
                        st.info("Image could not be loaded")
                st.markdown('<div class="english-text">**Description (English):** ' + article["description"] + '</div>', unsafe_allow_html=True)
                st.markdown('<div class="persian-text">**توضیحات (فارسی):** ' + article["translated_description"] + '</div>', unsafe_allow_html=True)
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

# Function to send a message to Telegram
def send_telegram_message(chat_id, message, disable_web_page_preview=False):
    try:
        # Ensure message length is within Telegram's limit (4096 characters)
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
        
        # Remove the @ symbol
        username = username[1:].lower()
        
        # Check if username is already in stored chat IDs
        if username in chat_ids:
            return chat_ids[username], None
        
        # Use getUpdates to check for recent chats
        url = f"{TELEGRAM_API_URL}/getUpdates"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("ok"):
            return None, "Failed to fetch updates from Telegram"
        
        # Look for the username in recent updates
        for update in data.get("result", []):
            if "message" in update and "chat" in update["message"]:
                chat = update["message"]["chat"]
                if chat.get("username", "").lower() == username:
                    chat_id = chat["id"]
                    chat_ids[username] = chat_id
                    save_chat_ids(chat_ids)
                    return chat_id, None
                # Check if it's a group with the username
                if chat.get("type") == "group" or chat.get("type") == "supergroup":
                    if chat.get("title", "").lower().find(username.lower()) != -1:
                        chat_id = chat["id"]
                        chat_ids[username] = chat_id
                        save_chat_ids(chat_ids)
                        return chat_id, None
        
        return None, f"Chat ID not found for username @{username}. Make sure the user/group has interacted with the bot."
    except Exception as e:
        logger.warning(f"Error fetching Chat ID for username {username}: {str(e)}")
        return None, str(e)

# Main Streamlit app
def main():
    st.title("Iran News Aggregator")
    
    # Initialize session state for selected articles and articles
    if 'selected_articles' not in st.session_state:
        st.session_state.selected_articles = []
    if 'articles' not in st.session_state:
        st.session_state.articles = load_articles_from_file()  # Load from file if exists
    if 'chat_ids' not in st.session_state:
        st.session_state.chat_ids = load_chat_ids()  # Load chat IDs from file
    
    # Debug: Log the state to see if articles are being cleared
    if not st.session_state.articles:
        st.info("No articles in session state. Please search for news or check if data was loaded from file.")
    else:
        st.info(f"Found {len(st.session_state.articles)} articles in session state.")
    
    # Sidebar for queries and filters
    with st.sidebar:
        st.header("Query Settings")
        query = st.text_input("Search Query", value="Iran", key="search_query").strip()
        today = datetime(2025, 5, 14)  # Today's date (May 14, 2025)
        start_date = st.date_input("Start Date", value=today, min_value=today - timedelta(days=30), max_value=today, key="start_date")
        end_date = st.date_input("End Date", value=today, min_value=start_date, max_value=today, key="end_date")
        max_articles = st.slider(label="Maximum number of articles per API", min_value=5, max_value=100, value=20, key="max_articles")
        
        # Add search button
        search_button = st.button("Search for News")
        
        # Add clear button to reset articles
        clear_button = st.button("Clear Results")
        
        # Telegram settings
        st.header("Telegram Settings")
        telegram_chat_id = st.text_input("Telegram Chat ID", value="5013104607", key="telegram_chat_id")
        telegram_user_or_group_id = st.text_input("Send to User/Group", value="", key="telegram_user_or_group_id", help="Enter the @username or @groupname to send selected news to (leave blank to use default Chat ID)")
        
        # Add a link to start a chat with the bot
        bot_username = "YourBotUsername"  # Replace with your bot's username, e.g., @YourBot
        st.markdown(f"[Start a chat with the bot](https://t.me/{bot_username}) to allow sending messages.", unsafe_allow_html=True)
        
        # Display stored usernames
        if st.session_state.chat_ids:
            st.subheader("Known Users/Groups")
            for username, chat_id in st.session_state.chat_ids.items():
                st.write(f"@{username}: {chat_id}")
        
        # Download options
        st.header("Download Options")
        download_format = st.selectbox("Download Format", ["CSV", "JSON"], key="download_format")
    
    # Clear articles if clear button is pressed
    if clear_button:
        st.session_state.articles = []
        st.session_state.selected_articles = []
        if os.path.exists(TEMP_FILE):
            os.remove(TEMP_FILE)
        st.experimental_rerun()  # Force a rerun to refresh the page
    
    # Execute search when button is clicked
    if search_button:
        with st.spinner(f"Searching for news about {query}..."):
            # Convert dates to string format for APIs
            from_date = start_date.strftime("%Y-%m-%d")
            to_date = end_date.strftime("%Y-%m-%d")
            articles = fetch_news(query=query, max_records=max_articles, from_date=from_date, to_date=to_date)
            if articles:
                articles = pre_process_articles(articles)  # Pre-process (stock prices only)
                st.session_state.articles = articles
                save_articles_to_file(articles)  # Save to temp file
                st.session_state.selected_articles = []
                st.success("Articles fetched successfully!")
            else:
                st.warning("No articles fetched. Check the error messages above or try a different query.")
    
    # Always display articles if they exist in session state
    if st.session_state.articles:
        st.write(f"Found {len(st.session_state.articles)} articles in session state. Displaying now...")
        display_news_articles(st.session_state.articles)
    else:
        st.info("No articles to display in session state.")
    
    # Download section in the sidebar
    if st.session_state.articles:
        with st.sidebar:
            if download_format == "CSV":
                csv_data = save_articles_to_file_for_download(st.session_state.articles, format="csv")
                st.download_button(
                    label="Download as CSV",
                    data=csv_data if csv_data else b"",
                    file_name=f"iran_news_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:  # JSON
                json_data = save_articles_to_file_for_download(st.session_state.articles, format="json")
                st.download_button(
                    label="Download as JSON",
                    data=json_data if json_data else b"",
                    file_name=f"iran_news_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json"
                )
            
            # Send selected news to Telegram
            if st.session_state.selected_articles:
                if st.button("Send Selected News to Telegram"):
                    with st.spinner("Sending to Telegram..."):
                        success_count = 0
                        fail_count = 0
                        # Determine the target chat ID
                        target_chat_id = telegram_user_or_group_id if telegram_user_or_group_id else telegram_chat_id
                        
                        # If the input starts with @, try to resolve username to Chat ID
                        if target_chat_id.startswith("@"):
                            chat_id, error = get_chat_id_from_username(target_chat_id, st.session_state.chat_ids)
                            if chat_id is None:
                                st.error(f"Failed to resolve username: {error}")
                                fail_count = len(st.session_state.selected_articles)  # Mark all as failed
                            else:
                                target_chat_id = chat_id
                        
                        # Debug: Show the target chat ID and message
                        st.info(f"Sending to Chat ID: {target_chat_id}")
                        
                        for article in st.session_state.selected_articles:
                            message = f"*{article['title']}*\n\n{article['description']}\n\n[Read more]({article['url']})"
                            stock_price = article.get("stock_price")
                            if stock_price is not None:
                                message += f"\n\n**Latest Stock Price (USD):** {stock_price}"
                            # Debug: Show the message being sent
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
                st.info("Select articles to send to Telegram")

if __name__ == "__main__":
    main()
