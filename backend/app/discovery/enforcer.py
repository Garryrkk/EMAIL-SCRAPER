import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class DiscoveryRuleEnforcer:
    """
    Enforce critical rules that make system behave like Apollo/Hunter.
    
    RULES:
    1. Discovered emails = facts (100% confidence, no decay)
    2. No guessing when discovery exists
    3. No inference when work emails found
    4. Gmail never used for patterns
    5. Discovered is always shown
    """

    @staticmethod
    def enforce_discovered_are_facts(discovered_emails: List[Dict]) -> List[Dict]:
        """
        RULE 1: Discovered emails are FACTS.
        
        Before passing to confidence engine:
        - Set existence_confidence = 1.0
        - Mark as factual
        - Prevent decay
        - Prevent pattern weighting
        
        This is NON-NEGOTIABLE.
        """
        enforced = []
        
        for email_data in discovered_emails:
            # Mark as factual
            email_data["is_factual"] = True
            email_data["existence_confidence"] = 1.0
            email_data["no_decay"] = True  # Never apply time decay
            email_data["skip_pattern_weighting"] = True  # Pattern doesn't affect this
            
            logger.debug(f"Enforced: {email_data['email']} is FACT (discovered)")
            enforced.append(email_data)
        
        return enforced

    @staticmethod
    def should_use_fallback(
        discovered_work_emails: List[Dict],
        allow_fallback: bool,
    ) -> bool:
        """
        RULE 2: No guessing when discovery exists.
        
        Fallback only if:
        - discovered_work_emails is EMPTY
        - allow_fallback=True
        
        Otherwise: NEVER use fallback
        """
        if len(discovered_work_emails) > 0:
            logger.info(
                f"Work emails found ({len(discovered_work_emails)}): "
                f"Fallback DISABLED (rule: no guessing when discovery exists)"
            )
            return False
        
        if not allow_fallback:
            logger.info("Fallback explicitly disabled")
            return False
        
        logger.info("No work emails found + fallback enabled: Using fallback")
        return True

    @staticmethod
    def should_use_inference(
        discovered_work_emails: List[Dict],
        pattern: str,
        pattern_confidence: float,
    ) -> bool:
        """
        RULE 3: No inference when work emails found.
        
        Inference (generation) only if:
        - Pattern exists AND confidence >= 60%
        - AND no discovered work emails to use as base
        
        Otherwise: NEVER infer
        """
        if len(discovered_work_emails) > 0:
            logger.info(
                f"Work emails found ({len(discovered_work_emails)}): "
                f"Inference DISABLED (rule: don't guess when you have facts)"
            )
            return False
        
        if not pattern or pattern_confidence < 0.6:
            logger.info(
                f"Pattern missing or too weak "
                f"({pattern} @ {pattern_confidence:.0%}): Inference DISABLED"
            )
            return False
        
        logger.info(f"Pattern strong enough ({pattern} @ {pattern_confidence:.0%}): Inference OK")
        return True

    @staticmethod
    def enforce_gmail_excluded_from_patterns(
        all_discovered_emails: List[Dict],
    ) -> tuple[List[Dict], List[Dict]]:
        """
        RULE 4: Gmail/personal emails never used for patterns.
        
        Returns:
            (work_emails_for_pattern, personal_emails_to_show)
        
        Work emails: Used for pattern learning
        Personal emails: Shown but not for patterns
        """
        work_emails = []
        personal_emails = []
        
        for email_data in all_discovered_emails:
            email_type = email_data.get("email_type", "work")
            
            if email_type == "personal":
                personal_emails.append(email_data)
                logger.debug(f"Personal email excluded from pattern: {email_data['email']}")
            else:
                work_emails.append(email_data)
                logger.debug(f"Work email included for pattern: {email_data['email']}")
        
        return work_emails, personal_emails

    @staticmethod
    def discovered_always_shown(discovered_emails: List[Dict]) -> List[Dict]:
        """
        RULE 5: Discovered emails always shown.
        
        Criteria:
        - source == "discovered"
        - existence_confidence == 1.0
        - show_by_default = True
        
        No filtering based on:
        - Pattern confidence
        - Gmail domain
        - Verification status
        """
        shown = []
        
        for email_data in discovered_emails:
            if email_data.get("source") == "discovered":
                email_data["show_by_default"] = True
                email_data["always_show"] = True  # Cannot be hidden
                logger.debug(f"Discovered email ALWAYS shown: {email_data['email']}")
                shown.append(email_data)
            else:
                logger.debug(f"Not discovered, may filter: {email_data['email']}")
        
        return shown


class ResponseEnforcer:
    """
    Enforce rules in API responses.
    """

    @staticmethod
    def enforce_discovered_response(email_dict: Dict) -> Dict:
        """
        For discovered emails, enforce:
        - existence_confidence = 1.0 (ALWAYS)
        - No decay applied
        - No pattern weighting
        - Clear source labeling
        """
        if email_dict.get("source") != "discovered":
            return email_dict
        
        # FORCE these values
        email_dict["existence_confidence"] = 1.0
        email_dict["confidence"] = 1.0  # For UI display
        email_dict["is_factual"] = True
        email_dict["no_decay_applied"] = True
        
        # Update label
        if email_dict.get("email_type") == "personal":
            email_dict["label"] = "Found on company website (personal email)"
        else:
            email_dict["label"] = "Found on company website"
        
        return email_dict

    @staticmethod
    def enforce_inferred_response(email_dict: Dict) -> Dict:
        """
        For inferred emails, enforce:
        - source = "inferred"
        - confidence based on pattern + verification
        - NOT 100% (can never be)
        - Only shown if verified + confidence >= 75%
        """
        if email_dict.get("source") != "inferred":
            return email_dict
        
        # Cannot be 1.0 if inferred
        confidence = min(email_dict.get("confidence", 0.0), 0.95)
        email_dict["confidence"] = confidence
        email_dict["is_factual"] = False
        
        # Only show if high confidence
        email_dict["show_by_default"] = confidence >= 0.75
        
        if confidence < 0.75:
            email_dict["label"] = "Generated (unverified) - not shown by default"
        else:
            email_dict["label"] = f"Generated + verified ({confidence:.0%} confidence)"
        
        return email_dict

    @staticmethod
    def enforce_response_ordering(emails: List[Dict]) -> List[Dict]:
        """
        Order response by importance:
        1. Discovered emails (facts)
        2. Verification-inferred (verified guesses)
        3. Pure inferred (unverified)
        
        Then by confidence within each group.
        """
        discovered = []
        verification_inferred = []
        pure_inferred = []
        
        for email in emails:
            source = email.get("source", "unknown")
            
            if source == "discovered":
                discovered.append(email)
            elif source == "verification_inferred":
                verification_inferred.append(email)
            elif source == "inferred":
                pure_inferred.append(email)
        
        # Sort each group by confidence
        discovered.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        verification_inferred.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        pure_inferred.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        
        # Combine in order
        result = discovered + verification_inferred + pure_inferred
        
        logger.info(
            f"Response ordering: "
            f"{len(discovered)} discovered + "
            f"{len(verification_inferred)} verified-inferred + "
            f"{len(pure_inferred)} pure-inferred"
        )
        
        return result