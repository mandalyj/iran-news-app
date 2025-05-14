# ... (بقیه کد بدون تغییر تا تابع main)

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
            st.write("Fetching news started...")
            # Convert dates to string format for APIs
            from_date = start_date.strftime("%Y-%m-%d")
            to_date = end_date.strftime("%Y-%m-%d")
            st.write(f"Fetching news from {from_date} to {to_date}")
            articles = fetch_news(query=query, max_records=max_articles, from_date=from_date, to_date=to_date)
            st.write("Fetch process completed.")
            if articles:
                st.write(f"Fetched {len(articles)} articles. Starting pre-processing...")
                articles = pre_process_articles(articles)  # Pre-process (stock prices only)
                st.write(f"Pre-processing done. Saving {len(articles)} articles to session state...")
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
# ... (بقیه کد بدون تغییر)
