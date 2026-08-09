"""
JSON structure definition for match results.
This is used for:
1. Building the prompt (telling AI what format to return)
2. Validating the response
3. Providing default structure for database storage
"""

# The JSON structure that the AI should return
MATCH_JSON_STRUCTURE = {
    "position_summary": {
        "title": "",
        "institution": "",
        "country": "",
        "position_type": "",
        "research_area": [],
        "main_research_objective": "",
        "key_topics": [],
        "required_background": [],
        "required_skills": [],
        "preferred_skills": [],
        "funding_and_duration": ""
    },
    "candidate_profile_summary": {
        "education_background": "",
        "research_background": "",
        "technical_and_methodological_skills": "",
        "professional_experience": "",
        "publication_and_academic_record": ""
    },
    "matching_score": {
        "overall_score": 0,
        "confidence": "low/medium/high",
        "evaluation_rounds": {
            "academic_fit_score": 0,
            "research_fit_score": 0,
            "competitiveness_score": 0
        }
    },
    "final_verdict": {
        "match_category": "excellent_match/good_match/possible_match/weak_match",
        "summary": "",
        "main_reason": ""
    }
}

# Convert to formatted JSON string for prompt
MATCH_JSON_STRUCTURE_STR = """{
    "position_summary": {
        "title": "",
        "institution": "",
        "country": "",
        "position_type": "",
        "research_area": [],
        "main_research_objective": "",
        "key_topics": [],
        "required_background": [],
        "required_skills": [],
        "preferred_skills": [],
        "funding_and_duration": ""
    },
    "candidate_profile_summary": {
        "education_background": "",
        "research_background": "",
        "technical_and_methodological_skills": "",
        "professional_experience": "",
        "publication_and_academic_record": ""
    },
    "matching_score": {
        "overall_score": 0,
        "confidence": "low/medium/high",
        "evaluation_rounds": {
            "academic_fit_score": 0,
            "research_fit_score": 0,
            "competitiveness_score": 0
        }
    },
    "final_verdict": {
        "match_category": "excellent_match/good_match/possible_match/weak_match",
        "summary": "",
        "main_reason": ""
    }
}"""

# JSON schema for validation (using jsonschema library if needed)
MATCH_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "position_summary": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "institution": {"type": "string"},
                "country": {"type": "string"},
                "position_type": {"type": "string"},
                "research_area": {"type": "array", "items": {"type": "string"}},
                "main_research_objective": {"type": "string"},
                "key_topics": {"type": "array", "items": {"type": "string"}},
                "required_background": {"type": "array", "items": {"type": "string"}},
                "required_skills": {"type": "array", "items": {"type": "string"}},
                "preferred_skills": {"type": "array", "items": {"type": "string"}},
                "funding_and_duration": {"type": "string"}
            }
        },
        "candidate_profile_summary": {
            "type": "object",
            "properties": {
                "education_background": {"type": "string"},
                "research_background": {"type": "string"},
                "technical_and_methodological_skills": {"type": "string"},
                "professional_experience": {"type": "string"},
                "publication_and_academic_record": {"type": "string"}
            }
        },
        "matching_score": {
            "type": "object",
            "properties": {
                "overall_score": {"type": "number"},
                "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                "evaluation_rounds": {
                    "type": "object",
                    "properties": {
                        "academic_fit_score": {"type": "number"},
                        "research_fit_score": {"type": "number"},
                        "competitiveness_score": {"type": "number"}
                    }
                }
            }
        },
        "final_verdict": {
            "type": "object",
            "properties": {
                "match_category": {
                    "type": "string",
                    "enum": ["excellent_match", "good_match", "possible_match", "weak_match"]
                },
                "summary": {"type": "string"},
                "main_reason": {"type": "string"}
            }
        }
    },
    "required": [
        "position_summary",
        "candidate_profile_summary", 
        "matching_score",
        "final_verdict"
    ]
}

# Default empty response (for database defaults)
DEFAULT_MATCH_RESPONSE = {
    "position_summary": {
        "title": "",
        "institution": "",
        "country": "",
        "position_type": "",
        "research_area": [],
        "main_research_objective": "",
        "key_topics": [],
        "required_background": [],
        "required_skills": [],
        "preferred_skills": [],
        "funding_and_duration": ""
    },
    "candidate_profile_summary": {
        "education_background": "",
        "research_background": "",
        "technical_and_methodological_skills": "",
        "professional_experience": "",
        "publication_and_academic_record": ""
    },
    "matching_score": {
        "overall_score": 0,
        "confidence": "low",
        "evaluation_rounds": {
            "academic_fit_score": 0,
            "research_fit_score": 0,
            "competitiveness_score": 0
        }
    },
    "final_verdict": {
        "match_category": "weak_match",
        "summary": "",
        "main_reason": ""
    }
}