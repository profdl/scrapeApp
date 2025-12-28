# LLM Metadata Enhancement

The slides creator can now use Claude AI to extract missing date and medium information from article text when it's not available in the structured metadata.

## How it works

When processing an article, if the year or medium is not found in the structured metadata (JSON-LD schema or HTML meta tags), the script will:
1. Extract the article text
2. Send it to Claude 3.5 Haiku
3. Ask Claude to identify the year and medium of the artwork/project
4. Add this information to the slide captions

## Setup

### Option 1: API Key File (Recommended - Easiest!)

1. Get your API key from: https://console.anthropic.com/
2. Create a file named `anthropic_api_key.txt` in the project directory
3. Paste your API key into the file (just the key, nothing else)

```bash
echo "sk-ant-your-actual-key-here" > anthropic_api_key.txt
```

That's it! The script will automatically read the key from this file.

**Note:** The `.gitignore` file is already configured to exclude `anthropic_api_key.txt` from version control, so your key stays private.

### Option 2: Environment Variable

Alternatively, you can set an environment variable:

```bash
export ANTHROPIC_API_KEY='sk-ant-your-actual-key-here'
```

## Usage

Once the API key is configured (via file or environment variable), the enhancement happens automatically:

```bash
source venv/bin/activate
python create_slides.py
```

The script will show when it's using LLM enhancement:
```
Processing: https://socks-studio.com/...
  Enhancing metadata with LLM...
    Found year: 1985
    Found medium: Photography
```

## Cost

This feature uses Claude 3.5 Haiku, which is very cost-effective:
- ~$0.001 per article (approximately)
- Only runs when metadata is missing
- Uses minimal tokens (max 200 output + ~1000 input per article)

## Without API key

If no API key is provided (no file and no environment variable), the script works normally but won't enhance missing metadata - captions will show "Unknown" for missing year/medium fields instead.
