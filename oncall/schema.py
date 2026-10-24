"""Every field name of the diagnosis report lives here and nowhere else.

The organisers' JSON schema arrives later. When it does, rename the string values below (and
adjust REPORT_FIELDS / EVIDENCE_FIELDS if the shape differs). The rest of the code only refers to
these constants.
"""

# --- report (written to report.json) -----------------------------------------------------------
INCIDENT_ID = "incident_id"
STARTED_AT = "started_at"
TRIGGER = "trigger"
STATUS = "status"
COMPONENT = "component"
CAUSE = "cause"
CONFIDENCE = "confidence"
STATED_CONFIDENCE = "stated_confidence"
CONFIDENCE_REASONS = "confidence_reasons"
EVIDENCE = "evidence"
ALTERNATIVES = "alternatives_considered"
STEPS = "investigation_steps"
LIMITATIONS = "limitations"
ESCALATION_REASON = "escalation_reason"
WARNINGS = "warnings"

REPORT_FIELDS = (INCIDENT_ID, STARTED_AT, TRIGGER, STATUS, COMPONENT, CAUSE, CONFIDENCE, STATED_CONFIDENCE,
                 CONFIDENCE_REASONS, EVIDENCE, ALTERNATIVES, STEPS, LIMITATIONS, ESCALATION_REASON, WARNINGS)

STATUS_DIAGNOSED = "diagnosed"
STATUS_ESCALATED = "escalated"

# --- one evidence item inside the report -------------------------------------------------------
EV_LEDGER_ID = "ledger_id"
EV_KIND = "kind"
EV_CLAIM = "claim"
EV_QUOTE = "quote"
EV_VALUE = "value"
EV_VALIDATED = "validated"
EV_NOTE = "validation_note"

EVIDENCE_FIELDS = (EV_LEDGER_ID, EV_KIND, EV_CLAIM, EV_QUOTE, EV_VALUE, EV_VALIDATED, EV_NOTE)

# --- one alternative inside the report ---------------------------------------------------------
ALT_HYPOTHESIS = "hypothesis"
ALT_WHY_REJECTED = "why_rejected"

# --- fields read from the files the agent already writes ---------------------------------------
# (candidate.json uses the report names above; run_info.json uses these)
RUN_INCIDENT_ID = "incident_id"
RUN_STARTED_AT = "started_at"
RUN_TRIGGER = "trigger"
RUN_BUDGET_EXHAUSTED = "budget_exhausted"
RUN_LLM_ERROR = "llm_error"
RUN_STOP_REASON = "stop_reason"

# --- file names inside a run folder ------------------------------------------------------------
LEDGER_FILE = "ledger.json"
CANDIDATE_FILE = "candidate.json"
RUN_INFO_FILE = "run_info.json"
REPORT_JSON_FILE = "report.json"
REPORT_MD_FILE = "report.md"

# The component value the agent uses for "I could not tell".
UNKNOWN_COMPONENT = "unknown"
