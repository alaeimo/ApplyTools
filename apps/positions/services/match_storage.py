"""
Service for storing match results in the database.
"""

import logging
from typing import Dict, Any, Optional
from django.db import transaction

from apps.positions.models import Position, PositionMatch

logger = logging.getLogger(__name__)


class MatchStorageService:
    """
    Service for storing match results from the PositionMatcher.
    """
    
    @classmethod
    def save_match_result(
        cls, 
        position: Position, 
        result: Dict[str, Any]
    ) -> PositionMatch:
        """
        Save or update a match result for a position.
        
        Args:
            position: The Position object
            result: The match result from PositionMatcher
            
        Returns:
            PositionMatch: Created or updated match object
        """
        with transaction.atomic():
            # Check if match already exists
            match, created = PositionMatch.objects.get_or_create(
                position=position,
                defaults=PositionMatch.create_from_json(position, result)
            )
            
            if not created:
                # Update existing match
                new_match = PositionMatch.create_from_json(position, result)
                for field in ['position_title', 'institution', 'country', 'position_type',
                              'research_area', 'main_research_objective', 'key_topics',
                              'required_background', 'required_skills', 'preferred_skills',
                              'funding_and_duration', 'education_background', 'research_background',
                              'technical_and_methodological_skills', 'professional_experience',
                              'publication_and_academic_record', 'overall_score', 'confidence',
                              'academic_fit_score', 'research_fit_score', 'competitiveness_score',
                              'match_category', 'summary', 'main_reason', 'prompt_id',
                              'prompt_name', 'prompt_version', 'language', 'raw_response',
                              'full_json_response']:
                    setattr(match, field, getattr(new_match, field))
                match.save()
                
                logger.info(f"Updated match for position {position.id}")
            else:
                logger.info(f"Created match for position {position.id}")
            
            # Update position status
            if position.status != 'MATCHED':
                position.status = 'MATCHED'
                position.save(update_fields=['status'])
            
            return match
    
    @classmethod
    def get_match_for_position(cls, position: Position) -> Optional[PositionMatch]:
        """Get the match for a position."""
        try:
            return PositionMatch.objects.get(position=position)
        except PositionMatch.DoesNotExist:
            return None
    
    @classmethod
    def get_high_matches(cls, min_score: float = 70) -> list:
        """Get all high-scoring matches."""
        return PositionMatch.objects.filter(
            overall_score__gte=min_score
        ).select_related('position')
    
    @classmethod
    def get_matches_by_category(cls, category: str) -> list:
        """Get matches by category."""
        return PositionMatch.objects.filter(
            match_category=category
        ).select_related('position')
    
    @classmethod
    def get_statistics(cls) -> Dict[str, Any]:
        """
        Get match statistics.
        
        Returns:
            dict: Statistics about matches
        """
        from django.db.models import Count, Avg
        
        total = PositionMatch.objects.count()
        
        if total == 0:
            return {
                'total_matches': 0,
                'average_score': 0,
                'by_category': {},
                'by_confidence': {},
            }
        
        avg_score = PositionMatch.objects.aggregate(Avg('overall_score'))['overall_score__avg']
        
        by_category = dict(
            PositionMatch.objects.values('match_category')
            .annotate(count=Count('id'))
            .values_list('match_category', 'count')
        )
        
        by_confidence = dict(
            PositionMatch.objects.values('confidence')
            .annotate(count=Count('id'))
            .values_list('confidence', 'count')
        )
        
        return {
            'total_matches': total,
            'average_score': round(avg_score or 0, 2),
            'by_category': by_category,
            'by_confidence': by_confidence,
        }