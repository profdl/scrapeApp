# Multi-Site Web UI - Quick Start Guide

## 🎉 What's New

Your scraping app now supports:
- ✅ **Multiple websites**: Socks Studio + Public Domain Review
- ✅ **Web interface**: Beautiful Streamlit UI with real-time progress
- ✅ **Site-specific organization**: Separate Drive folders and spreadsheets per site
- ✅ **Start/Stop controls**: Cancel processing mid-batch
- ✅ **Quick links**: Direct access to folders and spreadsheets

---

## 🚀 How to Use

### Option 1: Web Interface (Recommended)

1. **Start the web app:**
   ```bash
   source venv/bin/activate  # Activate virtual environment
   streamlit run app.py
   ```

2. **Your browser will open automatically** showing the web interface

3. **Use the interface:**
   - Select website (Socks Studio or Public Domain Review) in the sidebar
   - Enter number of items to process
   - Click "▶ Start Processing"
   - Watch real-time progress
   - Click "⏹ Stop" to cancel anytime
   - Click quick links to view folders and spreadsheets

### Option 2: Command Line

**Process Socks Studio articles:**
```bash
python create_slides.py 10 --site socks-studio
```

**Process Public Domain Review collections:**
```bash
python create_slides.py 10 --site public-domain-review
```

---

## 📁 Organization

### Socks Studio
- **Drive folder**: `socks-studio`
- **Spreadsheet**: "Socks Studio Presentations Catalog"
- **Tracking file**: `processed_articles_socks-studio.json`

### Public Domain Review
- **Drive folder**: `public-domain-review`
- **Spreadsheet**: "Public Domain Review Presentations Catalog"
- **Tracking file**: `processed_articles_public-domain-review.json`

---

## 🎨 Public Domain Review Details

The Public Domain Review integration works with their **image collections** at:
https://publicdomainreview.org/collections/images/

**How it works:**
- Scrapes collection pages (23 pages, ~550 collections)
- Each collection becomes one Google Slides presentation
- Extracts all images from each collection
- Preserves artist, title, year metadata from captions
- Curator credited as "author"

**Example:**
- Collection: "Chaïm Soutine's Still Lifes (ca. 1920s)"
- Result: One presentation with 20+ slides of Soutine paintings
- Metadata: Curator name, year from title, keywords via LLM

---

## 🔑 Features

### Web Interface Features
- ✅ Real-time progress bar
- ✅ Live status updates (current URL being processed)
- ✅ Live results display with presentation links
- ✅ Stop button (gracefully halts after current item)
- ✅ Quick links to Drive folders and catalogs
- ✅ Success/error indicators for each item
- ✅ Slide count and metadata preview

### Common Features (Web + CLI)
- ✅ Duplicate prevention (per-site tracking)
- ✅ LLM metadata enhancement (Claude)
- ✅ Automatic folder and spreadsheet creation
- ✅ Beautiful slide layouts with captions
- ✅ Keyword extraction and tagging

---

## 🧪 Testing Checklist

### Test 1: Socks Studio (Web)
- [ ] Start web app: `streamlit run app.py`
- [ ] Select "Socks Studio"
- [ ] Process 2 articles
- [ ] Verify Drive folder link works
- [ ] Verify catalog spreadsheet link works
- [ ] Check presentations created successfully

### Test 2: Public Domain Review (Web)
- [ ] Select "Public Domain Review" in sidebar
- [ ] Process 2 collections
- [ ] Verify separate Drive folder created
- [ ] Verify separate catalog created
- [ ] Check that images are extracted correctly

### Test 3: CLI Functionality
- [ ] Run: `python create_slides.py 2 --site socks-studio`
- [ ] Run: `python create_slides.py 2 --site public-domain-review`
- [ ] Verify both work correctly

### Test 4: Stop Button
- [ ] Start processing 10 items
- [ ] Click "⏹ Stop" after 2 items complete
- [ ] Verify processing stops gracefully
- [ ] Verify completed items are saved

---

## 📊 Sample Usage

**Start small to test:**
```bash
# Test with just 2 items first
streamlit run app.py  # Select 2 items, process
```

**Then scale up:**
```bash
# Process 10 collections from Public Domain Review
streamlit run app.py  # Select Public Domain Review, enter 10
```

**Bulk processing via CLI:**
```bash
# Process 50 Public Domain Review collections overnight
python create_slides.py 50 --site public-domain-review
```

---

## 🛠️ Troubleshooting

**Problem: "No module named streamlit"**
```bash
source venv/bin/activate
pip install -r requirements_slides.txt
```

**Problem: "credentials.json not found"**
- Make sure Google API credentials are set up
- See SETUP_GOOGLE_API.md for instructions

**Problem: "No images found"**
- Check if the website structure changed
- Verify network connection
- Try a different article/collection URL

**Problem: Web app won't start**
```bash
# Check if streamlit is installed
streamlit --version

# Reinstall if needed
pip install "streamlit>=1.28.0"
```

---

## 🎯 Next Steps

1. **Test the web interface**:
   ```bash
   streamlit run app.py
   ```

2. **Process your first Public Domain Review collection**:
   - Select "Public Domain Review"
   - Set count to 1
   - Click "▶ Start Processing"

3. **Check the results**:
   - Click the quick links to see your folder and catalog
   - Open a presentation to verify the slides look good

4. **Scale up**:
   - Once you're happy with the results, process more collections
   - The system will automatically skip already-processed items

---

## 💡 Tips

- **Start with small batches** (2-5 items) to test before processing many
- **Use the web interface** for interactive processing with progress updates
- **Use CLI for bulk processing** that you can run in the background or overnight
- **Check the catalog spreadsheet** to search and browse all your presentations
- **Each site has separate tracking**, so you can process both sites independently

---

## 📝 File Changes Summary

### Modified Files:
- **[create_slides.py](create_slides.py)** - Added multi-site support
  - Site parameter in constructor
  - Site-specific URL fetching and data extraction
  - Public Domain Review scraping functions
  - Dispatcher methods for site selection
  - `process_article()` method for Streamlit
  - Updated CLI to accept `--site` parameter

### New Files:
- **[app.py](app.py)** - Streamlit web interface
- **[MULTI_SITE_GUIDE.md](MULTI_SITE_GUIDE.md)** - This guide

### Updated Files:
- **[requirements_slides.txt](requirements_slides.txt)** - Added Streamlit

---

Happy scraping! 🎨✨
