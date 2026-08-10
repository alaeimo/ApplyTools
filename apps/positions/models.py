from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.websites.models import Website

class Position(models.Model):
    """
    Raw scraped position from websites.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),   # Not yet scraped
        ('SCRAPED', 'Scraped'),   # Scraped, awaiting matching
        ('PROCESSED', 'Processed'), # Matched and saved
        ('FAILED', 'Failed'),     # Error
    ]
        
    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='positions')
    url = models.URLField(unique=True)
    title = models.CharField(max_length=500)
    company = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    cleaned_text = models.TextField(blank=True, help_text="Cleaned text for AI processing")
    scraped_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-scraped_at']
        indexes = [
            models.Index(fields=['status', 'scraped_at']),
            models.Index(fields=['website', 'url']),
        ]
        verbose_name = "Position"
        verbose_name_plural = "Positions"
    
    def __str__(self):
        return f"{self.title} - {self.website.name}"


# class PositionMatch(models.Model):
#     """
#     Stores the matching result for a position.
#     Mirrors the JSON structure from the PositionMatcher.
#     """
    
#     # Confidence levels
#     CONFIDENCE_CHOICES = [
#         ('low', 'Low'),
#         ('medium', 'Medium'),
#         ('high', 'High'),
#     ]
    
#     # Match categories
#     MATCH_CATEGORY_CHOICES = [
#         ('excellent_match', 'Excellent Match'),
#         ('good_match', 'Good Match'),
#         ('possible_match', 'Possible Match'),
#         ('weak_match', 'Weak Match'),
#         ('error', 'Error'),
#     ]
    
#     # ============================================================
#     # RELATIONSHIPS
#     # ============================================================
#     position = models.OneToOneField(
#         Position,
#         on_delete=models.CASCADE,
#         related_name='match',
#         help_text="The position this match belongs to"
#     )
    
#     # ============================================================
#     # POSITION SUMMARY (from position_summary)
#     # ============================================================
#     position_title = models.CharField(
#         max_length=500,
#         blank=True,
#         help_text="Position title from the advertisement"
#     )
#     institution = models.CharField(
#         max_length=500,
#         blank=True,
#         help_text="Institution/organization name"
#     )
#     country = models.CharField(
#         max_length=100,
#         blank=True,
#         help_text="Country where the position is located"
#     )
#     position_type = models.CharField(
#         max_length=100,
#         blank=True,
#         help_text="Type of position (e.g., PhD, Postdoc, Faculty)"
#     )
#     research_area = models.JSONField(
#         default=list,
#         blank=True,
#         help_text="List of research areas mentioned"
#     )
#     main_research_objective = models.TextField(
#         blank=True,
#         help_text="Main research objective from the position"
#     )
#     key_topics = models.JSONField(
#         default=list,
#         blank=True,
#         help_text="Key topics mentioned in the position"
#     )
#     required_background = models.JSONField(
#         default=list,
#         blank=True,
#         help_text="Required background qualifications"
#     )
#     required_skills = models.JSONField(
#         default=list,
#         blank=True,
#         help_text="Required skills for the position"
#     )
#     preferred_skills = models.JSONField(
#         default=list,
#         blank=True,
#         help_text="Preferred skills (nice to have)"
#     )
#     funding_and_duration = models.CharField(
#         max_length=500,
#         blank=True,
#         help_text="Funding information and duration"
#     )
    
#     # ============================================================
#     # CANDIDATE PROFILE SUMMARY (from candidate_profile_summary)
#     # ============================================================
#     education_background = models.TextField(
#         blank=True,
#         help_text="Candidate's education background summary"
#     )
#     research_background = models.TextField(
#         blank=True,
#         help_text="Candidate's research background summary"
#     )
#     technical_and_methodological_skills = models.TextField(
#         blank=True,
#         help_text="Candidate's technical skills"
#     )
#     professional_experience = models.TextField(
#         blank=True,
#         help_text="Candidate's professional experience"
#     )
#     publication_and_academic_record = models.TextField(
#         blank=True,
#         help_text="Candidate's publication and academic record"
#     )
    
#     # ============================================================
#     # MATCHING SCORE (from matching_score)
#     # ============================================================
#     overall_score = models.FloatField(
#         default=0.0,
#         validators=[MinValueValidator(0), MaxValueValidator(100)],
#         help_text="Overall match score (0-100)"
#     )
#     confidence = models.CharField(
#         max_length=20,
#         choices=CONFIDENCE_CHOICES,
#         default='low',
#         help_text="Confidence level of the match assessment"
#     )
    
#     # Evaluation rounds (matching_score.evaluation_rounds)
#     academic_fit_score = models.FloatField(
#         default=0.0,
#         validators=[MinValueValidator(0), MaxValueValidator(100)],
#         help_text="Academic fit score (0-100)"
#     )
#     research_fit_score = models.FloatField(
#         default=0.0,
#         validators=[MinValueValidator(0), MaxValueValidator(100)],
#         help_text="Research fit score (0-100)"
#     )
#     competitiveness_score = models.FloatField(
#         default=0.0,
#         validators=[MinValueValidator(0), MaxValueValidator(100)],
#         help_text="Competitiveness score (0-100)"
#     )
    
#     # ============================================================
#     # FINAL VERDICT (from final_verdict)
#     # ============================================================
#     match_category = models.CharField(
#         max_length=50,
#         choices=MATCH_CATEGORY_CHOICES,
#         default='weak_match',
#         help_text="Match category from final verdict"
#     )
#     summary = models.TextField(
#         blank=True,
#         help_text="Summary of the match assessment"
#     )
#     main_reason = models.TextField(
#         blank=True,
#         help_text="Main reason for the match verdict"
#     )
    
#     # ============================================================
#     # METADATA & RAW DATA
#     # ============================================================
#     prompt_id = models.IntegerField(
#         null=True,
#         blank=True,
#         help_text="ID of the prompt template used"
#     )
#     prompt_name = models.CharField(
#         max_length=200,
#         blank=True,
#         help_text="Name of the prompt template used"
#     )
#     prompt_version = models.CharField(
#         max_length=50,
#         blank=True,
#         help_text="Version of the prompt template used"
#     )
#     language = models.CharField(
#         max_length=50,
#         default='English',
#         help_text="Language used for the match"
#     )
    
#     # Raw response from AI (for debugging/audit)
#     raw_response = models.TextField(
#         blank=True,
#         help_text="Raw AI response (for debugging)"
#     )
    
#     # Full JSON response (for reference)
#     full_json_response = models.JSONField(
#         default=dict,
#         blank=True,
#         help_text="Complete JSON response from AI"
#     )
    
#     # ============================================================
#     # TIMESTAMPS
#     # ============================================================
#     matched_at = models.DateTimeField(
#         auto_now_add=True,
#         help_text="When the match was created"
#     )
#     updated_at = models.DateTimeField(
#         auto_now=True,
#         help_text="When the match was last updated"
#     )
    
#     class Meta:
#         ordering = ['-overall_score', '-matched_at']
#         indexes = [
#             models.Index(fields=['overall_score']),
#             models.Index(fields=['match_category']),
#             models.Index(fields=['position', 'overall_score']),
#             models.Index(fields=['confidence']),
#         ]
#         verbose_name = "Position Match"
#         verbose_name_plural = "Position Matches"
    
#     def __str__(self):
#         return f"Match: {self.position.title} - {self.overall_score:.1f}% ({self.match_category})"
    
#     def get_match_category_display(self):
#         """Get human-readable match category."""
#         return dict(self.MATCH_CATEGORY_CHOICES).get(self.match_category, self.match_category)
    
#     def get_confidence_display(self):
#         """Get human-readable confidence level."""
#         return dict(self.CONFIDENCE_CHOICES).get(self.confidence, self.confidence)
    
#     def is_high_match(self) -> bool:
#         """Check if this is a high-quality match."""
#         return self.match_category in ['excellent_match', 'good_match'] and self.overall_score >= 70
    
#     def is_medium_match(self) -> bool:
#         """Check if this is a medium-quality match."""
#         return self.match_category == 'possible_match' and self.overall_score >= 50
    
#     def is_low_match(self) -> bool:
#         """Check if this is a low-quality match."""
#         return self.match_category in ['weak_match', 'error'] or self.overall_score < 50
    
#     @classmethod
#     def create_from_json(cls, position: Position, result: dict) -> 'PositionMatch':
#         """
#         Factory method to create a PositionMatch from the JSON result.
        
#         Args:
#             position: The Position object
#             result: The match result from PositionMatcher
            
#         Returns:
#             PositionMatch: Created match object
#         """
#         metadata = result.get('_metadata', {})
        
#         return cls(
#             position=position,
            
#             # Position summary
#             position_title=result.get('position_summary', {}).get('title', ''),
#             institution=result.get('position_summary', {}).get('institution', ''),
#             country=result.get('position_summary', {}).get('country', ''),
#             position_type=result.get('position_summary', {}).get('position_type', ''),
#             research_area=result.get('position_summary', {}).get('research_area', []),
#             main_research_objective=result.get('position_summary', {}).get('main_research_objective', ''),
#             key_topics=result.get('position_summary', {}).get('key_topics', []),
#             required_background=result.get('position_summary', {}).get('required_background', []),
#             required_skills=result.get('position_summary', {}).get('required_skills', []),
#             preferred_skills=result.get('position_summary', {}).get('preferred_skills', []),
#             funding_and_duration=result.get('position_summary', {}).get('funding_and_duration', ''),
            
#             # Candidate profile
#             education_background=result.get('candidate_profile_summary', {}).get('education_background', ''),
#             research_background=result.get('candidate_profile_summary', {}).get('research_background', ''),
#             technical_and_methodological_skills=result.get('candidate_profile_summary', {}).get('technical_and_methodological_skills', ''),
#             professional_experience=result.get('candidate_profile_summary', {}).get('professional_experience', ''),
#             publication_and_academic_record=result.get('candidate_profile_summary', {}).get('publication_and_academic_record', ''),
            
#             # Matching score
#             overall_score=result.get('matching_score', {}).get('overall_score', 0),
#             confidence=result.get('matching_score', {}).get('confidence', 'low'),
#             academic_fit_score=result.get('matching_score', {}).get('evaluation_rounds', {}).get('academic_fit_score', 0),
#             research_fit_score=result.get('matching_score', {}).get('evaluation_rounds', {}).get('research_fit_score', 0),
#             competitiveness_score=result.get('matching_score', {}).get('evaluation_rounds', {}).get('competitiveness_score', 0),
            
#             # Final verdict
#             match_category=result.get('final_verdict', {}).get('match_category', 'weak_match'),
#             summary=result.get('final_verdict', {}).get('summary', ''),
#             main_reason=result.get('final_verdict', {}).get('main_reason', ''),
            
#             # Metadata
#             prompt_id=metadata.get('prompt_id'),
#             prompt_name=metadata.get('prompt_name', ''),
#             prompt_version=metadata.get('prompt_version', ''),
#             language=metadata.get('language', 'English'),
#             raw_response=result.get('raw_response', ''),
#             full_json_response=result,
#         )
    
#     def to_dict(self) -> dict:
#         """
#         Convert the match back to the original JSON structure.
        
#         Returns:
#             dict: The match in the original JSON format
#         """
#         return {
#             "position_summary": {
#                 "title": self.position_title,
#                 "institution": self.institution,
#                 "country": self.country,
#                 "position_type": self.position_type,
#                 "research_area": self.research_area,
#                 "main_research_objective": self.main_research_objective,
#                 "key_topics": self.key_topics,
#                 "required_background": self.required_background,
#                 "required_skills": self.required_skills,
#                 "preferred_skills": self.preferred_skills,
#                 "funding_and_duration": self.funding_and_duration,
#             },
#             "candidate_profile_summary": {
#                 "education_background": self.education_background,
#                 "research_background": self.research_background,
#                 "technical_and_methodological_skills": self.technical_and_methodological_skills,
#                 "professional_experience": self.professional_experience,
#                 "publication_and_academic_record": self.publication_and_academic_record,
#             },
#             "matching_score": {
#                 "overall_score": self.overall_score,
#                 "confidence": self.confidence,
#                 "evaluation_rounds": {
#                     "academic_fit_score": self.academic_fit_score,
#                     "research_fit_score": self.research_fit_score,
#                     "competitiveness_score": self.competitiveness_score,
#                 }
#             },
#             "final_verdict": {
#                 "match_category": self.match_category,
#                 "summary": self.summary,
#                 "main_reason": self.main_reason,
#             },
#             "_metadata": {
#                 "prompt_id": self.prompt_id,
#                 "prompt_name": self.prompt_name,
#                 "prompt_version": self.prompt_version,
#                 "language": self.language,
#                 "processed_at": self.matched_at.isoformat() if self.matched_at else None,
#             }
#         }