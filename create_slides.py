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
    def __init__(self):
        self.base_url = "https://socks-studio.com"
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
        self.tracking_file = Path('processed_articles.json')
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

    def get_or_create_drive_folder(self, folder_name='socks-studio'):
        """Get or create a Google Drive folder for presentations"""
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
        # Search for existing catalog
        query = "name='Socks Studio Presentations Catalog' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
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
                    'title': 'Socks Studio Presentations Catalog'
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

    def get_article_urls(self, limit=None):
        """Get article URLs from the homepage (most recent first)"""
        print("Fetching article URLs...")
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
1. The year or date when the artwork/project was created (not when the article was published)
2. The medium or type of work (e.g., "Photography", "Architecture", "Drawing", "Installation", etc.)
3. 3-5 keywords or tags that describe the main topics/themes (e.g., "urban landscape", "abstract geometry", "vernacular architecture")

Respond in this exact format:
Year: [year or "Unknown" if not found]
Medium: [medium or "Unknown" if not found]
Keywords: [comma-separated keywords, or "Unknown" if not found]

Only include information that is explicitly stated in the text. Be concise."""
                }]
            )

            # Parse response
            response_text = message.content[0].text
            result = {}

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

    def extract_article_data(self, url):
        """Extract metadata and images from an article"""
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

        if metadata['author'] == 'Unknown':
            author_links = soup.find_all('a', href=True)
            for link in author_links:
                if 'author' in link.get('href', ''):
                    metadata['author'] = link.get_text(strip=True)
                    break

        # Find images
        images = []
        content_div = soup.find('article') or soup.find('div', class_='entry-content') or soup.body

        if content_div:
            img_tags = content_div.find_all('img')
            for img in img_tags:
                img_url = img.get('src') or img.get('data-src')
                if img_url:
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
                        head = self.session.head(img_url, timeout=5)
                        content_length = head.headers.get('content-length')
                        if content_length and int(content_length) < 5000:
                            continue
                    except:
                        pass

                    images.append(img_url)

        print(f"Found {len(images)} images")

        # Enhance metadata with LLM if year, medium is missing, or to extract keywords
        if self.anthropic_client and (metadata['year'] == 'Unknown' or metadata['medium'] == 'Unknown' or 'keywords' not in metadata):
            print("  Enhancing metadata with LLM...")
            enhanced_metadata = self.enhance_metadata_with_llm(soup, metadata)
            if enhanced_metadata:
                if metadata['year'] == 'Unknown' and enhanced_metadata.get('year'):
                    metadata['year'] = enhanced_metadata['year']
                    print(f"    Found year: {metadata['year']}")
                if metadata['medium'] == 'Unknown' and enhanced_metadata.get('medium'):
                    metadata['medium'] = enhanced_metadata['medium']
                    print(f"    Found medium: {metadata['medium']}")
                if enhanced_metadata.get('keywords'):
                    metadata['keywords'] = enhanced_metadata['keywords']
                    print(f"    Found keywords: {metadata['keywords']}")

        return {
            'metadata': metadata,
            'images': images
        }

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
            for idx, img_url in enumerate(images):
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
                        'url': img_url,
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
                textbox_id = f'textbox_{idx}'
                caption_parts = []
                if metadata['author'] and metadata['author'] != 'Unknown':
                    caption_parts.append(metadata['author'])
                if metadata['title'] and metadata['title'] != 'Unknown':
                    caption_parts.append(metadata['title'])

                # Combine medium and year on same line if both exist
                meta_line = []
                if metadata['medium'] and metadata['medium'] != 'Unknown':
                    meta_line.append(metadata['medium'])
                if metadata['year'] and metadata['year'] != 'Unknown':
                    meta_line.append(metadata['year'])
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


    def run_batch(self, count=1):
        """Run in batch mode - process N articles without prompting"""
        print("="*60)
        print("Socks Studio → Google Slides Creator (Batch Mode)")
        print("="*60)

        # Authenticate
        self.authenticate()

        # Get or create Drive folder
        print("\nSetting up Drive folder...")
        folder_id = self.get_or_create_drive_folder('socks-studio')
        folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
        print(f"Folder URL: {folder_url}")

        # Get or create catalog spreadsheet
        print("\nSetting up catalog spreadsheet...")
        catalog_sheet_id = self.get_or_create_catalog_sheet()
        catalog_url = f"https://docs.google.com/spreadsheets/d/{catalog_sheet_id}"
        print(f"Catalog URL: {catalog_url}")

        # Get article URLs (most recent first)
        print("\nFetching article list...")
        all_article_urls = self.get_article_urls(limit=None)  # Get all to check processed

        # Filter out already processed articles
        unprocessed_urls = [url for url in all_article_urls if not self.is_article_processed(url)]

        # Limit to requested count
        article_urls = unprocessed_urls[:count] if count else unprocessed_urls

        already_processed_count = len(all_article_urls) - len(unprocessed_urls)
        print(f"Total articles: {len(all_article_urls)}")
        print(f"Already processed: {already_processed_count}")
        print(f"Will process: {len(article_urls)} new article(s)")

        # Process articles
        created_presentations = []
        skipped_count = 0
        for i, article_url in enumerate(article_urls, 1):
            print(f"\n{'='*60}")
            print(f"Article {i}/{len(article_urls)}")
            print(f"{'='*60}")

            # Extract article data
            article_data = self.extract_article_data(article_url)

            if not article_data or not article_data['images']:
                print("Skipping (no valid images)")
                skipped_count += 1
                continue

            # Create presentation
            presentation_id = self.create_presentation(article_data)

            if presentation_id:
                # Move to folder
                print("  Moving to 'socks-studio' folder...")
                self.move_presentation_to_folder(presentation_id, folder_id)

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
                print("  Saving to tracking file...")
                self.save_processed_article(article_url, presentation_data)

                # Add to catalog spreadsheet
                print("  Adding to catalog spreadsheet...")
                self.add_to_catalog(article_url, presentation_data)

                created_presentations.append({
                    'title': article_data['metadata']['title'],
                    'url': presentation_url,
                    'slides': len(article_data['images']),
                    'keywords': article_data['metadata'].get('keywords', '')
                })
                print(f"\n{'='*60}")
                print("Presentation created successfully!")
                print(f"View at: {presentation_url}")
                print(f"{'='*60}")
            else:
                print("Failed to create presentation")
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
    import sys

    creator = SocksStudioSlidesCreator()

    # Check for command-line arguments
    if len(sys.argv) > 1:
        try:
            count = int(sys.argv[1])
            creator.run_batch(count=count)
        except ValueError:
            print("Usage: python create_slides.py [number_of_articles]")
            print("Example: python create_slides.py 5")
            sys.exit(1)
    else:
        # Default to batch mode with 1 article
        creator.run_batch(count=1)
