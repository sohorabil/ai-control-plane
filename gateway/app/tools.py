TICKETS = {
    "T-1001": {"id": "T-1001", "status": "open", "subject": "Cannot reset password"},
    "T-1002": {"id": "T-1002", "status": "resolved", "subject": "Invoice PDF missing"},
    "T-1003": {"id": "T-1003", "status": "pending", "subject": "API key not working"},
}

GET_TICKET_SCHEMA = {
    "name": "get_ticket",
    "description": "Look up a support ticket by its ID.",
    "input_schema": {
        "type": "object",
        "properties": {
            "ticket_id": {"type": "string", "description": "e.g. T-1001"},
        },
        "required": ["ticket_id"],
    },
}


def get_ticket(ticket_id: str) -> dict:
    return TICKETS.get(ticket_id, {"error": f"no ticket found with id {ticket_id}"})
