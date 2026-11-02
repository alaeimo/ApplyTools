import uuid
from django.db import models
from django.utils import timezone


class CV(models.Model):
    """A candidate CV — either pasted text or uploaded file (pdf/txt)."""

    FILE_TYPE_CHOICES = [
        ('txt', 'Text File'),
        ('pdf', 'PDF File'),
        ('paste', 'Pasted Text'),
    ]

    name = models.CharField(
        max_length=200,
        help_text="A friendly name to identify this CV"
    )
    content = models.TextField(
        blank=True,
        help_text="Pasted CV text, or extracted from file"
    )
    file = models.FileField(
        upload_to='cvs/',
        null=True, blank=True,
        help_text="Uploaded CV file (PDF or TXT)"
    )
    file_type = models.CharField(
        max_length=10,
        choices=FILE_TYPE_CHOICES,
        default='paste',
        help_text="How the CV was provided"
    )
    language = models.CharField(
        max_length=50,
        default='English',
        help_text="Default response language for matches using this CV"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['language']),
        ]
        verbose_name = "CV"
        verbose_name_plural = "CVs"

    def __str__(self):
        return f"{self.name} ({self.language})"

    def get_text(self) -> str:
        """Return CV text — from content field or extracted from file."""
        if self.content:
            return self.content
        if not self.file:
            return ''
        ext = (self.file.name.split('.')[-1] or '').lower()
        try:
            if ext == 'txt':
                return self.file.read().decode('utf-8', errors='replace')
            elif ext == 'pdf':
                return _extract_pdf_text(self.file.path)
        except Exception as e:
            return f"[CV extraction failed: {e}]"
        return ''


def _extract_pdf_text(pdf_path: str) -> str:
    """Extract text from a PDF file using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        return "[pdfplumber not installed — run: pip install pdfplumber]"
    pages_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            pages_text.append(page.extract_text() or '')
    return '\n'.join(pages_text).strip()


class MatchSession(models.Model):
    """Tracks a match run — survives page refresh."""

    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    session_key = models.UUIDField(
        unique=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Public identifier shared with the frontend"
    )
    cv = models.ForeignKey(
        CV,
        on_delete=models.CASCADE,
        related_name='match_sessions'
    )
    language = models.CharField(max_length=50, default='English')

    # DeepSeek conversation_id — persisted so refresh doesn't start a new chat
    conversation_id = models.CharField(
        max_length=200, blank=True,
        help_text="DeepSeek conversation_id for chat continuity"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='in_progress'
    )
    
    cancel_requested = models.BooleanField(
        default=False,
        help_text="Set to True when user requests cancellation"
    )
    # Live progress counters
    saved = models.IntegerField(default=0)
    skipped = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    total_processed = models.IntegerField(default=0)
    total_positions = models.IntegerField(default=0)

    # For resume-after-refresh
    last_position_id = models.IntegerField(
        null=True, blank=True,
        help_text="ID of the last position processed — resume from next"
    )

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['session_key']),
            models.Index(fields=['status']),
            models.Index(fields=['cv', 'status']),
        ]
        verbose_name = "Match Session"
        verbose_name_plural = "Match Sessions"

    def __str__(self):
        return f"Session {self.session_key} — {self.status}"

    def mark_completed(self):
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])

    def mark_failed(self, error: str):
        self.status = 'failed'
        self.error = error
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'error', 'completed_at'])