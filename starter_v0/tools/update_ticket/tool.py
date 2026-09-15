from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools._shared import ROOT, err


TICKET_DATA_FILE = ROOT / "helpdesk_data" / "tickets.json"
LOCAL_TICKET_DIR = ROOT / "tickets"
TICKET_ID_PATTERN = re.compile(r"^(?:INC|LAB|TKT)-\w+$", re.IGNORECASE)
SENSITIVE_DATA_PATTERN = re.compile(
    r"\b(?:password|passwd|token|api[ _-]?key|mfa|otp|recovery[ _-]?code)(?:\s*[:=]\s*|\s+(?:is|la|là)\s+)\S+",
    re.IGNORECASE,
)

VALID_PRIORITIES = {"low", "medium", "high", "critical"}
VALID_STATUSES = {"open", "in_progress", "pending_user", "resolved", "closed"}


def update_ticket(
    ticket_id: str = "",
    priority: str | None = None,
    status: str | None = None,
    note: str | None = None,
    confirmed: bool = False,
) -> dict[str, Any]:
    if not isinstance(ticket_id, str):
        return {"tool": "update_ticket", "error": "invalid_ticket_id_type"}
    
    normalized_id = ticket_id.strip().upper()
    if not normalized_id:
        return {"tool": "update_ticket", "error": "missing_ticket_id"}

    if not TICKET_ID_PATTERN.match(normalized_id):
        return {"tool": "update_ticket", "error": "invalid_ticket_id_format"}

    normalized_priority = priority.strip().lower() if isinstance(priority, str) and priority.strip() else None
    if normalized_priority and normalized_priority not in VALID_PRIORITIES:
        return {"tool": "update_ticket", "error": "invalid_priority", "priority": normalized_priority}

    normalized_status = status.strip().lower() if isinstance(status, str) and status.strip() else None
    if normalized_status and normalized_status not in VALID_STATUSES:
        return {"tool": "update_ticket", "error": "invalid_status", "status": normalized_status}

    normalized_note = note.strip() if isinstance(note, str) and note.strip() else None
    if normalized_note and SENSITIVE_DATA_PATTERN.search(normalized_note):
        return {
            "tool": "update_ticket",
            "error": "restricted_sensitive_data",
            "message": "Remove credentials, tokens, MFA values, and recovery codes from the note.",
        }

    if not normalized_priority and not normalized_status and not normalized_note:
        return {"tool": "update_ticket", "error": "no_update_fields_provided"}

    # Guardrail: explicit confirmation required
    if confirmed is not True:
        return {
            "tool": "update_ticket",
            "status": "needs_confirmation",
            "ticket_id": normalized_id,
            "proposed_changes": {
                "priority": normalized_priority,
                "status": normalized_status,
                "note": normalized_note,
            },
            "message": "Update the ticket only after explicit user confirmation.",
        }

    try:
        now_iso = datetime.now(timezone.utc).isoformat()

        # Base record: local ticket store first (created tickets / earlier updates),
        # otherwise the read-only fixture. The fixture file is never modified.
        ticket_file = LOCAL_TICKET_DIR / f"{normalized_id}.json"
        ticket: dict[str, Any] | None = None
        if ticket_file.exists():
            ticket = json.loads(ticket_file.read_text(encoding="utf-8"))
        elif TICKET_DATA_FILE.exists():
            data = json.loads(TICKET_DATA_FILE.read_text(encoding="utf-8"))
            ticket = next((dict(t) for t in data.get("tickets", []) if t.get("ticket_id", "").upper() == normalized_id), None)

        if ticket is None:
            return {
                "tool": "update_ticket",
                "error": "ticket_not_found",
                "ticket_id": normalized_id,
                "message": f"No ticket found with ID {normalized_id}",
            }

        before = dict(ticket)
        if normalized_priority:
            ticket["priority"] = normalized_priority
        if normalized_status:
            ticket["status"] = normalized_status
        if normalized_note:
            old_notes = ticket.get("technical_notes", "")
            ticket["technical_notes"] = f"{old_notes} | {normalized_note}" if old_notes else normalized_note
        ticket["updated_at"] = now_iso

        LOCAL_TICKET_DIR.mkdir(parents=True, exist_ok=True)
        ticket_file.write_text(json.dumps(ticket, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "tool": "update_ticket",
            "status": "updated",
            "ticket_id": normalized_id,
            "before": before,
            "after": ticket,
            "path": str(ticket_file),
        }
    except Exception as exc:
        return err("update_ticket", exc)
