from prometheus_client import Counter, Gauge, Histogram

# Task-level metrics
TASK_TOTAL = Counter(
    "agent_task_total",
    "Total number of agent tasks",
    ["status"],  # success, failure, partial
)

TASK_DURATION = Histogram(
    "agent_task_duration_seconds",
    "Duration of agent task execution",
    buckets=[1, 5, 10, 30, 60, 120, 300],
)

# Tool-level metrics
TOOL_CALLS_TOTAL = Counter(
    "agent_tool_calls_total",
    "Total number of tool calls",
    ["tool"],  # jira, email, calendar
)

TOOL_ERRORS_TOTAL = Counter(
    "agent_tool_errors_total",
    "Total number of tool call errors",
    ["tool", "error_type"],
)

# LLM metrics
LLM_TOKENS_TOTAL = Counter(
    "agent_llm_tokens_total",
    "Total LLM tokens used",
    ["model", "type"],  # type: input, output
)

LLM_LATENCY = Histogram(
    "agent_llm_latency_seconds",
    "LLM call latency",
    ["model"],
    buckets=[0.5, 1, 2, 5, 10, 30],
)

# Session metrics
ACTIVE_SESSIONS = Gauge(
    "agent_active_sessions",
    "Number of currently active agent sessions",
)

# Guardrail metrics
GUARDRAIL_VIOLATIONS = Counter(
    "agent_guardrail_violations_total",
    "Total guardrail violations",
    ["guardrail_type"],
)
