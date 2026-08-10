import json
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from apps.ai.deepseek import DeepSeekClient
from apps.ai.models import PromptTemplate
from apps.ai.constants import MATCH_JSON_STRUCTURE_STR, DEFAULT_MATCH_RESPONSE

logger = logging.getLogger(__name__)


class PositionMatcher:
    """
    AI-powered position matcher that uses stored prompt templates.
    JSON structure is loaded from constants, not stored in the prompt.
    """
    
    def __init__(
        self,
        deepseek_client: Optional[DeepSeekClient] = None,
        prompt_id: Optional[int] = None,
        language: Optional[str] = None,
    ):
        """
        Initialize the position matcher.
        
        Args:
            deepseek_client: Existing DeepSeekClient instance (optional)
            prompt_id: Specific prompt ID to use (uses active if None)
            language: Response language (overrides prompt's default)
        """
        self.client = deepseek_client or DeepSeekClient()
        self.prompt_id = prompt_id
        self.language = language
        
        # Get the prompt template
        self.prompt_template = self._get_prompt_template()
        
        # Use provided language or prompt's default
        if self.language is None:
            self.language = self.prompt_template.default_language
        
        # Load JSON structure from constants
        self.json_structure = MATCH_JSON_STRUCTURE_STR
    
    def _get_prompt_template(self) -> PromptTemplate:
        """
        Get the prompt template to use.
        
        Returns:
            PromptTemplate: The prompt template instance
        """
        if self.prompt_id:
            try:
                return PromptTemplate.objects.get(id=self.prompt_id)
            except PromptTemplate.DoesNotExist:
                logger.warning(f"Prompt {self.prompt_id} not found. Using active prompt.")
                return PromptTemplate.get_active()
        else:
            return PromptTemplate.get_active()
    
    def _build_prompt(self, cv: str, position: str) -> str:
        """
        Build the complete prompt from template.
        Injects the JSON structure and language from constants.
        
        Args:
            cv: Candidate CV text
            position: Position advertisement text
            
        Returns:
            Complete prompt string
        """
        return self.prompt_template.template.format(
            cv=cv,
            position=position,
            language=self.language,
            json_structure=self.json_structure,
        )
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse DeepSeek response and extract JSON.
        
        Args:
            response_text: Raw response from DeepSeek
            
        Returns:
            Parsed JSON dictionary
            
        Raises:
            ValueError: If response is not valid JSON
        """
        try:
            data = json.loads(response_text)
            return data
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            
            # Try to find JSON object without code blocks
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
            
            logger.error(f"Failed to parse JSON from response: {response_text[:500]}...")
            raise ValueError("Response is not valid JSON")
    
    def _ensure_valid_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure the response has all required fields, filling with defaults if missing.
        
        Args:
            data: Parsed response data
            
        Returns:
            Validated response data
        """
        # Start with default response
        validated = DEFAULT_MATCH_RESPONSE.copy()
        
        # Update with actual data if available
        for key in validated.keys():
            if key in data and data[key]:
                if isinstance(validated[key], dict) and isinstance(data[key], dict):
                    # Merge nested dictionaries
                    validated[key].update(data[key])
                else:
                    validated[key] = data[key]
        
        return validated
    
    def match(
        self,
        cv: str,
        position: str,
        language: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Match a candidate CV against a position advertisement.
        
        Args:
            cv: Candidate CV text
            position: Position advertisement text
            language: Override response language (optional)
            conversation_id: Optional conversation ID for continuing chat
            
        Returns:
            Dict containing the match result
            
        Example:
            >>> matcher = PositionMatcher()
            >>> with open("cv.txt", "r") as f:
            ...     cv = f.read()
            >>> with open("position.txt", "r") as f:
            ...     position = f.read()
            >>> result = matcher.match(cv, position)
            >>> print(result['matching_score']['overall_score'])
            >>> print(result['final_verdict']['match_category'])
        """
        # Override language if provided
        if language:
            self.language = language
        
        try:
            # Build prompt
            prompt = self._build_prompt(cv, position)
            
            # Send to DeepSeek
            if conversation_id:
                response = self.client.chat(prompt, conversation_id=conversation_id)
            else:
                response = self.client.chat(prompt)
            
            # Parse response
            parsed_data = self._parse_response(response.text)
            
            # Ensure response has all required fields
            validated_data = self._ensure_valid_response(parsed_data)
            
            # Add metadata
            validated_data['_metadata'] = {
                'conversation_id': response.conversation_id,
                'prompt_id': self.prompt_template.id,
                'prompt_name': self.prompt_template.name,
                'prompt_version': self.prompt_template.version,
                'language': self.language,
                'processed_at': datetime.now().isoformat(),
            }
            
            logger.info(
                f"Match completed: {validated_data['final_verdict'].get('match_category', 'unknown')} - "
                f"Score: {validated_data['matching_score'].get('overall_score', 0)}%"
            )
            
            return validated_data
            
        except Exception as e:
            logger.error(f"Match failed: {e}")
            # Return default response with error info
            error_response = DEFAULT_MATCH_RESPONSE.copy()
            error_response['final_verdict']['summary'] = f"Error processing match: {str(e)}"
            error_response['final_verdict']['match_category'] = "error"
            error_response['_metadata'] = {
                'error': str(e),
                'prompt_id': self.prompt_template.id,
                'prompt_name': self.prompt_template.name,
                'prompt_version': self.prompt_template.version,
                'language': self.language,
                'processed_at': datetime.now().isoformat(),
            }
            return error_response
    
    def match_from_files(
        self,
        cv_file: str,
        position_file: str,
        language: Optional[str] = None,
        conversation_id: Optional[str] = None,
        encoding: str = "utf-8",
    ) -> Dict[str, Any]:
        """
        Match a candidate CV and position from files.
        
        Args:
            cv_file: Path to CV text file
            position_file: Path to position text file
            language: Override response language (optional)
            conversation_id: Optional conversation ID for continuing chat
            encoding: File encoding (default: utf-8)
            
        Returns:
            Dict containing the match result
        """
        with open(cv_file, "r", encoding=encoding) as f:
            cv = f.read()
        
        with open(position_file, "r", encoding=encoding) as f:
            position = f.read()
        
        return self.match(cv, position, language, conversation_id)
    
    def stream_match(
        self,
        cv: str,
        position: str,
        language: Optional[str] = None,
        conversation_id: Optional[str] = None,
        callback=None,
    ) -> Dict[str, Any]:
        """
        Stream the matching process chunk by chunk.
        
        Args:
            cv: Candidate CV text
            position: Position advertisement text
            language: Override response language (optional)
            conversation_id: Optional conversation ID for continuing chat
            callback: Optional callback function called with each chunk
            
        Returns:
            Parsed result dictionary
        """
        # Override language if provided
        if language:
            self.language = language
        
        prompt = self._build_prompt(cv, position)
        full_response = ""
        
        for chunk in self.client.stream(prompt, conversation_id):
            full_response += chunk
            if callback:
                callback(chunk)
        
        # Parse the complete response
        parsed_data = self._parse_response(full_response)
        return self._ensure_valid_response(parsed_data)


# Convenience functions
def get_active_prompt() -> PromptTemplate:
    """Get the active prompt template."""
    return PromptTemplate.get_active()


def quick_match(
    cv: str, 
    position: str, 
    language: str = "English"
) -> Dict[str, Any]:
    """
    Quick convenience function to match a position using active prompt.
    
    Args:
        cv: Candidate CV text
        position: Position advertisement text
        language: Response language (default: English)
        
    Returns:
        Dict containing the match result
    """
    matcher = PositionMatcher(language=language)
    return matcher.match(cv, position)


def quick_match_from_files(
    cv_file: str, 
    position_file: str, 
    language: str = "English"
) -> Dict[str, Any]:
    """
    Quick convenience function to match from files.
    
    Args:
        cv_file: Path to CV file
        position_file: Path to position file
        language: Response language (default: English)
        
    Returns:
        Dict containing the match result
    """
    matcher = PositionMatcher(language=language)
    return matcher.match_from_files(cv_file, position_file)


def match_and_save(
    cv: str,
    position_id: int,
    language: str = "English",
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Match a specific position by ID and save the result.
    
    Args:
        cv: Candidate CV text
        position_id: ID of the Position object
        language: Response language (default: English)
        conversation_id: Optional conversation ID for continuing chat
        
    Returns:
        Dict containing the match result with status metadata
        
    Raises:
        ValueError: If position not found or invalid
        Exception: For other errors (with detailed logging)
    """
    from apps.positions.models import Position, PositionMatch
    time.sleep(1.5)
    try:
        # ─── Step 1: Get Position ────────────────────────────────────
        try:
            position = Position.objects.get(id=position_id)
            logger.info(f"📌 Processing position: {position.id} - {position.title[:50]}...")
        except ObjectDoesNotExist:
            logger.error(f"❌ Position {position_id} not found")
            return {
                'error': f'Position {position_id} not found',
                '_metadata': {
                    'status': 'failed',
                    'error_type': 'position_not_found',
                    'position_id': position_id,
                    'processed_at': datetime.now().isoformat(),
                }
            }
        
        # ─── Step 2: Check if already matched ───────────────────────
        if hasattr(position, 'match') and position.match:
            logger.warning(f"⚠️ Position {position_id} already has a match (ID: {position.match.id})")
            return {
                'error': 'Position already has a match',
                'existing_match_id': position.match.id,
                '_metadata': {
                    'status': 'skipped',
                    'error_type': 'already_matched',
                    'position_id': position_id,
                    'match_id': position.match.id,
                    'processed_at': datetime.now().isoformat(),
                }
            }
        
        # ─── Step 3: Run Matcher ─────────────────────────────────────
        try:
            matcher = PositionMatcher(language=language)
            logger.info(f"🔄 Running matcher for position {position_id}")
            result = matcher.match(cv, position.cleaned_text, conversation_id=conversation_id)
        except Exception as e:
            logger.error(f"❌ Matcher failed for position {position_id}: {e}")
            # Return structured error with matcher failure
            return {
                'error': f'Matcher failed: {str(e)}',
                '_metadata': {
                    'status': 'failed',
                    'error_type': 'matcher_error',
                    'position_id': position_id,
                    'error_detail': str(e),
                    'processed_at': datetime.now().isoformat(),
                }
            }
        
        # ─── Step 4: Validate Result ─────────────────────────────────
        if result.get('final_verdict', {}).get('match_category') == 'error':
            logger.warning(f"⚠️ Matcher returned error for position {position_id}: {result.get('_metadata', {}).get('error', 'Unknown error')}")
            # Still save but mark as failed
            result['_metadata']['status'] = 'failed'
            result['_metadata']['error_type'] = 'matcher_returned_error'
            # We'll still try to save, but mark position as FAILED
        
        # ─── Step 5: Save Match (Atomic Transaction) ─────────────────
        try:
            with transaction.atomic():
                logger.info(f"💾 Saving match for position {position_id}")
                match = PositionMatch.create_from_json(position, result)
                match.save()
                logger.info(f"✅ Match saved (ID: {match.id}) for position {position_id}")
                
                # Update position status based on match success
                if result.get('final_verdict', {}).get('match_category') == 'error':
                    position.status = 'FAILED'
                    logger.warning(f"⚠️ Position {position_id} marked as FAILED due to matcher error")
                else:
                    position.status = 'MATCHED'
                    logger.info(f"✅ Position {position_id} marked as MATCHED")
                
                position.save(update_fields=['status'])
                
                # Add success metadata
                result['_metadata']['status'] = 'success'
                result['_metadata']['match_id'] = match.id
                result['_metadata']['position_status'] = position.status
                
                logger.info(
                    f"🎉 Match complete for position {position_id}: "
                    f"Score: {match.overall_score:.1f}%, "
                    f"Category: {match.match_category}"
                )
                
                return result
                
        except Exception as e:
            logger.error(f"❌ Database save failed for position {position_id}: {e}")
            # Return structured error with save failure
            return {
                'error': f'Failed to save match: {str(e)}',
                '_metadata': {
                    'status': 'failed',
                    'error_type': 'database_error',
                    'position_id': position_id,
                    'error_detail': str(e),
                    'processed_at': datetime.now().isoformat(),
                },
                # Include the result even though save failed (for debugging)
                'partial_result': result
            }
            
    except Exception as e:
        # ─── Catch-all for unexpected errors ────────────────────────
        logger.error(f"❌ Unexpected error in match_and_save for position {position_id}: {e}")
        import traceback
        traceback.print_exc()
        return {
            'error': f'Unexpected error: {str(e)}',
            '_metadata': {
                'status': 'failed',
                'error_type': 'unexpected_error',
                'position_id': position_id,
                'error_detail': str(e),
                'processed_at': datetime.now().isoformat(),
            }
        }