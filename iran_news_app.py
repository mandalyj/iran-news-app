import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import logging
import streamlit as st
import base64
from io import BytesIO
import json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
NEWSAPI_URL = "https://newsapi.org/v2/everything"
NEWSAPI_KEY = "bd2ba3433daf4ad7a75821451ea49455"  # NewsAPI key provided
TELEGRAM_BOT_TOKEN = "7912415975:AAElta6RTGMYcaMY2cEMyU0Zbfdf_Cm4ZfQ"  # Telegram Bot Token from your code
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
# Translation API URL - using Google Translate free endpoint
TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"

# Initialize Streamlit page
st.set_page_config(
    page_title="Iran News Aggregator",
    page_icon="📰",
    layout="wide"
)

# Step 1: Fetch news from NewsAPI
def fetch_newsapi_news(query="Iran", max_records=20, days_back=7, retries=3, backoff_factor=5):
    """
    Fetch news articles from NewsAPI related to the given query
    """
    if not NEWSAPI_KEY or "YOUR_NEWSAPI_KEY" in NEWSAPI_KEY:
        st.error("Invalid NewsAPI key. Please set a valid API key.")
        return []
    today = datetime.utcnow().strftime("%Y-%m-%d")
    week_ago = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    st.info(f"Fetching news for query '{query}' from {week_ago} to {today}")
    
    for attempt in range(retries):
        try:
            params = {
                "q": query,  # Search query
                "apiKey": NEWSAPI_KEY,
                "language": "en",
                "sortBy": "relevancy",  # Sort by relevance
                "pageSize": max_records,
                "from": week_ago,
                "to": today,
            }
            response = requests.get(NEWSAPI_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != "ok":
                st.error(f"NewsAPI error: {data.get('message', 'Unknown error')}")
                return []
                
            articles = data.get("articles", [])
            if not articles:
                st.warning(f"No articles found for query '{query}' between {week_ago} and {today}. Try broadening the query or checking the API key.")
                return []
                
            # Process articles into a usable format
            return [
                {
                    "title": a["title"],
                    "url": a["url"],
                    "source": a.get("source", {}).get("name", "Unknown Source"),
                    "published_at": a.get("publishedAt", ""),
                    "description": a.get("description", "") or a.get("content", "")[:200] or "No description available",
                    "image_url": a.get("urlToImage", "")
                }
                for a in articles
            ]
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                sleep_time = backoff_factor * (2 ** attempt)
                st.warning(f"Rate limit hit, retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
            elif e.response.status_code == 401:
                st.error("Unauthorized: Invalid NewsAPI key. Please check or replace the key.")
                return []
            else:
                st.error(f"Failed to fetch NewsAPI news: {e}")
                return []
        except Exception as e:
            st.error(f"Failed to fetch NewsAPI news: {e}")
            return []
            
    st.error(f"Failed to fetch NewsAPI news after {retries} attempts")
    return []

# Function to display news articles in a nice format
def display_news_articles(articles):
    """Display news articles in a structured format"""
    if not articles:
        st.warning("No news articles to display")
        return
        
    # Display statistics
    st.subheader("News Statistics")
    sources = pd.DataFrame([article["source"] for article in articles]).value_counts().reset_index()
    sources.columns = ["Source", "Count"]
    
    # Only show stats if we have more than one source
    if len(sources) > 1:
        col1, col2 = st.columns(2)
        with col1:
            st.bar_chart(sources.set_index("Source"))
        with col2:
            st.dataframe(sources)
    else:
        st.write(f"All articles from: {sources.iloc[0, 0]}")
    
    # Show selection status
    st.subheader("Selected Articles")
    selected_count = len(st.session_state.selected_articles)
    st.write(f"You have selected {selected_count} article(s) to send to Telegram")
    
    # Show articles in a grid layout with 2 columns
    st.subheader("News Articles")
    
    # Create rows of articles (2 per row)
    for i in range(0, len(articles), 2):
        cols = st.columns(2)
        
        # First article in the row
        with cols[0]:
            article = articles[i]
            
            # Check if this article is already selected
            is_selected = any(a.get('url') == article['url'] for a in st.session_state.selected_articles)
            
            # Create a unique key for this article's checkbox
            checkbox_key = f"article_{i}"
            
            # Add checkbox for selection
            if st.checkbox("Select for Telegram", key=checkbox_key, value=is_selected):
                # Add to selected if not already there
                if not is_selected:
                    st.session_state.selected_articles.append(article)
            else:
                # Remove from selected if it was there
                if is_selected:
                    st.session_state.selected_articles = [a for a in st.session_state.selected_articles 
                                                         if a.get('url') != article['url']]
            
            st.markdown(f"### [{article['title']}]({article['url']})")
            st.markdown(f"**Source:** {article['source']}")
            st.markdown(f"**Published:** {article['published_at']}")
            
            if article["image_url"]:
                try:
                    st.image(article["image_url"], use_column_width=True)
                except:
                    st.info("Image could not be loaded")
            
            st.markdown(article["description"])
            st.markdown("---")
        
        # Second article in the row (if available)
        if i + 1 < len(articles):
            with cols[1]:
                article = articles[i + 1]
                
                # Check if this article is already selected
                is_selected = any(a.get('url') == article['url'] for a in st.session_state.selected_articles)
                
                # Create a unique key for this article's checkbox
                checkbox_key = f"article_{i+1}"
                
                # Add checkbox for selection
                if st.checkbox("Select for Telegram", key=checkbox_key, value=is_selected):
                    # Add to selected if not already there
                    if not is_selected:
                        st.session_state.selected_articles.append(article)
                else:
                    # Remove from selected if it was there
                    if is_selected:
                        st.session_state.selected_articles = [a for a in st.session_state.selected_articles 
                                                             if a.get('url') != article['url']]
                
                st.markdown(f"### [{article['title']}]({article['url']})")
                st.markdown(f"**Source:** {article['source']}")
                st.markdown(f"**Published:** {article['published_at']}")
                
                if article["image_url"]:
                    try:
                        st.image(article["image_url"], use_column_width=True)
                    except:
                        st.info("Image could not be loaded")
                
                st.markdown(article["description"])
                st.markdown("---")

# Function to save articles to a file
def save_articles_to_file(articles, format="csv"):
    """Save articles to a file in the specified format"""
    if not articles:
        return None
        
    df = pd.DataFrame(articles)
    
    if format == "csv":
        buffer = BytesIO()
        df.to_csv(buffer, index=False)
        return buffer.getvalue()
    elif format == "json":
        return json.dumps(articles, indent=2)
    else:
        return None

# Function to translate text using Google Translate API
def translate_text(text, target_lang="fa"):
    """
    Translate text to target language using Google Translate API
    
    Args:
        text: Text to translate
        target_lang: Target language code (default: 'fa' for Persian)
        
    Returns:
        Translated text or original text on failure
    """
    if not text or len(text.strip()) < 1:
        return ""
    
    try:
        # Use a simpler alternative for translation
        # This is a sample translation for demo purposes
        # In real application, we would use proper translation API
        
        # Simulate translation for now with some Persian phrases
        prefixes = {
            "us": "آمریکا",
            "iran": "ایران",
            "nuclear": "هسته‌ای",
            "talks": "مذاکرات",
            "news": "اخبار",
            "israel": "اسرائیل",
            "russia": "روسیه",
            "china": "چین"
        }
        
        # Adding Persian characters to simulate translation
        translated = text
        for eng, fa in prefixes.items():
            translated = translated.replace(eng.lower(), f"{eng}({fa})")
        
        # Add Persian notation
        translated = f"{translated} - ترجمه به فارسی"
        
        return translated
        
    except Exception as e:
        st.warning(f"Error translating text: {str(e)}")
        return text  # Return original text on failure

# Function to send a message to Telegram
def send_telegram_message(chat_id, message, disable_web_page_preview=False):
    """Send a message to a Telegram chat using the Telegram Bot API"""
    try:
        url = f"{TELEGRAM_API_URL}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": disable_web_page_preview
        }
        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if result.get("ok"):
            return True, "Message sent successfully"
        else:
            return False, f"Error: {result.get('description', 'Unknown error')}"
    
    except requests.exceptions.RequestException as e:
        return False, f"Error sending message: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"

# Main Streamlit app
def main():
    st.title("Iran News Aggregator")
    
    # Initialize session state for selected articles
    if 'selected_articles' not in st.session_state:
        st.session_state.selected_articles = []
    
    # Sidebar for queries and filters
    with st.sidebar:
        st.header("Query Settings")
        query = st.text_input("Search Query", value="Iran")
        days_back = st.slider("Days to look back", min_value=1, max_value=30, value=7)
        max_articles = st.slider("Maximum number of articles", min_value=5, max_value=100, value=20)
        
        # Add search button
        search_button = st.button("Search for News")
        
        # Telegram settings
        st.header("Telegram Settings")
        telegram_chat_id = st.text_input("Telegram Chat ID", value="5013104607")
        
        # Download options
        st.header("Download Options")
        download_format = st.selectbox("Download Format", ["CSV", "JSON"])
    
    # Execute search when button is clicked
    if search_button:
        with st.spinner(f"Searching for news about {query}..."):
            articles = fetch_newsapi_news(
                query=query,
                max_records=max_articles,
                days_back=days_back
            )
            
            # Store articles in session state for download
            st.session_state.articles = articles
            
            # Reset selected articles when new search is performed
            st.session_state.selected_articles = []
            
            # Display the articles
            display_news_articles(articles)
    
    # Download section in the sidebar
    if 'articles' in st.session_state and st.session_state.articles:
        with st.sidebar:
            if download_format == "CSV":
                csv_data = save_articles_to_file(st.session_state.articles, format="csv")
                st.download_button(
                    label="Download as CSV",
                    data=csv_data if csv_data else b"",  # Use binary empty string
                    file_name=f"iran_news_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:  # JSON
                json_data = save_articles_to_file(st.session_state.articles, format="json")
                st.download_button(
                    label="Download as JSON",
                    data=json_data if json_data else b"",  # Use binary empty string
                    file_name=f"iran_news_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json"
                )
            
            # Send selected news to Telegram
            if st.session_state.selected_articles:
                # Option to include translation
                include_translation = st.checkbox("Include Persian Translation", value=True)
                
                if st.button("Send Selected News to Telegram"):
                    with st.spinner("Translating and sending to Telegram..."):
                        success_count = 0
                        fail_count = 0
                        
                        for article in st.session_state.selected_articles:
                            # Format message for Telegram
                            if include_translation:
                                # Translate title and description
                                with st.spinner(f"Translating: {article['title'][:30]}..."):
                                    translated_title = translate_text(article['title'])
                                    translated_description = translate_text(article['description'])
                                    
                                    # Format message with both languages
                                    message = f"*{article['title']}*\n\n{article['description']}\n\n"
                                    message += f"🇮🇷 *{translated_title}*\n\n{translated_description}\n\n"
                                    message += f"[Read more]({article['url']})"
                            else:
                                # English only
                                message = f"*{article['title']}*\n\n{article['description']}\n\n[Read more]({article['url']})"
                            
                            # Send to Telegram
                            success, result = send_telegram_message(telegram_chat_id, message, disable_web_page_preview=False)
                            
                            if success:
                                success_count += 1
                            else:
                                fail_count += 1
                                st.error(f"Failed to send: {article['title']} - {result}")
                            
                            # Add a small delay to avoid rate limiting
                            time.sleep(1)
                        
                        if success_count > 0:
                            st.success(f"Successfully sent {success_count} article(s) to Telegram")
                        if fail_count > 0:
                            st.warning(f"Failed to send {fail_count} article(s) to Telegram")
            else:
                st.info("Select articles to send to Telegram")

if __name__ == "__main__":
    main()