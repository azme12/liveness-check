"""ComplyCube-compatible webhook event catalog for Trustanova."""

from __future__ import annotations

WEBHOOK_EVENT_TYPES: list[dict[str, str]] = [
    {"value": "workflow.session.started", "description": "A workflow session has been started.", "resource_type": "sessions"},
    {"value": "workflow.session.cancelled", "description": "A workflow session has been cancelled.", "resource_type": "sessions"},
    {"value": "workflow.session.processing", "description": "The customer finished steps; checks are in progress.", "resource_type": "sessions"},
    {"value": "workflow.session.completed", "description": "A workflow session has been completed.", "resource_type": "sessions"},
    {"value": "workflow.session.updated", "description": "A workflow session outcome has been updated.", "resource_type": "sessions"},
    {"value": "workflow.session.abandoned", "description": "A workflow session was abandoned.", "resource_type": "sessions"},
    {"value": "check.pending", "description": "A check has been created and is in pending state.", "resource_type": "checks"},
    {"value": "check.completed", "description": "A check has completed with any outcome.", "resource_type": "checks"},
    {"value": "check.completed.clear", "description": "A check has completed with clear outcome.", "resource_type": "checks"},
    {"value": "check.completed.attention", "description": "A check has completed with attention outcome.", "resource_type": "checks"},
    {"value": "check.completed.rejected", "description": "A check has completed with rejected outcome.", "resource_type": "checks"},
    {"value": "check.completed.match_confirmed", "description": "A check has completed with match_confirmed outcome.", "resource_type": "checks"},
    {"value": "check.monitoring.attention", "description": "A monitoring check has completed with attention outcome.", "resource_type": "checks"},
    {"value": "check.failed", "description": "A check has failed.", "resource_type": "checks"},
    {"value": "check.updated", "description": "A check has been updated.", "resource_type": "checks"},
    {"value": "client.created", "description": "A client has been created.", "resource_type": "clients"},
    {"value": "client.updated", "description": "A client has been updated.", "resource_type": "clients"},
    {"value": "client.deleted", "description": "A client has been deleted.", "resource_type": "clients"},
    {"value": "document.created", "description": "A document has been created.", "resource_type": "documents"},
    {"value": "document.updated", "description": "A document has been updated.", "resource_type": "documents"},
    {"value": "document.updated.image_uploaded", "description": "A document image has been uploaded.", "resource_type": "documents"},
    {"value": "document.updated.image_deleted", "description": "A document image has been deleted.", "resource_type": "documents"},
    {"value": "document.deleted", "description": "A document has been deleted.", "resource_type": "documents"},
    {"value": "address.created", "description": "An address has been created.", "resource_type": "addresses"},
    {"value": "address.updated", "description": "An address has been updated.", "resource_type": "addresses"},
    {"value": "address.deleted", "description": "An address has been deleted.", "resource_type": "addresses"},
    {"value": "*", "description": "Subscribe to all events.", "resource_type": "*"},
]

ALLOWED_EVENT_VALUES = {e["value"] for e in WEBHOOK_EVENT_TYPES}

# Seconds to wait after a failed attempt before the next try (attempt index 1..9).
# First delivery is immediate (attempt 1). Then: 60, 120, 480, ... exponential-ish.
RETRY_DELAYS_SECONDS = [60, 120, 480, 960, 1920, 3840, 7680, 15360, 30720]
MAX_ATTEMPTS = 10


def resource_type_for_event(event_type: str) -> str:
    for item in WEBHOOK_EVENT_TYPES:
        if item["value"] == event_type:
            return item["resource_type"]
    if event_type.startswith("workflow.session"):
        return "sessions"
    if event_type.startswith("check"):
        return "checks"
    if event_type.startswith("client"):
        return "clients"
    if event_type.startswith("document"):
        return "documents"
    if event_type.startswith("address"):
        return "addresses"
    return "unknown"


def validate_events(events: list[str]) -> list[str]:
    if not events:
        raise ValueError("Select at least one event")
    unknown = [e for e in events if e not in ALLOWED_EVENT_VALUES]
    if unknown:
        raise ValueError(f"Unknown event type(s): {', '.join(unknown)}")
    if "*" in events:
        return ["*"]
    return list(dict.fromkeys(events))
