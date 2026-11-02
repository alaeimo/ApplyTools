import json
import logging
import queue
import threading
import asyncio
import time

from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import CV, MatchSession
from .serializers import CVSerializer, MatchSessionSerializer

logger = logging.getLogger(__name__)


class CVViewSet(viewsets.ModelViewSet):
    """CRUD for CV records."""
    queryset = CV.objects.all()
    serializer_class = CVSerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['get'], url_path='latest')
    def latest(self, request):
        """Return the most recently created CV (for default selection)."""
        cv = CV.objects.filter(is_active=True).first()
        if not cv:
            return Response({'detail': 'No CVs found'}, status=404)
        serializer = self.get_serializer(cv)
        return Response(serializer.data)


# ─── Match orchestration ─────────────────────────────────────

# Module-level registry: session_key (str) → MatchQueue (for in-flight SSE)
# This bridges the background thread's async match runner with the sync SSE view.
_active_matches = {}
MATCH_QUEUE_TTL = 300  # 5 minutes


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, default=str)}\n\n"


def _run_async_match(session_key):
    """Run the async matcher in a background thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_match_async(session_key))
    except Exception as e:
        logger.exception("Match thread crashed")
        try:
            session = MatchSession.objects.get(session_key=session_key)
            session.mark_failed(str(e))
        except MatchSession.DoesNotExist:
            pass
    finally:
        state = _active_matches.get(session_key)
        if state:
            state['queue'].put(None)  # sentinel
        loop.close()


async def _match_async(session_key):
    """Async coroutine — drives the matcher, persists progress to DB."""
    from apps.positions.models import Position
    from apps.ai.services.matcher import match_and_save
    from asgiref.sync import sync_to_async

    @sync_to_async
    def _load_session():
        return MatchSession.objects.select_related('cv').get(session_key=session_key)

    @sync_to_async
    def _get_pending_positions(session):
        qs = Position.objects.filter(
            status='SCRAPED', match__isnull=True
        ).order_by('scraped_at')
        if session.last_position_id:
            qs = qs.filter(id__gt=session.last_position_id)
        return list(qs)

    @sync_to_async
    def _count_pending(session):
        qs = Position.objects.filter(status='SCRAPED', match__isnull=True)
        if session.last_position_id:
            qs = qs.filter(id__gt=session.last_position_id)
        return qs.count()

    @sync_to_async
    def _save_session(session, fields):
        session.save(update_fields=fields)

    @sync_to_async
    def _mark_completed(session):
        session.mark_completed()

    @sync_to_async
    def _mark_failed(session, error):
        session.mark_failed(error)

    @sync_to_async
    def _check_cancelled(session):
        session.refresh_from_db()
        return session.cancel_requested
    
    session = await _load_session()
    cv_text = await sync_to_async(lambda: session.cv.get_text())()

    if not cv_text:
        await _mark_failed(session, "CV has no text content")
        return

    # Set total_positions
    total = await _count_pending(session)
    session.total_positions = total
    await _save_session(session, ['total_positions'])

    state = _active_matches.setdefault(session_key, {
        'queue': queue.Queue(),
        'started_at': time.time(),
    })
    item_queue = state['queue']

    # Initial progress event
    item_queue.put(('progress', {
        'message': f'Starting match for {total} positions...',
        'percentage': 5,
    }))

    conversation_id = session.conversation_id or None

    positions = await _get_pending_positions(session)

    for idx, position in enumerate(positions, session.total_processed + 1):
         # ─── Check for cancellation ───
        if await _check_cancelled(session):
            item_queue.put(('progress', {
                'message': 'Cancellation requested — stopping...',
                'percentage': 100,
            }))
            logger.info("Match cancelled by user for session=%s", session_key)
            break
        # Send progress
        pct = int((idx / max(total, 1)) * 100) if total else 100
        item_queue.put(('progress', {
            'message': f'Processing {idx}/{total}: {position.title[:50]}...',
            'percentage': min(pct, 95),
        }))

        try:
            # match_and_save is a sync blocking function — run it in a worker thread
            result = await sync_to_async(match_and_save)(
                cv_text, position.id,
                session.language,
                conversation_id=conversation_id,
            )

            # Extract conversation_id from result
            new_cid = result.get('_metadata', {}).get('conversation_id')
            if new_cid and new_cid != conversation_id:
                conversation_id = new_cid
                session.conversation_id = conversation_id

            if 'error' in result:
                session.failed += 1
                # If we had a conversation_id that may have caused the failure,
                # reset it so the NEXT position starts a fresh chat.
                # This ensures at most ONE new chat per failure — not one per position.
                if conversation_id:
                    conversation_id = None
                    session.conversation_id = ''
                    logger.info("Reset conversation_id after failure — next position will start a new chat")
                item_queue.put(('position', {
                    'position_id': position.id,
                    'title': position.title,
                    'error': result.get('error', 'Unknown'),
                    'status': 'failed',
                }))
            else:
                session.saved += 1
                score = result.get('matching_score', {}).get('overall_score', 0)
                category = result.get('final_verdict', {}).get('match_category', 'unknown')
                match_id = result.get('_metadata', {}).get('match_id')
                item_queue.put(('position', {
                    'position_id': position.id,
                    'title': position.title,
                    'score': score,
                    'category': category,
                    'match_id': match_id,
                    'status': 'matched',
                }))

        except Exception as e:
            logger.warning("Match failed for position %s: %s", position.id, e)
            session.failed += 1
            # Reset conversation_id on exception too — could be a stale session
            if conversation_id:
                conversation_id = None
                session.conversation_id = ''
                logger.info("Reset conversation_id after exception — next position will start a new chat")
            item_queue.put(('position', {
                'position_id': position.id,
                'title': position.title,
                'error': str(e),
                'status': 'failed',
            }))

        # Persist progress in DB (so reconnects see accurate counts)
        session.total_processed = idx
        session.last_position_id = position.id
        await _save_session(session, [
            'saved', 'skipped', 'failed', 'total_processed',
            'last_position_id', 'conversation_id',
        ])

    # Done
    if await _check_cancelled(session):
        # User cancelled — mark completed but indicate cancellation
        await _mark_completed(session)
        item_queue.put(('progress', {
            'message': 'Cancelled.',
            'percentage': 100,
        }))
        item_queue.put(('cancelled', {
            'saved': session.saved,
            'skipped': session.skipped,
            'failed': session.failed,
            'total_processed': session.total_processed,
            'summary': f'⏹️ Cancelled by user — Saved: {session.saved}, Failed: {session.failed}',
        }))
    else:
        await _mark_completed(session)
        item_queue.put(('progress', {
            'message': 'Finalizing...',
            'percentage': 100,
        }))
        item_queue.put(None)  # sentinel
# ─── Endpoints ────────────────────────────────────────────────

@csrf_exempt
def match_start(request):
    """Create a MatchSession. Returns session_key.

    POST body: { "cv_id": 1, "language": "English" }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        body = json.loads(request.body)
        cv_id = body.get('cv_id')
        language = body.get('language', 'English')
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not cv_id:
        return JsonResponse({'error': 'cv_id is required'}, status=400)

    try:
        cv = CV.objects.get(id=cv_id, is_active=True)
    except CV.DoesNotExist:
        return JsonResponse({'error': 'CV not found'}, status=404)

    session = MatchSession.objects.create(
        cv=cv,
        language=language,
        status='in_progress',
    )

    # Start the background thread
    thread = threading.Thread(
        target=_run_async_match,
        args=(str(session.session_key),),
        daemon=True,
    )
    thread.start()

    return JsonResponse({
        'session_key': str(session.session_key),
        'total_positions': session.total_positions,
        'language': session.language,
    })


@csrf_exempt
def match_stream(request, session_key):
    """SSE stream for a match session. Reconnects to in-flight matches."""
    try:
        session = MatchSession.objects.get(session_key=session_key)
    except MatchSession.DoesNotExist:
        return StreamingHttpResponse(
            _sse({'type': 'error', 'message': 'Session not found'}),
            content_type='text/event-stream'
        )

    # If already completed, send final state immediately
    if session.status == 'completed':
        def _done():
            yield _sse({
                'type': 'complete',
                'saved': session.saved,
                'skipped': session.skipped,
                'failed': session.failed,
                'total': session.total_positions,
                'total_processed': session.total_processed,
                'summary': f'✅ {session.saved} matched, ❌ {session.failed} failed',
            })
        return StreamingHttpResponse(_done(), content_type='text/event-stream')

    # Attach to the in-flight queue
    state = _active_matches.get(session_key)
    if not state:
        # Session exists in DB but no active queue — restart from last_position_id
        state = {'queue': queue.Queue(), 'started_at': time.time()}
        _active_matches[session_key] = state
        # Restart the background thread
        thread = threading.Thread(
            target=_run_async_match,
            args=(session_key,),
            daemon=True,
        )
        thread.start()

    item_queue = state['queue']

    def event_stream():
        # Refresh session from DB for live counts
        yield _sse({
            'type': 'start',
            'message': f'Resuming match (saved={session.saved}, skipped={session.skipped}, failed={session.failed})...',
            'saved': session.saved,
            'skipped': session.skipped,
            'failed': session.failed,
            'total_processed': session.total_processed,
            'total_positions': session.total_positions,
        })

        saved = session.saved
        skipped = session.skipped
        failed = session.failed
        total_processed = session.total_processed

        while True:
            try:
                item = item_queue.get(timeout=600)
            except queue.Empty:
                # Check if session completed while we waited
                session.refresh_from_db()
                if session.status in ('completed', 'failed'):
                    break
                continue

            if item is None:
                break

            kind, payload = item

            if kind == 'progress':
                yield _sse({'type': 'progress', **payload})
                continue

            if kind == 'cancelled':
                yield _sse({'type': 'complete', 'cancelled': True, **payload})
                continue
            # kind == 'position'
            session.refresh_from_db()
            saved = session.saved
            skipped = session.skipped
            failed = session.failed
            total_processed = session.total_processed

            status = payload.pop('status', 'matched')
            payload['saved'] = saved
            payload['skipped'] = skipped
            payload['failed'] = failed
            payload['total_processed'] = total_processed

            if status == 'matched':
                yield _sse({'type': 'position_matched', **payload})
            elif status == 'failed':
                yield _sse({'type': 'position_failed', **payload})
            else:
                yield _sse({'type': 'position_skipped', **payload})

        # Final completion event
        session.refresh_from_db()
        if session.status == 'failed':
            yield _sse({
                'type': 'error',
                'message': session.error or 'Match failed',
            })
        else:
            yield _sse({
                'type': 'complete',
                'saved': session.saved,
                'skipped': session.skipped,
                'failed': session.failed,
                'total': session.total_positions,
                'total_processed': session.total_processed,
                'summary': (
                    f'✅ {session.saved} matched, ⏭️ {session.skipped} skipped, '
                    f'❌ {session.failed} failed (out of {session.total_positions})'
                ),
            })

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


def match_status(request, session_key):
    """Return current state of a match session."""
    try:
        session = MatchSession.objects.get(session_key=session_key)
    except MatchSession.DoesNotExist:
        return JsonResponse({'in_progress': False, 'error': 'Session not found'})

    return JsonResponse({
        'in_progress': session.status == 'in_progress',
        'completed': session.status == 'completed',
        'failed': session.status == 'failed',
        'saved': session.saved,
        'skipped': session.skipped,
        'failed_count': session.failed,
        'total_processed': session.total_processed,
        'total_positions': session.total_positions,
        'last_position_id': session.last_position_id,
        'started_at': session.started_at.isoformat() if session.started_at else None,
        'completed_at': session.completed_at.isoformat() if session.completed_at else None,
        'error': session.error,
        'language': session.language,
        'cv_id': session.cv_id,
        'cv_name': session.cv.name,
    })

@csrf_exempt
@require_http_methods(["POST"])
def match_cancel(request, session_key):
    """Cancel an in-flight match session."""
    try:
        session = MatchSession.objects.get(session_key=session_key)
    except MatchSession.DoesNotExist:
        return JsonResponse({'status': 'not_found'}, status=404)

    if session.status == 'in_progress':
        session.cancel_requested = True
        session.save(update_fields=['cancel_requested'])
        logger.info("Cancel requested for match session=%s", session_key)
        return JsonResponse({'status': 'cancelling', 'session_key': session_key})
    return JsonResponse({'status': 'not_running'}, status=404)