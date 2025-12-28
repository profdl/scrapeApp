#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup

url = "https://socks-studio.com"
print(f"Fetching {url}...")

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}

response = requests.get(url, headers=headers, timeout=10)
print(f"Status code: {response.status_code}")

soup = BeautifulSoup(response.text, 'html.parser')

# Find all article tags
articles = soup.find_all('article')
print(f"\nFound {len(articles)} <article> tags")

if articles:
    print("\nFirst article structure:")
    print(articles[0].prettify()[:500])

# Look for h2 tags
h2_tags = soup.find_all('h2')
print(f"\nFound {len(h2_tags)} <h2> tags")

if h2_tags:
    print("\nFirst h2:")
    print(h2_tags[0])

# Look for any links
links = soup.find_all('a', href=True)
print(f"\nTotal links: {len(links)}")
print("\nFirst 5 links:")
for i, link in enumerate(links[:5]):
    print(f"{i+1}. {link.get('href')} - {link.get_text(strip=True)[:50]}")
