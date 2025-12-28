# Socks Studio → Google Slides Creator

Creates beautiful Google Slides presentations from [socks-studio.com](https://socks-studio.com/) articles. Each article becomes one presentation with one slide per image, complete with metadata and keywords.

## ✨ Features

### Core Functionality
- **Automated Slide Generation**: One presentation per article, one slide per image
- **Beautiful Layout**: Black background, widescreen 16:9 format, optimized image sizing
- **Smart Metadata**: Extracts author, title, medium, year from articles
- **LLM Enhancement**: Uses Claude AI to extract missing metadata and keywords from article text
- **Keyword Tagging**: Automatically generates 3-5 searchable keywords per article

### Organization & Tracking
- **Google Drive Folder**: All presentations organized in "socks-studio" folder
- **Google Sheets Catalog**: Searchable spreadsheet with all presentations and metadata
- **Duplicate Prevention**: Tracks processed articles to avoid re-processing
- **Progress Tracking**: Local JSON file tracks all completed presentations

### Smart Processing
- Filters tiny images (< 5KB) and thumbnails
- Handles both portrait and landscape images with optimal sizing
- Extracts metadata from JSON-LD schemas when available
- Falls back to LLM extraction for missing data

## 📊 Current Status

- **Total Articles Available**: 1,023
- **Articles Processed**: 19+
- **Presentations Created**: [View Folder](https://drive.google.com/drive/folders/1LXkzeJj6W2ib_Oo06swCOs8CnQIgpf-K)
- **Searchable Catalog**: [View Spreadsheet](https://docs.google.com/spreadsheets/d/1ZPgNitBcdss_xr3W9PCPs9ZQ_-P-2QNTpBUwPkNXpYk)

## 🚀 Installation

### 1. Clone Repository
```bash
git clone https://github.com/profdl/scrapeApp.git
cd scrapeApp
```

### 2. Install Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_slides.txt
```

### 3. Set Up Google API Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable:
   - Google Slides API
   - Google Drive API
   - Google Sheets API
3. Create OAuth 2.0 credentials
4. Download as `credentials.json` and place in project directory

### 4. Set Up Anthropic API Key

Create a file named `anthropic_api_key.txt` with your API key:

```bash
echo "sk-ant-your-actual-key-here" > anthropic_api_key.txt
```

Get your API key from: https://console.anthropic.com/

## 📖 Usage

### Process Articles

Process the N most recent articles:

```bash
source venv/bin/activate
python create_slides.py 10  # Process 10 articles
```

The first run will open a browser for Google authentication.

### What Happens

1. **Setup**: Creates/finds "socks-studio" folder and catalog spreadsheet
2. **Filtering**: Skips already-processed articles automatically
3. **Processing**: For each article:
   - Extracts images and metadata
   - Uses Claude AI to extract missing data and keywords
   - Creates beautiful slide presentation
   - Moves to Google Drive folder
   - Adds to catalog spreadsheet
   - Saves to local tracking file
4. **Summary**: Shows results with links and keywords

### Example Output

```
============================================================
Batch Complete!
============================================================
Created: 8 presentation(s)
Skipped: 2 article(s)
============================================================
All presentations saved to folder:
  https://drive.google.com/drive/folders/1LXkzeJj6W2ib_Oo06swCOs8CnQIgpf-K

Catalog spreadsheet:
  https://docs.google.com/spreadsheets/d/1ZPgNitBcdss_xr3W9PCPs9ZQ_-P-2QNTpBUwPkNXpYk
============================================================
1. Forgotten Corners of the World (9 slides) | Keywords: abandoned spaces, memory, loss
   https://docs.google.com/presentation/d/115OKY_...
```

## 🎨 Slide Layout

- **Format**: Widescreen 16:9 (10" × 5.625")
- **Background**: Black
- **Images**: Centered at top, optimized for portrait/landscape
  - Portrait: Constrained by height (5.025")
  - Landscape: Uses full width (9"), extends proportionally
- **Caption**: Author, Title, Medium/Year at bottom (light gray)
- **Link**: "Socks-studio" link in bottom right (dark gray)

## 📁 Project Structure

```
scrapeApp/
├── create_slides.py              # Main slides creator
├── processed_articles.json       # Tracking file (auto-generated)
├── credentials.json              # Google API credentials (you provide)
├── anthropic_api_key.txt         # Anthropic API key (you provide)
├── token.pickle                  # Google auth token (auto-generated)
├── requirements_slides.txt       # Python dependencies
├── LLM_METADATA_ENHANCEMENT.md   # LLM feature documentation
├── EXPANSION_PLAN.md             # Future roadmap
└── README.md                     # This file
```

## 🔍 Catalog Spreadsheet Columns

- **Article URL**: Link to original article
- **Presentation URL**: Link to Google Slides
- **Title**: Article/artwork title
- **Author**: Creator name
- **Year**: Creation year
- **Medium**: Type of work (Photography, Architecture, Drawing, etc.)
- **Keywords**: Searchable tags (3-5 per article)
- **Slides**: Number of slides in presentation
- **Processed Date**: When it was created

## 🤖 LLM Enhancement

The app uses Claude 3.5 Haiku to:
- Extract missing year/medium from article text
- Generate 3-5 relevant keywords for searchability
- Understand context and relationships in articles

**Cost**: ~$0.001 per article (very affordable)

See [LLM_METADATA_ENHANCEMENT.md](LLM_METADATA_ENHANCEMENT.md) for details.

## 📝 Tracking System

The app maintains `processed_articles.json` to:
- Track all processed articles
- Prevent duplicate processing
- Store metadata and keywords
- Enable resume after interruption

This file is automatically updated and excluded from git.

## 🚀 Future Plans

See [EXPANSION_PLAN.md](EXPANSION_PLAN.md) for detailed roadmap including:
- **Multi-site support**: 50watts.com, publicdomainreview.org
- **Book processing**: Scan and process art books with Vision LLM
- **Web interface**: Collaborative web app for teams

## 💰 Cost Estimates

### API Usage
- **Anthropic API**: ~$0.001 per article
- **Google APIs**: Free
- **Example**: 100 articles ≈ $0.10

### Processing Time
- ~15-30 seconds per article (depends on image count)
- Can process in batches of any size
- Automatically resumes if interrupted

## 🛠️ Development

### Run Tests
```bash
python test_scrape.py
```

### Monitor Progress
```bash
# Check how many articles processed
jq 'length' processed_articles.json

# View catalog
open "https://docs.google.com/spreadsheets/d/1ZPgNitBcdss_xr3W9PCPs9ZQ_-P-2QNTpBUwPkNXpYk"
```

## 📄 License

MIT

## 🙏 Credits

- **Website**: [Socks Studio](https://socks-studio.com/)
- **LLM**: Claude 3.5 Haiku by Anthropic
- **APIs**: Google Slides, Drive, Sheets APIs

---

Built with ❤️ using Claude Code
