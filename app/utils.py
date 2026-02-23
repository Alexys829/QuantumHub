from __future__ import annotations

from datetime import datetime


def format_rate(bytes_per_sec: float) -> str:
    """Format bytes/s as KB/s or MB/s with auto-scaling."""
    kb = bytes_per_sec / 1024
    if kb >= 1024:
        return f"{kb / 1024:.1f} MB/s"
    return f"{kb:.1f} KB/s"


def format_docker_datetime(iso_str: str) -> str:
    """Convert Docker ISO 8601 datetime to DD/MM/YYYY HH:MM:SS.

    Handles formats like:
        2024-01-15T10:30:45.123456789Z
        2024-01-15T10:30:45.123456Z
        2024-01-15T10:30:45Z
        2024-01-15T10:30:45+00:00
    """
    if not iso_str:
        return ""
    try:
        cleaned = iso_str.rstrip("Z")
        # Truncate nanoseconds to microseconds (Python max precision)
        if "." in cleaned:
            base, frac = cleaned.split(".", 1)
            # Remove timezone offset from fraction if present
            tz_part = ""
            for sep in ("+", "-"):
                if sep in frac[1:]:  # skip first char (could be sign)
                    idx = frac.index(sep, 1)
                    tz_part = frac[idx:]
                    frac = frac[:idx]
                    break
            frac = frac[:6]
            cleaned = f"{base}.{frac}"
        else:
            # Handle +00:00 timezone
            for sep in ("+",):
                if sep in cleaned[11:]:
                    cleaned = cleaned[: cleaned.index(sep, 11)]
                    break
            if cleaned.count("-") > 2:
                # Has timezone like 2024-01-15T10:30:45-05:00
                parts = cleaned.rsplit("-", 1)
                if ":" in parts[-1] and "T" not in parts[-1]:
                    cleaned = parts[0]

        dt = datetime.fromisoformat(cleaned)
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except (ValueError, IndexError):
        return iso_str
