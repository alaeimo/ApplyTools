"""Models for the browser extension integration."""
import secrets
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


def generate_extension_token() -> str:
    """Generate a secure random token prefixed with 'ext-'."""
    return f"ext-{secrets.token_urlsafe(32)}"


class ExtensionToken(models.Model):
    """Per-user API token for the ApplyTools browser extension.

    A user can have at most one active token. Generating a new token
    invalidates (deletes) the previous one.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='extension_tokens',
    )
    token = models.CharField(
        max_length=100,
        unique=True,
        default=generate_extension_token,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Extension Token"
        verbose_name_plural = "Extension Tokens"

    def __str__(self):
        return f"ExtensionToken(user={self.user.username}, active={self.is_active})"

    def touch(self):
        """Update last_used_at timestamp."""
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at'])

    @classmethod
    def for_user(cls, user) -> 'ExtensionToken':
        """Get or create an active token for the user.

        Invalidates any existing tokens for the user first.
        """
        # Invalidate existing tokens
        cls.objects.filter(user=user).delete()
        # Create new token
        return cls.objects.create(user=user)

    @classmethod
    def get_active(cls, token_str: str):
        """Validate a token string and return the token (or None)."""
        if not token_str:
            return None
        try:
            token = cls.objects.get(token=token_str, is_active=True)
            token.touch()
            return token
        except cls.DoesNotExist:
            return None
