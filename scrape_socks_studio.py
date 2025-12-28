#!/usr/bin/env python3
"""
Scraper for socks-studio.com
Downloads all images with metadata: Author, Title, Medium, Year, and source links
"""

import sys
import requests
from bs4 import BeautifulSoup
import json
import csv
import os
import time
import re
from urllib.parse import urljoin, urlparse
from pathlib import Path

class SocksStudioScraper:
    def __init__(self, output_dir="socks_studio_images"):
        self.base_url = "https://socks-studio.com"
        self.output_dir = Path(output_dir)
        self.images_dir = self.output_dir / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.metadata = []

    def get_all_article_urls(self):
        """Scrape all pages to collect article URLs"""
        print("Collecting article URLs from all pages...", flush=True)
        article_urls = []

        # Start with page 1
        page = 1
        while True:
            if page == 1:
                url = self.base_url
            else:
                url = f"{self.base_url}/page/{page}/"

            print(f"Scraping page {page}...", flush=True)
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
            except Exception as e:
                print(f"Error fetching page {page}: {e}", flush=True)
                break

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find article links (looking for blog post titles)
            articles = soup.find_all('article')
            if not articles:
                print(f"No more articles found on page {page}", flush=True)
                break

            for article in articles:
                # Find h2 with a link inside
                h2 = article.find('h2')
                if h2:
                    link = h2.find('a')
                    if link and link.get('href'):
                        article_url = urljoin(self.base_url, link['href'])
                        if article_url not in article_urls:
                            article_urls.append(article_url)

            print(f"Found {len(articles)} articles on page {page}", flush=True)
            page += 1
            time.sleep(1)  # Be respectful to the server

            # Safety limit
            if page > 50:
                print(f"Reached safety limit at page {page}", flush=True)
                break

        print(f"\nTotal articles found: {len(article_urls)}", flush=True)
        return article_urls

    def extract_metadata_from_article(self, url):
        """Extract metadata and images from a single article"""
        print(f"\nProcessing: {url}", flush=True)

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"Error fetching article: {e}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract metadata from JSON-LD
        metadata = {
            'author': 'Unknown',
            'title': 'Unknown',
            'year': 'Unknown',
            'medium': 'Unknown',
            'article_url': url
        }

        # Try to find JSON-LD schema
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    # Extract author
                    if 'author' in data:
                        if isinstance(data['author'], dict):
                            metadata['author'] = data['author'].get('name', 'Unknown')
                        elif isinstance(data['author'], str):
                            metadata['author'] = data['author']

                    # Extract title
                    if 'headline' in data:
                        metadata['title'] = data['headline']
                    elif 'name' in data:
                        metadata['title'] = data['name']

                    # Extract date (year)
                    if 'datePublished' in data:
                        date_match = re.search(r'(\d{4})', data['datePublished'])
                        if date_match:
                            metadata['year'] = date_match.group(1)

                    # Extract keywords/medium
                    if 'keywords' in data:
                        metadata['medium'] = data['keywords']
            except json.JSONDecodeError:
                pass

        # Also try to extract from article header
        if metadata['title'] == 'Unknown':
            title_tag = soup.find('h1') or soup.find('h2')
            if title_tag:
                metadata['title'] = title_tag.get_text(strip=True)

        if metadata['author'] == 'Unknown':
            # Look for author link in the page metadata
            author_links = soup.find_all('a', href=True)
            for link in author_links:
                if 'author' in link.get('href', ''):
                    metadata['author'] = link.get_text(strip=True)
                    break

        # Find all images in the article content
        article_images = []
        content_div = soup.find('article') or soup.find('div', class_='entry-content') or soup.body

        if content_div:
            images = content_div.find_all('img')
            for img in images:
                img_url = img.get('src') or img.get('data-src')
                if img_url:
                    # Convert to absolute URL
                    img_url = urljoin(url, img_url)

                    # Skip tiny images by URL patterns
                    if 'icon' in img_url.lower() or 'logo' in img_url.lower():
                        continue

                    # Check HTML dimensions if available
                    width = img.get('width')
                    height = img.get('height')

                    # Skip images with tiny dimensions in HTML
                    if width and height:
                        try:
                            if int(width) < 50 or int(height) < 50:
                                continue
                        except (ValueError, TypeError):
                            pass

                    # Skip common thumbnail sizes
                    if '-150x150' in img_url or '-300x' in img_url or 'thumbnail' in img_url:
                        continue

                    article_images.append({
                        'image_url': img_url,
                        'author': metadata['author'],
                        'title': metadata['title'],
                        'medium': metadata['medium'],
                        'year': metadata['year'],
                        'article_url': metadata['article_url']
                    })

        print(f"Found {len(article_images)} images", flush=True)
        return article_images

    def download_image(self, image_data, index):
        """Download a single image"""
        img_url = image_data['image_url']

        try:
            response = self.session.get(img_url, timeout=15, stream=True)
            response.raise_for_status()

            # Generate filename
            parsed = urlparse(img_url)
            original_filename = os.path.basename(parsed.path)
            ext = os.path.splitext(original_filename)[1] or '.jpg'

            # Create safe filename
            safe_title = re.sub(r'[^\w\s-]', '', image_data['title'])[:50]
            safe_title = re.sub(r'[-\s]+', '_', safe_title)
            filename = f"{index:04d}_{safe_title}{ext}"

            filepath = self.images_dir / filename

            # Download image
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Check file size - skip if too small (likely not artwork)
            file_size = os.path.getsize(filepath)
            if file_size < 5000:  # Less than 5KB is likely not an artwork
                os.remove(filepath)
                print(f"Skipped (too small: {file_size} bytes)", flush=True)
                return False

            print(f"Downloaded: {filename} ({file_size // 1024}KB)", flush=True)

            # Add filename to metadata
            image_data['local_filename'] = filename
            image_data['file_size_bytes'] = file_size
            return True

        except Exception as e:
            print(f"Error downloading {img_url}: {e}", flush=True)
            image_data['local_filename'] = 'FAILED'
            return False

    def save_metadata_incremental(self, image_data):
        """Save a single image's metadata incrementally to CSV and JSON"""
        csv_path = self.output_dir / "metadata.csv"
        json_path = self.output_dir / "metadata.json"

        # Append to CSV
        file_exists = csv_path.exists()
        with open(csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=image_data.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(image_data)

        # Update JSON (read all, append, write all)
        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                try:
                    all_data = json.load(f)
                except json.JSONDecodeError:
                    all_data = []
        else:
            all_data = []

        all_data.append(image_data)

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)

    def save_metadata(self):
        """Save final summary"""
        print(f"\nMetadata saved incrementally to:", flush=True)
        print(f"  - {self.output_dir / 'metadata.csv'}", flush=True)
        print(f"  - {self.output_dir / 'metadata.json'}", flush=True)

    def run(self):
        """Main scraping process"""
        print("Starting Socks Studio scraper...")
        print(f"Output directory: {self.output_dir.absolute()}\n")

        # Step 1: Get all article URLs
        article_urls = self.get_all_article_urls()

        if not article_urls:
            print("No articles found!")
            return

        # Step 2: Process each article and download images immediately
        image_counter = 0
        downloaded_counter = 0
        for i, article_url in enumerate(article_urls, 1):
            print(f"\n[{i}/{len(article_urls)}] Processing article...", flush=True)
            images = self.extract_metadata_from_article(article_url)

            # Download images immediately
            for image_data in images:
                image_counter += 1
                print(f"  [{image_counter}] Downloading image...", end=" ", flush=True)
                success = self.download_image(image_data, downloaded_counter + 1)

                if success:
                    downloaded_counter += 1
                    self.metadata.append(image_data)
                    # Save metadata incrementally after each successful download
                    self.save_metadata_incremental(image_data)

            time.sleep(1)  # Be respectful to the server

        print(f"\n\nTotal images found: {image_counter}", flush=True)
        print(f"Total images downloaded: {downloaded_counter}", flush=True)
        print(f"Skipped (too small): {image_counter - downloaded_counter}", flush=True)

        # Step 3: Save metadata
        self.save_metadata()

        print(f"\n{'='*60}", flush=True)
        print("Scraping complete!", flush=True)
        print(f"Images downloaded: {len([m for m in self.metadata if m.get('local_filename') and m['local_filename'] != 'FAILED'])}", flush=True)
        print(f"Failed downloads: {len([m for m in self.metadata if m.get('local_filename') == 'FAILED'])}", flush=True)
        print(f"Output directory: {self.output_dir.absolute()}", flush=True)
        print(f"{'='*60}", flush=True)


if __name__ == "__main__":
    scraper = SocksStudioScraper()
    scraper.run()
