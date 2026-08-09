from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from .constants import MATCH_JSON_STRUCTURE_STR

class PromptTemplate(models.Model):
    """
    Model to store prompt templates for the matcher.
    Only one prompt can be active at a time.
    """
    
    # Basic info
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique name to identify this prompt template"
    )
    description = models.TextField(
        blank=True,
        help_text="Description of what this prompt is optimized for"
    )
    
    # The actual prompt content (without JSON structure)
    template = models.TextField(
        help_text="The prompt template with placeholders: {cv}, {position}, {language}, {json_structure}"
    )
    
    # Default language for this prompt
    default_language = models.CharField(
        max_length=50,
        default="English",
        help_text="Default language for responses"
    )
    
    # Metadata
    version = models.CharField(
        max_length=20,
        default="1.0.0",
        help_text="Semantic version of this prompt"
    )
    
    is_active = models.BooleanField(
        default=False,
        help_text="Is this the currently active prompt? Only one can be active."
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    activated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this prompt was last activated"
    )
    
    class Meta:
        ordering = ['-is_active', '-created_at']
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['name', 'version']),
        ]
        verbose_name = "Prompt Template"
        verbose_name_plural = "Prompt Templates"
    
    def __str__(self):
        status = "✓ ACTIVE" if self.is_active else "○ inactive"
        return f"{self.name} v{self.version} [{status}]"
    
    def clean(self):
        """Validate that only one prompt is active"""
        if self.is_active:
            active_prompts = PromptTemplate.objects.filter(is_active=True)
            if self.pk:
                active_prompts = active_prompts.exclude(pk=self.pk)
            
            if active_prompts.exists():
                raise ValidationError(
                    f"Only one prompt can be active at a time. '{active_prompts.first().name}' is already active."
                )
    
    def save(self, *args, **kwargs):
        """Override save to handle activation logic"""
        if self.is_active:
            # Deactivate all other active prompts
            PromptTemplate.objects.filter(is_active=True).exclude(pk=self.pk).update(
                is_active=False,
                activated_at=None
            )
            
            # Set activation timestamp if not already set
            if not self.activated_at:
                self.activated_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    @classmethod
    def get_active(cls):
        """
        Get the currently active prompt template.
        Creates a default one if none exists.
        
        Returns:
            PromptTemplate: The active prompt
        """
        try:
            return cls.objects.get(is_active=True)
        except cls.DoesNotExist:
            return cls.create_default_prompt()
    
    @classmethod
    def create_default_prompt(cls):
        """
        Create the default prompt template.
        JSON structure is injected via {json_structure} placeholder.
        
        Returns:
            PromptTemplate: The created default prompt
        """
        default_template = """
You are an expert academic recruitment evaluator specializing in PhD, research, and academic position matching.

Your task:
Analyze the candidate CV and the full academic position advertisement provided below.

Response language: {language}

Return ONLY valid JSON. Do not include markdown or explanations outside JSON.

JSON OUTPUT STRUCTURE:
{json_structure}

Evaluation principles:
- Evaluate based on the actual position requirements.
- Adapt criteria according to the discipline and position type.
- Consider equivalent backgrounds and transferable skills.
- Be realistic and conservative.

INPUT A - Candidate CV:
{cv}

INPUT B - Academic Position Advertisement:
{position}
"""
        
        default_prompt, created = cls.objects.get_or_create(
            name="default_academic_matcher",
            defaults={
                "description": "Default prompt for academic position matching",
                "template": default_template,
                "default_language": "English",
                "version": "1.0.0",
                "is_active": True,
                "activated_at": timezone.now(),
            }
        )
        
        if not created and not default_prompt.is_active:
            default_prompt.is_active = True
            default_prompt.activated_at = timezone.now()
            default_prompt.save()
        
        return default_prompt