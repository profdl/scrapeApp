# Google Slides API Setup Guide

Follow these steps to enable the Google Slides integration:

## Step 1: Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** → **New Project**
3. Name it something like "Socks Studio Scraper"
4. Click **Create**

## Step 2: Enable APIs

1. In your project, go to **APIs & Services** → **Library**
2. Search for and enable:
   - **Google Slides API**
   - **Google Drive API**

## Step 3: Create OAuth 2.0 Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **+ CREATE CREDENTIALS** → **OAuth client ID**
3. If prompted, configure the OAuth consent screen:
   - User Type: **External**
   - App name: "Socks Studio Scraper"
   - User support email: your email
   - Developer contact: your email
   - Click **Save and Continue** through all steps
   - Add yourself as a test user
4. Back in Credentials, create OAuth client ID:
   - Application type: **Desktop app**
   - Name: "Socks Studio Desktop Client"
   - Click **Create**
5. Click **Download JSON**
6. Rename the downloaded file to `credentials.json`
7. Move it to this directory: `/Users/daniellefcourt/Documents/GitHub/scrapeApp/`

## Step 4: Run the Script

```bash
cd /Users/daniellefcourt/Documents/GitHub/scrapeApp
source venv/bin/activate
python create_slides.py
```

## First Run

On first run:
1. A browser window will open
2. Sign in with your Google account
3. Click **Advanced** → **Go to Socks Studio Scraper (unsafe)**
4. Click **Continue**
5. Grant permissions for Google Slides and Google Drive

The authentication token will be saved as `token.pickle` for future runs.

## Security Note

- `credentials.json` and `token.pickle` are excluded from git
- Never commit these files to a public repository
- Keep them secure as they grant access to your Google account

## Troubleshooting

### "Access blocked: This app's request is invalid"
- Make sure you added yourself as a test user in the OAuth consent screen

### "The API is not enabled"
- Double-check that both Google Slides API and Google Drive API are enabled

### "credentials.json not found"
- Make sure the file is in the same directory as create_slides.py
- Check that it's named exactly `credentials.json`

## Need Help?

See the official documentation:
- [Google Slides API Quickstart](https://developers.google.com/slides/api/quickstart/python)
- [OAuth 2.0 Setup](https://developers.google.com/workspace/guides/create-credentials)
