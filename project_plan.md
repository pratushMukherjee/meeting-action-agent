# Multi-Step Meeting Action Agent — Project Plan

## 1. Project Overview

### 1.1 Problem Statement

After meetings, participants waste significant time on manual follow-ups: creating Jira tickets for action items, sending summary emails, and scheduling follow-up meetings. These tasks are repetitive, error-prone, and often delayed or forgotten entirely.

### 1.2 Solution

An autonomous AI agent that ingests meeting transcripts, extracts action items using LLM reasoning, and orchestrates multi-step follow-up workflows — including Jira ticket creation, email summary dispatch, and calendar event scheduling — through coordinated API calls with built-in error recovery, guardrails, and human-in-the-loop approval.

### 1.3 Key Differentiators (Aligned with Zoom GenAI Role)

| Role Requirement | How This Project Demonstrates It |
|---|---|
| Agent architectures for reasoning, planning, executing | ReAct-style planning loop with LangGraph StateGraph |
| Tool orchestration frameworks | Coordinated Jira, Gmail, Calendar API calls via supervisor-worker pattern |
| Guardrails, safety layers, monitoring | Three-layer guardrail architecture + Prometheus observability |
| Evaluation frameworks and metrics | DeepEval unit tests + LangSmith tracing + production metrics |
| Scalable infrastructure | FastAPI + Celery + Redis + Docker + Kubernetes |
| Cross-functional agentic workflows | End-to-end pipeline from transcript to executed actions |

### 1.4 Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Agent Framework | LangChain, LangGraph |
| LLM Provider | OpenAI API (GPT-4o) |
| API Server | FastAPI |
| Task Queue | Celery + Redis (broker) |
| Database | PostgreSQL (persistence) + Redis (caching/state) |
| External APIs | Jira REST API, Google Calendar API, Gmail API |
| Containerization | Docker, Docker Compose |
| Orchestration | Kubernetes |
| Monitoring | Prometheus, Grafana |
| Evaluation | DeepEval, LangSmith |
| Cloud | AWS or GCP |

---

## 2. Architecture

### 2.1 High-Level Architecture Diagram

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────────────────┐
│   Client     │────▶│  FastAPI      │────▶│  Celery Task Queue          │
│  (UI/API)    │◀────│  (REST API)   │     │  (Redis Broker)             │
└─────────────┘     └──────────────┘     └────────────┬────────────────┘
                                                       │
                                                       ▼
                                          ┌────────────────────────┐
                                          │  LangGraph Agent Core  │
                                          │                        │
                                          │  ┌──────────────────┐  │
                                          │  │ parse_transcript  │  │
                                          │  └────────┬─────────┘  │
                                          │           ▼            │
                                          │  ┌──────────────────┐  │
                                          │  │  plan_actions    │  │
                                          │  └────────┬─────────┘  │
                                          │           ▼            │
                                          │  ┌──────────────────┐  │
                                          │  │ human_approval   │  │
                                          │  └────────┬─────────┘  │
                                          │           ▼            │
                                          │  ┌─────┬──────┬─────┐  │
                                          │  │Jira │Email │Cal  │  │
                                          │  │Wrkr │Wrkr  │Wrkr │  │
                                          │  └──┬──┴──┬───┴──┬──┘  │
                                          │     ▼     ▼      ▼     │
                                          │  ┌──────────────────┐  │
                                          │  │   synthesize     │  │
                                          │  └──────────────────┘  │
                                          └────────────┬───────────┘
                           ┌───────────────┬───────────┼────────────┐
                           ▼               ▼           ▼            ▼
                    ┌────────────┐  ┌───────────┐ ┌─────────┐ ┌──────────┐
                    │ Jira API   │  │ Gmail API │ │Cal API  │ │PostgreSQL│
                    └────────────┘  └───────────┘ └─────────┘ └──────────┘
```

### 2.2 Agent Pattern: Supervisor-Worker

The agent uses a **supervisor-worker architecture** built on LangGraph:

- **Supervisor**: Central orchestrator that receives parsed action items and delegates to specialized workers based on action type.
- **Workers**: Three isolated worker nodes (Jira, Email, Calendar), each with their own tool access, error handling, and retry logic.
- **Fan-out/Fan-in**: LangGraph's `Send` API enables parallel execution of independent workers, with results aggregated in the `synthesize` node.

### 2.3 ReAct-Style Reasoning Loop

```
┌──────────────────────────────────────────┐
│              ReAct Loop                  │
│                                          │
│  REASON ──▶ What action items exist?     │
│     │       Which tools are needed?      │
│     ▼                                    │
│  ACT ────▶ Call Jira/Gmail/Calendar API  │
│     │                                    │
│     ▼                                    │
│  OBSERVE ─▶ Did the API call succeed?    │
│     │        What's the result?          │
│     ▼                                    │
│  REASON ──▶ Are there more actions?      │
│     │       Should I retry or proceed?   │
│     └──────▶ Loop or Terminate           │
└──────────────────────────────────────────┘
```

### 2.4 LangGraph State Schema

```python
class MeetingAgentState(TypedDict):
    transcript: str                         # Raw meeting transcript
    parsed_items: list[ActionItem]          # Extracted action items
    execution_plan: list[PlannedTask]       # LLM-generated execution plan
    human_approved: bool                    # Whether plan was approved
    jira_results: Annotated[list, add]      # Created ticket IDs/URLs
    email_results: Annotated[list, add]     # Email send confirmations
    calendar_results: Annotated[list, add]  # Scheduled event IDs
    errors: Annotated[list, add]            # Failures during execution
    messages: Annotated[list, add]          # LangChain message history
    retry_count: int                        # Retry counter (max iterations)
```

### 2.5 Graph Topology

```
START
  │
  ▼
parse_transcript ──▶ plan_actions ──▶ human_approval
                                          │
                          ┌───────────────┼───────────────┐
                          ▼               ▼               ▼
                    jira_worker     email_worker    calendar_worker
                          │               │               │
                          └───────────────┼───────────────┘
                                          ▼
                                     synthesize
                                          │
                                          ▼
                                         END
```

**Conditional Edge Logic:**
- After `plan_actions`, route to workers based on action types present in the plan.
- After each worker, check if all planned tasks are complete; if not, route to next pending worker.
- Workers can execute in parallel via `Send` API when tasks are independent.

---

## 3. Component Design

### 3.1 Transcript Parser (`parse_transcript` node)

**Purpose:** Extract structured action items from raw meeting transcript text.

**Input:** Raw transcript string.

**Output:** List of `ActionItem` objects:
```python
class ActionItem(BaseModel):
    type: Literal["jira_ticket", "email_summary", "calendar_event"]
    title: str
    description: str
    assignee: Optional[str]
    priority: Optional[str]        # For Jira: high/medium/low
    due_date: Optional[str]        # ISO date
    recipients: Optional[list[str]]  # For email
    attendees: Optional[list[str]]   # For calendar
    meeting_time: Optional[str]      # For calendar scheduling
    confidence: float               # 0.0-1.0 extraction confidence
```

**LLM Prompt Strategy:** Structured output with JSON schema enforcement. Prompt includes few-shot examples of transcript → action item extraction.

### 3.2 Action Planner (`plan_actions` node)

**Purpose:** Take extracted action items and generate an ordered execution plan.

**Responsibilities:**
- Determine execution order (e.g., create Jira ticket before referencing its ID in the email summary).
- Identify dependencies between actions.
- Estimate which actions can run in parallel vs. sequentially.
- Validate that all required fields are present for each action.

### 3.3 Human Approval (`human_approval` node)

**Purpose:** Present the execution plan to the user for review before taking irreversible actions.

**Implementation:** Uses LangGraph's `interrupt()` function to pause graph execution. The user can:
- **Approve**: Continue execution as planned.
- **Edit**: Modify specific action items (change assignee, adjust priority).
- **Reject**: Cancel execution entirely.

**When approval is required:**
- Sending emails to external recipients.
- Creating high-priority Jira tickets.
- Scheduling meetings with 5+ attendees.

### 3.4 Worker Nodes

#### 3.4.1 Jira Worker

**Tool:** `JiraTool` wrapping Jira REST API v3.

**Operations:**
- `create_issue(project, summary, description, assignee, priority, labels)`
- Returns: issue key, URL, status.

**Error Recovery:**
- HTTP 429 (rate limit): Exponential backoff, max 3 retries.
- HTTP 400 (bad request): Log error, mark action as failed, continue.
- HTTP 500/503: Retry with backoff, max 3 retries, then fail gracefully.

#### 3.4.2 Email Worker

**Tool:** `GmailTool` wrapping Gmail API.

**Operations:**
- `send_email(to, subject, body, cc, reply_to)`
- Body is LLM-generated summary of the meeting, optionally referencing Jira tickets created.

**Guardrails:**
- Recipient domain allowlist validation.
- Max 20 recipients per email.
- Content filtering for PII leakage.

#### 3.4.3 Calendar Worker

**Tool:** `CalendarTool` wrapping Google Calendar API.

**Operations:**
- `create_event(summary, start_time, end_time, attendees, description, location)`
- Returns: event ID, calendar link.

**Guardrails:**
- Events cannot be scheduled more than 30 days out.
- Max 50 attendees per event.
- Must not conflict with existing events (check free/busy API).

### 3.5 Synthesizer (`synthesize` node)

**Purpose:** Aggregate all worker results into a final execution report.

**Output:**
```python
class ExecutionReport(BaseModel):
    transcript_id: str
    total_actions: int
    successful_actions: int
    failed_actions: int
    jira_tickets: list[dict]       # {key, url, status}
    emails_sent: list[dict]        # {to, subject, status}
    events_created: list[dict]     # {event_id, link, status}
    errors: list[dict]             # {action, error_type, message}
    execution_time_ms: int
```

---

## 4. API Design

### 4.1 REST Endpoints

```
POST   /api/v1/transcripts              # Submit a transcript for processing
GET    /api/v1/transcripts/{id}         # Get transcript status and results
GET    /api/v1/transcripts/{id}/actions # Get all actions for a transcript
POST   /api/v1/transcripts/{id}/approve # Approve pending execution plan
POST   /api/v1/transcripts/{id}/reject  # Reject pending execution plan
GET    /api/v1/health                   # Health check
GET    /api/v1/metrics                  # Prometheus metrics endpoint
```

### 4.2 Request/Response Examples

**Submit Transcript:**
```json
POST /api/v1/transcripts
{
  "transcript": "Meeting transcript text...",
  "meeting_id": "mtg_12345",
  "participants": ["alice@company.com", "bob@company.com"],
  "metadata": {
    "meeting_title": "Q1 Sprint Planning",
    "date": "2026-02-23"
  }
}

Response: 202 Accepted
{
  "transcript_id": "txn_abc123",
  "status": "processing",
  "estimated_completion": "2026-02-23T10:05:00Z"
}
```

### 4.3 Async Processing Flow

1. Client submits transcript via `POST /api/v1/transcripts`.
2. FastAPI validates input and enqueues a Celery task.
3. Returns `202 Accepted` with a `transcript_id` immediately.
4. Celery worker picks up the task and runs the LangGraph agent.
5. Client polls `GET /api/v1/transcripts/{id}` for status updates.
6. If human approval is required, status returns `awaiting_approval` with the proposed plan.
7. Client calls `POST /api/v1/transcripts/{id}/approve` to continue.
8. Final results are available via `GET /api/v1/transcripts/{id}/actions`.

---

## 5. Guardrails & Safety

### 5.1 Three-Layer Guardrail Architecture

```
┌─────────────────────────────────────────────┐
│  Layer 1: INPUT GUARDRAILS                  │
│  • Transcript validation (length, encoding) │
│  • PII detection and redaction              │
│  • Prompt injection defense                 │
│  • Rate limiting (per-user, per-session)    │
└──────────────────────┬──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│  Layer 2: PROCESSING GUARDRAILS             │
│  • Tool allowlists per worker role          │
│  • Parameter validation (schemas)           │
│  • Budget/cost caps (token usage)           │
│  • Max iteration limits (20 steps)          │
│  • Action scope limits (no deletes)         │
└──────────────────────┬──────────────────────┘
                       ▼
┌─────────────────────────────────────────────┐
│  Layer 3: OUTPUT GUARDRAILS                 │
│  • Schema validation (API payloads)         │
│  • Content filtering (hallucination check)  │
│  • PII scrubbing on generated text          │
│  • Confidence threshold gating              │
└─────────────────────────────────────────────┘
```

### 5.2 Safety-Critical Design Decisions

- **Default-deny**: No tool call executes unless it passes all validation. Fail closed.
- **Audit logging**: Every tool call (attempted + executed) logged to PostgreSQL with timestamp, user ID, tool name, parameters, result, and approval status.
- **Idempotency keys**: Generated for Jira/Calendar API calls to prevent duplicate creation on retry.
- **Rollback reporting**: If multi-step execution partially fails, the report clearly indicates which actions completed and which did not.
- **Action scope limits**: The agent can only CREATE resources. It cannot update, delete, or modify existing Jira tickets, calendar events, or emails.

---

## 6. State Persistence & Checkpointing

### 6.1 Dual-Store Strategy

| Store | Purpose | Use Case |
|---|---|---|
| Redis (`AsyncRedisSaver`) | Hot state | Active agent sessions, sub-ms read/write |
| PostgreSQL (`AsyncPostgresSaver`) | Cold state | Completed session history, audit trail |

### 6.2 Checkpointing Behavior

- LangGraph automatically checkpoints state after every node execution.
- If the agent crashes mid-execution, it resumes from the last checkpoint.
- `thread_id` serves as the persistent cursor for each transcript processing session.
- Checkpoints survive server restarts and enable human-in-the-loop interruptions.

---

## 7. Evaluation Framework

### 7.1 Metrics

**Task-Level Metrics (End-to-End):**

| Metric | Definition | Target |
|---|---|---|
| Task Success Rate | % of transcripts where all actions execute correctly | > 90% |
| Partial Success Rate | Fraction of planned actions completed per transcript | > 95% |
| End-to-End Latency | Time from transcript input to all actions completed | < 60s |
| Cost per Task | Total API token cost per transcript | < $0.50 |

**Trajectory-Level Metrics (Step-by-Step):**

| Metric | Definition | Target |
|---|---|---|
| Tool Selection Accuracy | Correct tool chosen for each action type | > 95% |
| Tool Parameter Accuracy | Correct parameters passed to each tool call | > 90% |
| Step Success Rate | % of individual steps that execute successfully | > 95% |
| Path Efficiency | Ratio of optimal steps to actual steps taken | > 0.8 |

**Quality Metrics (Output Content):**

| Metric | Definition | Target |
|---|---|---|
| Action Item Extraction F1 | Precision/recall vs. ground truth action items | > 0.85 |
| Email Summary Quality | LLM-judged coherence, completeness, tone (1-5) | > 4.0 |
| Jira Ticket Completeness | % of fields correctly populated | > 90% |

### 7.2 Evaluation Strategy

1. **Unit Tests (DeepEval):** Test each worker node in isolation with mocked API responses. Assert tool selection and parameter correctness.
2. **Integration Tests (LangSmith):** Run full graph execution against a golden dataset of 50-100 annotated transcripts. Measure Task Success Rate and Progress Rate.
3. **Production Monitoring (Prometheus):** Track latency, cost, error rate, and success rate in real-time. Alert on metric degradation.
4. **LLM-as-Judge:** Separate LLM call evaluates email summary quality and Jira ticket completeness against rubrics.

---

## 8. Infrastructure & Deployment

### 8.1 Local Development

```
docker-compose up
```
Services: FastAPI (port 8000), PostgreSQL (5432), Redis (6379), Celery worker, Prometheus (9090), Grafana (3000).

### 8.2 Production Deployment (Kubernetes)

```
┌──────────────────────────────────────┐
│           Kubernetes Cluster         │
│                                      │
│  ┌──────────┐  ┌──────────────────┐  │
│  │ FastAPI   │  │ Celery Workers   │  │
│  │ Pods (3)  │  │ Pods (5)         │  │
│  └────┬─────┘  └────────┬─────────┘  │
│       │                 │            │
│  ┌────▼─────────────────▼─────────┐  │
│  │     Redis (ElastiCache)        │  │
│  └────────────────────────────────┘  │
│                                      │
│  ┌────────────────────────────────┐  │
│  │   PostgreSQL (RDS)             │  │
│  └────────────────────────────────┘  │
│                                      │
│  ┌────────────────────────────────┐  │
│  │   Prometheus + Grafana         │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

### 8.3 CI/CD Pipeline

```
Push to main
  │
  ├──▶ Lint (ruff, mypy)
  ├──▶ Unit Tests (pytest + DeepEval)
  ├──▶ Integration Tests (docker-compose test environment)
  │
  ▼
Build Docker Images
  │
  ▼
Push to Container Registry (ECR/GCR)
  │
  ▼
Deploy to Staging (Kubernetes)
  │
  ├──▶ Smoke Tests
  ├──▶ Eval Suite (golden dataset)
  │
  ▼
Deploy to Production (Kubernetes, rolling update)
```

---

## 9. Observability

### 9.1 Monitoring Stack

| Component | Tool | Purpose |
|---|---|---|
| Metrics | Prometheus | Latency, throughput, error rates, token usage |
| Dashboards | Grafana | Visualize agent performance, API health |
| Tracing | LangSmith | LLM call traces, tool invocations, token costs |
| Logging | Structured JSON logs | Audit trail, debugging, error forensics |
| Alerting | Prometheus Alertmanager | SLA violations, error rate spikes |

### 9.2 Key Prometheus Metrics

```
agent_task_total{status="success|failure|partial"}        # Counter
agent_task_duration_seconds                                # Histogram
agent_tool_calls_total{tool="jira|email|calendar"}        # Counter
agent_tool_errors_total{tool, error_type}                 # Counter
agent_llm_tokens_total{model, type="input|output"}        # Counter
agent_llm_latency_seconds{model}                          # Histogram
agent_active_sessions                                     # Gauge
```

---

## 10. Project Directory Structure

```
meeting-action-agent/
│
├── docker/
│   ├── Dockerfile.api
│   ├── Dockerfile.worker
│   ├── docker-compose.yml
│   └── docker-compose.test.yml
│
├── k8s/
│   ├── base/
│   │   ├── deployment-api.yaml
│   │   ├── deployment-worker.yaml
│   │   ├── service.yaml
│   │   ├── configmap.yaml
│   │   └── kustomization.yaml
│   └── overlays/
│       ├── staging/
│       └── production/
│
├── src/
│   ├── __init__.py
│   │
│   ├── api/                          # FastAPI layer
│   │   ├── __init__.py
│   │   ├── main.py                   # App factory, lifespan
│   │   ├── dependencies.py           # Dependency injection
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── routes/
│   │       │   ├── transcripts.py    # Transcript CRUD + processing
│   │       │   ├── actions.py        # Action status queries
│   │       │   └── health.py         # Health checks
│   │       └── schemas/
│   │           ├── transcript.py     # Request/response models
│   │           └── action.py
│   │
│   ├── agent/                        # LangGraph agent core
│   │   ├── __init__.py
│   │   ├── graph.py                  # StateGraph definition + compile()
│   │   ├── state.py                  # State schema + reducer functions
│   │   ├── nodes/
│   │   │   ├── __init__.py
│   │   │   ├── parse_transcript.py   # Transcript → action items
│   │   │   ├── plan_actions.py       # Action planning + ordering
│   │   │   ├── human_approval.py     # HITL interrupt node
│   │   │   └── synthesize.py         # Result aggregation
│   │   ├── workers/
│   │   │   ├── __init__.py
│   │   │   ├── jira_worker.py        # Jira ticket creation
│   │   │   ├── email_worker.py       # Email dispatch
│   │   │   └── calendar_worker.py    # Calendar scheduling
│   │   └── edges/
│   │       ├── __init__.py
│   │       └── routing.py            # Conditional edge functions
│   │
│   ├── tools/                        # LangChain Tool definitions
│   │   ├── __init__.py
│   │   ├── jira.py                   # Jira REST API wrapper
│   │   ├── gmail.py                  # Gmail API wrapper
│   │   └── calendar.py              # Google Calendar API wrapper
│   │
│   ├── guardrails/                   # Safety & validation
│   │   ├── __init__.py
│   │   ├── input_validators.py       # Transcript validation, PII detection
│   │   ├── output_validators.py      # Schema validation, content filtering
│   │   ├── tool_policies.py          # Tool allowlists, param validation
│   │   └── rate_limiter.py           # Per-user rate limiting
│   │
│   ├── tasks/                        # Celery async tasks
│   │   ├── __init__.py
│   │   ├── celery_app.py             # Celery configuration
│   │   ├── process_transcript.py     # Main agent execution task
│   │   └── notifications.py          # Status update notifications
│   │
│   ├── db/                           # Database layer
│   │   ├── __init__.py
│   │   ├── models.py                 # SQLAlchemy ORM models
│   │   ├── repository.py             # Data access patterns
│   │   ├── session.py                # DB session management
│   │   └── migrations/
│   │       ├── env.py
│   │       └── versions/
│   │
│   ├── core/                         # Cross-cutting concerns
│   │   ├── __init__.py
│   │   ├── config.py                 # Pydantic Settings (env vars)
│   │   ├── logging.py                # Structured logging
│   │   ├── metrics.py                # Prometheus metric definitions
│   │   └── exceptions.py            # Custom exception hierarchy
│   │
│   └── prompts/                      # LLM prompt templates
│       ├── parse_transcript.txt
│       ├── plan_actions.txt
│       ├── email_summary.txt
│       └── jira_description.txt
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                   # Shared fixtures
│   ├── unit/
│   │   ├── test_parse_transcript.py
│   │   ├── test_jira_tool.py
│   │   ├── test_email_tool.py
│   │   ├── test_calendar_tool.py
│   │   └── test_guardrails.py
│   ├── integration/
│   │   ├── test_graph_execution.py
│   │   └── test_api_endpoints.py
│   └── eval/                         # LLM evaluation tests
│       ├── test_action_extraction.py
│       ├── test_email_quality.py
│       └── golden_datasets/
│           ├── transcripts.json
│           └── expected_actions.json
│
├── scripts/
│   ├── seed_db.py
│   └── run_eval.py
│
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/
│       └── dashboards/
│           └── agent-performance.json
│
├── .env.example
├── .gitignore
├── pyproject.toml
├── alembic.ini
├── Makefile
└── README.md
```

---

## 11. Implementation Phases

### Phase 1: Foundation (Week 1-2)

**Goal:** Project setup, core agent graph, transcript parsing.

| Task | Files | Description |
|---|---|---|
| Project scaffolding | `pyproject.toml`, `.env.example`, `.gitignore` | Initialize project with dependencies |
| Config management | `src/core/config.py` | Pydantic Settings for environment variables |
| Database setup | `src/db/models.py`, `src/db/session.py` | SQLAlchemy models, Alembic migrations |
| Agent state schema | `src/agent/state.py` | Define `MeetingAgentState` TypedDict |
| Transcript parser | `src/agent/nodes/parse_transcript.py` | LLM-powered action item extraction |
| Prompt templates | `src/prompts/parse_transcript.txt` | Few-shot prompts for extraction |
| Unit tests | `tests/unit/test_parse_transcript.py` | Test extraction against sample transcripts |

### Phase 2: Tool Integration (Week 3-4)

**Goal:** Build tool wrappers and worker nodes.

| Task | Files | Description |
|---|---|---|
| Jira tool | `src/tools/jira.py` | REST API wrapper with auth, error handling |
| Gmail tool | `src/tools/gmail.py` | OAuth2 + API wrapper for sending emails |
| Calendar tool | `src/tools/calendar.py` | Google Calendar API wrapper |
| Jira worker | `src/agent/workers/jira_worker.py` | LangGraph node with retry logic |
| Email worker | `src/agent/workers/email_worker.py` | LangGraph node with content generation |
| Calendar worker | `src/agent/workers/calendar_worker.py` | LangGraph node with conflict checking |
| Tool unit tests | `tests/unit/test_*_tool.py` | Mocked API tests for each tool |

### Phase 3: Agent Orchestration (Week 5-6)

**Goal:** Wire up the full LangGraph, implement planning and routing.

| Task | Files | Description |
|---|---|---|
| Action planner | `src/agent/nodes/plan_actions.py` | LLM-based execution planning |
| Graph definition | `src/agent/graph.py` | Full StateGraph with all nodes and edges |
| Conditional routing | `src/agent/edges/routing.py` | Route to workers based on action types |
| Synthesizer | `src/agent/nodes/synthesize.py` | Aggregate results into execution report |
| Human approval | `src/agent/nodes/human_approval.py` | `interrupt()` based HITL gate |
| Integration tests | `tests/integration/test_graph_execution.py` | End-to-end graph tests |

### Phase 4: API & Async Processing (Week 7-8)

**Goal:** Build the FastAPI server and Celery task queue.

| Task | Files | Description |
|---|---|---|
| FastAPI app | `src/api/main.py` | App factory with lifespan management |
| API routes | `src/api/v1/routes/*.py` | REST endpoints for transcript processing |
| Request schemas | `src/api/v1/schemas/*.py` | Pydantic models for validation |
| Celery config | `src/tasks/celery_app.py` | Redis broker, result backend |
| Processing task | `src/tasks/process_transcript.py` | Async agent execution task |
| API tests | `tests/integration/test_api_endpoints.py` | Endpoint integration tests |

### Phase 5: Guardrails & Safety (Week 9)

**Goal:** Implement three-layer guardrail architecture.

| Task | Files | Description |
|---|---|---|
| Input validators | `src/guardrails/input_validators.py` | PII detection, injection defense |
| Output validators | `src/guardrails/output_validators.py` | Schema validation, content filtering |
| Tool policies | `src/guardrails/tool_policies.py` | Allowlists, parameter validation |
| Rate limiter | `src/guardrails/rate_limiter.py` | Redis-backed per-user limits |
| Guardrail tests | `tests/unit/test_guardrails.py` | Validation logic unit tests |

### Phase 6: Observability & Evaluation (Week 10)

**Goal:** Production monitoring and evaluation pipeline.

| Task | Files | Description |
|---|---|---|
| Prometheus metrics | `src/core/metrics.py` | Define and expose custom metrics |
| Structured logging | `src/core/logging.py` | JSON logging with correlation IDs |
| Grafana dashboards | `monitoring/grafana/dashboards/` | Agent performance dashboards |
| Eval suite | `tests/eval/test_action_extraction.py` | DeepEval tests against golden dataset |
| Golden dataset | `tests/eval/golden_datasets/` | Annotated transcripts with expected outputs |

### Phase 7: Containerization & Deployment (Week 11-12)

**Goal:** Docker, Kubernetes, and CI/CD.

| Task | Files | Description |
|---|---|---|
| Dockerfiles | `docker/Dockerfile.api`, `docker/Dockerfile.worker` | Multi-stage builds |
| Docker Compose | `docker/docker-compose.yml` | Local dev environment |
| K8s manifests | `k8s/base/*.yaml` | Deployments, services, configmaps |
| Kustomize overlays | `k8s/overlays/` | Staging and production configs |
| CI/CD pipeline | `.github/workflows/ci.yml` | Lint, test, build, deploy |
| Makefile | `Makefile` | Common dev commands |

---

## 12. Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Agent framework | LangGraph (not raw LangChain agents) | Explicit graph topology, state checkpointing, HITL support |
| Agent pattern | Supervisor-Worker | Isolated workers for testability, parallel execution |
| Async execution | Celery + Redis | Decouple HTTP request lifecycle from long-running agent |
| Hot state | Redis (`AsyncRedisSaver`) | Sub-millisecond read/write for active sessions |
| Cold state | PostgreSQL (`AsyncPostgresSaver`) | Durable audit trail, query-friendly |
| Prompt storage | Text files in `src/prompts/` | Version-controlled, reviewable, hot-reloadable |
| Guardrails | Custom middleware (not NeMo) | Lightweight, no DSL overhead, integrated with LangGraph |
| Evaluation | DeepEval + LangSmith + Prometheus | Three-tier: unit eval, integration tracing, production monitoring |
| API style | REST with async polling | Simple, stateless, works with any client |

---

## 13. Risk Mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| LLM hallucination in action extraction | Wrong tickets/emails created | Confidence thresholds + human approval for high-stakes actions |
| API rate limits (Jira, Google) | Delayed or failed execution | Exponential backoff, rate limit tracking, graceful degradation |
| Partial execution failure | Incomplete follow-ups | Checkpoint-based recovery, clear status reporting |
| Token cost explosion | Budget overrun | Per-session cost caps, token usage monitoring, alerts |
| Prompt injection via transcript | Agent hijacking | Input sanitization, prompt injection classifier |
| Data privacy (PII in transcripts) | Compliance violation | PII detection/redaction before LLM processing |

---

## 14. Resume Bullet Points

> - Built an AI agent using LLMs to autonomously process meeting transcripts, extract action items, and execute multi-step follow-ups including Jira ticket creation, email summaries, and calendar scheduling via API orchestration.
> - Implemented a ReAct-style reasoning and planning loop enabling the agent to decompose complex tasks, select appropriate tools, and recover gracefully from API failures with retry and fallback mechanisms.
> - Designed evaluation framework to measure agent reliability, task completion rate, and end-to-end latency, achieving consistent performance across diverse meeting formats and workflow scenarios.
