from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tools._shared import ROOT, err


TICKET_DATA_FILE = ROOT / "helpdesk_data" / "tickets.json"
# Local ticket store (gitignored): tickets created by create_ticket and the latest
# confirmed updates of fixture tickets. It takes precedence over the read-only fixture.
LOCAL_TICKET_DIR = ROOT / "tickets"
TICKET_ID_PATTERN = re.compile(r"^(?:INC|LAB|TKT)-\w+$", re.IGNORECASE)


def _ticket_view(ticket: dict[str, Any], normalized_id: str, source: str) -> dict[str, Any]:
    return {
        "tool": "lookup_ticket_status",
        "found": True,
        "ticket_id": ticket.get("ticket_id", normalized_id),
        "status": ticket.get("status", "open"),
        "priority": ticket.get("priority", "medium"),
        "summary": ticket.get("summary", ""),
        "assigned_to": ticket.get("assigned_to", "Service Desk Queue"),
        "created_at": ticket.get("created_at"),
        "updated_at": ticket.get("updated_at", ticket.get("created_at")),
        "technical_notes": ticket.get("technical_notes", ""),
        "source": source,
    }


def lookup_ticket_status(ticket_id: str = "") -> dict[str, Any]:
    if not isinstance(ticket_id, str):
        return {"tool": "lookup_ticket_status", "error": "invalid_ticket_id_type"}

    normalized_id = ticket_id.strip().upper()
    if not normalized_id:
        return {"tool": "lookup_ticket_status", "error": "missing_ticket_id"}

    if not TICKET_ID_PATTERN.match(normalized_id):
        return {
            "tool": "lookup_ticket_status",
            "error": "invalid_ticket_id_format",
            "message": "Ticket ID must match format like INC-XXXX or LAB-XXXXXXXX",
        }

    try:
        # 1. Local ticket store first (created tickets and confirmed updates).
        ticket_file = LOCAL_TICKET_DIR / f"{normalized_id}.json"
        if ticket_file.exists():
            return _ticket_view(json.loads(ticket_file.read_text(encoding="utf-8")), normalized_id, "local_ticket_store")

        # 2. Read-only fixture in helpdesk_data/tickets.json.
        if TICKET_DATA_FILE.exists():
            data = json.loads(TICKET_DATA_FILE.read_text(encoding="utf-8"))
            for ticket in data.get("tickets", []):
                if ticket.get("ticket_id", "").upper() == normalized_id:
                    return _ticket_view(ticket, normalized_id, "helpdesk_data")

        return {
            "tool": "lookup_ticket_status",
            "found": False,
            "error": "ticket_not_found",
            "ticket_id": normalized_id,
            "message": f"No ticket found with ID {normalized_id}",
        }
    except Exception as exc:
        return err("lookup_ticket_status", exc)
