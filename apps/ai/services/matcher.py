import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

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
        encoding: str = "utf-8",
    ) -> Dict[str, Any]:
        """
        Match a candidate CV and position from files.
        
        Args:
            cv_file: Path to CV text file
            position_file: Path to position text file
            language: Override response language (optional)
            encoding: File encoding (default: utf-8)
            
        Returns:
            Dict containing the match result
        """
        with open(cv_file, "r", encoding=encoding) as f:
            cv = f.read()
        
        with open(position_file, "r", encoding=encoding) as f:
            position = f.read()
        
        return self.match(cv, position, language=language)
    
    def stream_match(
        self,
        cv: str,
        position: str,
        language: Optional[str] = None,
        callback=None,
    ) -> Dict[str, Any]:
        """
        Stream the matching process chunk by chunk.
        
        Args:
            cv: Candidate CV text
            position: Position advertisement text
            language: Override response language (optional)
            callback: Optional callback function called with each chunk
            
        Returns:
            Parsed result dictionary
        """
        # Override language if provided
        if language:
            self.language = language
        
        prompt = self._build_prompt(cv, position)
        full_response = ""
        
        for chunk in self.client.stream(prompt):
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


