#!/usr/bin/env python3
"""
Creates Google Slides presentations from Socks Studio articles
One presentation per article, with one slide per image
"""

import os
import re
import sys
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pathlib import Path
from anthropic import Anthropic
import json
from datetime import datetime

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pickle

# Google API scopes
SCOPES = ['https://www.googleapis.com/auth/presentations',
          'https://www.googleapis.com/auth/drive',
          'https://www.googleapis.com/auth/spreadsheets']

class SocksStudioSlidesCreator:
    def __init__(self, site='socks-studio'):
        self.site = site  # 'socks-studio' or 'public-domain-review'

        # Set base URL based on site
        if self.site == 'socks-studio':
            self.base_url = "https://socks-studio.com"
        elif self.site == 'public-domain-review':
            self.base_url = "https://publicdomainreview.org"
        else:
            raise ValueError(f"Unknown site: {site}")

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.slides_service = None
        self.drive_service = None
        self.sheets_service = None
        self.credentials_path = Path('credentials.json')
        self.token_path = Path('token.pickle')
        self.anthropic_key_path = Path('anthropic_api_key.txt')
        self.tracking_file = Path(f'processed_articles_{self.site}.json')
        self.drive_folder_id = None  # Will be set after authentication
        self.catalog_sheet_id = None  # Will be set after creating/finding catalog

        # Initialize Anthropic client for metadata enhancement
        # Try to read from file first, then fall back to environment variable
        api_key = None
        if self.anthropic_key_path.exists():
            api_key = self.anthropic_key_path.read_text().strip()
        else:
            api_key = os.environ.get('ANTHROPIC_API_KEY')

        self.anthropic_client = Anthropic(api_key=api_key) if api_key else None

    def authenticate(self):
        """Authenticate with Google API"""
        creds = None

        # Load existing token
        if self.token_path.exists():
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)

        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("Refreshing credentials...")
                creds.refresh(Request())
            else:
                if not self.credentials_path.exists():
                    print("\n" + "="*60)
                    print("ERROR: credentials.json not found!")
                    print("="*60)
                    print("\nTo set up Google Slides API:")
                    print("1. Go to: https://console.cloud.google.com/")
                    print("2. Create a new project or select existing")
                    print("3. Enable Google Slides API and Google Drive API")
                    print("4. Create OAuth 2.0 credentials (Desktop app)")
                    print("5. Download credentials.json to this directory")
                    print("\nDetailed instructions:")
                    print("https://developers.google.com/slides/api/quickstart/python")
                    print("="*60)
                    sys.exit(1)

                print("Starting authentication flow...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), SCOPES)
                creds = flow.run_local_server(port=0)

            # Save credentials
            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)

        # Build services
        self.slides_service = build('slides', 'v1', credentials=creds)
        self.drive_service = build('drive', 'v3', credentials=creds)
        self.sheets_service = build('sheets', 'v4', credentials=creds)
        print("✓ Authentication successful!")

    def get_or_create_drive_folder(self, folder_name=None):
        """Get or create a Google Drive folder for presentations"""
        if folder_name is None:
            folder_name = self.site

        # Search for existing folder
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = self.drive_service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute()

        folders = results.get('files', [])

        if folders:
            folder_id = folders[0]['id']
            print(f"✓ Found existing folder: '{folder_name}' (ID: {folder_id})")
        else:
            # Create new folder
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = self.drive_service.files().create(
                body=folder_metadata,
                fields='id, name'
            ).execute()
            folder_id = folder['id']
            print(f"✓ Created new folder: '{folder_name}' (ID: {folder_id})")

        self.drive_folder_id = folder_id
        return folder_id

    def move_presentation_to_folder(self, presentation_id, folder_id):
        """Move a presentation into a specific Drive folder"""
        # Get current parents
        file = self.drive_service.files().get(
            fileId=presentation_id,
            fields='parents'
        ).execute()

        previous_parents = ','.join(file.get('parents', []))

        # Move to new folder
        self.drive_service.files().update(
            fileId=presentation_id,
            addParents=folder_id,
            removeParents=previous_parents,
            fields='id, parents'
        ).execute()

    def load_processed_articles(self):
        """Load the tracking file of processed articles"""
        if self.tracking_file.exists():
            with open(self.tracking_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_processed_article(self, article_url, presentation_data):
        """Save a processed article to the tracking file"""
        processed = self.load_processed_articles()
        processed[article_url] = {
            'presentation_id': presentation_data['presentation_id'],
            'presentation_url': presentation_data['presentation_url'],
            'title': presentation_data['title'],
            'author': presentation_data.get('author', 'Unknown'),
            'year': presentation_data.get('year', 'Unknown'),
            'medium': presentation_data.get('medium', 'Unknown'),
            'keywords': presentation_data.get('keywords', ''),
            'slide_count': presentation_data['slide_count'],
            'processed_date': datetime.now().isoformat()
        }
        with open(self.tracking_file, 'w', encoding='utf-8') as f:
            json.dump(processed, f, indent=2, ensure_ascii=False)

    def is_article_processed(self, article_url):
        """Check if an article has already been processed"""
        processed = self.load_processed_articles()
        return article_url in processed

    def get_or_create_catalog_sheet(self):
        """Get or create a Google Sheets catalog for all presentations"""
        # Create site-specific catalog name
        catalog_name = f"{self.site.replace('-', ' ').title()} Presentations Catalog"

        # Search for existing catalog
        query = f"name='{catalog_name}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
        results = self.drive_service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute()

        sheets = results.get('files', [])

        if sheets:
            sheet_id = sheets[0]['id']
            print(f"✓ Found existing catalog spreadsheet (ID: {sheet_id})")
            self.catalog_sheet_id = sheet_id
            return sheet_id
        else:
            # Create new spreadsheet
            spreadsheet = {
                'properties': {
                    'title': catalog_name
                },
                'sheets': [{
                    'properties': {
                        'title': 'Presentations',
                        'gridProperties': {
                            'frozenRowCount': 1
                        }
                    }
                }]
            }
            spreadsheet = self.sheets_service.spreadsheets().create(
                body=spreadsheet,
                fields='spreadsheetId'
            ).execute()
            sheet_id = spreadsheet['spreadsheetId']

            # Move to socks-studio folder
            if self.drive_folder_id:
                self.move_presentation_to_folder(sheet_id, self.drive_folder_id)

            # Add headers
            headers = [['Article URL', 'Presentation URL', 'Title', 'Author', 'Year', 'Medium', 'Keywords', 'Slides', 'Processed Date']]
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range='Presentations!A1:I1',
                valueInputOption='RAW',
                body={'values': headers}
            ).execute()

            # Format headers
            requests = [{
                'repeatCell': {
                    'range': {
                        'sheetId': 0,
                        'startRowIndex': 0,
                        'endRowIndex': 1
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'backgroundColor': {'red': 0.2, 'green': 0.2, 'blue': 0.2},
                            'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}}
                        }
                    },
                    'fields': 'userEnteredFormat(backgroundColor,textFormat)'
                }
            }]
            self.sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body={'requests': requests}
            ).execute()

            print(f"✓ Created new catalog spreadsheet (ID: {sheet_id})")

        self.catalog_sheet_id = sheet_id
        return sheet_id

    def add_to_catalog(self, article_url, presentation_data):
        """Add a presentation entry to the catalog spreadsheet"""
        if not self.catalog_sheet_id:
            return

        row = [[
            article_url,
            presentation_data['presentation_url'],
            presentation_data['title'],
            presentation_data.get('author', 'Unknown'),
            presentation_data.get('year', 'Unknown'),
            presentation_data.get('medium', 'Unknown'),
            presentation_data.get('keywords', ''),
            str(presentation_data['slide_count']),
            presentation_data.get('processed_date', datetime.now().isoformat())
        ]]

        self.sheets_service.spreadsheets().values().append(
            spreadsheetId=self.catalog_sheet_id,
            range='Presentations!A:I',
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body={'values': row}
        ).execute()

    def _get_socks_studio_urls(self, limit=None):
        """Get article URLs from Socks Studio homepage (most recent first)"""
        print("Fetching Socks Studio article URLs...")
        article_urls = []

        page = 1
        while True:
            if page == 1:
                url = self.base_url
            else:
                url = f"{self.base_url}/page/{page}/"

            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
            except Exception as e:
                print(f"Error fetching page {page}: {e}")
                break

            soup = BeautifulSoup(response.text, 'html.parser')
            articles = soup.find_all('article')

            if not articles:
                break

            for article in articles:
                h2 = article.find('h2')
                if h2:
                    link = h2.find('a')
                    if link and link.get('href'):
                        article_url = urljoin(self.base_url, link['href'])
                        if article_url not in article_urls:
                            article_urls.append(article_url)
                            if limit and len(article_urls) >= limit:
                                return article_urls

            page += 1
            if page > 50:  # Safety limit
                break

            time.sleep(0.5)

        return article_urls

    def _get_public_domain_urls(self, limit=None):
        """Get collection URLs from Public Domain Review image collections"""
        print("Fetching Public Domain Review collection URLs...")
        collection_urls = []

        # PDR has 23 pages of image collections, 24 per page
        max_pages = 23
        for page in range(1, max_pages + 1):
            url = f"{self.base_url}/collections/images/{page}/"

            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
            except Exception as e:
                print(f"Error fetching page {page}: {e}")
                break

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find collection links: <a href="/collection/[slug]/">
            links = soup.find_all('a', href=re.compile(r'^/collection/[^/]+/$'))

            if not links:
                break

            for link in links:
                href = link.get('href')
                if href:
                    collection_url = urljoin(self.base_url, href)
                    if collection_url not in collection_urls:
                        collection_urls.append(collection_url)
                        if limit and len(collection_urls) >= limit:
                            return collection_urls

            time.sleep(0.5)

        return collection_urls

    def get_article_urls(self, limit=None):
        """Get article/collection URLs (dispatches to site-specific method)"""
        if self.site == 'socks-studio':
            return self._get_socks_studio_urls(limit)
        elif self.site == 'public-domain-review':
            return self._get_public_domain_urls(limit)
        else:
            raise ValueError(f"Unknown site: {self.site}")

    def enhance_metadata_with_llm(self, soup, existing_metadata):
        """Use Claude to extract missing date/medium and keywords from article text"""
        if not self.anthropic_client:
            return None

        # Extract article text
        content_div = soup.find('article') or soup.find('div', class_='entry-content') or soup.body
        if not content_div:
            return None

        # Get text content (limit to first 3000 chars to stay within reasonable token limits)
        article_text = content_div.get_text(separator='\n', strip=True)[:3000]

        try:
            message = self.anthropic_client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": f"""Read this article excerpt and extract information about the artwork/project discussed.

Article title: {existing_metadata['title']}
Article text excerpt:
{article_text}

Please extract:
1. The artist/creator name (the person whose work is featured, NOT the article author)
2. The year or date when the artwork/project was created (not when the article was published)
3. The medium or type of work (e.g., "Photography", "Architecture", "Drawing", "Installation", etc.)
4. 3-5 keywords or tags that describe the main topics/themes (e.g., "urban landscape", "abstract geometry", "vernacular architecture")

Respond in this exact format:
Artist: [artist/creator name or "Unknown" if not found]
Year: [year or "Unknown" if not found]
Medium: [medium or "Unknown" if not found]
Keywords: [comma-separated keywords, or "Unknown" if not found]

Only include information that is explicitly stated in the text. Be concise."""
                }]
            )

            # Parse response
            response_text = message.content[0].text
            result = {}

            # Extract artist
            artist_match = re.search(r'Artist:\s*(.+?)(?:\n|$)', response_text)
            if artist_match and artist_match.group(1).strip() not in ['Unknown', 'unknown']:
                result['author'] = artist_match.group(1).strip()

            # Extract year
            year_match = re.search(r'Year:\s*(\d{4}|Unknown)', response_text)
            if year_match and year_match.group(1) != 'Unknown':
                result['year'] = year_match.group(1)

            # Extract medium
            medium_match = re.search(r'Medium:\s*(.+?)(?:\n|$)', response_text)
            if medium_match and medium_match.group(1).strip() != 'Unknown':
                result['medium'] = medium_match.group(1).strip()

            # Extract keywords
            keywords_match = re.search(r'Keywords:\s*(.+?)(?:\n|$)', response_text, re.IGNORECASE)
            if keywords_match and keywords_match.group(1).strip() not in ['Unknown', 'unknown']:
                result['keywords'] = keywords_match.group(1).strip()

            return result

        except Exception as e:
            print(f"    LLM enhancement failed: {e}")
            return None

    def parse_figcaption(self, caption_text, fallback_metadata):
        """Parse figcaption to extract artwork-specific metadata

        Common formats:
        - "Artist, Title, Year medium"
        - "Artist, Title, medium, Year"
        """
        result = {}

        if not caption_text:
            return result

        # Try to parse format: "Artist, Title, Year medium"
        parts = [p.strip() for p in caption_text.split(',')]

        if len(parts) >= 2:
            # First part is likely artist name
            result['artist'] = parts[0]

            # Rest is title + possibly year/medium
            title_and_more = ', '.join(parts[1:])

            # Try to extract year (4 digits)
            year_match = re.search(r'\b(1\d{3}|20\d{2})\b', title_and_more)
            if year_match:
                result['year'] = year_match.group(1)
                # Remove year from title
                title_and_more = title_and_more.replace(year_match.group(0), '').strip()

            # What's left after removing year is likely title + medium
            # Medium is usually the last word(s) after year
            remaining = title_and_more.split(',')
            if remaining:
                result['title'] = remaining[0].strip()
                if len(remaining) > 1:
                    result['medium'] = remaining[-1].strip()
            else:
                result['title'] = title_and_more.strip()

        return result

    def _extract_socks_studio_data(self, url):
        """Extract metadata and images from a Socks Studio article"""
        print(f"\nProcessing: {url}")

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"Error fetching article: {e}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract metadata
        metadata = {
            'author': 'Unknown',
            'title': 'Unknown',
            'year': 'Unknown',
            'medium': 'Unknown',
            'article_url': url
        }

        # Try JSON-LD schema
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_ld_scripts:
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict):
                    if 'author' in data:
                        if isinstance(data['author'], dict):
                            metadata['author'] = data['author'].get('name', 'Unknown')
                    if 'headline' in data:
                        metadata['title'] = data['headline']
                    elif 'name' in data:
                        metadata['title'] = data['name']
                    if 'datePublished' in data:
                        date_match = re.search(r'(\d{4})', data['datePublished'])
                        if date_match:
                            metadata['year'] = date_match.group(1)
                    if 'keywords' in data:
                        metadata['medium'] = data['keywords']
            except:
                pass

        # Fallback to HTML parsing
        if metadata['title'] == 'Unknown':
            title_tag = soup.find('h1') or soup.find('h2')
            if title_tag:
                metadata['title'] = title_tag.get_text(strip=True)

        # Don't extract blog post author - we want the artist/creator name instead
        # which will be extracted by LLM

        # Find images with their captions
        images = []
        content_div = soup.find('article') or soup.find('div', class_='entry-content') or soup.body

        if content_div:
            # Look for figure elements (which contain img + figcaption)
            figures = content_div.find_all('figure')
            for figure in figures:
                img = figure.find('img')
                if not img:
                    continue

                # Check multiple possible image URL attributes (lazy loading support)
                img_url = img.get('data-original') or img.get('src') or img.get('data-src')
                if not img_url:
                    continue

                img_url = urljoin(url, img_url)

                # Filter tiny images
                if 'icon' in img_url.lower() or 'logo' in img_url.lower():
                    continue

                width = img.get('width')
                height = img.get('height')
                if width and height:
                    try:
                        if int(width) < 50 or int(height) < 50:
                            continue
                    except:
                        pass

                if '-150x150' in img_url or '-300x' in img_url or 'thumbnail' in img_url:
                    continue

                # Check if image is accessible and size
                try:
                    head = self.session.head(img_url, timeout=5, allow_redirects=True)
                    content_length = head.headers.get('content-length')
                    if content_length and int(content_length) < 5000:
                        continue
                except:
                    pass

                # Extract figcaption
                figcaption = figure.find('figcaption')
                caption_text = figcaption.get_text(strip=True) if figcaption else ''

                # Parse figcaption for artwork metadata
                # Format is usually: "Artist, Title, Year medium"
                artwork_metadata = self.parse_figcaption(caption_text, metadata)

                # Use collection-level metadata as fallback when per-image data is missing
                artist = artwork_metadata.get('artist') if artwork_metadata.get('artist') and artwork_metadata.get('artist') != 'Unknown' else metadata.get('author', 'Unknown')
                title = artwork_metadata.get('title') if artwork_metadata.get('title') and artwork_metadata.get('title') != 'Unknown' else metadata.get('title', 'Unknown')
                year = artwork_metadata.get('year') if artwork_metadata.get('year') and artwork_metadata.get('year') != 'Unknown' else metadata.get('year', 'Unknown')
                medium = artwork_metadata.get('medium') if artwork_metadata.get('medium') and artwork_metadata.get('medium') != 'Unknown' else metadata.get('medium', 'Unknown')

                images.append({
                    'url': img_url,
                    'caption': caption_text,
                    'artist': artist,
                    'title': title,
                    'year': year,
                    'medium': medium
                })

        # Remove duplicates while preserving order (based on URL)
        seen = set()
        unique_images = []
        for img in images:
            if img['url'] not in seen:
                seen.add(img['url'])
                unique_images.append(img)
        images = unique_images

        print(f"Found {len(images)} images")

        # Enhance metadata with LLM if author, year, medium is missing, or to extract keywords
        if self.anthropic_client and (metadata['author'] == 'Unknown' or metadata['year'] == 'Unknown' or metadata['medium'] == 'Unknown' or 'keywords' not in metadata):
            print("  Enhancing metadata with LLM...")
            enhanced_metadata = self.enhance_metadata_with_llm(soup, metadata)
            if enhanced_metadata:
                if metadata['author'] == 'Unknown' and enhanced_metadata.get('author'):
                    metadata['author'] = enhanced_metadata['author']
                    print(f"    Found artist: {metadata['author']}")
                if metadata['year'] == 'Unknown' and enhanced_metadata.get('year'):
                    metadata['year'] = enhanced_metadata['year']
                    print(f"    Found year: {metadata['year']}")
                if metadata['medium'] == 'Unknown' and enhanced_metadata.get('medium'):
                    metadata['medium'] = enhanced_metadata['medium']
                    print(f"    Found medium: {metadata['medium']}")
                if enhanced_metadata.get('keywords'):
                    metadata['keywords'] = enhanced_metadata['keywords']
                    print(f"    Found keywords: {metadata['keywords']}")

            # Update image data with enhanced metadata
            for img in images:
                if img['artist'] == 'Unknown' and metadata.get('author') != 'Unknown':
                    img['artist'] = metadata['author']
                if img['medium'] == 'Unknown' and metadata.get('medium') != 'Unknown':
                    img['medium'] = metadata['medium']
                if img['year'] == 'Unknown' and metadata.get('year') != 'Unknown':
                    img['year'] = metadata['year']

        return {
            'metadata': metadata,
            'images': images
        }

    def _extract_public_domain_data(self, url):
        """Extract metadata and images from a Public Domain Review collection"""
        print(f"\nProcessing collection: {url}")

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"Error fetching collection: {e}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract metadata
        metadata = {
            'author': 'Unknown',  # Curator
            'title': 'Unknown',
            'year': 'Unknown',
            'medium': 'Unknown',
            'article_url': url
        }

        # Try JSON-LD schema first
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    if 'headline' in data:
                        metadata['title'] = data['headline']
                    elif 'name' in data:
                        metadata['title'] = data['name']
                    if 'author' in data:
                        if isinstance(data['author'], dict):
                            metadata['author'] = data['author'].get('name', 'Unknown')
                        elif isinstance(data['author'], list) and len(data['author']) > 0:
                            if isinstance(data['author'][0], dict):
                                metadata['author'] = data['author'][0].get('name', 'Unknown')
            except:
                pass

        # Fallback to HTML parsing for title
        if metadata['title'] == 'Unknown':
            # Try article title or h1
            title_tag = soup.find('h1', class_='collection__title') or soup.find('h1')
            if title_tag:
                metadata['title'] = title_tag.get_text(strip=True)

        # Extract artist from title (patterns like "Artist's Works" or "Title: Artist's Works")
        if metadata['author'] == 'Unknown' and metadata['title'] != 'Unknown':
            # Pattern 1: Look for "Name's" possessive pattern
            # Match any sequence of words (including accented chars) followed by 's
            # Handle both straight (') and curly (') apostrophes
            possessive_match = re.search(r"([A-ZÀ-ÿ][A-Za-zÀ-ÿ\s]+)['\u2019]s\s+", metadata['title'])
            if possessive_match:
                # Get the name before "'s"
                potential_artist = possessive_match.group(1).strip()
                metadata['author'] = potential_artist
            else:
                # Pattern 2: Try to extract name before parentheses
                # E.g., "Artist Name (dates)" -> "Artist Name"
                before_paren = metadata['title'].split('(')[0].strip()
                # If it looks like a name (2-4 words, not too long)
                words = before_paren.split()
                if 2 <= len(words) <= 4 and len(before_paren) < 50:
                    metadata['author'] = before_paren

        # Extract year from title (often in format "Title (ca. 1920s)" or "Title (1985)")
        if '(' in metadata['title'] and ')' in metadata['title']:
            year_match = re.search(r'\(([^\)]*\d{4}[^\)]*)\)', metadata['title'])
            if year_match:
                metadata['year'] = year_match.group(1)

        # Find all images in the collection
        images = []

        # PDR uses a gallery structure: <div class="collection__gallery">
        gallery = soup.find('div', class_='collection__gallery')

        if gallery:
            # Find all img tags within the gallery
            img_tags = gallery.find_all('img')

            for img in img_tags:
                # Get image URL
                img_url = img.get('src') or img.get('data-src')
                if not img_url:
                    continue

                img_url = urljoin(url, img_url)

                # Filter tiny images
                if 'icon' in img_url.lower() or 'logo' in img_url.lower():
                    continue

                # Skip if URL contains width parameter < 200px
                if 'width=' in img_url and re.search(r'width=(\d+)', img_url):
                    width_match = re.search(r'width=(\d+)', img_url)
                    if width_match and int(width_match.group(1)) < 200:
                        continue

                # Try to find caption in parent button or nearby elements
                # PDR structure: <button class="collection__gallery__image">
                caption_text = ''
                button = img.find_parent('button', class_='collection__gallery__image')
                if button:
                    # Look for aria-label or title attribute
                    caption_text = button.get('aria-label', '') or button.get('title', '')

                # If no caption found, try to extract from image alt text
                if not caption_text:
                    caption_text = img.get('alt', '')

                # Parse caption for artist, title, year
                artwork_metadata = self.parse_figcaption(caption_text, metadata)

                # For PDR, use collection-level metadata as fallback
                # since individual images don't have detailed captions
                artist = artwork_metadata.get('artist') if artwork_metadata.get('artist') and artwork_metadata.get('artist') != 'Unknown' else metadata.get('author', 'Unknown')
                title = artwork_metadata.get('title') if artwork_metadata.get('title') and artwork_metadata.get('title') != 'Unknown' else metadata.get('title', '')
                year = artwork_metadata.get('year') if artwork_metadata.get('year') and artwork_metadata.get('year') != 'Unknown' else metadata.get('year', 'Unknown')
                medium = artwork_metadata.get('medium') if artwork_metadata.get('medium') and artwork_metadata.get('medium') != 'Unknown' else metadata.get('medium', 'Unknown')

                images.append({
                    'url': img_url,
                    'caption': caption_text,
                    'artist': artist,
                    'title': title,
                    'year': year,
                    'medium': medium
                })

        # Remove duplicates while preserving order
        seen = set()
        unique_images = []
        for img in images:
            if img['url'] not in seen:
                seen.add(img['url'])
                unique_images.append(img)
        images = unique_images

        print(f"Found {len(images)} images")

        # Set medium to 'Images' for PDR collections
        if metadata['medium'] == 'Unknown':
            metadata['medium'] = 'Images'

        # Use LLM for keywords extraction if available
        if self.anthropic_client and 'keywords' not in metadata:
            print("  Extracting keywords with LLM...")
            enhanced_metadata = self.enhance_metadata_with_llm(soup, metadata)
            if enhanced_metadata and enhanced_metadata.get('keywords'):
                metadata['keywords'] = enhanced_metadata['keywords']
                print(f"    Found keywords: {metadata['keywords']}")

        # Update image data with finalized metadata
        for img in images:
            if img['medium'] == 'Unknown' and metadata.get('medium') != 'Unknown':
                img['medium'] = metadata['medium']

        return {
            'metadata': metadata,
            'images': images
        }

    def extract_article_data(self, url):
        """Extract metadata and images (dispatches to site-specific method)"""
        if self.site == 'socks-studio':
            return self._extract_socks_studio_data(url)
        elif self.site == 'public-domain-review':
            return self._extract_public_domain_data(url)
        else:
            raise ValueError(f"Unknown site: {self.site}")

    def create_presentation(self, article_data):
        """Create a Google Slides presentation for an article"""
        metadata = article_data['metadata']
        images = article_data['images']

        if not images:
            print("No images to create slides from")
            return None

        # Create presentation
        presentation_title = metadata['title'][:100]  # Limit title length
        print(f"\nCreating presentation: {presentation_title}")

        try:
            presentation = self.slides_service.presentations().create(
                body={'title': presentation_title}
            ).execute()

            presentation_id = presentation['presentationId']
            print(f"✓ Created presentation ID: {presentation_id}")
            print(f"  URL: https://docs.google.com/presentation/d/{presentation_id}")

            # Delete the default blank slide
            requests_list = []
            if presentation.get('slides'):
                first_slide_id = presentation['slides'][0]['objectId']
                requests_list.append({
                    'deleteObject': {
                        'objectId': first_slide_id
                    }
                })

            # Create slides for each image
            for idx, img_data in enumerate(images):
                print(f"  Adding slide {idx + 1}/{len(images)}...")

                # Create slide
                slide_id = f'slide_{idx}'
                requests_list.append({
                    'createSlide': {
                        'objectId': slide_id,
                        'slideLayoutReference': {
                            'predefinedLayout': 'BLANK'
                        }
                    }
                })

                # Set black background
                requests_list.append({
                    'updatePageProperties': {
                        'objectId': slide_id,
                        'fields': 'pageBackgroundFill',
                        'pageProperties': {
                            'pageBackgroundFill': {
                                'solidFill': {
                                    'color': {
                                        'rgbColor': {
                                            'red': 0.0,
                                            'green': 0.0,
                                            'blue': 0.0
                                        }
                                    }
                                }
                            }
                        }
                    }
                })

                # Add image centered at top (no spacing)
                # Slide: 10" x 5.625" (9144000 x 5143500 EMU) - Widescreen 16:9
                # Reserve 0.6" for caption at bottom
                # Available height: 5.625" - 0.6" = 5.025"
                # Image box: 9" wide x 5.025" tall (allows landscape images to extend)
                # Portrait images will be constrained by height and centered within
                # Landscape images will use more width with height at 5.025"
                # Centered horizontally: (10" - 9") / 2 = 0.5" = 457200 EMU
                image_id = f'image_{idx}'
                requests_list.append({
                    'createImage': {
                        'objectId': image_id,
                        'url': img_data['url'],
                        'elementProperties': {
                            'pageObjectId': slide_id,
                            'size': {
                                'width': {'magnitude': 8229600, 'unit': 'EMU'},   # 9" wide (allows landscape)
                                'height': {'magnitude': 4594860, 'unit': 'EMU'}   # 5.025" height constraint
                            },
                            'transform': {
                                'scaleX': 1,
                                'scaleY': 1,
                                'translateX': 457200,  # Center horizontally: 0.5" from edge
                                'translateY': 0,       # Top of slide (no spacing)
                                'unit': 'EMU'
                            }
                        }
                    }
                })

                # Add caption text box (aligned to bottom of slide)
                # Use per-image metadata (from figcaption) instead of article-level metadata
                textbox_id = f'textbox_{idx}'
                caption_parts = []
                if img_data['artist'] and img_data['artist'] != 'Unknown':
                    caption_parts.append(img_data['artist'])
                if img_data['title'] and img_data['title'] != 'Unknown':
                    caption_parts.append(img_data['title'])

                # Combine medium and year on same line if both exist
                meta_line = []
                if img_data['medium'] and img_data['medium'] != 'Unknown':
                    meta_line.append(img_data['medium'])
                if img_data['year'] and img_data['year'] != 'Unknown':
                    meta_line.append(img_data['year'])
                if meta_line:
                    caption_parts.append(', '.join(meta_line))

                caption_text = '\n'.join(caption_parts) if caption_parts else 'Untitled'

                # Caption box directly below image (no spacing)
                # Position Y: 5.025" (directly after image) = 4594860 EMU
                # Width: 7.5" (leave room for link on right)
                # Height: 0.6" (548640 EMU)
                requests_list.append({
                    'createShape': {
                        'objectId': textbox_id,
                        'shapeType': 'TEXT_BOX',
                        'elementProperties': {
                            'pageObjectId': slide_id,
                            'size': {
                                'width': {'magnitude': 6858000, 'unit': 'EMU'},   # 7.5" (leave room for link)
                                'height': {'magnitude': 548640, 'unit': 'EMU'}    # 0.6"
                            },
                            'transform': {
                                'scaleX': 1,
                                'scaleY': 1,
                                'translateX': 0,          # No left margin
                                'translateY': 4594860,    # Directly below 5.025" image
                                'unit': 'EMU'
                            }
                        }
                    }
                })

                # Insert caption text
                requests_list.append({
                    'insertText': {
                        'objectId': textbox_id,
                        'text': caption_text
                    }
                })

                # Style the caption text (9pt font, light gray on black)
                requests_list.append({
                    'updateTextStyle': {
                        'objectId': textbox_id,
                        'fields': 'fontSize,foregroundColor',
                        'style': {
                            'fontSize': {
                                'magnitude': 9,
                                'unit': 'PT'
                            },
                            'foregroundColor': {
                                'opaqueColor': {
                                    'rgbColor': {
                                        'red': 0.85,
                                        'green': 0.85,
                                        'blue': 0.85
                                    }
                                }
                            }
                        },
                        'textRange': {'type': 'ALL'}
                    }
                })

                # Align caption text to bottom of text box
                requests_list.append({
                    'updateShapeProperties': {
                        'objectId': textbox_id,
                        'fields': 'contentAlignment',
                        'shapeProperties': {
                            'contentAlignment': 'BOTTOM'
                        }
                    }
                })

                # Add link to Socks-studio (right side, aligned with caption)
                # Position X: 7.5" (right of caption box) = 6858000 EMU
                # Position Y: 5.025" (aligned with caption) = 4594860 EMU
                # Width: 2.5" (remaining space to right edge at 10")
                # Height: 0.6" = 548640 EMU
                link_id = f'link_{idx}'
                requests_list.append({
                    'createShape': {
                        'objectId': link_id,
                        'shapeType': 'TEXT_BOX',
                        'elementProperties': {
                            'pageObjectId': slide_id,
                            'size': {
                                'width': {'magnitude': 2286000, 'unit': 'EMU'},   # 2.5"
                                'height': {'magnitude': 548640, 'unit': 'EMU'}    # Match caption height (0.6")
                            },
                            'transform': {
                                'scaleX': 1,
                                'scaleY': 1,
                                'translateX': 6858000,  # 7.5" from left (after caption box)
                                'translateY': 4594860,  # Align with caption
                                'unit': 'EMU'
                            }
                        }
                    }
                })

                requests_list.append({
                    'insertText': {
                        'objectId': link_id,
                        'text': 'Socks-studio'
                    }
                })

                # Style and add hyperlink (9pt font, dark gray on black)
                requests_list.append({
                    'updateTextStyle': {
                        'objectId': link_id,
                        'fields': 'link,fontSize,foregroundColor',
                        'style': {
                            'link': {
                                'url': metadata['article_url']
                            },
                            'fontSize': {
                                'magnitude': 9,
                                'unit': 'PT'
                            },
                            'foregroundColor': {
                                'opaqueColor': {
                                    'rgbColor': {
                                        'red': 0.6,
                                        'green': 0.6,
                                        'blue': 0.6
                                    }
                                }
                            }
                        },
                        'textRange': {'type': 'ALL'}
                    }
                })

                # Right-align the link text
                requests_list.append({
                    'updateParagraphStyle': {
                        'objectId': link_id,
                        'fields': 'alignment',
                        'style': {
                            'alignment': 'END'
                        },
                        'textRange': {'type': 'ALL'}
                    }
                })

                # Align link text to bottom of text box
                requests_list.append({
                    'updateShapeProperties': {
                        'objectId': link_id,
                        'fields': 'contentAlignment',
                        'shapeProperties': {
                            'contentAlignment': 'BOTTOM'
                        }
                    }
                })

            # Execute all requests
            if requests_list:
                self.slides_service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={'requests': requests_list}
                ).execute()

            print(f"✓ Successfully created {len(images)} slides!")
            return presentation_id

        except HttpError as error:
            print(f"Error creating presentation: {error}")
            return None

    def run_interactive(self):
        """Run in interactive mode - process one article at a time"""
        print("="*60)
        print("Socks Studio → Google Slides Creator")
        print("="*60)

        # Authenticate
        self.authenticate()

        # Get article URLs (most recent first)
        print("\nFetching article list...")
        article_urls = self.get_article_urls()
        print(f"Found {len(article_urls)} articles")

        # Process articles one at a time
        for i, article_url in enumerate(article_urls, 1):
            print(f"\n{'='*60}")
            print(f"Article {i}/{len(article_urls)}")
            print(f"{'='*60}")

            # Extract article data
            article_data = self.extract_article_data(article_url)

            if not article_data or not article_data['images']:
                print("Skipping (no valid images)")
                continue

            # Create presentation
            presentation_id = self.create_presentation(article_data)

            if not presentation_id:
                print("Failed to create presentation")
                continue

            # Ask for approval before continuing
            print(f"\n{'='*60}")
            print("Presentation created successfully!")
            print(f"View at: https://docs.google.com/presentation/d/{presentation_id}")
            print(f"{'='*60}")

            if i < len(article_urls):
                response = input(f"\nProceed to next article? (y/n/q to quit): ").strip().lower()
                if response == 'q' or response == 'n':
                    print("Stopped by user")
                    break
                elif response != 'y':
                    print("Invalid response. Stopping.")
                    break

            time.sleep(1)  # Be respectful to APIs

        print(f"\n{'='*60}")
        print("Done!")
        print(f"{'='*60}")


    def process_article(self, url):
        """Process a single article/collection and return results

        This method is designed for Streamlit interruptibility - it processes
        one article/collection at a time and returns structured data.

        Args:
            url: Article or collection URL to process

        Returns:
            dict with presentation data, or raises Exception on error
        """
        # Extract article data
        article_data = self.extract_article_data(url)

        if not article_data or not article_data['images']:
            raise Exception(f"No images found at {url}")

        # Create presentation
        presentation_id = self.create_presentation(article_data)

        if not presentation_id:
            raise Exception(f"Failed to create presentation for {url}")

        # Move to folder
        if self.drive_folder_id:
            self.move_presentation_to_folder(presentation_id, self.drive_folder_id)

        presentation_url = f"https://docs.google.com/presentation/d/{presentation_id}"

        # Prepare presentation data for tracking/catalog
        presentation_data = {
            'presentation_id': presentation_id,
            'presentation_url': presentation_url,
            'title': article_data['metadata']['title'],
            'author': article_data['metadata'].get('author', 'Unknown'),
            'year': article_data['metadata'].get('year', 'Unknown'),
            'medium': article_data['metadata'].get('medium', 'Unknown'),
            'keywords': article_data['metadata'].get('keywords', ''),
            'slide_count': len(article_data['images']),
            'processed_date': datetime.now().isoformat()
        }

        # Save to tracking file
        self.save_processed_article(url, presentation_data)

        # Add to catalog spreadsheet
        if self.catalog_sheet_id:
            self.add_to_catalog(url, presentation_data)

        return presentation_data

    def run_batch(self, count=1):
        """Run in batch mode - process N articles without prompting"""
        print("="*60)
        print(f"{self.site.replace('-', ' ').title()} → Google Slides Creator (Batch Mode)")
        print("="*60)

        # Authenticate
        self.authenticate()

        # Get or create Drive folder
        print("\nSetting up Drive folder...")
        folder_id = self.get_or_create_drive_folder()
        folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
        print(f"Folder URL: {folder_url}")

        # Get or create catalog spreadsheet
        print("\nSetting up catalog spreadsheet...")
        catalog_sheet_id = self.get_or_create_catalog_sheet()
        catalog_url = f"https://docs.google.com/spreadsheets/d/{catalog_sheet_id}"
        print(f"Catalog URL: {catalog_url}")

        # Get article URLs (most recent first)
        # Fetch incrementally until we have enough unprocessed articles
        print("\nFetching article URLs...")
        article_urls = []
        fetched_count = 0
        skipped_already_processed = 0
        batch_size = 50  # Fetch in batches of 50

        while len(article_urls) < count:
            # Fetch next batch
            fetch_limit = fetched_count + batch_size
            all_urls = self.get_article_urls(limit=fetch_limit)

            # Check if we've fetched all available articles
            if len(all_urls) == fetched_count:
                print(f"Reached end of available articles")
                break

            # Process newly fetched URLs
            new_urls = all_urls[fetched_count:]
            for url in new_urls:
                if not self.is_article_processed(url):
                    article_urls.append(url)
                    if len(article_urls) >= count:
                        break
                else:
                    skipped_already_processed += 1

            fetched_count = len(all_urls)
            print(f"  Fetched {fetched_count} articles, found {len(article_urls)} unprocessed...")

        print(f"Already processed: {skipped_already_processed}")
        print(f"Will process: {len(article_urls)} new article(s)")

        # Process articles
        created_presentations = []
        skipped_count = 0
        for i, article_url in enumerate(article_urls, 1):
            print(f"\n{'='*60}")
            print(f"Article {i}/{len(article_urls)}")
            print(f"{'='*60}")

            try:
                presentation_data = self.process_article(article_url)

                created_presentations.append({
                    'title': presentation_data['title'],
                    'url': presentation_data['presentation_url'],
                    'slides': presentation_data['slide_count'],
                    'keywords': presentation_data.get('keywords', '')
                })

                print(f"\n{'='*60}")
                print("Presentation created successfully!")
                print(f"View at: {presentation_data['presentation_url']}")
                print(f"{'='*60}")

            except Exception as e:
                print(f"Error processing article: {e}")
                skipped_count += 1

            time.sleep(1)  # Be respectful to APIs

        # Summary
        print(f"\n{'='*60}")
        print(f"Batch Complete!")
        print(f"{'='*60}")
        print(f"Created: {len(created_presentations)} presentation(s)")
        print(f"Skipped: {skipped_count} article(s)")
        print(f"{'='*60}")
        print(f"All presentations saved to folder:")
        print(f"  {folder_url}")
        print(f"")
        print(f"Catalog spreadsheet:")
        print(f"  {catalog_url}")
        print(f"{'='*60}")
        for i, pres in enumerate(created_presentations, 1):
            keywords_str = f" | Keywords: {pres['keywords']}" if pres.get('keywords') else ""
            print(f"{i}. {pres['title']} ({pres['slides']} slides){keywords_str}")
            print(f"   {pres['url']}")
        print(f"{'='*60}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description='Create Google Slides presentations from web articles/collections'
    )
    parser.add_argument(
        'count',
        type=int,
        nargs='?',
        default=10,
        help='Number of articles/collections to process (default: 10)'
    )
    parser.add_argument(
        '--site',
        choices=['socks-studio', 'public-domain-review'],
        default='socks-studio',
        help='Website to scrape (default: socks-studio)'
    )

    args = parser.parse_args()

    creator = SocksStudioSlidesCreator(site=args.site)
    creator.run_batch(count=args.count)
