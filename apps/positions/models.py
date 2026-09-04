from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.websites.models import Website
from datetime import datetime
from django.utils import timezone

class Position(models.Model):
    """
    Raw scraped position from websites.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),   # Not yet scraped
        ('SCRAPED', 'Scraped'),   # Scraped, awaiting matching
        ('MATCHED', 'Matched'), # Matched and saved
        ('FAILED', 'Failed'),     # Error
    ]

    APPLICATION_STATUS_CHOICES = [
        ('PENDING_REVIEW', 'Pending Review'),
        ('SHORTLISTED', 'Shortlisted'),
        ('APPLIED', 'Applied'),
        ('INTERVIEWING', 'Interviewing'),
        ('OFFERED', 'Offer Received'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),
        ('DEADLINE_MISSED', 'Deadline Missed'),
        ('NOT_INTERESTED', 'Not Interested'),
    ]

    REJECTION_REASON_CHOICES = [
        ('NOT_QUALIFIED', 'Not Qualified'),
        ('SALARY_MISMATCH', 'Salary Mismatch'),
        ('LOCATION_MISMATCH', 'Location Mismatch'),
        ('DEADLINE_PASSED', 'Deadline Passed'),
        ('FOUND_BETTER', 'Found Better'),
        ('OTHER', 'Other'),
    ]

    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='positions')
    url = models.URLField(unique=True)
    title = models.CharField(max_length=500)
    company = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    cleaned_text = models.TextField(blank=True, help_text="Cleaned text for AI processing")
    scraped_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    application_status = models.CharField(max_length=20, choices=APPLICATION_STATUS_CHOICES, default='PENDING_REVIEW', help_text="Application workflow status")
    shortlisted_at = models.DateTimeField(null=True, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    application_result = models.CharField(max_length=20, choices=[('ACCEPTED', 'Accepted'), ('REJECTED', 'Rejected'), ('OFFERED', 'Offered'), ('WITHDRAWN', 'Withdrawn')], null=True, blank=True, help_text="Final outcome")
    rejection_reason = models.CharField(max_length=20, choices=REJECTION_REASON_CHOICES, null=True, blank=True, help_text="Why rejected")

    class Meta:
        ordering = ['-scraped_at']
        indexes = [models.Index(fields=['status', 'scraped_at']), models.Index(fields=['website', 'url']), models.Index(fields=['application_status'])]
        verbose_name = "Position"
        verbose_name_plural = "Positions"
    
    def __str__(self):
        return f"{self.title} - {self.website.name}"
    
    def mark_shortlisted(self):
        self.application_status = 'SHORTLISTED'
        self.shortlisted_at = timezone.now()
        self.save(update_fields=['application_status', 'shortlisted_at', 'updated_at'])

    def mark_applied(self):
        self.application_status = 'APPLIED'
        self.applied_at = timezone.now()
        self.save(update_fields=['application_status', 'applied_at', 'updated_at'])

    def mark_rejected(self, reason=None):
        self.application_status = 'REJECTED'
        self.application_result = 'REJECTED'
        if reason:
            self.rejection_reason = reason
        self.save(update_fields=['application_status', 'application_result', 'rejection_reason', 'updated_at'])

    def mark_accepted(self):
        self.application_status = 'ACCEPTED'
        self.application_result = 'ACCEPTED'
        self.save(update_fields=['application_status', 'application_result', 'updated_at'])

    def mark_not_interested(self):
        self.application_status = 'NOT_INTERESTED'
        self.save(update_fields=['application_status', 'updated_at'])


class PositionMatch(models.Model):
    CONFIDENCE_CHOICES = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High')]
    MATCH_CATEGORY_CHOICES = [
        ('excellent_match', 'Excellent Match'),
        ('good_match', 'Good Match'),
        ('possible_match', 'Possible Match'),
        ('weak_match', 'Weak Match'),
        ('error', 'Error'),
    ]
    APPLICATION_RECOMMENDATION_CHOICES = [
        ('strongly_recommended', 'Strongly Recommended'),
        ('recommended', 'Recommended'),
        ('possible_but_risky', 'Possible but Risky'),
        ('not_recommended', 'Not Recommended'),
    ]

    # ─── Position Relationship ──────────────────────────────────────
    position = models.OneToOneField(
        Position, on_delete=models.CASCADE, related_name='match',
        help_text="The position this match belongs to"
    )

    # ─── Position Summary ──────────────────────────────────────────
    position_title = models.CharField(max_length=500, blank=True, help_text="Position title from the advertisement")
    institution = models.CharField(max_length=500, blank=True, help_text="Institution/organization name")
    country = models.CharField(max_length=100, blank=True, help_text="Country where the position is located")
    city = models.CharField(max_length=100, blank=True, help_text="City where the position is located")
    address = models.TextField(blank=True, help_text="Full address of the position")
    position_type = models.CharField(max_length=100, blank=True, help_text="Type of position (e.g., PhD, Postdoc, Faculty)")
    research_area = models.JSONField(default=list, blank=True, help_text="List of research areas mentioned")
    main_research_objective = models.TextField(blank=True, help_text="Main research objective from the position")
    key_topics = models.JSONField(default=list, blank=True, help_text="Key topics mentioned in the position")
    research_methods = models.JSONField(default=list, blank=True, help_text="Research methods mentioned in the position")
    target_application_domain = models.JSONField(default=list, blank=True, help_text="Target application domains")

    # Structured requirements (JSON objects)
    required_background = models.JSONField(default=dict, blank=True, help_text="Required background with mandatory/core/preferred")
    required_skills = models.JSONField(default=dict, blank=True, help_text="Required skills with mandatory/core/preferred")

    funding_and_duration = models.CharField(max_length=500, blank=True, help_text="Funding information and duration")

    # Dates
    application_deadline = models.DateField(null=True, blank=True, help_text="Application deadline date (YYYY-MM-DD)")
    application_deadline_timezone = models.CharField(max_length=50, blank=True, help_text="Timezone of the deadline")
    application_deadline_iso = models.CharField(max_length=50, blank=True, help_text="Full ISO datetime of deadline")
    start_date = models.DateField(null=True, blank=True, help_text="Start date of the position (YYYY-MM-DD)")
    start_date_iso = models.CharField(max_length=50, blank=True, help_text="Full ISO datetime of start date")

    # Application info
    application_url = models.URLField(max_length=500, blank=True, help_text="Direct link to apply")
    contact_email = models.EmailField(max_length=200, blank=True, help_text="Contact email for inquiries")
    contact_name = models.CharField(max_length=200, blank=True, help_text="Contact person name")
    required_documents = models.JSONField(default=list, blank=True, help_text="List of required application documents")

    # ─── Candidate Profile Summary ─────────────────────────────────
    education_background = models.TextField(blank=True, help_text="Candidate's education background summary")
    research_background = models.TextField(blank=True, help_text="Candidate's research background summary")
    technical_and_methodological_skills = models.TextField(blank=True, help_text="Candidate's technical skills")
    professional_experience = models.TextField(blank=True, help_text="Candidate's professional experience")
    publication_and_academic_record = models.TextField(blank=True, help_text="Candidate's publication and academic record")

    # ─── Matching Score ─────────────────────────────────────────────
    overall_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Overall match score (0-100)"
    )
    confidence = models.CharField(max_length=20, choices=CONFIDENCE_CHOICES, default='low')

    # Evaluation rounds (individual scores)
    eligibility_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Eligibility score (0-100)"
    )
    academic_fit_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Academic fit score (0-100)"
    )
    research_fit_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Research fit score (0-100)"
    )
    technical_methodological_fit_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Technical and methodological fit score (0-100)"
    )
    domain_fit_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Domain fit score (0-100)"
    )
    research_experience_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Research experience score (0-100)"
    )
    competitiveness_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Competitiveness score (0-100)"
    )

    # Weighted dimensions (JSON)
    weighted_dimensions = models.JSONField(default=dict, blank=True, help_text="Weighted dimension scores")

    # Evidence (JSON)
    evidence = models.JSONField(default=dict, blank=True, help_text="Evidence of matches and gaps")

    # ─── Final Verdict ──────────────────────────────────────────────
    match_category = models.CharField(
        max_length=50,
        choices=MATCH_CATEGORY_CHOICES,
        default='weak_match',
        help_text="Match category from final verdict"
    )
    application_recommendation = models.CharField(
        max_length=50,
        choices=APPLICATION_RECOMMENDATION_CHOICES,
        blank=True,
        help_text="Application recommendation"
    )
    summary = models.TextField(blank=True, help_text="Summary of the match assessment")
    main_reason = models.TextField(blank=True, help_text="Main reason for the match verdict")

    # ─── Metadata ────────────────────────────────────────────────────
    prompt_id = models.IntegerField(null=True, blank=True, help_text="ID of the prompt template used")
    prompt_name = models.CharField(max_length=200, blank=True, help_text="Name of the prompt template used")
    prompt_version = models.CharField(max_length=50, blank=True, help_text="Version of the prompt template used")
    language = models.CharField(max_length=50, default='English', help_text="Language used for the match")
    raw_response = models.TextField(blank=True, help_text="Raw AI response (for debugging)")
    full_json_response = models.JSONField(default=dict, blank=True, help_text="Complete JSON response from AI")

    # ─── Timestamps ──────────────────────────────────────────────────
    matched_at = models.DateTimeField(auto_now_add=True, help_text="When the match was created")
    updated_at = models.DateTimeField(auto_now=True, help_text="When the match was last updated")

    class Meta:
        ordering = ['-overall_score', '-matched_at']
        indexes = [
            models.Index(fields=['overall_score']),
            models.Index(fields=['match_category']),
            models.Index(fields=['position', 'overall_score']),
            models.Index(fields=['confidence']),
            models.Index(fields=['application_deadline']),
        ]
        verbose_name = "Position Match"
        verbose_name_plural = "Position Matches"

    def __str__(self):
        return f"Match: {self.position.title} - {self.overall_score:.1f}% ({self.match_category})"

    def get_match_category_display(self):
        return dict(self.MATCH_CATEGORY_CHOICES).get(self.match_category, self.match_category)

    def get_confidence_display(self):
        return dict(self.CONFIDENCE_CHOICES).get(self.confidence, self.confidence)

    def get_application_recommendation_display(self):
        return dict(self.APPLICATION_RECOMMENDATION_CHOICES).get(
            self.application_recommendation, self.application_recommendation
        )

    def is_high_match(self) -> bool:
        return self.match_category in ['excellent_match', 'good_match'] and self.overall_score >= 70

    def is_medium_match(self) -> bool:
        return self.match_category == 'possible_match' and self.overall_score >= 50

    def is_low_match(self) -> bool:
        return self.match_category in ['weak_match', 'error'] or self.overall_score < 50

    @property
    def project_narrative_description(self) -> str:
        """
        Retrieve the project narrative description from the full JSON response.
        This avoids adding a new database column.
        """
        return self.full_json_response.get('project_narrative_description', '')
    
    @classmethod
    def create_from_json(cls, position: Position, result: dict) -> 'PositionMatch':
        m = result.get('_metadata', {})
        ps = result.get('position_summary', {})
        cp = result.get('candidate_profile_summary', {})
        ms = result.get('matching_score', {})
        fv = result.get('final_verdict', {})
        er = ms.get('evaluation_rounds', {})
        wd = ms.get('weighted_dimensions', {})
        ev = ms.get('evidence', {})

        def parse_date(date_str):
            if date_str:
                try:
                    return datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    pass
            return None

        return cls(
            position=position,

            # Position Summary
            position_title=ps.get('title', ''),
            institution=ps.get('institution', ''),
            country=ps.get('country', ''),
            city=ps.get('city', ''),
            address=ps.get('address', ''),
            position_type=ps.get('position_type', ''),
            research_area=ps.get('research_area', []),
            main_research_objective=ps.get('main_research_objective', ''),
            key_topics=ps.get('key_topics', []),
            research_methods=ps.get('research_methods', []),
            target_application_domain=ps.get('target_application_domain', []),
            required_background=ps.get('required_background', {}),
            required_skills=ps.get('required_skills', {}),
            funding_and_duration=ps.get('funding_and_duration', ''),
            application_deadline=parse_date(ps.get('application_deadline', '')),
            application_deadline_timezone=ps.get('application_deadline_timezone', ''),
            application_deadline_iso=ps.get('application_deadline_iso', ''),
            start_date=parse_date(ps.get('start_date', '')),
            start_date_iso=ps.get('start_date_iso', ''),
            application_url=ps.get('application_url', ''),
            contact_email=ps.get('contact_email', ''),
            contact_name=ps.get('contact_name', ''),
            required_documents=ps.get('required_documents', []),

            # Candidate Profile
            education_background=cp.get('education_background', ''),
            research_background=cp.get('research_background', ''),
            technical_and_methodological_skills=cp.get('technical_and_methodological_skills', ''),
            professional_experience=cp.get('professional_experience', ''),
            publication_and_academic_record=cp.get('publication_and_academic_record', ''),

            # Matching Score
            overall_score=ms.get('overall_score', 0),
            confidence=ms.get('confidence', 'low'),
            eligibility_score=er.get('eligibility_score', 0),
            academic_fit_score=er.get('academic_fit_score', 0),
            research_fit_score=er.get('research_fit_score', 0),
            technical_methodological_fit_score=er.get('technical_methodological_fit_score', 0),
            domain_fit_score=er.get('domain_fit_score', 0),
            research_experience_score=er.get('research_experience_score', 0),
            competitiveness_score=er.get('competitiveness_score', 0),
            weighted_dimensions=wd,
            evidence=ev,

            # Final Verdict
            match_category=fv.get('match_category', 'weak_match'),
            application_recommendation=fv.get('application_recommendation', ''),
            summary=fv.get('summary', ''),
            main_reason=fv.get('main_reason', ''),

            # Metadata
            prompt_id=m.get('prompt_id'),
            prompt_name=m.get('prompt_name', ''),
            prompt_version=m.get('prompt_version', ''),
            language=m.get('language', 'English'),
            raw_response=result.get('raw_response', ''),
            full_json_response=result,
        )