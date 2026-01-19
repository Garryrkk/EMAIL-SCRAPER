import unicodedata
import re
import logging

logger = logging.getLogger("email_intel")

class NameNormalizer:
    @staticmethod
    def normalize_name(name: str) -> str:
        if not name:
            return ""
        # Remove accents
        nfkd_form = unicodedata.normalize('NFKD', name)
        return ''.join([c for c in nfkd_form if not unicodedata.combining(c)])
    
    @staticmethod
    def extract_names(full_name: str) -> tuple:
        full_name = full_name.strip()
        parts = full_name.split()
        if len(parts) == 0:
            return "", ""
        elif len(parts) == 1:
            return parts[0], ""
        else:
            return parts[0], parts[-1]
    
    @staticmethod
    def is_valid_name(name: str) -> bool:
        return len(name) > 1 and name.isalpha()
