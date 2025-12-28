#!/usr/bin/env python3
"""
Streamlit Web Interface for Multi-Site Slides Creator
Supports Socks Studio and Public Domain Review
"""

import streamlit as st
from create_slides import SocksStudioSlidesCreator
import time

# Page configuration
st.set_page_config(
    page_title="Slides Creator",
    layout="centered"
)

# Custom CSS for ultra-compact styling
st.markdown("""
<style>
.block-container {
    padding-top: 3rem;
    padding-bottom: 0rem;
    max-width: 100%;
}
h1 {
    font-size: 1.1rem !important;
    margin: 0 !important;
    padding: 0 !important;
    line-height: 36px !important;
    height: 36px;
}
h2 {
    font-size: 0.95rem !important;
    margin-top: 0.2rem !important;
    margin-bottom: 0.2rem !important;
}
.stAlert {
    margin-top: 0.25rem;
    margin-bottom: 0.25rem;
    padding: 0.35rem 0.6rem;
    font-size: 0.85rem;
}
div[data-testid="stNumberInput"],
div[data-testid="stSelectbox"] {
    margin-bottom: 0 !important;
}
div[data-testid="stNumberInput"] input {
    font-size: 0.9rem !important;
    padding: 0.5rem !important;
    height: 36px !important;
    min-height: 36px !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"] {
    font-size: 0.9rem !important;
    min-height: 36px !important;
    height: 36px !important;
}
div[data-testid="stNumberInput"] > div,
div[data-testid="stSelectbox"] > div {
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}
.stButton button {
    padding: 0.5rem 1rem;
    font-size: 0.9rem;
    margin-top: 0;
    height: 36px !important;
    min-height: 36px !important;
    line-height: 1;
}
div[data-testid="stVerticalBlock"] > div {
    gap: 0.3rem;
}
div[data-testid="stHorizontalBlock"] {
    gap: 0.5rem;
}
hr {
    margin: 0.5rem 0;
}
div[data-testid="column"] {
    display: flex;
    align-items: center;
    padding: 0;
}
p {
    font-size: 0.85rem;
    margin-bottom: 0.3rem;
}
div[data-testid="stProgress"] {
    margin-top: 0.5rem;
    margin-bottom: 0.5rem;
}
div[data-testid="stProgress"] > div {
    height: 4px;
}
</style>
""", unsafe_allow_html=True)

# Initialize session state for cancellation and results
if 'stop_requested' not in st.session_state:
    st.session_state.stop_requested = False
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'results' not in st.session_state:
    st.session_state.results = []

# Single row: Title, Site selector, Count, Buttons
col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 1])

with col1:
    st.markdown("<h1>Slides Creator</h1>", unsafe_allow_html=True)

with col2:
    site = st.selectbox(
        "Site",
        options=['socks-studio', 'public-domain-review'],
        format_func=lambda x: x.replace('-', ' ').title(),
        label_visibility="collapsed"
    )

with col3:
    count = st.number_input(
        "Items",
        min_value=1,
        max_value=100,
        value=10,
        label_visibility="collapsed"
    )

with col4:
    start_button = st.button(
        "Start",
        type="primary",
        disabled=st.session_state.processing,
        use_container_width=True
    )

with col5:
    stop_button = st.button(
        "Stop",
        disabled=not st.session_state.processing,
        use_container_width=True
    )

if stop_button:
    st.session_state.stop_requested = True

st.markdown("<div style='margin-top: 0.75rem;'></div>", unsafe_allow_html=True)

# Quick links section - inline and compact
try:
    # Create creator instance to get links
    with st.spinner("Initializing..."):
        creator = SocksStudioSlidesCreator(site=site)
        creator.authenticate()
        creator.get_or_create_drive_folder()
        creator.get_or_create_catalog_sheet()

    # Compact links in one line
    links = []
    if creator.drive_folder_id:
        folder_url = f"https://drive.google.com/drive/folders/{creator.drive_folder_id}"
        links.append(f'<a href="{folder_url}" target="_blank">Drive Folder</a>')
    if creator.catalog_sheet_id:
        sheet_url = f"https://docs.google.com/spreadsheets/d/{creator.catalog_sheet_id}"
        links.append(f'<a href="{sheet_url}" target="_blank">Catalog</a>')

    if links:
        st.markdown("<div style='font-size: 0.9rem;'>" + " • ".join(links) + "</div>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Error: {str(e)}")
    st.stop()

st.markdown("---")

# Processing logic
if start_button:
    st.session_state.stop_requested = False
    st.session_state.processing = True
    st.session_state.results = []

    progress_bar = st.progress(0)
    status_text = st.empty()
    results_container = st.container()

    try:
        # Fetch URLs
        with st.spinner("Fetching URLs..."):
            status_text.info("Fetching URLs...")
            article_urls = creator.get_article_urls()

        # Filter unprocessed
        status_text.info("Filtering processed items...")
        unprocessed_urls = []
        for url in article_urls:
            if not creator.is_article_processed(url):
                unprocessed_urls.append(url)
                if len(unprocessed_urls) >= count:
                    break

        total = len(unprocessed_urls)

        if total == 0:
            st.warning("No unprocessed items found")
            st.session_state.processing = False
            st.stop()

        status_text.success(f"Found {total} items")
        time.sleep(0.5)

        # Process each item
        for idx, url in enumerate(unprocessed_urls):
            if st.session_state.stop_requested:
                status_text.warning("Processing stopped")
                break

            # Update progress
            progress = (idx + 1) / total
            progress_bar.progress(progress)
            url_short = url.split('/')[-2] if len(url.split('/')) > 2 else url
            status_text.info(f"Processing {idx + 1}/{total}: {url_short}")

            # Process article
            try:
                result = creator.process_article(url)
                st.session_state.results.append(result)

                # Display compact result
                with results_container:
                    info_parts = [
                        f"[{result['title']}]({result['presentation_url']})",
                        f"{result['slide_count']} slides",
                        f"{result.get('author', 'Unknown')}"
                    ]
                    st.success(" • ".join(info_parts))

            except Exception as e:
                with results_container:
                    st.error(f"Error: {url_short} - {str(e)}")

            # Small delay between items
            time.sleep(0.3)

        # Final status
        progress_bar.progress(1.0)
        if st.session_state.results:
            total_slides = sum(r['slide_count'] for r in st.session_state.results)
            status_text.success(f"Complete: {len(st.session_state.results)}/{total} items • {total_slides} slides")
        else:
            status_text.warning("Completed with errors")

    except Exception as e:
        st.error(f"Error: {str(e)}")

    finally:
        st.session_state.processing = False
        st.session_state.stop_requested = False
