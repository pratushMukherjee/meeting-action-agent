# Meeting Action Agent

An autonomous AI agent that processes meeting transcripts and executes multi-step follow-up actions — Jira ticket creation, email summaries, and calendar scheduling — through coordinated API orchestration with built-in guardrails and human-in-the-loop approval.

Built as a production-grade agentic system demonstrating **ReAct-style reasoning**, **tool orchestration**, **three-layer guardrails**, and **distributed infrastructure** — aligned with the responsibilities of an AI Agent Engineer.

---

## Table of Contents

- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Key Features](#key-features)
- [Testing](#testing)
- [Deployment](#deployment)
- [Monitoring & Observability](#monitoring--observability)
- [License](#license)

---

## Architecture

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                       MEETING ACTION AGENT                          │
│                                                                     │
│  ┌───────────┐    ┌───────────┐    ┌────────────────────────────┐   │
│  │  Client    │───▶│  FastAPI  │───▶│  Celery Task Queue       │   │
│  │ (REST API) │◀───│  REST API │    │  (Redis Broker)          │    │
│  └───────────┘    └─────┬─────┘    └──────────────┬─────────────┘   │
│                         │                         │                 │
│                         │ Prometheus              │                 │
│                         │ /metrics                ▼                 │
│                         │             ┌──────────────────────┐      │
│                         │             │ LangGraph Agent Core │      │
│                         │             │                      │      │
│                         │             │ ┌──────────────────┐ │      │
│                         │             │ │ parse_transcript │ │      │
│                         │             │ └────────┬─────────┘ │      │
│                         │             │          ▼           │      │
│                         │             │ ┌──────────────────┐ │      │
│                         │             │ │ plan_actions     │ │      │
│                         │             │ └────────┬─────────┘ │      │
│                         │             │          ▼           │      │
│                         │             │ ┌──────────────────┐ │      │
│                         │             │ │ human_approval   │ │      │
│                         │             │ │ (HITL interrupt) │ │      │
│                         │             │ └────────┬─────────┘ │      │
│                         │             │          ▼           │      │
│                         │             │ ┌──────┬─────┬────┐ │       │
│                         │             │ │ Jira │Email│Cal │ │       │
│                         │             │ │ Wrkr │Wrkr │Wrkr│ │       │
│                         │             │ └──┬───┴──┬──┴──┬─┘ │       │
│                         │             │    ▼      ▼     ▼   │       │
│                         │             │ ┌──────────────────┐ │      │
│                         │             │ │ synthesize       │ │      │
│                         │             │ └──────────────────┘ │      │
│                         │             └──────────┬───────────┘      │
│                         │                        │                  │
│  ┌──────────────────────┴────────────────────────┴──────────────┐   │
│  │                     External Services                        │   │
│  │  ┌───────────┐  ┌───────────┐  ┌──────────────┐              │   │
│  │  │ Jira API  │  │ Gmail API │  │ Calendar API │              │   │
│  │  └───────────┘  └───────────┘  └──────────────┘              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                     Data & Persistence                       │   │
│  │  ┌──────────────────┐  ┌──────────────────┐                  │   │
│  │  │ PostgreSQL       │  │ Redis            │                  │   │
│  │  │ - Transcripts    │  │ - Hot state      │                  │   │
│  │  │ - Action records │  │ - Celery broker  │                  │   │
│  │  │ - Audit logs     │  │ - Rate limiting  │                  │   │
│  │  │ - Checkpoints    │  │ - Checkpoints    │                  │   │
│  │  └──────────────────┘  └──────────────────┘                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                     Observability                            │   │
│  │  ┌────────────┐ ┌──────────┐ ┌───────────┐ ┌─────────────┐   │   │
│  │  │ Prometheus │ │ Grafana  │ │ LangSmith │ │ Structured  │   │   │
│  │  │ Metrics    │ │Dashboards│ │ Tracing   │ │ JSON Logs   │   │   │
│  │  └────────────┘ └──────────┘ └───────────┘ └─────────────┘   │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Agent Graph Topology (LangGraph StateGraph)

```
                        START
                          │
                          ▼
                ┌──────────────────┐
                │ parse_transcript │    LLM extracts action items
                └────────┬─────────┘    from raw transcript
                         │
                   ┌─────┴─────┐
                   ▼           ▼
             items found    no items ─────────────────┐
                   │                                  │
                   ▼                                  │
           ┌──────────────┐                           │
           │ plan_actions │    LLM determines         │
           └──────┬───────┘    execution order        │
                  │                                   │
                  ▼                                   │
          ┌───────────────┐                           │
          │human_approval │    interrupt() pauses     │
          │  (HITL gate)  │    graph for user review  │
          └───────┬───────┘                           │
                  │                                   │
            ┌─────┴─────┐                             │
            ▼           ▼                             │
         approved    rejected ─────────────────┐      │
            │                                  │      │
     ┌──────┼──────┐                           │      │
     ▼      ▼      ▼                           │      │
  ┌──────┐┌──────┐┌──────┐   Fan-out via       │      │
  │ Jira ││Email ││ Cal  │   Send API          │      │
  │Worker││Worker││Worker│   (parallel)        │      │
  └──┬───┘└──┬───┘└──┬───┘                     │      │
     │       │       │                         │      │
     └───────┼───────┘                         │      │
             ▼                                 ▼      ▼
        ┌───────────┐                     ┌───────────┐
        │synthesize │                     │synthesize │
        └─────┬─────┘                     └─────┬─────┘
              ▼                                 ▼
             END                               END
```

### ReAct Reasoning Loop

Each worker node follows a ReAct (Reasoning + Acting) pattern:

```
┌─────────────────────────────────────────────────┐
│                  ReAct Loop                     │
│                                                 │
│  REASON ──▶ What action items exist?            │
│     │       Which tool should I call?           │
│     │       What parameters are needed?         │
│     ▼                                           │
│  ACT ────▶ Call Jira / Gmail / Calendar API     │
│     │       with validated parameters           │
│     ▼                                           │
│  OBSERVE ─▶ Did the API call succeed?           │
│     │        Parse response, extract IDs        │
│     ▼                                           │
│  REASON ──▶ Are there more actions?             │
│     │       Should I retry (transient error)?   │
│     │       Should I fail (permanent error)?    │
│     └──────▶ Loop or Terminate                 │
└─────────────────────────────────────────────────┘
```

### Three-Layer Guardrail Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  LAYER 1: INPUT GUARDRAILS (before LLM)                          │
│                                                                  │
│  - Transcript validation (length: 10-100K chars, encoding)       │
│  - PII detection (SSN, credit cards, API keys) + redaction       │
│  - Prompt injection defense (pattern matching classifier)        │
│  - Rate limiting (10/min, 100/hr per user via Redis)             │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  LAYER 2: PROCESSING GUARDRAILS (during execution)               │
│                                                                  │
│  - Tool allowlists: jira_worker -> jira, email_worker -> gmail   │
│  - Parameter validation: domain allowlists, field limits         │
│  - Budget caps: max 10K tokens per session                       │
│  - Iteration limits: max 20 agent steps per transcript           │
│  - Scope limits: CREATE only (no update/delete operations)       │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  LAYER 3: OUTPUT GUARDRAILS (after LLM, before delivery)         │
│                                                                  │
│  - Schema validation: Pydantic models for all API payloads       │
│  - Content filtering: hallucination detection patterns           │
│  - PII scrubbing: regex redaction on generated text              │
│  - Confidence gating: items below 0.7 flagged for review         │
└──────────────────────────────────────────────────────────────────┘
```

### Async Processing Flow

```
Client              FastAPI             Celery              LangGraph
  |                    |                   |                     |
  |  POST /transcripts |                   |                     |
  |───────────────────>|                   |                     |
  |                    |  enqueue task     |                     |
  |                    |──────────────────>|                     |
  |  202 {id}          |                   |                     |
  |<───────────────────|                   |  run agent graph    |
  |                    |                   |────────────────────>|
  |  GET /status       |                   |                     |
  |───────────────────>|                   |    parse -> plan    |
  |  "processing"      |                   |      -> approve     |
  |<───────────────────|                   |                     |
  |                    |                   |  awaiting_approval  |
  |  GET /status       |                   |<────────────────────|
  |───────────────────>|                   |                     |
  |  "awaiting_        |                   |                     |
  |   approval"        |                   |                     |
  |<───────────────────|                   |                     |
  |                    |                   |                     |
  |  POST /approve     |                   |                     |
  |───────────────────>|  resume graph     |                     |
  |                    |──────────────────>|  execute workers    |
  |  "executing"       |                   |────────────────────>|
  |<───────────────────|                   |                     |
  |                    |                   |  Jira  ──┐          |
  |                    |                   |  Email ──┤ parallel |
  |                    |                   |  Cal   ──┘          |
  |                    |                   |       |             |
  |                    |                   |    synthesize       |
  |                    |                   |<────────────────────|
  |  GET /status       |                   |                     |
  |───────────────────>|                   |                     |
  |  "completed"       |                   |                     |
  |<───────────────────|                   |                     |
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Language** | Python 3.11+ | Primary language |
| **Agent Framework** | LangChain, LangGraph | Agent orchestration, state management |
| **LLM** | OpenAI GPT-4o | Action extraction, email generation, planning |
| **API Server** | FastAPI | Async REST API with auto-generated docs |
| **Task Queue** | Celery + Redis | Async transcript processing |
| **Database** | PostgreSQL | Transcripts, action records, audit logs |
| **Cache/State** | Redis | Hot state, rate limiting, Celery broker |
| **External APIs** | Jira REST API v3 | Ticket creation |
| | Gmail API | Email sending |
| | Google Calendar API | Event scheduling |
| **Monitoring** | Prometheus + Grafana | Metrics, dashboards, alerting |
| **Tracing** | LangSmith | LLM call traces, token costs |
| **Logging** | structlog | Structured JSON logging |
| **Testing** | pytest, DeepEval | Unit, integration, LLM evaluation |
| **Infrastructure** | Docker, Kubernetes | Containerization, orchestration |
| **CI/CD** | GitHub Actions | Automated lint, test, build, deploy |

---

## Prerequisites

- **Python 3.11+**
- **Docker & Docker Compose** (for infrastructure services)
- **OpenAI API key** ([platform.openai.com](https://platform.openai.com))
- **Jira API token** ([Atlassian API tokens](https://id.atlassian.com/manage-profile/security/api-tokens))
- **Google Cloud credentials** with Gmail and Calendar APIs enabled ([Google Cloud Console](https://console.cloud.google.com))

---

## Setup & Installation

### 1. Clone the Repository

```bash
git clone https://github.com/pratushMukherjee/meeting-action-agent.git
cd meeting-action-agent
```

### 2. Create a Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows
```

### 3. Install Dependencies

```bash
# Production dependencies
pip install .

# Development dependencies (includes pytest, ruff, mypy, deepeval)
pip install ".[dev]"
```

### 4. Start Infrastructure Services

```bash
# Start PostgreSQL, Redis, Prometheus, and Grafana via Docker
make docker-up
```

This starts:
| Service | Port | Description |
|---|---|---|
| PostgreSQL | 5432 | Primary database |
| Redis | 6379 | Cache, task broker, rate limiting |
| Prometheus | 9090 | Metrics collection |
| Grafana | 3000 | Dashboards (login: admin/admin) |

### 5. Run Database Migrations

```bash
make migrate
```

### 6. (Optional) Seed Sample Data

```bash
make seed
```

---

## Configuration

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

### Required Environment Variables

```env
# OpenAI — powers transcript parsing, email generation, action planning
OPENAI_API_KEY=sk-your-openai-api-key

# PostgreSQL — stores transcripts, actions, audit logs
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/meeting_agent

# Redis — Celery broker, rate limiting, agent state caching
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1

# Jira — ticket creation
JIRA_SERVER_URL=https://your-domain.atlassian.net
JIRA_USER_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-jira-api-token
JIRA_DEFAULT_PROJECT=MEET

# Google — Gmail and Calendar APIs
GOOGLE_CREDENTIALS_FILE=credentials/google_credentials.json
GOOGLE_TOKEN_FILE=credentials/google_token.json
```

### Optional Configuration

```env
# LangSmith tracing (recommended for development)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-api-key

# Application tuning
CONFIDENCE_THRESHOLD=0.7      # Minimum confidence for auto-execution
MAX_AGENT_STEPS=20             # Max ReAct loop iterations
MAX_TOKEN_BUDGET=10000         # Token budget cap per session
ALLOWED_EMAIL_DOMAINS=company.com,partner.com  # Email domain allowlist
```

### Google API Setup

1. Create a project in [Google Cloud Console](https://console.cloud.google.com)
2. Enable the **Gmail API** and **Google Calendar API**
3. Create OAuth 2.0 credentials (Desktop application type)
4. Download the credentials JSON to `credentials/google_credentials.json`
5. On first run, the app will open a browser for OAuth consent — the token is saved automatically

---

## Running the Application

### Start the API Server

```bash
make run
# → uvicorn running on http://localhost:8000
# → Swagger docs at http://localhost:8000/docs
```

### Start the Celery Worker (separate terminal)

```bash
make worker
# → Celery worker processing meeting_agent and notifications queues
```

### Submit a Transcript

```bash
curl -X POST http://localhost:8000/api/v1/transcripts \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "Alice: Welcome to the sprint planning. Bob, can you fix the login bug by Friday? Bob: Sure, I will handle it. Alice: Great. Lets schedule a follow-up next Tuesday at 2pm. Charlie, send a summary to stakeholders.",
    "participants": ["alice@company.com", "bob@company.com", "charlie@company.com"],
    "metadata": {
      "meeting_title": "Q1 Sprint Planning",
      "date": "2026-02-23"
    }
  }'
```

Response:
```json
{
  "transcript_id": "a1b2c3d4-...",
  "status": "processing",
  "message": "Transcript submitted for processing"
}
```

### Check Processing Status

```bash
curl http://localhost:8000/api/v1/transcripts/{transcript_id}
```

### Approve or Reject the Execution Plan

```bash
# Approve
curl -X POST http://localhost:8000/api/v1/transcripts/{transcript_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'

# Reject
curl -X POST http://localhost:8000/api/v1/transcripts/{transcript_id}/reject
```

### View Executed Actions

```bash
curl http://localhost:8000/api/v1/actions/{transcript_id}
```

---

## API Reference

| Method | Endpoint | Description | Status Codes |
|---|---|---|---|
| `POST` | `/api/v1/transcripts` | Submit a transcript for processing | 202, 422 |
| `GET` | `/api/v1/transcripts/{id}` | Get transcript status and results | 200, 404 |
| `GET` | `/api/v1/actions/{id}` | Get all actions for a transcript | 200, 404 |
| `POST` | `/api/v1/transcripts/{id}/approve` | Approve pending execution plan | 200, 409 |
| `POST` | `/api/v1/transcripts/{id}/reject` | Reject pending execution plan | 200, 409 |
| `GET` | `/api/v1/health` | Health check | 200 |
| `GET` | `/api/v1/health/ready` | Readiness check (dependencies) | 200 |
| `GET` | `/metrics` | Prometheus metrics endpoint | 200 |

---

## Project Structure

```
meeting-action-agent/
│
├── src/
│   ├── agent/                        # LangGraph agent core
│   │   ├── graph.py                  # StateGraph definition + compile()
│   │   ├── state.py                  # State schema, data models, reducers
│   │   ├── nodes/
│   │   │   ├── parse_transcript.py   # LLM-powered action item extraction
│   │   │   ├── plan_actions.py       # Execution order planning
│   │   │   ├── human_approval.py     # HITL interrupt gate
│   │   │   └── synthesize.py         # Result aggregation
│   │   ├── workers/
│   │   │   ├── jira_worker.py        # Jira ticket creation with retry
│   │   │   ├── email_worker.py       # Email generation + sending
│   │   │   └── calendar_worker.py    # Calendar event scheduling
│   │   └── edges/
│   │       └── routing.py            # Conditional edges + Send fan-out
│   │
│   ├── tools/                        # External API client wrappers
│   │   ├── jira.py                   # Jira REST API v3 (async, tenacity retry)
│   │   ├── gmail.py                  # Gmail API (OAuth2)
│   │   └── calendar.py              # Google Calendar API (OAuth2)
│   │
│   ├── guardrails/                   # Three-layer safety system
│   │   ├── input_validators.py       # PII detection, prompt injection defense
│   │   ├── output_validators.py      # Schema validation, content filtering
│   │   ├── tool_policies.py          # Tool allowlists, parameter limits
│   │   └── rate_limiter.py           # Redis-backed per-user rate limiting
│   │
│   ├── api/                          # FastAPI REST layer
│   │   ├── main.py                   # App factory, lifespan, middleware
│   │   ├── dependencies.py           # Dependency injection
│   │   └── v1/
│   │       ├── routes/               # Endpoint handlers
│   │       └── schemas/              # Pydantic request/response models
│   │
│   ├── tasks/                        # Celery async processing
│   │   ├── celery_app.py             # Celery configuration
│   │   ├── process_transcript.py     # Main agent execution task
│   │   └── notifications.py          # Status notifications
│   │
│   ├── db/                           # Database layer
│   │   ├── models.py                 # SQLAlchemy ORM (Transcript, Action, Audit)
│   │   ├── repository.py             # Data access patterns
│   │   ├── session.py                # Async session management
│   │   └── migrations/               # Alembic migrations
│   │
│   ├── core/                         # Cross-cutting concerns
│   │   ├── config.py                 # Pydantic Settings (env vars)
│   │   ├── exceptions.py             # Custom exception hierarchy
│   │   ├── logging.py                # Structured JSON logging (structlog)
│   │   └── metrics.py                # Prometheus metric definitions
│   │
│   └── prompts/                      # LLM prompt templates
│       ├── parse_transcript.txt      # Action item extraction (few-shot)
│       ├── plan_actions.txt          # Execution planning
│       ├── email_summary.txt         # Email generation
│       └── jira_description.txt      # Jira ticket formatting
│
├── tests/
│   ├── conftest.py                   # Shared fixtures
│   ├── unit/                         # Unit tests (mocked APIs)
│   ├── integration/                  # End-to-end graph + API tests
│   └── eval/                         # LLM evaluation suite
│       └── golden_datasets/          # Annotated transcripts
│
├── docker/                           # Containerization
│   ├── Dockerfile.api                # FastAPI multi-stage build
│   ├── Dockerfile.worker             # Celery worker image
│   ├── docker-compose.yml            # Full local dev stack (6 services)
│   └── docker-compose.test.yml       # Test environment
│
├── k8s/                              # Kubernetes manifests
│   ├── base/                         # Deployments, services, configmaps
│   └── overlays/                     # Staging / production overrides
│
├── monitoring/                       # Observability config
│   ├── prometheus.yml                # Scrape configuration
│   └── grafana/dashboards/           # Pre-built performance dashboard
│
├── scripts/                          # Utility scripts
├── .github/workflows/ci.yml          # CI pipeline (lint → test → build)
├── pyproject.toml                    # Dependencies + tool config
├── Makefile                          # Developer commands
└── project_plan.md                   # Detailed project plan
```

---

## Key Features

### Agent Orchestration
- **ReAct-style reasoning** — LLM plans which tools to invoke and in what order, observes results, and decides next steps
- **Supervisor-worker pattern** — Isolated workers for Jira, Email, and Calendar with independent error handling and retry logic
- **Parallel execution** — Independent actions fan out via LangGraph's `Send` API for concurrent execution
- **State checkpointing** — Persistent state via Redis (hot) and PostgreSQL (cold) enables crash recovery and HITL interrupts
- **Deterministic + LLM planning** — Simple plans use rule-based ordering; complex plans (5+ items) use LLM reasoning

### Guardrails & Safety
- **Input validation** — Transcript length/encoding checks, PII detection (SSN, credit cards, API keys) with automatic redaction, prompt injection defense via pattern matching
- **Processing controls** — Tool allowlists per worker role, parameter validation (email domain allowlists, attendee limits), token budget caps, max iteration limits
- **Output filtering** — Pydantic schema validation for all API payloads, hallucination detection patterns, PII scrubbing on LLM-generated content
- **Human-in-the-loop** — LangGraph `interrupt()` pauses the graph for user review before executing irreversible actions
- **Audit logging** — Every tool call (attempted + executed) logged with timestamp, parameters, result, and approval status

### Observability
- **Prometheus metrics** — Task success/failure/partial rates, duration histograms, tool call counts, LLM token usage, error rates by type, active session gauge, guardrail violations
- **Grafana dashboards** — Pre-built 8-panel dashboard: success rate, active sessions, p95 latency, error rate, tool calls by type, token usage, LLM latency percentiles, guardrail violations
- **Structured logging** — JSON logs with correlation IDs via structlog; console renderer for dev, JSON renderer for production
- **LangSmith tracing** — Full LLM call traces, tool invocations, token costs, latency breakdown per node

### Evaluation
- **Golden dataset** — 3 annotated meeting transcripts with 10 expected action items covering all 3 types
- **Unit tests** — 50 tests with mocked APIs covering transcript parsing, all 3 tool wrappers, guardrails (PII, injection, validation, access control)
- **Integration tests** — End-to-end graph execution and API endpoint tests
- **Quality metrics** — Action extraction F1, email quality (LLM-as-judge), Jira ticket completeness, task success rate

---

## Testing

```bash
# Run all tests
make test

# Unit tests only (~5s)
make test-unit

# Integration tests
make test-integration

# LLM evaluation suite
make test-eval

# Lint + type check
make lint

# Auto-format
make format
```

### Test Coverage

| Test Suite | Count | Covers |
|---|---|---|
| Transcript parsing | 5 | JSON extraction, markdown fences, invalid input, partial failures |
| Jira tool | 4 | Success, 400 errors, 500 retry behavior, client cleanup |
| Gmail tool | 3 | Success, CC recipients, API failures |
| Calendar tool | 4 | Success, default end time, conflict detection, API failures |
| Guardrails | 19 | PII detection (SSN, CC, API keys), prompt injection, redaction, tool access control, parameter limits, confidence filtering |
| Eval suite | 5 | Golden dataset format, action type coverage, quality rubrics |
| Integration | 8 | Graph execution, API endpoints, health checks |
| **Total** | **58** | |

---

## Deployment

### Docker (Local / Staging)

```bash
# Build images
make docker-build

# Start full stack (API + Worker + PostgreSQL + Redis + Prometheus + Grafana)
make docker-up

# Stop
make docker-down
```

### Kubernetes (Production)

```bash
# Apply base manifests
kubectl apply -k k8s/base/

# Or with environment-specific overlays
kubectl apply -k k8s/overlays/production/
```

Production deployment includes:
- **3 API pods** with health/readiness probes
- **5 worker pods** for concurrent transcript processing
- **Resource limits** (API: 1 CPU / 1Gi, Worker: 2 CPU / 2Gi)

### CI/CD Pipeline

The GitHub Actions pipeline runs on every push/PR to `main`:

```
Push → Lint (ruff + mypy) → Unit Tests (pytest + coverage) → Build Docker Images
```

---

## Monitoring & Observability

### Prometheus Metrics

| Metric | Type | Description |
|---|---|---|
| `agent_task_total` | Counter | Tasks by status (success/failure/partial) |
| `agent_task_duration_seconds` | Histogram | End-to-end execution time |
| `agent_tool_calls_total` | Counter | Tool calls by type (jira/email/calendar) |
| `agent_tool_errors_total` | Counter | Tool errors by type and error class |
| `agent_llm_tokens_total` | Counter | Token usage by model and direction |
| `agent_llm_latency_seconds` | Histogram | LLM call latency |
| `agent_active_sessions` | Gauge | Currently processing sessions |
| `agent_guardrail_violations_total` | Counter | Guardrail violations by type |

### Dashboards

Access Grafana at `http://localhost:3000` (admin/admin) with the pre-built **Meeting Action Agent Performance** dashboard.

---

## License

MIT
