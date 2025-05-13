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

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration - Gnews API instead of NewsAPI
GNEWS_API_URL = "https://gnews.io/api/v4/search"
GNEWS_API_KEY = os.environ.get("GNEWS_API_KEY", "99cbce3921a97e9454302dc0e15789fa")  # Using your provided Gnews API Key
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "7912415975:AAElta6RTGMYcaMY2cEMyU0Zbfdf_Cm4ZfQ")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
# MyMemory Translation API endpoint
MYMEMORY_API_URL = "https://api.mymemory.translated.net/get"

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
        font-size: 14px !important; /* Reduced English font size by 2 units */
    }
    .article-section {
        margin-bottom: 20px;
    }
    .title-link {
        font-size: 16px !important; /* Title font size */
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Step 1: Fetch news from Gnews API
def fetch_gnews(query="Iran", max_records=20, days_back=7, retries=3, backoff_factor=5):
    """
    Fetch news articles from Gnews API related to the given query
    """
    if not GNEWS_API_KEY or GNEWS_API_KEY == "YOUR_GNEWS_API_KEY":
        st.error("Invalid Gnews API key. Please set a valid API key.")
        return []
    
    today = datetime.utcnow()
    week_ago = today - timedelta(days=days_back)
    from_date = week_ago.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    st.info(f"Fetching news for query '{query}' from the past {days_back} days")
    
    for attempt in range(retries):
        try:
            params = {
                "q": query,  # Search query
                "apikey": GNEWS_API_KEY,
                "lang": "en",
                "country": "us",  # Can be changed to get news from different countries
                "max": min(max_records, 100),  # Gnews free plan limits to 100 articles
                "from": from_date
            }
            response = requests.get(GNEWS_API_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            # Check for error responses
            if "errors" in data:
                st.error(f"Gnews API error: {data['errors']}")
                return []
                
            articles = data.get("articles", [])
            if not articles:
                st.warning(f"No articles found for query '{query}'. Try broadening the query.")
                return []
                
            # Process articles into the same format as before
            return [
                {
                    "title": a.get("title", "No title"),
                    "url": a.get("url", ""),
                    "source": a.get("source", {}).get("name", "Unknown Source"),
                    "published_at": a.get("publishedAt", ""),
                    "description": a.get("description", "") or "No description available",
                    "image_url": a.get("image", "")
                }
                for a in articles
            ]
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                sleep_time = backoff_factor * (2 ** attempt)
                st.warning(f"Rate limit hit, retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
            elif e.response.status_code == 401:
                st.error("Unauthorized: Invalid Gnews API key. Please check or replace the key.")
                return []
            else:
                st.error(f"Failed to fetch Gnews: {e}")
                return []
        except Exception as e:
            st.error(f"Failed to fetch Gnews: {e}")
            return []
            
    st.error(f"Failed to fetch Gnews after {retries} attempts")
    return []

# Function to translate text using MyMemory Translation API
def translate_text(text, target_lang="fa"):
    """
    Translate text to target language using MyMemory Translation API
    
    Args:
        text: Text to translate
        target_lang: Target language code (default: 'fa' for Persian)
        
    Returns:
        Translated text or fallback translation on failure
    """
    if not text or len(text.strip()) < 1:
        return ""
    
    # Fallback translation in case API fails
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
    fallback_translated = text
    for eng, fa in prefixes.items():
        fallback_translated = fallback_translated.replace(eng.lower(), f"{eng}({fa})")
    fallback_translated = f"{fallback_translated} - ترجمه به فارسی"

    try:
        params = {
            "q": text,
            "langpair": f"en|{target_lang}"
        }
        response = requests.get(MYMEMORY_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("responseStatus") == 200 and data.get("responseData", {}).get("translatedText"):
            translated = data["responseData"]["translatedText"]
            # Remove "IR" if it appears at the start
            translated = translated.replace("IR ", "").strip()
            return translated
        else:
            logger.warning("Translation API returned unexpected response")
            return fallback_translated
    except requests.exceptions.RequestException as e:
        logger.warning(f"Error translating text with MyMemory: {str(e)}")
        return fallback_translated
    except Exception as e:
        logger.warning(f"Unexpected error translating text: {str(e)}")
        return fallback_translated

# Function to display news articles in a nice format with translations
def display_news_articles(articles):
    """Display news articles in a structured format with Persian translations"""
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
            
            # Translate title and description
            with st.spinner(f"Translating: {article['title'][:30]}..."):
                translated_title = translate_text(article["title"])
                translated_description = translate_text(article["description"])
            
            # Display article with translation
            st.markdown(f'<div class="article-section">', unsafe_allow_html=True)
            st.markdown(f'<h3 class="title-link"><a href="{article["url"]}" target="_blank">{article["title"]}</a></h3>', unsafe_allow_html=True)
            st.markdown('<div class="persian-text">**عنوان (فارسی):** ' + translated_title + '</div>', unsafe_allow_html=True)
            st.markdown(f'**Source:** {article["source"]}')
            st.markdown(f'**Published:** {article["published_at"]}')
            
            if article["image_url"]:
                try:
                    st.image(article["image_url"], use_column_width=True)
                except:
                    st.info("Image could not be loaded")
            
            st.markdown('<div class="english-text">**Description (English):** ' + article["description"] + '</div>', unsafe_allow_html=True)
            st.markdown('<div class="persian-text">**توضیحات (فارسی):** ' + translated_description + '</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
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
                
                # Translate title and description
                with st.spinner(f"Translating: {article['title'][:30]}..."):
                    translated_title = translate_text(article["title"])
                    translated_description = translate_text(article["description"])
                
                # Display article with translation
                st.markdown(f'<div class="article-section">', unsafe_allow_html=True)
                st.markdown(f'<h3 class="title-link"><a href="{article["url"]}" target="_blank">{article["title"]}</a></h3>', unsafe_allow_html=True)
                st.markdown('<div class="persian-text">**عنوان (فارسی):** ' + translated_title + '</div>', unsafe_allow_html=True)
                st.markdown(f'**Source:** {article["source"]}')
                st.markdown(f'**Published:** {article["published_at"]}')
                
                if article["image_url"]:
                    try:
                        st.image(article["image_url"], use_column_width=True)
                    except:
                        st.info("Image could not be loaded")
                
                st.markdown('<div class="english-text">**Description (English):** ' + article["description"] + '</div>', unsafe_allow_html=True)
                st.markdown('<div class="persian-text">**توضیحات (فارسی):** ' + translated_description + '</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

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
            articles = fetch_gnews(
                query=query,
                max_records=max_articles,
                days_back=days_back
            )
            
            # Store articles in session state for download
            st.session_state.articles = articles
            
            # Reset selected articles when new search is performed
            st.session_state.selected_articles = []
            
            # Display the articles with translations
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
                if st.button("Send Selected News to Telegram"):
                    with st.spinner("Sending to Telegram..."):
                        success_count = 0
                        fail_count = 0
                        
                        for article in st.session_state.selected_articles:
                            # Since translations are already shown, we just send the English version
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
                            st.warning(f"Failed to send {fail_count) article(s) to Telegram")
            else:
                st.info("Select articles to send to Telegram")

if __name__ == "__main__":
    main()
