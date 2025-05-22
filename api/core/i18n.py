"""
Internationalization module.

This module provides utilities for language detection and multilingual support.
"""
import logging
from typing import List, Optional

from fastapi import Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Supported languages with their codes and English names
class Language(BaseModel):
    """Language model."""
    
    code: str
    name: str


# List of supported languages
SUPPORTED_LANGUAGES = [
    Language(code="en-US", name="English (US)"),
    Language(code="es-ES", name="Spanish (Spain)"),
    Language(code="fr-FR", name="French (France)"),
    Language(code="de-DE", name="German (Germany)"),
    Language(code="it-IT", name="Italian (Italy)"),
    Language(code="ja-JP", name="Japanese (Japan)"),
    Language(code="ko-KR", name="Korean (Korea)"),
    Language(code="pt-BR", name="Portuguese (Brazil)"),
    Language(code="ru-RU", name="Russian (Russia)"),
    Language(code="zh-CN", name="Chinese (Simplified)"),
    Language(code="zh-TW", name="Chinese (Traditional)"),
]

# Default language code
DEFAULT_LANGUAGE = "en-US"

# Map of language codes to Language objects for quick lookup
LANGUAGE_MAP = {lang.code: lang for lang in SUPPORTED_LANGUAGES}


def get_supported_languages() -> List[Language]:
    """
    Get list of supported languages.
    
    Returns:
        List[Language]: List of supported languages
    """
    return SUPPORTED_LANGUAGES


def is_language_supported(lang_code: str) -> bool:
    """
    Check if a language code is supported.
    
    Args:
        lang_code: Language code
        
    Returns:
        bool: True if the language is supported
    """
    # Normalize language code
    lang_code = normalize_language_code(lang_code)
    return lang_code in LANGUAGE_MAP


def normalize_language_code(lang_code: str) -> str:
    """
    Normalize language code.
    
    Args:
        lang_code: Language code
        
    Returns:
        str: Normalized language code
    """
    if not lang_code:
        return DEFAULT_LANGUAGE
        
    # First try exact match
    if lang_code in LANGUAGE_MAP:
        return lang_code
        
    # Try matching primary language code
    primary_code = lang_code.split('-')[0]
    for supported_code in LANGUAGE_MAP:
        if supported_code.startswith(f"{primary_code}-"):
            return supported_code
            
    return DEFAULT_LANGUAGE


def get_language_from_request(request: Request) -> str:
    """
    Get language from request.
    
    Args:
        request: FastAPI request
        
    Returns:
        str: Language code
    """
    # Check query parameter first
    lang_param = request.query_params.get("lang")
    if lang_param and is_language_supported(lang_param):
        return normalize_language_code(lang_param)
        
    # Check Accept-Language header
    accept_language = request.headers.get("Accept-Language")
    if accept_language:
        # Parse Accept-Language header (e.g., "en-US,en;q=0.9,fr;q=0.8")
        for lang in accept_language.split(","):
            code = lang.split(";")[0].strip()
            if is_language_supported(code):
                return normalize_language_code(code)
                
    # Fall back to default
    return DEFAULT_LANGUAGE
