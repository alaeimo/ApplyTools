# from django.test import TestCase
from apps.websites.models import Website
from apps.websites.services import PositionScraper

def test_scraper(website_id, max_pages=1):
    # Get the website object (sync ORM call wrapped with sync_to_async)
    website = Website.objects.get(id=website_id, is_active=True)
    print(f"Testing scraper for: {website.name} ({website.scraping_method})")
    print("=" * 60)

    scraper = PositionScraper(website)
    count = 0

    try:
        for data in scraper.scrape(max_pages):
            count += 1
            print(f"\n📌 Position #{count}")
            print(f"  Title:    {data.get('title', 'N/A')}")
            print(f"  URL:      {data.get('url', 'N/A')}")
            print(f"  Company:  {data.get('company', 'N/A')}")
            # Show a snippet of the cleaned text (first 300 chars)
            text = data.get('cleaned_text', '')
            snippet = text[:300] + ('...' if len(text) > 300 else '')
            print(f"  Text:     {snippet}")
            print("-" * 50)
    except Exception as e:
        print(f"❌ Error during scraping: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # The scraper's scrape() generator already closes the browsers
        # when it finishes (or if an exception occurs). No extra cleanup needed.
        pass

    print(f"\n✅ Scraping finished. Total positions processed: {count}")


