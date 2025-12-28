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

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pickle

# Google API scopes
SCOPES = ['https://www.googleapis.com/auth/presentations',
          'https://www.googleapis.com/auth/drive.file']

class SocksStudioSlidesCreator:
    def __init__(self):
        self.base_url = "https://socks-studio.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.slides_service = None
        self.drive_service = None
        self.credentials_path = Path('credentials.json')
        self.token_path = Path('token.pickle')

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
        print("✓ Authentication successful!")

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
                # Slide: 10" x 7.5" (9144000 x 6858000 EMU)
                # Image: 6.9" x 6.9" square (6306960 x 6306960 EMU)
                # Centered horizontally: (10" - 6.9") / 2 = 1.55" = 1417020 EMU
                image_id = f'image_{idx}'
                requests_list.append({
                    'createImage': {
                        'objectId': image_id,
                        'url': img_url,
                        'elementProperties': {
                            'pageObjectId': slide_id,
                            'size': {
                                'width': {'magnitude': 6306960, 'unit': 'EMU'},   # 6.9" square
                                'height': {'magnitude': 6306960, 'unit': 'EMU'}   # 6.9" square
                            },
                            'transform': {
                                'scaleX': 1,
                                'scaleY': 1,
                                'translateX': 1417020,  # Center horizontally
                                'translateY': 0,        # Top of slide (no spacing)
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
                # Position Y: 6.9" (directly after image)
                # Width: 7.5" (leave room for link on right)
                # Height: 0.6" (551040 EMU)
                requests_list.append({
                    'createShape': {
                        'objectId': textbox_id,
                        'shapeType': 'TEXT_BOX',
                        'elementProperties': {
                            'pageObjectId': slide_id,
                            'size': {
                                'width': {'magnitude': 6858000, 'unit': 'EMU'},   # 7.5" (leave room for link)
                                'height': {'magnitude': 551040, 'unit': 'EMU'}    # 0.6"
                            },
                            'transform': {
                                'scaleX': 1,
                                'scaleY': 1,
                                'translateX': 0,          # No left margin
                                'translateY': 6306960,    # Directly below 6.9" image
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

                # Add link to Socks-studio (right side, aligned with caption)
                # Position X: 7.5" (right of caption box)
                # Width: 2.5" (remaining space to right edge at 10")
                link_id = f'link_{idx}'
                requests_list.append({
                    'createShape': {
                        'objectId': link_id,
                        'shapeType': 'TEXT_BOX',
                        'elementProperties': {
                            'pageObjectId': slide_id,
                            'size': {
                                'width': {'magnitude': 2286000, 'unit': 'EMU'},   # 2.5"
                                'height': {'magnitude': 551040, 'unit': 'EMU'}    # Match caption height (0.6")
                            },
                            'transform': {
                                'scaleX': 1,
                                'scaleY': 1,
                                'translateX': 6858000,  # 7.5" from left (after caption box)
                                'translateY': 6306960,  # Align with caption
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

                # Style and add hyperlink (9pt font, light blue on black)
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
                                        'red': 0.5,
                                        'green': 0.7,
                                        'blue': 1.0
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

        # Get article URLs (most recent first)
        print("\nFetching article list...")
        article_urls = self.get_article_urls(limit=count)
        print(f"Will process {len(article_urls)} article(s)")

        # Process articles
        created_presentations = []
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

            if presentation_id:
                presentation_url = f"https://docs.google.com/presentation/d/{presentation_id}"
                created_presentations.append({
                    'title': article_data['metadata']['title'],
                    'url': presentation_url,
                    'slides': len(article_data['images'])
                })
                print(f"\n{'='*60}")
                print("Presentation created successfully!")
                print(f"View at: {presentation_url}")
                print(f"{'='*60}")
            else:
                print("Failed to create presentation")

            time.sleep(1)  # Be respectful to APIs

        # Summary
        print(f"\n{'='*60}")
        print(f"Batch Complete! Created {len(created_presentations)} presentation(s)")
        print(f"{'='*60}")
        for i, pres in enumerate(created_presentations, 1):
            print(f"{i}. {pres['title']} ({pres['slides']} slides)")
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
