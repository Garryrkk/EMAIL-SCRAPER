# User Plans
class UserPlan:
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


# User Status
class UserStatus:
    ACTIVE = "active"
    PENDING = "pending"
    SUSPENDED = "suspended"
    DELETED = "deleted"


# Email Status
class EmailStatus:
    VALID = "valid"
    INVALID = "invalid"
    ACCEPT_ALL = "accept_all"
    UNKNOWN = "unknown"
    RISKY = "risky"


# Company Status
class CompanyStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"
    HIDDEN = "hidden"


# Email Source
class EmailSource:
    INFERRED = "inferred"
    DISCOVERED = "discovered"
    IMPORTED = "imported"
    ENRICHED = "enriched"


# Risk Levels
class RiskLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Plan Limits (API calls per month)
PLAN_LIMITS = {
    UserPlan.FREE: {
        "searches": 50,
        "verifications": 10,
        "exports": 5,
    },
    UserPlan.STARTER: {
        "searches": 5000,
        "verifications": 1000,
        "exports": 100,
    },
    UserPlan.PROFESSIONAL: {
        "searches": 50000,
        "verifications": 10000,
        "exports": 1000,
    },
    UserPlan.ENTERPRISE: {
        "searches": float("inf"),
        "verifications": float("inf"),
        "exports": float("inf"),
    },
}

# Credit costs
CREDIT_COSTS = {
    "search": 1,
    "verification": 2,
    "export": 1,
    "enrichment": 3,
}

# Email patterns
COMMON_EMAIL_PATTERNS = [
    "firstname.lastname@domain",
    "firstname@domain",
    "f.lastname@domain",
    "flastname@domain",
    "firstname_lastname@domain",
    "fn@domain",
    "firstnameln@domain",
]

# Domain patterns (generic domains to exclude)
GENERIC_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "aol.com",
    "protonmail.com",
    "icloud.com",
    "mail.com",
    "123.com",
}

# Role-based email patterns
ROLE_BASED_PATTERNS = {
    "info@",
    "contact@",
    "support@",
    "hello@",
    "noreply@",
    "no-reply@",
    "sales@",
    "admin@",
    "team@",
}

# GDPR Countries
GDPR_COUNTRIES = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE",
}