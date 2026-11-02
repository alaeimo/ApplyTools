"""Website views — rewritten for the new async scraper architecture.

The SSE endpoint uses a background thread running an asyncio event loop,
pushing scraped positions through a thread-safe queue.Queue to the main
thread's sync SSE generator. This preserves the exact event schema the
frontend expects while using the new async PositionScraper underneath.

Includes a module-level scrape registry so the frontend can reconnect
to an in-flight scrape after a page refresh.

NOT touched by this rewrite: the positions app, match functionality.
"""
import asyncio
import json
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Dict

from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods
from rest_framework import viewsets, permissions

from .models import Website
from .serializers import WebsiteSerializer

logger = logging.getLogger(__name__)


# ─── Scrape state registry (for reconnect-after-refresh) ────

@dataclass
class ScrapeState:
    """Tracks an in-flight scrape so the frontend can reconnect after refresh.

    NOTE: the field is named `item_queue` (not `queue`) to avoid shadowing
    the `queue` module in `field(default_factory=queue.Queue)`.
    """
    item_queue: queue.Queue = field(default_factory=queue.Queue)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    saved: int = 0
    skipped: int = 0
    failed: int = 0
    total_processed: int = 0
    started_at: float = field(default_factory=time.time)
    completed: bool = False
    error: Optional[str] = None
    last_event_type: Optional[str] = None
    website_id: Optional[int] = None


# Module-level registry: website_id -> ScrapeState
_active_scrapes: Dict[int, ScrapeState] = {}

# How long to keep a completed scrape in the registry (seconds)
SCRAPE_STATE_TTL = 300  # 5 minutes


# ─── DRF ViewSet ─────────────────────────────────────────────

class WebsiteViewSet(viewsets.ModelViewSet):
    """DRF ViewSet for Website CRUD."""
    queryset = Website.objects.all()
    serializer_class = WebsiteSerializer
    permission_classes = [permissions.AllowAny]


# ─── SSE helper ───────────────────────────────────────────────

def _sse(data: dict) -> str:
    """Format a Server-Sent Event chunk."""
    return f"data: {json.dumps(data, default=str)}\n\n"


# ─── Async scraper runner (runs in background thread) ────────

def _run_async_scraper(website_id, max_pages, state, error_holder):
    """Run the async scraper in a dedicated event loop.

    Args:
        website_id: The Website record ID.
        max_pages: Override for max_pages (None = use config).
        state: Shared ScrapeState — items are pushed to state.item_queue.
        error_holder: dict for storing any uncaught exception message.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(
            _scrape_async(website_id, max_pages, state, error_holder)
        )
    except Exception as e:
        logger.exception("Scraper thread crashed")
        error_holder['error'] = str(e)
    finally:
        # Sentinel — signals SSE clients that the scrape is done
        state.item_queue.put(None)
        loop.close()


async def _scrape_async(website_id, max_pages, state, error_holder):
    """Async coroutine that drives the scraper and pushes results to the queue."""
    from apps.scraper.orchestrator.scraper import PositionScraper
    from apps.scraper.pipeline.django_pipeline import DjangoPositionPipeline
    from apps.scraper.services.site_config_provider import website_to_config

    # Re-fetch the website inside the async context to avoid cross-thread ORM issues
    website = await _get_website_async(website_id)
    if website is None:
        error_holder['error'] = f"Website {website_id} not found or inactive"
        return

    config = website_to_config(website)
    if max_pages is not None and max_pages > 0:
        config.max_pages = max_pages

    pipeline = DjangoPositionPipeline(website)
    scraper = PositionScraper(config=config, pipeline=None)

    try:
        state.item_queue.put(('progress', {
            'message': 'Loading existing positions for dedup...',
            'percentage': 5,
        }))
        await pipeline.warmup()

        state.item_queue.put(('progress', {
            'message': f'Extracting positions (max {config.max_pages} pages)...',
            'percentage': 10,
        }))

        # Single async loop (no duplicate nesting)
        async for position in scraper.iter_positions():
            if state.cancel_event.is_set():
                state.item_queue.put(('progress', {
                    'message': 'Cancellation requested — stopping...',
                    'percentage': 100,
                }))
                logger.info("Scrape cancelled by user for website_id=%s", website_id)
                break

            try:
                ok = await pipeline.process(position)
                status = 'saved' if ok else 'skipped'
                if status == 'saved':
                    state.saved += 1
                else:
                    state.skipped += 1
                state.total_processed += 1
                state.last_event_type = status
                state.item_queue.put(('position', (position, status, None)))
            except Exception as e:
                logger.warning("Pipeline error for %s: %s", position.url, e)
                state.failed += 1
                state.total_processed += 1
                state.last_event_type = 'failed'
                state.item_queue.put(('position', (position, 'failed', str(e))))

        state.item_queue.put(('progress', {
            'message': 'Finalizing...',
            'percentage': 95,
        }))

    except Exception as e:
        logger.exception("Async scraper error")
        error_holder['error'] = str(e)
    finally:
        try:
            await scraper.fetcher.close()
        except Exception:
            pass
        try:
            await pipeline.close()
        except Exception:
            pass

        # Mark the scrape as completed in the registry
        state.completed = True
        state.error = error_holder.get('error')
        # Sentinel for any attached SSE clients (put again — harmless if already put)
        state.item_queue.put(None)


async def _get_website_async(website_id):
    """Fetch the Website in a thread-safe manner."""
    from asgiref.sync import sync_to_async

    try:
        return await sync_to_async(Website.objects.get)(
            id=website_id, is_active=True
        )
    except Website.DoesNotExist:
        return None


# ─── SSE streaming view ──────────────────────────────────────

@csrf_exempt
@require_GET
def scrape_website_stream(request, website_id):
    """Stream scraping progress via Server-Sent Events.

    Event schema:
      - start:            {type, message}
      - progress:        {type, message, percentage}
      - position_saved:   {type, title, url, saved, skipped, failed, total_processed}
      - position_skipped: {type, title, url, saved, skipped, failed, total_processed}
      - position_failed:  {type, title, url, error, saved, skipped, failed, total_processed}
      - complete:         {type, saved, skipped, failed, total_processed, total, summary}
      - error:            {type, message}

    Reconnect behavior: if a scrape is already in-flight for this website_id,
    the SSE stream attaches to the existing queue (no new scrape is started).
    """
    logger.info("Scrape request for website_id=%s", website_id)

    # Parse max_pages from query string (default: use website's max_pages)
    max_pages_param = request.GET.get('max_pages')
    max_pages = int(max_pages_param) if max_pages_param else None

    def event_stream():
        # 1. Send start event immediately
        yield _sse({
            'type': 'start',
            'message': f'Starting scrape for website {website_id}...',
        })

        # 2. Clean up old completed scrapes (TTL)
        now = time.time()
        expired = [
            wid for wid, st in _active_scrapes.items()
            if st.completed and (now - st.started_at) > SCRAPE_STATE_TTL
        ]
        for wid in expired:
            _active_scrapes.pop(wid, None)

        # 3. Check if a scrape is already running for this website
        existing = _active_scrapes.get(website_id)
        if existing and not existing.completed:
            logger.info("Attaching to in-flight scrape for website_id=%s", website_id)
            item_queue = existing.item_queue
            state = existing
            thread = None
            error_holder = {'error': None}
        else:
            # Start a new scrape
            state = ScrapeState(website_id=website_id)
            _active_scrapes[website_id] = state
            item_queue = state.item_queue
            error_holder = {'error': None}

            thread = threading.Thread(
                target=_run_async_scraper,
                args=(website_id, max_pages, state, error_holder),
                daemon=True,
            )
            thread.start()

        # 4. Track local counters (for total_processed display)
        saved = 0
        skipped = 0
        failed = 0
        total_processed = 0

        # 5. Drain the queue and yield SSE events
        while True:
            try:
                item = item_queue.get(timeout=300)
            except queue.Empty:
                if thread is None:
                    # Attached to an existing scrape — check if it completed
                    if state.completed:
                        break
                    continue
                if not thread.is_alive():
                    yield _sse({
                        'type': 'error',
                        'message': 'Scraper thread died unexpectedly (timeout).',
                    })
                    break
                continue

            if item is None:
                # Sentinel — scrape is done
                break

            kind, payload = item

            if kind == 'progress':
                yield _sse({'type': 'progress', **payload})
                continue

            # kind == 'position'
            position, status, error = payload
            total_processed += 1

            # Read live counts from the shared state (so reconnects see accurate numbers)
            saved = state.saved
            skipped = state.skipped
            failed = state.failed

            if status == 'saved':
                yield _sse({
                    'type': 'position_saved',
                    'title': position.title,
                    'url': position.url,
                    'saved': saved,
                    'skipped': skipped,
                    'failed': failed,
                    'total_processed': total_processed,
                })
            elif status == 'skipped':
                yield _sse({
                    'type': 'position_skipped',
                    'title': position.title,
                    'url': position.url,
                    'saved': saved,
                    'skipped': skipped,
                    'failed': failed,
                    'total_processed': total_processed,
                })
            else:  # failed
                yield _sse({
                    'type': 'position_failed',
                    'title': position.title,
                    'url': position.url,
                    'error': error or 'Unknown error',
                    'saved': saved,
                    'skipped': skipped,
                    'failed': failed,
                    'total_processed': total_processed,
                })

        # 6. Wait for the thread to finish (only if we started it)
        if thread is not None:
            thread.join(timeout=5)

        # 7. Update scrape stats (only if THIS view started the scrape)
        if thread is not None:
            try:
                website = Website.objects.get(id=website_id)
                website.update_scrape_stats(saved)
            except Website.DoesNotExist:
                pass
            except Exception as e:
                logger.error("Failed to update scrape stats: %s", e)

        # 8. Send completion or error event (read error from shared state)
        was_cancelled = state.cancel_event.is_set() if state else False
        scrape_error = state.error if state else error_holder.get('error')
        if was_cancelled:
            yield _sse({
                'type': 'complete',
                'saved': saved,
                'skipped': skipped,
                'failed': failed,
                'total_processed': total_processed,
                'total': saved,  # don't re-fetch website
                'summary': f'⏹️ Cancelled by user — Saved: {saved}, Skipped: {skipped}, Failed: {failed}',
                'cancelled': True,
            })
        elif scrape_error:
            yield _sse({
                'type': 'error',
                'message': f'Scrape error: {scrape_error}',
            })
        else:
            try:
                website = Website.objects.get(id=website_id)
                total = website.total_scraped_count
            except Website.DoesNotExist:
                total = saved

            yield _sse({
                'type': 'complete',
                'saved': saved,
                'skipped': skipped,
                'failed': failed,
                'total_processed': total_processed,
                'total': total,
                'summary': (
                    f'✅ {saved} saved, ⏭️ {skipped} skipped, '
                    f'❌ {failed} failed (out of {total_processed})'
                ),
            })

        logger.info(
            "Scrape complete: website_id=%s saved=%d skipped=%d failed=%d",
            website_id, saved, skipped, failed,
        )

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


# ─── Scrape status endpoint (for reconnect-after-refresh) ────

def scrape_status(request, website_id):
    """Return the current scrape state for a website.

    Frontend calls this on page load to detect in-flight scrapes.
    """
    state = _active_scrapes.get(website_id)
    if state is None:
        return JsonResponse({'in_progress': False})

    return JsonResponse({
        'in_progress': not state.completed,
        'completed': state.completed,
        'saved': state.saved,
        'skipped': state.skipped,
        'failed': state.failed,
        'total_processed': state.total_processed,
        'last_event_type': state.last_event_type,
        'started_at': state.started_at,
        'error': state.error,
    })

@csrf_exempt
@require_http_methods(["POST"])
def scrape_cancel(request, website_id):
    """Cancel an in-flight scrape."""
    state = _active_scrapes.get(website_id)
    if state and not state.completed:
        state.cancel_event.set()
        logger.info("Cancel requested for website_id=%s", website_id)
        return JsonResponse({'status': 'cancelling', 'website_id': website_id})
    return JsonResponse({'status': 'not_running'}, status=404)