import json
import logging
from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets, permissions
from .models import Website
from .serializers import WebsiteSerializer
from .services import ScrapeOrchestrator

logger = logging.getLogger(__name__)

class WebsiteViewSet(viewsets.ModelViewSet):
    queryset = Website.objects.all()
    serializer_class = WebsiteSerializer
    permission_classes = [permissions.AllowAny]  
    

@csrf_exempt
def scrape_website_stream(request, website_id):
    """Stream scraping progress in real-time using Server-Sent Events."""
    logger.info(f"🔍 Scrape request received for website ID: {website_id}")
    logger.info(f"📝 Request path: {request.path}")
    logger.info(f"📝 Request method: {request.method}")
    
    def event_stream():
        try:
            logger.info(f"🔍 Looking for website ID: {website_id}")
            website = Website.objects.get(id=website_id, is_active=True)
            logger.info(f"✅ Found website: {website.name}")
            max_pages = request.GET.get('max_pages')
            max_pages = 10 
            if max_pages:
                max_pages = int(max_pages)
                logger.info(f"📄 Max pages: {max_pages}")
            
            # Send initial event
            yield f"data: {json.dumps({'type': 'start', 'message': f'Starting scrape for {website.name}...'})}\n\n"
            
            # Run the scrape with progress tracking
            orchestrator = ScrapeOrchestrator(website)
            
            saved = 0
            skipped = 0
            failed = 0
            existing_urls = set(website.positions.values_list('url', flat=True))
            
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Extracting links...', 'percentage': 10})}\n\n"
            
            for data in orchestrator.scraper.scrape(max_pages):
                if data['url'] in existing_urls:
                    skipped += 1
                    continue
                try:
                    orchestrator._save_position(data)
                    saved += 1
                    existing_urls.add(data['url'])
                    yield f"data: {json.dumps({'type': 'position_saved', 'title': data['title'], 'saved': saved, 'skipped': skipped})}\n\n"
                except Exception as e:
                    failed += 1
                    logger.error(f"❌ Error saving position: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'title': data['title']})}\n\n"
            
            # Update stats
            website.update_scrape_stats(saved)
            
            # Send completion event
            yield f"data: {json.dumps({'type': 'complete', 'saved': saved, 'skipped': skipped, 'failed': failed, 'total': website.total_scraped_count})}\n\n"
            logger.info(f"✅ Scrape complete: saved={saved}, skipped={skipped}, failed={failed}")
            
        except Website.DoesNotExist:
            logger.error(f"❌ Website {website_id} not found")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Website not found'})}\n\n"
        except Exception as e:
            logger.error(f"❌ Scrape error: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
    return response