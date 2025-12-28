#!/bin/bash
# Monitor scraper progress

echo "=== Scraper Progress Monitor ==="
echo ""
echo "Images downloaded so far: $(ls socks_studio_images/images/ 2>/dev/null | wc -l)"
echo ""
echo "Recent activity:"
tail -20 scraper_output.log
echo ""
echo "To see full log: tail -f scraper_output.log"
