import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List
import asyncio

from app.api.deps import get_current_user, check_user_rate_limit, get_db
from app.users.model import User

from app.companies.service import CompanyService
from app.companies.pattern_tracker import PatternTracker
from app.emails.service import EmailService

from app.discovery.service import PublicDiscoveryEngine
from app.discovery.fallback_engine import FallbackInferenceEngine
from app.discovery.enforcer import DiscoveryRuleEnforcer, ResponseEnforcer
from app.inference.pattern_detector import PatternDetector
from app.emails.generator import EmailGenerator
from app.verification.aggregator import VerificationAggregator
from app.scoring.confidence_layered import LayeredConfidenceEngine

logger = logging.getLogger(__name__)

router = APIRouter()


class SearchDomainRequest(BaseModel):
    """Domain search request."""
    domain: str


class SearchPersonRequest(BaseModel):
    """Person search request."""
    domain: str
    first_name: str
    last_name: str


class EmailResultV3(BaseModel):
    """Email result - Apollo/Hunter model."""
    email: str
    source: str  # "discovered", "verification_inferred", "inferred"
    exists: bool  # Existence confidence (always 1.0 or 0.0)
    person_match_confidence: Optional[float] = None  # Association confidence
    deliverability_confidence: Optional[float] = None
    label: str
    email_type: Optional[str] = None


class SearchDomainResponse(BaseModel):
    """Domain search response."""
    domain: str
    discovered_count: int
    personal_emails_found: int
    pattern: Optional[str]
    pattern_confidence: float
    emails: List[EmailResultV3]
    stats: dict


@router.post("/domain", response_model=SearchDomainResponse)
async def search_domain(
    req: SearchDomainRequest,
    include_unverified: bool = Query(False),
    allow_fallback: bool = Query(True),
    current_user: User = Depends(check_user_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """
    APOLLO/HUNTER CORRECT PIPELINE.
    
    Key differences from before:
    1. Discovered emails = facts (100%, no decay)
    2. No guessing when work emails exist
    3. Separate existence vs association confidence
    4. Gmail never used for patterns
    """
    try:
        domain = req.domain.lower().strip()

        # === STAGE 1: DISCOVERY ===
        logger.info(f"[{domain}] Discovery phase")

        discovery_engine = PublicDiscoveryEngine(domain)
        await discovery_engine.initialize()

        try:
            discovery_result = await discovery_engine.discover()
        finally:
            await discovery_engine.close()

        work_emails_raw = discovery_result["work_emails"]
        personal_emails_raw = discovery_result["personal_emails"]

        # === ENFORCE: Discovered emails are facts ===
        all_discovered = work_emails_raw + personal_emails_raw
        all_discovered = DiscoveryRuleEnforcer.enforce_discovered_are_facts(all_discovered)

        logger.info(
            f"[{domain}] Discovered: "
            f"{len(work_emails_raw)} work (facts), "
            f"{len(personal_emails_raw)} personal (facts)"
        )

        # === STAGE 2: PATTERN LEARNING ===
        pattern = None
        pattern_confidence = 0.0

        # ENFORCE: Gmail excluded from patterns
        work_for_pattern, personal_for_show = DiscoveryRuleEnforcer.enforce_gmail_excluded_from_patterns(
            all_discovered
        )

        if work_for_pattern:
            pattern_detector = PatternDetector()
            work_email_addresses = [e["email"] for e in work_for_pattern]
            pattern, pattern_confidence = pattern_detector.learn_from_discovered(
                work_email_addresses
            )

        # === STAGE 3: DECIDE - NO GUESSING RULE ===
        use_fallback = DiscoveryRuleEnforcer.should_use_fallback(
            work_for_pattern,
            allow_fallback,
        )

        fallback_candidates = []
        if use_fallback:
            logger.info(f"[{domain}] Fallback triggered (no work emails)")
            fallback_engine = FallbackInferenceEngine(domain)
            # Note: Would need person info to use fallback
            # For now, just mark as available

        # === STAGE 4: VERIFICATION ===
        logger.info(f"[{domain}] Verification phase")

        verifier = VerificationAggregator()
        verified_results = {}

        for email_data in all_discovered:
            email = email_data["email"]
            result = await verifier.verify(email)
            verified_results[email] = result

        # === STAGE 5: CONFIDENCE SCORING (Layered Model) ===
        logger.info(f"[{domain}] Scoring phase (layered model)")

        confidence_engine = LayeredConfidenceEngine()
        all_scored = []

        for email_data in all_discovered:
            email = email_data["email"]
            verification = verified_results[email]
            email_type = email_data.get("email_type", "work")

            # LAYER 1: Existence confidence (for discovered emails = 1.0)
            existence = confidence_engine.score_email_existence(
                email=email,
                source="discovered",  # All are discovered
                verification_status=verification.verification_status,
            )

            # LAYER 3: Deliverability confidence
            deliverability = confidence_engine.score_deliverability(
                email=email,
                verification_status=verification.verification_status,
                mx_valid=verification.mx_exists,
                catch_all=(verification.verification_status == "catch_all"),
            )

            # Combine layers (no association layer for domain search)
            combined = confidence_engine.combine_layers(
                existence=existence,
                association=None,
                deliverability=deliverability,
            )

            # Enforce response rules
            email_result = {
                "email": email,
                "source": "discovered",
                "exists": combined["email_exists"],
                "existence_confidence": combined["existence_confidence"],
                "deliverability_confidence": combined.get("deliverability_confidence"),
                "label": combined.get("reason_existence"),
                "email_type": email_type,
                "verification_status": verification.verification_status,
                "show_by_default": True,  # ALWAYS show discovered
            }

            email_result = ResponseEnforcer.enforce_discovered_response(email_result)
            all_scored.append(email_result)

        # === STAGE 6: ORDERING ===
        all_scored = ResponseEnforcer.enforce_response_ordering(all_scored)

        # === STAGE 7: SAVE TO DATABASE ===
        logger.info(f"[{domain}] Saving results")

        company_service = CompanyService(db)
        company = await company_service.create_company(domain)
        
        if pattern:
            await company_service.set_detected_pattern(company.id, pattern, pattern_confidence)

        email_service = EmailService(db)
        for email_data in all_discovered:
            email = email_data["email"]
            await email_service.create_email(
                address=email,
                domain=domain,
                company_id=company.id,
                source="discovered",
            )

        await db.commit()

        # === RESPONSE ===
        return SearchDomainResponse(
            domain=domain,
            discovered_count=len(work_emails_raw),
            personal_emails_found=len(personal_emails_raw),
            pattern=pattern,
            pattern_confidence=pattern_confidence,
            emails=all_scored,
            stats={
                "work_emails_discovered": len(work_emails_raw),
                "personal_emails_discovered": len(personal_emails_raw),
                "pattern_learned": pattern is not None,
                "can_generate": pattern is not None and pattern_confidence >= 0.6,
                "fallback_available": use_fallback,
                "total_shown": len(all_scored),
                "all_are_facts": True,  # Key indicator
            },
        )

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed",
        )


@router.post("/person")
async def search_person(
    req: SearchPersonRequest,
    current_user: User = Depends(check_user_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """
    Person search - this is where association confidence applies.
    
    Returns THREE confidence values:
    1. existence_confidence (100% if exists, 0% if not)
    2. person_match_confidence (0-95%, probabilistic)
    3. deliverability_confidence (0-100%, time-aware)
    """
    try:
        domain = req.domain.lower().strip()

        company_service = CompanyService(db)
        company = await company_service.get_company_by_domain(domain)

        if not company or not company.detected_pattern:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No confirmed pattern for {domain}. Search domain first.",
            )

        # === GENERATE CANDIDATES ===
        # ENFORCE: Only generate if pattern exists
        generator = EmailGenerator()
        candidates = generator.generate_candidates(
            first_name=req.first_name,
            last_name=req.last_name,
            domain=domain,
            pattern=company.detected_pattern,
            pattern_confidence=company.pattern_confidence,
        )

        if not candidates:
            return {
                "domain": domain,
                "person": f"{req.first_name} {req.last_name}",
                "candidates": [],
            }

        # === VERIFY ===
        verifier = VerificationAggregator()
        verified_candidates = []

        for candidate in candidates:
            verification = await verifier.verify(candidate["email"])
            candidate["verification_status"] = verification.verification_status
            candidate["mx_valid"] = verification.mx_exists
            candidate["catch_all"] = verification.verification_status == "catch_all"
            verified_candidates.append(candidate)

        # === SCORE (Three Layers) ===
        confidence_engine = LayeredConfidenceEngine()
        scored_candidates = []

        for candidate in verified_candidates:
            # LAYER 1: Existence (is this email real?)
            # For inferred: only "exists" if verified
            if candidate["verification_status"] == "valid":
                existence = {
                    "exists": True,
                    "existence_confidence": 1.0,
                    "reason": "SMTP verified (exists)",
                }
            else:
                existence = {
                    "exists": False,
                    "existence_confidence": 0.0,
                    "reason": "Not verified as existing",
                }

            # LAYER 2: Association (is this John Doe's email?)
            association = confidence_engine.score_person_association(
                person_first=req.first_name,
                person_last=req.last_name,
                email=candidate["email"],
                pattern_used=candidate["pattern_used"],
                pattern_confidence=candidate["pattern_confidence"],
                verification_status=candidate["verification_status"],
            )

            # LAYER 3: Deliverability
            deliverability = confidence_engine.score_deliverability(
                email=candidate["email"],
                verification_status=candidate["verification_status"],
                mx_valid=candidate["mx_valid"],
                catch_all=candidate["catch_all"],
            )

            # Combine
            combined = confidence_engine.combine_layers(
                existence=existence,
                association=association,
                deliverability=deliverability,
            )

            # Only show if exists
            if not combined["email_exists"]:
                continue

            # Enforce response rules
            email_result = {
                "email": candidate["email"],
                "source": "inferred",
                "exists": combined["email_exists"],
                "existence_confidence": combined["existence_confidence"],
                "person_match_confidence": combined.get("person_match_confidence"),
                "deliverability_confidence": combined.get("deliverability_confidence"),
                "label": combined.get("reason_association", ""),
                "verification_status": candidate["verification_status"],
                "show_by_default": combined.get("person_match_confidence", 0) >= 0.75,
            }

            email_result = ResponseEnforcer.enforce_inferred_response(email_result)
            scored_candidates.append(email_result)

        # Sort by person match confidence
        scored_candidates.sort(key=lambda x: x.get("person_match_confidence", 0), reverse=True)

        await db.commit()

        return {
            "domain": domain,
            "person": f"{req.first_name} {req.last_name}",
            "pattern": company.detected_pattern,
            "pattern_confidence": company.pattern_confidence,
            "candidates": scored_candidates,
            "note": "Each email shows: exists (factual), person_match (probabilistic), deliverability (practical)",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Person search error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Person search failed",
        )