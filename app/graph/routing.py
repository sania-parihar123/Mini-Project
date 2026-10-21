"""ProcessFoundry AI: Graph Routing Logic."""
from typing import Dict, Any
from app.graph.state import ProcessFoundryState

def check_critical_gaps_router(state: ProcessFoundryState) -> str:
    """Explicit deterministic Python routing rule per Part 3.5.
    
    Checks if there are unresolved critical questions (conflicting_rules or missing_actor).
    If yes, pauses the graph for human intervention.
    """
    issues = state.get("issues", [])
    has_open_critical = any(
        iss.get("status") == "open" and iss.get("kind") in ("conflicting_rules", "missing_actor")
        for iss in issues
    )

    if has_open_critical:
        return "pause_for_human"
    return "proceed_to_redesign"

def quality_repair_router(state: ProcessFoundryState) -> str:
    """Route after quality check: bounded repair attempts (at most 2)."""
    errors = state.get("validation_errors", [])
    retry_count = state.get("retry_count", 0)

    if not errors:
        return "complete"

    if retry_count < 2:
        return "repair_and_retry"

    return "mark_needs_review"
