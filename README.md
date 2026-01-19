# Apollo - Email Intelligence Platform

Production-ready FastAPI + PostgreSQL email discovery and verification system.

## Architecture Overview

```
main.py (Bootstrap)
├── core/ (Configuration & Security)
│   ├── config.py
│   ├── database.py
│   ├── security.py
│   ├── logging.py
│   ├── rate_limit.py
│   └── constants.py
│
├── auth/ (Authentication)
│   ├── service.py
│   └── schemas.py
│
├── users/ (User Management)
│   ├── model.py
│   ├── service.py
│   └── limits.py
│
├── companies/ (Company Intelligence)
│   ├── model.py
│   ├── service.py
│   └── discovery.py
│
├── people/ (Person Data)
│   ├── model.py
│   └── normalizer.py
│
├── emails/ (Email Entity)
│   ├── model.py
│   ├── service.py
│   ├── generator.py
│   └── formatter.py
│
├── discovery/ (Web Crawling)
│   ├── crawler.py
│   ├── extractor.py
│   └── sanitizer.py
│
├── inference/ (Confidence Engine)
│   ├── pattern_detector.py
│   └── confidence.py
│
├── verification/ (Deliverability)
│   ├── syntax.py
│   ├── dns.py
│   ├── smtp.py
│   └── aggregator.py
│
├── api/ (REST Layer)
│   ├── router.py
│   ├── deps.py
│   └── routes/
│       ├── auth.py
│       ├── users.py
│       ├── companies.py
│       ├── search.py
│       └── emails.py
│
└── workers/ (Background Jobs)
    ├── tasks.py
    └── scheduler.py
```

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Docker & Docker Compose (optional)

### Local Development Setup

1. **Clone and setup environment:**
```bash
git clone <repo>
cd apollo
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

2. **Start services with Docker:**
```bash
docker-compose up -d
```

3. **Initialize database:**
```bash
python -c "from core.database import init_db; import asyncio; asyncio.run(init_db())"
```

4. **Run server:**
```bash
uvicorn main:app --reload
```

Server runs at `http://localhost:8000`
API docs at `http://localhost:8000/docs`

## API Endpoints

### Authentication
- `POST /api/v1/auth/signup` - Register user
- `POST /api/v1/auth/login` - Login
- `POST /api/v1/auth/refresh` - Refresh token
- `GET /api/v1/auth/me` - Get profile
- `POST /api/v1/auth/change-password` - Change password

### Search
- `POST /api/v1/search/domain` - Search domain for emails
- `POST /api/v1/search/person` - Search person at domain

### Emails
- `POST /api/v1/emails/verify` - Verify single email
- `POST /api/v1/emails/bulk-verify` - Bulk verify emails
- `GET /api/v1/emails/{id}` - Get email details

### Companies
- `GET /api/v1/companies/{domain}` - Get company info
- `POST /api/v1/companies/{domain}/rescan` - Rescan company

### Users
- `GET /api/v1/users/me` - Get profile
- `PUT /api/v1/users/me` - Update profile
- `GET /api/v1/users/credits` - Get credits
- `GET /api/v1/users/usage` - Get usage stats

## Core Features

### 1. Email Discovery
- **Web Crawling**: Respectful domain crawling with robots.txt support
- **HTML Extraction**: Email/name extraction with context awareness
- **Pattern Detection**: Automatic dominant email pattern detection
- **Result Deduplication**: Smart duplicate handling

### 2. Email Generation
- **Pattern-Based**: Generate emails using detected patterns
- **Alternative Patterns**: Generate permutations for matching
- **Person Integration**: Generate specific emails for individuals
- **Risk Scoring**: Evaluate likelihood of generated emails

### 3. Email Verification
- **Syntax Validation**: RFC-compliant email validation
- **DNS Lookup**: MX record verification
- **SMTP Verification**: Safe handshake-only verification
- **Catch-All Detection**: Identify catch-all domains
- **Bounce Tracking**: Track bounce history

### 4. Confidence Scoring
- **Multi-Factor**: Combines syntax, SMTP, pattern, bounce rate
- **Source-Based**: Different confidence for discovered vs inferred
- **Risk Assessment**: Evaluates role-based and generic emails
- **Company-Level**: Domain confidence from public email analysis

### 5. Rate Limiting
- **User-Based**: Per-user request limiting
- **IP-Based**: Per-IP address limiting
- **Endpoint-Specific**: Different limits per endpoint
- **Sliding Window**: Redis-based sliding window

### 6. Credit System
- **Per-Action Costs**: Configurable credits for searches/verifications
- **Plan-Based**: Different limits per subscription plan
- **Usage Tracking**: Track all API usage
- **Enforcement**: Prevent operations when credits exhausted

### 7. Background Jobs
- **Domain Crawling**: Queue crawl tasks for domains
- **Email Verification**: Async batch verification
- **Data Cleanup**: Automatic cleanup of old data
- **Statistics Update**: Periodic bounce rate updates

## Database Schema

### Users
- Email, password hash, credits
- Plan (free/starter/professional/enterprise)
- Status (active/suspended)
- Risk score for abuse detection

### Companies
- Domain, name, industry, size
- Detected pattern & confidence
- Public emails found count
- Bounce rate, confidence score

### People
- First/last name, title, department
- Company association
- LinkedIn/Twitter URLs
- Seniority level

### Emails
- Address, domain, company
- Source (inferred/discovered/enriched)
- Verification status & confidence
- Bounce tracking
- Usage stats (views/exports)

## Configuration

Key environment variables:

```
DATABASE_URL=postgresql+asyncpg://user:pass@host/db
REDIS_URL=redis://host:6379/0
ELASTICSEARCH_URL=http://host:9200

SMTP_HOST=smtp.gmail.com
SMTP_USER=your@email.com
SMTP_PASSWORD=app-password

JWT_EXPIRY_MINUTES=60
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD_SECONDS=60

FEATURE_VERIFICATION_ENABLED=True
ABUSE_DETECTION_ENABLED=True
```

## Production Deployment

### Using Docker

```bash
docker build -t apollo:latest .
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://... \
  -e REDIS_URL=redis://... \
  apollo:latest
```

### Using Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: apollo-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: apollo
  template:
    metadata:
      labels:
        app: apollo
    spec:
      containers:
      - name: apollo
        image: apollo:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: apollo-secrets
              key: database-url
```

### Scaling Considerations

1. **Database**: Use read replicas for search queries
2. **Redis**: Cluster for rate limiting & caching
3. **Workers**: Horizontal scaling with async tasks
4. **API**: Stateless, scale behind load balancer

## Testing

```bash
pytest tests/ -v
pytest tests/ --cov=.  # With coverage
pytest tests/test_emails.py -v  # Specific test
```

## Common Issues & Solutions

**Issue: Database connection fails**
- Check PostgreSQL is running: `docker-compose ps`
- Verify credentials in `.env`
- Run: `docker-compose logs postgres`

**Issue: SMTP verification times out**
- Increase `SMTP_VERIFY_TIMEOUT` in config
- Check firewall rules for port 25/587
- Verify `SMTP_HOST` and credentials

**Issue: Rate limiting not working**
- Verify Redis is running and accessible
- Check `REDIS_URL` in `.env`
- Try: `redis-cli ping`

**Issue: Crawler blocked**
- Check `CRAWLER_USER_AGENT` is proper
- Verify `robots.txt` compliance
- Reduce `CRAWLER_RATE_LIMIT_PER_DOMAIN`

## Performance Tips

1. **Batch Operations**: Use bulk endpoints when possible
2. **Caching**: Results cached by domain, re-use when available
3. **Index Emails**: Create database indexes on frequently queried columns
4. **Async Verification**: Verification happens asynchronously in background
5. **Connection Pooling**: Database pool size tunable in config

## Security Best Practices

1. **Change `SECRET_KEY`** in production
2. **Use environment variables** for sensitive data
3. **Enable HTTPS** in production
4. **Rate limiting** enabled by default
5. **CORS configured** - customize `CORS_ORIGINS`
6. **GDPR support** - automatic data cleanup
7. **Password hashing** with bcrypt (rounds=12)
8. **Token expiry** configured - 60 min access, 7 day refresh

## Monitoring

Key metrics to monitor:
- API response times (p50, p95, p99)
- Error rates by endpoint
- Database connection pool usage
- Redis memory usage
- Email verification success rate
- Bounce rate trends

## Support & Contributing

For issues or questions, check the documentation or submit an issue.

---

**Built with ❤️ for email intelligence**