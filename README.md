# Funding Aggregator

> Microservice for aggregating grants, scholarships, and funding opportunities  
> from Grants.gov, NIH RePORTER, and USASpending.gov.

[![CI Pipeline](https://github.com/YOUR_ORG/Funding-Aggregator/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_ORG/Funding-Aggregator/actions/workflows/ci.yml)

---

## Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI + Uvicorn |
| Database | PostgreSQL 15 + SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Task Queue | Celery + Redis |
| Containerization | Docker + docker-compose |
| Monitoring | Prometheus + Grafana |
| Testing | pytest + httpx (async) |
| Load Testing | k6 / Locust |
| Auth | JWT (python-jose) |
| Linting | ruff |

---

## Data Sources

| Source | Type | Records | Schedule |
|---|---|---|---|
| [Grants.gov](https://grants.gov) | REST API | ~100/run | Every 6h |
| [NIH RePORTER](https://reporter.nih.gov) | REST API | ~100/run | Daily 3am |
| [USASpending.gov](https://usaspending.gov) | REST API | ~150/run | Daily 4am |

---

## Quick Start

```bash
# 1. Clone & setup env
git clone https://github.com/YOUR_ORG/Funding-Aggregator.git
cd Funding-Aggregator
cp .env.example .env

# 2. Start all services
docker compose up -d

# 3. Check health
curl http://localhost:8000/api/v1/health

# 4. Trigger manual data collection (requires auth)
# Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"Admin123!"}'

# Login → get token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"Admin123!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Trigger collection from all 3 sources
curl -X POST http://localhost:8000/api/v1/grants/collect/grants_gov \
  -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8000/api/v1/grants/collect/nih_reporter \
  -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8000/api/v1/grants/collect/usa_spending \
  -H "Authorization: Bearer $TOKEN"

# 5. Check stats
curl http://localhost:8000/api/v1/stats
```

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/` | No | Root info |
| GET | `/docs` | No | Swagger UI |
| GET | `/redoc` | No | ReDoc |
| GET | `/metrics` | No | Prometheus metrics |
| GET | `/api/v1/health` | No | Health check |
| GET | `/api/v1/stats` | No | DB statistics |
| POST | `/api/v1/auth/register` | No | Register user |
| POST | `/api/v1/auth/login` | No | Login → JWT token |
| GET | `/api/v1/auth/me` | Yes | Current user |
| GET | `/api/v1/grants` | No | List grants (filters + pagination) |
| GET | `/api/v1/grants/{id}` | No | Grant detail |
| POST | `/api/v1/grants/collect/{source}` | Yes | Trigger collection |
| GET | `/api/v1/categories` | No | List categories |

### Grant Filters

```
GET /api/v1/grants?search=health&source=grants_gov&status=open
  &agency_name=NIH&deadline_from=2025-01-01&deadline_to=2025-12-31
  &amount_min=10000&amount_max=500000&category_slug=science
  &page=1&per_page=20
```

---

## Monitoring

| Service | URL | Credentials |
|---|---|---|
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | — |
| API Docs | http://localhost:8000/docs | — |
| Metrics | http://localhost:8000/metrics | — |

Grafana dashboard is auto-provisioned at startup.

---

## Load Testing

### k6

```bash
# Install k6
brew install k6  # macOS
# or: https://k6.io/docs/getting-started/installation/

# Basic load test (ramp to 100 users)
k6 run load_tests/k6_script.js

# With custom base URL
BASE_URL=http://localhost:8000 k6 run load_tests/k6_script.js

# Export results
k6 run --out json=load_tests/results.json load_tests/k6_script.js
```

### Locust

```bash
pip install locust

# Web UI mode
locust -f load_tests/locustfile.py --host=http://localhost:8000
# Open http://localhost:8089 → set Users=100, Spawn rate=10

# Headless (for CI / reports)
locust -f load_tests/locustfile.py \
  --host=http://localhost:8000 \
  --headless -u 100 -r 10 --run-time 3m \
  --html=load_tests/report.html \
  --csv=load_tests/results
```

### Performance Targets

| Metric | Target |
|---|---|
| P95 latency | < 500ms |
| Error rate | < 5% |
| Concurrent users | 100+ |

---

## Development

```bash
# Local setup (without Docker)
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start dev server
uvicorn app.main:app --reload --port 8000

# Run tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html
open htmlcov/index.html

# Lint
ruff check app/ tests/
ruff format app/ tests/

# Start Celery worker
celery -A app.tasks.celery_app worker --loglevel=info

# Start Celery beat (scheduler)
celery -A app.tasks.celery_app beat --loglevel=info
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Client / Browser                      │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼──────────────────────────────┐
│              FastAPI App (port 8000)                     │
│  /api/v1/grants  /api/v1/auth  /api/v1/categories       │
│  Prometheus metrics at /metrics                         │
└──────┬────────────────────────────────┬─────────────────┘
       │ SQLAlchemy async               │ Celery task
┌──────▼──────┐                ┌────────▼────────┐
│ PostgreSQL  │                │  Redis (broker) │
│ (port 5432) │                │  (port 6379)    │
└─────────────┘                └────────┬────────┘
                                        │
                               ┌────────▼────────┐
                               │  Celery Worker  │
                               │  + Beat         │
                               │                 │
                               │ Collectors:     │
                               │  • grants_gov   │
                               │  • nih_reporter │
                               │  • usa_spending │
                               └─────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Observability Stack                                     │
│  Prometheus (9090) ← scrapes /metrics every 15s         │
│  Grafana (3000) ← reads from Prometheus                  │
└─────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
Funding-Aggregator/
├── app/
│   ├── api/v1/          # FastAPI routers
│   │   ├── auth.py      # register / login / me
│   │   ├── grants.py    # list / detail / collect
│   │   ├── categories.py
│   │   └── health.py    # health + stats
│   ├── auth/            # JWT + password hashing
│   ├── collector/       # Data collectors
│   │   ├── base.py      # BaseCollector (retries, UA rotation)
│   │   ├── grants_gov.py
│   │   ├── nih_reporter.py
│   │   └── usa_spending.py
│   ├── models/          # SQLAlchemy ORM models
│   ├── processor/       # Data cleaning pipeline
│   │   ├── cleaner.py   # clean_html, extract_keywords, parse_date
│   │   └── pipeline.py  # process_grant, run_pipeline
│   ├── schemas/         # Pydantic schemas
│   ├── tasks/           # Celery tasks
│   ├── config.py        # Settings (pydantic-settings)
│   ├── database.py      # Async engine + session
│   └── main.py          # FastAPI app entry point
├── migrations/          # Alembic migrations
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/
│       ├── provisioning/  # Auto-configured on startup
│       └── dashboards/    # Funding Aggregator dashboard
├── load_tests/
│   ├── k6_script.js     # k6 load test (100+ VUs)
│   └── locustfile.py    # Locust alternative
├── tests/               # pytest tests (coverage > 40%)
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .github/workflows/ci.yml
```
