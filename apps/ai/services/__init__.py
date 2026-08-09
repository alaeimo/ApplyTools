from .matcher import (
    # Main class
    PositionMatcher,
    
    # Convenience functions
    quick_match,
    quick_match_from_files,
    get_active_prompt,
)

# Expose all public interfaces
__all__ = [
    # Main matcher class
    'PositionMatcher',
    
    # Convenience functions
    'quick_match',
    'quick_match_from_files',
    'get_active_prompt',
]

# Package metadata
__version__ = '1.0.0'
__author__ = 'MindCodeLab'
__description__ = 'AI-powered position matching services for academic recruitment'
