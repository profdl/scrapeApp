# Socks Studio Slides App - Expansion Plan

## Vision
Expand from single-site CLI tool to multi-site web application supporting:
- Multiple websites (50watts.com, publicdomainreview.org, etc.)
- Scanned art book processing
- Collaborative web interface for colleagues

---

## Current Status

**Working Features:**
- ✅ Google Slides generation with beautiful layouts
- ✅ LLM metadata enhancement + keyword extraction
- ✅ Tracking system prevents duplicates
- ✅ Google Sheets catalog for searchability
- ✅ 19+ Socks Studio presentations created

**Limitations:**
- ❌ Single site only (socks-studio.com)
- ❌ CLI only (not collaborative)
- ❌ No book/PDF support

---

## Phase 1: Multi-Site Support (2-3 weeks)

### Goal
Support multiple art/design websites using adapter pattern

### Architecture
```python
class SiteAdapter(ABC):
    @abstractmethod
    def get_article_urls(self): pass

    @abstractmethod
    def extract_metadata(self, url): pass

    @abstractmethod
    def extract_images(self, url): pass

class SocksStudioAdapter(SiteAdapter):
    # Current implementation

class FiftyWattsAdapter(SiteAdapter):
    # 50watts.com specific logic

class PublicDomainAdapter(SiteAdapter):
    # publicdomainreview.org specific
```

### Tasks
1. Refactor existing code into `SocksStudioAdapter`
2. Create base `SiteAdapter` abstract class
3. Implement `FiftyWattsAdapter`
4. Implement `PublicDomainAdapter`
5. Add site selection to CLI: `python create_slides.py --site socks-studio 10`
6. Update tracking system to handle multiple sources
7. Test with all three sites

### Output
CLI that works with multiple sites:
```bash
python create_slides.py --site socks-studio 10
python create_slides.py --site 50watts 10
python create_slides.py --site publicdomain 10
```

---

## Phase 2: Book Processing (2-3 weeks)

### Goal
Process scanned art books using Vision LLM

### Why Vision LLM over OCR?
- **Traditional OCR (Tesseract):** Poor accuracy on complex art book layouts
- **Vision LLM (Claude 3.5 Sonnet):** Excellent at understanding context and complex layouts
- **Cost:** ~$3-10 per 300-page book (acceptable for quality)

### Architecture
```python
class BookProcessor:
    def extract_pages_from_pdf(self, pdf_path):
        # Use PyMuPDF or pdf2image
        return page_images

    def extract_artwork_from_page(self, page_image):
        # Send to Claude Vision API
        # Prompt: "Extract all artworks with author, title, year, medium"
        return artworks_list

    def generate_slides_from_book(self, artworks_list):
        # Create presentation from extracted metadata
        return presentation_id
```

### Tasks
1. Add PDF upload/processing module (PyMuPDF or pdf2image)
2. Integrate Claude Vision API
3. Create page-by-page artwork extraction logic
4. Handle multi-page artworks (spreads)
5. Generate slides from extracted metadata
6. Add books to tracking system
7. Update catalog to include source type (web/book)

### Output
```bash
python process_book.py artbook.pdf
# Creates presentation with all artworks from book
```

---

## Phase 3: Web Interface MVP (2-4 weeks)

### Goal
Streamlit web app for colleagues to use

### Why Streamlit?
- Quickest to implement (builds on Python code)
- Free/cheap hosting
- Good enough UI for small teams
- Can upgrade later if needed

### Architecture
- **Framework:** Streamlit (Python)
- **Hosting:** Railway or Render (free tier)
- **Backend:** Reuse existing Python processing code
- **Storage:** Keep Google Drive integration

### Features
1. File upload interface (URLs or PDF files)
2. Site selection dropdown (Socks Studio, 50 Watts, Public Domain, Book)
3. Real-time progress indicators
4. Results viewer with links
5. Browse previously created presentations
6. Search by keywords

### UI Mockup Flow
```
1. Landing page
   - Upload file OR enter URL
   - Select source type
   - Click "Process"

2. Processing page
   - Progress bar
   - Current status ("Extracting images 5/10...")
   - Live preview of created slides

3. Results page
   - Links to presentation and catalog
   - Keywords extracted
   - Option to process another
```

### Tasks
1. Create Streamlit app structure
2. Add file upload widget
3. Add URL input + site selection
4. Integrate existing processing code
5. Add progress indicators
6. Create results display
7. Deploy to Railway/Render
8. Test with colleagues
9. Add basic auth (optional)

### Output
Web app at https://slides-creator.railway.app

---

## Phase 4: Enhanced Web App (4-8 weeks, OPTIONAL)

### Goal
Production-ready collaborative platform

### Architecture
- **Frontend:** Next.js (React) on Vercel
- **Backend:** FastAPI (Python) on Railway
- **Queue:** Celery + Redis (background jobs)
- **Database:** PostgreSQL (user data, job history)
- **Auth:** NextAuth.js or Auth0
- **Storage:** Keep Google Drive integration

### Features
- Professional UI/UX
- User accounts and authentication
- Job queue with progress tracking
- Browse/search all presentations
- API key management per user
- Admin dashboard
- Team workspaces
- Notification system

### When to Consider This
- Team grows beyond 10 people
- Need robust concurrent processing
- Want polished, branded interface
- Budget for hosting ($20-50/month)

---

## Comparison Table

| Feature | Current | Phase 3 (Streamlit) | Phase 4 (Full App) |
|---------|---------|---------------------|-------------------|
| Multi-site support | ❌ | ✅ | ✅ |
| Book processing | ❌ | ✅ | ✅ |
| Web interface | ❌ | ✅ (basic) | ✅ (polished) |
| Concurrent users | N/A | ~5 | 100+ |
| Authentication | N/A | Basic | Full |
| Total time | - | 6-8 weeks | 12-16 weeks |
| Hosting cost | $0 | $0-10/mo | $20-50/mo |

---

## Recommended Path

**Start with Phases 1-3:**

1. **Week 1-3:** Multi-site adapters
2. **Week 4-6:** Book processing with Vision LLM
3. **Week 7-10:** Streamlit web interface

**Then evaluate:**
- If Streamlit works well for team → Keep it
- If need more scale/polish → Upgrade to Phase 4

---

## Key Decisions Needed

1. **How many colleagues will use this?** (affects architecture)
2. **How often?** (daily vs occasional)
3. **Budget for hosting?** ($0 vs $50/month)
4. **Technical skills of users?** (affects UI needs)
5. **Priority: speed vs polish?** (MVP vs production)

---

## Next Steps

When ready to proceed:
1. Analyze 50watts.com and publicdomainreview.org HTML structure
2. Create adapter interfaces
3. Test book processing with sample PDF
4. Build Streamlit prototype

---

## Cost Estimates

### Development Time
- Phase 1: 2-3 weeks
- Phase 2: 2-3 weeks
- Phase 3: 2-4 weeks
- Phase 4: 4-8 weeks (optional)

### Running Costs
- **Anthropic API:** ~$0.001 per article, ~$0.01-0.03 per book page
- **Google APIs:** Free
- **Hosting (Streamlit):** $0-10/month
- **Hosting (Full App):** $20-50/month

### Example Usage Costs
- 100 articles: ~$0.10
- 10 books (300 pages each): ~$30-90
- Very affordable for the value created
