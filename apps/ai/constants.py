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
        "city": "",
        "address": "",
        "position_type": "",
        "research_area": [],
        "main_research_objective": "",
        "key_topics": [],
        "research_methods": [],
        "target_application_domain": [],
        "required_background": {
            "mandatory": [],
            "core": [],
            "preferred": []
        },
        "required_skills": {
            "mandatory": [],
            "core": [],
            "preferred": []
        },
        "funding_and_duration": "",
        "application_deadline": "",
        "application_deadline_timezone": "",
        "application_deadline_iso": "",
        "start_date": "",
        "start_date_iso": "",
        "application_url": "",
        "contact_email": "",
        "contact_name": "",
        "required_documents": []
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
            "eligibility_score": 0,
            "academic_fit_score": 0,
            "research_fit_score": 0,
            "technical_methodological_fit_score": 0,
            "domain_fit_score": 0,
            "research_experience_score": 0,
            "competitiveness_score": 0
        },

        "weighted_dimensions": {
            "mandatory_requirements": 0,
            "research_project_fit": 0,
            "research_experience": 0,
            "technical_methodological_fit": 0,
            "domain_application_fit": 0,
            "education_academic_record": 0,
            "research_outputs": 0,
            "lab_supervisor_fit": 0,
            "preferred_requirements": 0
        },

        "evidence": {
            "direct_matches": [],
            "transferable_matches": [],
            "missing_requirements": [],
            "unclear_requirements": []
        }
    },

    "final_verdict": {
        "match_category": "excellent_match/good_match/possible_match/weak_match",
        "application_recommendation": "strongly_recommended/recommended/possible_but_risky/not_recommended",
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
        "city": "",
        "address": "",
        "position_type": "",
        "research_area": [],
        "main_research_objective": "",
        "key_topics": [],
        "research_methods": [],
        "target_application_domain": [],
        "required_background": {
            "mandatory": [],
            "core": [],
            "preferred": []
        },
        "required_skills": {
            "mandatory": [],
            "core": [],
            "preferred": []
        },
        "funding_and_duration": "",
        "application_deadline": "",
        "application_deadline_timezone": "",
        "application_deadline_iso": "",
        "start_date": "",
        "start_date_iso": "",
        "application_url": "",
        "contact_email": "",
        "contact_name": "",
        "required_documents": []
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
            "eligibility_score": 0,
            "academic_fit_score": 0,
            "research_fit_score": 0,
            "technical_methodological_fit_score": 0,
            "domain_fit_score": 0,
            "research_experience_score": 0,
            "competitiveness_score": 0
        },
        "weighted_dimensions": {
            "mandatory_requirements": 0,
            "research_project_fit": 0,
            "research_experience": 0,
            "technical_methodological_fit": 0,
            "domain_application_fit": 0,
            "education_academic_record": 0,
            "research_outputs": 0,
            "lab_supervisor_fit": 0,
            "preferred_requirements": 0
        },
        "evidence": {
            "direct_matches": [],
            "transferable_matches": [],
            "missing_requirements": [],
            "unclear_requirements": []
        }
    },
    "final_verdict": {
        "match_category": "excellent_match/good_match/possible_match/weak_match",
        "application_recommendation": "strongly_recommended/recommended/possible_but_risky/not_recommended",
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
                "city": {"type": "string"},
                "address": {"type": "string"},
                "position_type": {"type": "string"},
                "research_area": {"type": "array", "items": {"type": "string"}},
                "main_research_objective": {"type": "string"},
                "key_topics": {"type": "array", "items": {"type": "string"}},
                "research_methods": {"type": "array", "items": {"type": "string"}},
                "target_application_domain": {"type": "array", "items": {"type": "string"}},
                "required_background": {
                    "type": "object",
                    "properties": {
                        "mandatory": {"type": "array", "items": {"type": "string"}},
                        "core": {"type": "array", "items": {"type": "string"}},
                        "preferred": {"type": "array", "items": {"type": "string"}}
                    },
                    "additionalProperties": False
                },
                "required_skills": {
                    "type": "object",
                    "properties": {
                        "mandatory": {"type": "array", "items": {"type": "string"}},
                        "core": {"type": "array", "items": {"type": "string"}},
                        "preferred": {"type": "array", "items": {"type": "string"}}
                    },
                    "additionalProperties": False
                },
                "funding_and_duration": {"type": "string"},
                "application_deadline": {"type": "string"},
                "application_deadline_timezone": {"type": "string"},
                "application_deadline_iso": {"type": "string"},
                "start_date": {"type": "string"},
                "start_date_iso": {"type": "string"},
                "application_url": {"type": "string"},
                "contact_email": {"type": "string"},
                "contact_name": {"type": "string"},
                "required_documents": {"type": "array", "items": {"type": "string"}}
            },
            "additionalProperties": False
        },
        "candidate_profile_summary": {
            "type": "object",
            "properties": {
                "education_background": {"type": "string"},
                "research_background": {"type": "string"},
                "technical_and_methodological_skills": {"type": "string"},
                "professional_experience": {"type": "string"},
                "publication_and_academic_record": {"type": "string"}
            },
            "additionalProperties": False
        },
        "matching_score": {
            "type": "object",
            "properties": {
                "overall_score": {"type": "number"},
                "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                "evaluation_rounds": {
                    "type": "object",
                    "properties": {
                        "eligibility_score": {"type": "number"},
                        "academic_fit_score": {"type": "number"},
                        "research_fit_score": {"type": "number"},
                        "technical_methodological_fit_score": {"type": "number"},
                        "domain_fit_score": {"type": "number"},
                        "research_experience_score": {"type": "number"},
                        "competitiveness_score": {"type": "number"}
                    },
                    "additionalProperties": False
                },
                "weighted_dimensions": {
                    "type": "object",
                    "properties": {
                        "mandatory_requirements": {"type": "number"},
                        "research_project_fit": {"type": "number"},
                        "research_experience": {"type": "number"},
                        "technical_methodological_fit": {"type": "number"},
                        "domain_application_fit": {"type": "number"},
                        "education_academic_record": {"type": "number"},
                        "research_outputs": {"type": "number"},
                        "lab_supervisor_fit": {"type": "number"},
                        "preferred_requirements": {"type": "number"}
                    },
                    "additionalProperties": False
                },
                "evidence": {
                    "type": "object",
                    "properties": {
                        "direct_matches": {"type": "array", "items": {"type": "string"}},
                        "transferable_matches": {"type": "array", "items": {"type": "string"}},
                        "missing_requirements": {"type": "array", "items": {"type": "string"}},
                        "unclear_requirements": {"type": "array", "items": {"type": "string"}}
                    },
                    "additionalProperties": False
                }
            },
            "additionalProperties": False
        },
        "final_verdict": {
            "type": "object",
            "properties": {
                "match_category": {
                    "type": "string",
                    "enum": ["excellent_match", "good_match", "possible_match", "weak_match"]
                },
                "application_recommendation": {
                    "type": "string",
                    "enum": ["strongly_recommended", "recommended", "possible_but_risky", "not_recommended"]
                },
                "summary": {"type": "string"},
                "main_reason": {"type": "string"}
            },
            "additionalProperties": False
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
        "city": "",
        "address": "",
        "position_type": "",
        "research_area": [],
        "main_research_objective": "",
        "key_topics": [],
        "research_methods": [],
        "target_application_domain": [],
        "required_background": {
            "mandatory": [],
            "core": [],
            "preferred": []
        },
        "required_skills": {
            "mandatory": [],
            "core": [],
            "preferred": []
        },
        "funding_and_duration": "",
        "application_deadline": "",
        "application_deadline_timezone": "",
        "application_deadline_iso": "",
        "start_date": "",
        "start_date_iso": "",
        "application_url": "",
        "contact_email": "",
        "contact_name": "",
        "required_documents": []
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
            "eligibility_score": 0,
            "academic_fit_score": 0,
            "research_fit_score": 0,
            "technical_methodological_fit_score": 0,
            "domain_fit_score": 0,
            "research_experience_score": 0,
            "competitiveness_score": 0
        },
        "weighted_dimensions": {
            "mandatory_requirements": 0,
            "research_project_fit": 0,
            "research_experience": 0,
            "technical_methodological_fit": 0,
            "domain_application_fit": 0,
            "education_academic_record": 0,
            "research_outputs": 0,
            "lab_supervisor_fit": 0,
            "preferred_requirements": 0
        },
        "evidence": {
            "direct_matches": [],
            "transferable_matches": [],
            "missing_requirements": [],
            "unclear_requirements": []
        }
    },
    "final_verdict": {
        "match_category": "weak_match",
        "application_recommendation": "",
        "summary": "",
        "main_reason": ""
    }
}