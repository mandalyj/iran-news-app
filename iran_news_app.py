# (همه کد قبلی بدون تغییر تا بخش main باقی می‌ماند)

def main():
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
                                # ترجمه پویا با مدیریت خطا
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
