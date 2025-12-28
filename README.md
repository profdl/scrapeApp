# Socks Studio Scraper

A web scraper for [socks-studio.com](https://socks-studio.com/) that extracts images and metadata, with planned Google Slides integration.

## Features

- Scrapes all articles from socks-studio.com (1023+ articles)
- Extracts metadata for each image:
  - Author
  - Title
  - Medium
  - Year
  - Article URL
  - Image URL
- Filters out tiny images (< 5KB) and thumbnails
- Saves metadata incrementally to CSV and JSON
- Planned: Google Slides presentation generation

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

### Run the scraper

```bash
source venv/bin/activate
python scrape_socks_studio.py
```

### Monitor progress

```bash
./monitor_progress.sh
```

## Output

- Images saved to: `socks_studio_images/images/`
- Metadata saved to:
  - `socks_studio_images/metadata.csv`
  - `socks_studio_images/metadata.json`

## Project Structure

```
scrapeApp/
├── scrape_socks_studio.py  # Main scraper script
├── test_scrape.py          # Test utility
├── monitor_progress.sh     # Progress monitoring script
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Metadata Format

Each image entry includes:
- `image_url`: Direct link to the image
- `author`: Article author
- `title`: Article title
- `medium`: Keywords/medium
- `year`: Publication year
- `article_url`: Source article URL
- `local_filename`: Downloaded filename
- `file_size_bytes`: File size in bytes

## Future Plans

- Google Slides integration: Create one presentation per article with image slides
- Each slide will include the image with caption (Artist, Title, Medium, Date)
- Link to original article with "Socks-studio" text

## License

MIT
