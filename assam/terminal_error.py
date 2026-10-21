"""Expected guest-facing terminal operation errors."""

from __future__ import annotations


class TerminalOperationError(ValueError):
    """Raised for invalid operations requested of the terminal bus."""
