import os
import requests
import streamlit as st
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load API Key and base URLs from environment variables or defaults
AVALAI_API_KEY = os.environ.get("AVALAI_API_KEY", "YOUR_AVALAI_API_KEY")
BASE_URLS = [
    "https://api.avalai.ir/v1",
    "https://api.avalapis.ir/v1"
]

# Headers for API requests
HEADERS = {
    "Authorization": f"Bearer {AVALAI_API_KEY}",
    "Content-Type": "application/json",
    "User-Agent": "TranslateApp/1.0 (Contact: your-email@example.com)"
}

def translate_with_avalai(text, source_lang="en", target_lang="fa", retries=3, backoff_factor=2):
    if not text:
        logger.warning("No text provided for translation")
        return "No text to translate"
    
    if AVALAI_API_KEY == "YOUR_AVALAI_API_KEY":
        logger.error("Avalai API key is not set. Please set the AVALAI_API_KEY environment variable.")
        return text
    
    for base_url in BASE_URLS:
        endpoint = f"{base_url}/chat/completions"
        for attempt in range(retries):
            try:
                logger.info(f"Sending request to {base_url} with model gpt-4.1-nano (Attempt {attempt + 1}/{retries}): {text[:50]}...")
                payload = {
                    "model": "gpt-4.1-nano",
                    "messages": [{"role": "user", "content": f"Translate this text from {source_lang} to {target_lang}: {text}"}],
                    "max_tokens": 500
                }
                response = requests.post(endpoint, headers=HEADERS, json=payload, timeout=30)
                response.raise_for_status()
                data = response.json()
                logger.info(f"Response from {base_url}: {data}")
                if "choices" in data and data["choices"]:
                    translated_text = data["choices"][0]["message"]["content"]
                    logger.info(f"Translated text: {translated_text[:50]}...")
                    return translated_text
                logger.warning(f"No choices in response from {base_url}: {data}")
                return text
            except requests.exceptions.RequestException as e:
                if attempt == retries - 1:
                    logger.error(f"Error with {base_url} after {retries} attempts: {str(e)}")
                    break
                logger.warning(f"Attempt {attempt + 1} failed with {base_url}: {str(e)}. Retrying in {backoff_factor ** attempt} seconds...")
                time.sleep(backoff_factor ** attempt)
    
    logger.error("All API endpoints failed. Returning original text.")
    return text

def main():
    # Streamlit page configuration
    st.set_page_config(page_title="Text Translator", page_icon="🌐", layout="wide")

    # Custom CSS for styling
    st.markdown(
        """
        <style>
        .persian-text { direction: rtl; text-align: right; font-family: "B Nazanin", "Arial Unicode MS", sans-serif; font-size: 16px; }
        .english-text { direction: ltr; text-align: left; font-size: 16px; }
        .section { margin-bottom: 20px; padding: 10px; background-color: #f9f9f9; border-radius: 5px; }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.title("Text Translator (English to Persian)")

    # Input section
    with st.form(key="translate_form"):
        text_to_translate = st.text_area("Enter text to translate (English)", value="", height=150)
        submit_button = st.form_submit_button(label="Translate")

    # Translation section
    if submit_button and text_to_translate:
        with st.spinner("Translating..."):
            translated_text = translate_with_avalai(text_to_translate, source_lang="en", target_lang="fa")
            st.markdown('<div class="section">', unsafe_allow_html=True)
            st.markdown(f'<div class="english-text"><strong>Original Text (English):</strong><br>{text_to_translate}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="persian-text"><strong>Translated Text (Persian):</strong><br>{translated_text}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
    elif submit_button and not text_to_translate:
        st.warning("Please enter some text to translate.")

    # Display logs in the sidebar
    st.sidebar.header("Recent Logs")
    for record in logging.getLogger().handlers[0].records[-10:]:
        st.sidebar.text(f"{record.asctime} - {record.levelname} - {record.message}")

if __name__ == "__main__":
    main()
