"""
ApplyTools — Gemini (Google AI Studio) client
Drop-in replacement for DeepSeekClient.

Free tier (Nov 2026):
  - 15 RPM (requests per minute)
  - 1,500 RPD (requests per day)
  - 1M TPM (tokens per minute)
  - 1M token context window
  - No credit card required

Auth: API key from https://aistudio.google.com/apikey
"""
import os
import uuid
import logging
import threading
from typing import Optional, Iterator, Dict, Any, List

logger = logging.getLogger(__name__)

try:
    from google import genai
    from google.genai import types as gtypes
except ImportError:
    genai = None
    gtypes = None


class GeminiResponse:
    """
    Wrapper that mimics the DeepSeekClient response object so the rest of
    the matcher code (matcher.py) doesn't need to change.

    Exposes:
      - .text  -> str (the model's text response)
      - .conversation_id -> str (the conversation_id used for this call)
    """
    def __init__(self, text: str, conversation_id: str):
        self.text = text
        self.conversation_id = conversation_id

    def __repr__(self):
        return f"GeminiResponse(conversation_id={self.conversation_id!r}, text_len={len(self.text)})"


def _make_content(role: str, text: str):
    """Build a google.genai.types.Content object from a role + text string."""
    return gtypes.Content(
        role=role,
        parts=[gtypes.Part(text=text)],
    )


class GeminiClient:
    """
    Drop-in replacement for DeepSeekClient.

    Maintains per-conversation chat history in memory as types.Content objects
    (NOT plain dicts — the SDK rejects dicts) so multi-turn chats work.

    Interface (compatible with DeepSeekClient):
      - chat(prompt, conversation_id=None) -> GeminiResponse
      - stream(prompt, conversation_id=None) -> Iterator[str]
      - reset_conversation(conversation_id=None) -> None
    """

    DEFAULT_MODEL = "gemini-3.1-flash-lite"
    MAX_CONVERSATIONS = 20

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        if genai is None or gtypes is None:
            raise ImportError(
                "google-genai not installed. Run: pip install google-genai"
            )

        from django.conf import settings
        self.api_key = (
            api_key
            or getattr(settings, 'GEMINI_API_KEY', None)
            or os.environ.get('GEMINI_API_KEY')
            or os.environ.get('GOOGLE_API_KEY')
        )
        if not self.api_key:
            raise ValueError(
                "No Gemini API key found. Set GEMINI_API_KEY in .env or "
                "config/settings.py, or pass api_key=... to GeminiClient(). "
                "Get a free key at https://aistudio.google.com/apikey"
            )

        self.model_name = (
            model
            or getattr(settings, 'GEMINI_MODEL', None)
            or self.DEFAULT_MODEL
        )

        self.temperature = getattr(settings, 'GEMINI_TEMPERATURE', 0.7)
        self.max_output_tokens = getattr(settings, 'GEMINI_MAX_OUTPUT_TOKENS', 8192)
        self.timeout = getattr(settings, 'GEMINI_TIMEOUT', 120)

        self._client = genai.Client(api_key=self.api_key)

        # In-memory conversation store: conversation_id -> list of types.Content
        # Each entry is a types.Content object (NOT a plain dict).
        self._conversations: Dict[str, List] = {}
        self._lock = threading.Lock()

        logger.info(
            "GeminiClient initialised: model=%s, temperature=%.2f, max_tokens=%d",
            self.model_name, self.temperature, self.max_output_tokens,
        )

    # ─── Internals ───────────────────────────────────────────────

    def _build_config(self, search: bool = False):
        kwargs: Dict[str, Any] = {
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
        }
        if search:
            kwargs["tools"] = [gtypes.Tool(google_search=gtypes.GoogleSearch())]
        return gtypes.GenerateContentConfig(**kwargs)

    def _get_or_create_history(self, conversation_id: Optional[str]):
        """
        Returns (conversation_id, history_list, is_new).
        Acquires the lock, ensures the conversation exists, and returns a
        reference to the history list (which remains valid after the lock
        is released because Python lists are mutable references).
        """
        with self._lock:
            if conversation_id is None or conversation_id not in self._conversations:
                conversation_id = conversation_id or str(uuid.uuid4())
                if conversation_id not in self._conversations:
                    self._conversations[conversation_id] = []
                    self._evict_if_needed()
                is_new = True
            else:
                is_new = False
            # Grab reference to the history list (still valid after lock release)
            history = self._conversations[conversation_id]
        return conversation_id, history, is_new

    def _evict_if_needed(self) -> None:
        """Caller must hold self._lock."""
        if len(self._conversations) <= self.MAX_CONVERSATIONS:
            return
        oldest = next(iter(self._conversations))
        del self._conversations[oldest]
        logger.debug("Evicted oldest Gemini conversation %s", oldest)

    # ─── Public API ──────────────────────────────────────────────

    def chat(
        self,
        prompt: str,
        conversation_id: Optional[str] = None,
        thinking: bool = False,   # ignored — Gemini Flash doesn't expose this
        search: bool = False,     # enable Google Search grounding if True
        **kwargs,
    ) -> GeminiResponse:
        """
        Send a prompt and return the model's text response.

        If conversation_id is None OR unknown to us, a NEW conversation is
        started. The returned GeminiResponse.conversation_id tells the caller
        which conversation was used — pass it back on the next call to
        continue the same chat.
        """
        from django.conf import settings

        conversation_id, history, is_new = self._get_or_create_history(conversation_id)

        # Build the user Content object — MUST be types.Content, NOT a dict.
        user_content = _make_content('user', prompt)
        history.append(user_content)

        config = self._build_config(search=search)

        # Retry on transient network errors (WinError 10053, 10054, 10060,
        # ConnectionError, TimeoutError, etc.) — common on Windows with VPNs,
        # antivirus, or proxy software that kills long-lived connections.
        max_retries = getattr(settings, 'GEMINI_MAX_RETRIES', 3)
        base_delay = float(getattr(settings, 'GEMINI_RETRY_BASE_DELAY', '2.0'))
        text = None
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=history,  # list of types.Content objects
                    config=config,
                )
                # response.text raises ValueError if the response was blocked
                try:
                    text = response.text or ""
                except ValueError:
                    # Likely a safety block — extract whatever parts we can
                    text = ""
                    if hasattr(response, 'candidates') and response.candidates:
                        for cand in response.candidates:
                            if hasattr(cand, 'content') and cand.content:
                                for part in cand.content.parts:
                                    if hasattr(part, 'text') and part.text:
                                        text += part.text
                    if not text:
                        text = '{"final_verdict": {"match_category": "error", "summary": "Gemini response was blocked or empty (likely safety filter)"}}'
                        logger.warning(
                            "Gemini response blocked/empty for conversation_id=%s — using fallback",
                            conversation_id,
                        )
                last_error = None
                break  # success — exit retry loop

            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                # Detect transient/network errors worth retrying
                is_transient = (
                    'winerror 10053' in err_str or  # connection aborted
                    'winerror 10054' in err_str or  # connection reset
                    'winerror 10060' in err_str or  # timeout
                    'connectionerror' in err_str or
                    'connection aborted' in err_str or
                    'connection reset' in err_str or
                    'timeout' in err_str or
                    'timed out' in err_str or
                    'remote end' in err_str or
                    'chunked encoding' in err_str or
                    isinstance(e, (ConnectionError, TimeoutError, OSError))
                )

                if is_transient and attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))  # 2s, 4s, 8s, ...
                    logger.warning(
                        "Gemini transient error (attempt %d/%d, conversation_id=%s): %s — retrying in %.1fs",
                        attempt, max_retries, conversation_id, e, delay,
                    )
                    import time as _time
                    _time.sleep(delay)
                    continue
                else:
                    # Non-transient error OR retries exhausted — bail out
                    logger.error(
                        "Gemini API error (conversation_id=%s, attempt %d/%d): %s",
                        conversation_id, attempt, max_retries, e,
                    )
                    # Remove the user message we just appended so the next call
                    # doesn't have a dangling incomplete turn
                    if history and history[-1] is user_content:
                        history.pop()
                    raise

        # Should not happen, but guard anyway
        if text is None:
            if history and history[-1] is user_content:
                history.pop()
            raise last_error or RuntimeError("Gemini returned no text")

        # Append model response to history (so the conversation grows correctly)
        model_content = _make_content('model', text)
        history.append(model_content)

        logger.debug(
            "Gemini chat: conversation_id=%s (new=%s), prompt_len=%d, response_len=%d",
            conversation_id, is_new, len(prompt), len(text),
        )

        return GeminiResponse(text=text, conversation_id=conversation_id)

    def stream(
        self,
        prompt: str,
        conversation_id: Optional[str] = None,
        **kwargs,
    ) -> Iterator[str]:
        """Stream the response chunk by chunk. Returns an iterator of str chunks."""

        from django.conf import settings
        conversation_id, history, _ = self._get_or_create_history(conversation_id)

        user_content = _make_content('user', prompt)
        history.append(user_content)

        config = self._build_config()

        # Retry on transient network errors
        max_retries = getattr(settings, 'GEMINI_MAX_RETRIES', 3)
        base_delay = float(getattr(settings, 'GEMINI_RETRY_BASE_DELAY', '2.0'))

        for attempt in range(1, max_retries + 1):
            full_text = ""
            try:
                stream = self._client.models.generate_content_stream(
                    model=self.model_name,
                    contents=history,
                    config=config,
                )
                for chunk in stream:
                    try:
                        chunk_text = chunk.text or ""
                    except ValueError:
                        chunk_text = ""
                    full_text += chunk_text
                    yield chunk_text
                break  # success
            except Exception as e:
                err_str = str(e).lower()
                # Check for SDK-specific error types first
                from google.genai import errors as genai_errors
                is_retryable_sdk_error = isinstance(e, (
                    genai_errors.ServerError,    # 500, 502, 503, 504
                    genai_errors.ClientError,   # 429 (rate limit) — retryable
                ))

                is_transient = is_retryable_sdk_error or (
                    'winerror 10053' in err_str or
                    'winerror 10054' in err_str or
                    'winerror 10060' in err_str or
                    'connectionerror' in err_str or
                    'connection aborted' in err_str or
                    'connection reset' in err_str or
                    'timeout' in err_str or
                    'timed out' in err_str or
                    'remote end' in err_str or
                    'chunked encoding' in err_str or
                    '503' in err_str or           # service unavailable
                    '502' in err_str or           # bad gateway
                    '500' in err_str or           # internal server error
                    '504' in err_str or           # gateway timeout
                    '429' in err_str or           # rate limit
                    'high demand' in err_str or   # Gemini's overload message
                    'try again later' in err_str or
                    'unavailable' in err_str or
                    isinstance(e, (ConnectionError, TimeoutError, OSError))
                )
                if is_transient and attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "Gemini stream transient error (attempt %d/%d, conversation_id=%s): %s — retrying in %.1fs",
                        attempt, max_retries, conversation_id, e, delay,
                    )
                    import time as _time
                    _time.sleep(delay)
                    continue
                else:
                    logger.error(
                        "Gemini stream error (conversation_id=%s, attempt %d/%d): %s",
                        conversation_id, attempt, max_retries, e,
                    )
                    if history and history[-1] is user_content:
                        history.pop()
                    raise

        # Append the full streamed response to history
        model_content = _make_content('model', full_text)
        history.append(model_content)

    def reset_conversation(self, conversation_id: Optional[str] = None) -> None:
        """Clear conversation history. If conversation_id is None, clear ALL."""
        with self._lock:
            if conversation_id is None:
                count = len(self._conversations)
                self._conversations.clear()
                logger.info("Cleared all %d Gemini conversation(s)", count)
            elif conversation_id in self._conversations:
                del self._conversations[conversation_id]
                logger.info("Cleared Gemini conversation %s", conversation_id)

    # Aliases for compatibility with various method names the matcher might use
    def new_conversation(self) -> str:
        """Start a fresh conversation and return its ID."""
        cid = str(uuid.uuid4())
        with self._lock:
            self._conversations[cid] = []
            self._evict_if_needed()
        return cid

    def clear_history(self, conversation_id: Optional[str] = None) -> None:
        self.reset_conversation(conversation_id)


# ─── Provider-agnostic factory (used by matcher.py) ─────────────

_client_singleton = None
_client_lock = threading.Lock()


def get_ai_client():
    """
    Factory: returns a DeepSeekClient or GeminiClient based on settings.
    Single instance per process (singleton).
    """
    global _client_singleton
    if _client_singleton is not None:
        return _client_singleton

    with _client_lock:
        if _client_singleton is not None:
            return _client_singleton

        from django.conf import settings
        provider = (
            getattr(settings, 'APPLYTOOLS_AI_PROVIDER', 'gemini')
            or os.environ.get('APPLYTOOLS_AI_PROVIDER', 'gemini')
        ).lower().strip()

        if provider == 'gemini':
            # If AI_FALLBACK_MODELS is set, use FallbackClient (multi-model chain)
            fallback_models_str = (
                getattr(settings, 'AI_FALLBACK_MODELS', None)
                or os.environ.get('AI_FALLBACK_MODELS', '')
            )
            if fallback_models_str:
                client = FallbackClient()
                logger.info("AI provider: FallbackClient with chain [%s]",
                            ', '.join(client.models))
            else:
                client = GeminiClient()
                logger.info("AI provider: Gemini (%s)", client.model_name)
        elif provider == 'deepseek':
            from apps.ai.deepseek import DeepSeekClient
            client = DeepSeekClient()
            logger.info("AI provider: DeepSeek")
        elif provider == 'fallback':
            # Explicit 'fallback' provider — requires AI_FALLBACK_MODELS
            client = FallbackClient()
            logger.info("AI provider: FallbackClient with chain [%s]",
                        ', '.join(client.models))
        else:
            raise ValueError(
                f"Unknown APPLYTOOLS_AI_PROVIDER={provider!r}. "
                f"Supported: 'gemini', 'deepseek', or 'fallback'."
            )

        _client_singleton = client
        return client



# ─── Fallback chain client ─────────────────────────────────────

class FallbackClient:
    """
    Wraps multiple GeminiClient instances (each pointing to a different model)
    and tries them in order until one succeeds. Maintains a SEPARATE
    conversation history per (model, conversation_id) pair — so when we
    fall back to a different model, that model starts a fresh chat.

    Interface (compatible with DeepSeekClient / GeminiClient):
      - chat(prompt, conversation_id=None) -> GeminiResponse
      - reset_conversation(conversation_id=None) -> None

    Configuration (in .env / settings.py):
        AI_FALLBACK_MODELS=gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-3.8-flash
        # Optionally add deepseek at the end:
        # AI_FALLBACK_MODELS=gemini-3.5-flash-lite,gemini-3.1-flash-lite,deepseek
    """

    def __init__(self, models: Optional[list] = None, api_key: Optional[str] = None):
        from django.conf import settings

        # Resolve the model list
        if models is None:
            models_str = (
                getattr(settings, 'AI_FALLBACK_MODELS', None)
                or os.environ.get('AI_FALLBACK_MODELS', '')
            )
            models = [m.strip() for m in models_str.split(',') if m.strip()]

        if not models:
            # Fallback: just use the default Gemini model
            models = [getattr(settings, 'GEMINI_MODEL', None) or GeminiClient.DEFAULT_MODEL]

        self.models = models
        self._clients: Dict[str, Any] = {}  # model_name -> client instance
        self._active_model: Optional[str] = None
        # Per-conversation model tracking: conversation_id -> model_name
        # (so the next call with the same conversation_id goes to the same model)
        self._conversation_models: Dict[str, str] = {}
        self._lock = threading.Lock()

        # Instantiate each client eagerly so we fail fast on bad config
        for model in self.models:
            if model.lower() == 'deepseek':
                try:
                    from apps.ai.deepseek import DeepSeekClient
                    self._clients[model] = DeepSeekClient()
                    logger.info("FallbackClient: initialised DeepSeek client")
                except Exception as e:
                    logger.warning("FallbackClient: failed to init DeepSeek: %s — skipping", e)
            else:
                try:
                    self._clients[model] = GeminiClient(model=model, api_key=api_key)
                    logger.info("FallbackClient: initialised Gemini client for model=%s", model)
                except Exception as e:
                    logger.warning("FallbackClient: failed to init Gemini model=%s: %s — skipping", model, e)

        if not self._clients:
            raise ValueError(
                "FallbackClient: no usable AI clients. Check AI_FALLBACK_MODELS and "
                "your API keys (GEMINI_API_KEY / DEEPSEEK_API_KEY)."
            )

        # Pick the first available model as the default starting point
        self._active_model = next(iter(self._clients.keys()))
        logger.info(
            "FallbackClient: %d model(s) in chain: %s. Starting with %s",
            len(self._clients), ', '.join(self._clients.keys()), self._active_model,
        )

    def chat(
        self,
        prompt: str,
        conversation_id: Optional[str] = None,
        **kwargs,
    ) -> GeminiResponse:
        """
        Try each model in order. If a model raises a non-retryable error OR
        exhausts its retries, move on to the next model.

        If conversation_id is set and we've already picked a model for it,
        we'll try that model FIRST (to keep conversation continuity),
        then fall back to the others if it fails.
        """
        # Resolve conversation_id and the "preferred" model for it
        with self._lock:
            if conversation_id and conversation_id in self._conversation_models:
                preferred_model = self._conversation_models[conversation_id]
            else:
                preferred_model = self._active_model
                if conversation_id is None:
                    conversation_id = str(uuid.uuid4())

        # Build the ordered list of models to try:
        # preferred first, then the rest in original order
        ordered_models = [preferred_model] + [
            m for m in self._clients.keys() if m != preferred_model
        ]

        last_error = None
        for model_name in ordered_models:
            client = self._clients[model_name]
            try:
                response = client.chat(prompt, conversation_id=conversation_id, **kwargs)
                # Success — remember which model served this conversation
                with self._lock:
                    self._conversation_models[conversation_id] = model_name
                    self._active_model = model_name
                # Make sure the response carries the correct conversation_id
                # (the underlying client may have generated a new one)
                response.conversation_id = conversation_id
                logger.debug(
                    "FallbackClient: success on model=%s (conversation_id=%s)",
                    model_name, conversation_id,
                )
                return response

            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                # Decide if this error should trigger a fallback to the next model
                should_fallback = (
                    '503' in err_str or           # service unavailable
                    '502' in err_str or           # bad gateway
                    '500' in err_str or           # internal server error
                    '504' in err_str or           # gateway timeout
                    'high demand' in err_str or
                    'unavailable' in err_str or
                    'try again later' in err_str or
                    'overloaded' in err_str or
                    'capacity' in err_str or
                    'model is no longer available' in err_str or  # deprecation
                    '404' in err_str or           # model not found
                    '429' in err_str or           # rate limit (try a different model)
                    'winerror 10053' in err_str or  # connection aborted
                    'winerror 10054' in err_str or  # connection reset
                    'winerror 10060' in err_str or  # timeout
                    isinstance(e, (ConnectionError, TimeoutError, OSError))
                )

                if should_fallback:
                    logger.warning(
                        "FallbackClient: model=%s failed (%s) — trying next model",
                        model_name, str(e)[:120],
                    )
                    continue
                else:
                    # Non-fallback-worthy error (auth, bad request, safety block)
                    # — raise immediately so the caller knows
                    logger.error(
                        "FallbackClient: model=%s raised non-fallback error: %s",
                        model_name, e,
                    )
                    raise

        # All models failed
        raise RuntimeError(
            f"FallbackClient: all {len(self._clients)} model(s) failed. "
            f"Last error: {last_error}"
        )

    def reset_conversation(self, conversation_id: Optional[str] = None) -> None:
        """Clear conversation history across ALL underlying clients."""
        with self._lock:
            if conversation_id is None:
                # Reset everything
                for client in self._clients.values():
                    try:
                        client.reset_conversation()
                    except Exception as e:
                        logger.warning("FallbackClient: error clearing %s: %s",
                                       client.__class__.__name__, e)
                self._conversation_models.clear()
            else:
                # Reset only the specified conversation
                model_name = self._conversation_models.get(conversation_id)
                if model_name and model_name in self._clients:
                    try:
                        self._clients[model_name].reset_conversation(conversation_id)
                    except Exception:
                        pass
                self._conversation_models.pop(conversation_id, None)

    # Aliases for compatibility
    def new_conversation(self) -> str:
        cid = str(uuid.uuid4())
        # Don't pre-assign a model — the first chat() call will pick one
        return cid

    def clear_history(self, conversation_id: Optional[str] = None) -> None:
        self.reset_conversation(conversation_id)