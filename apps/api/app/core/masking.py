"""API-side masking engine, response redaction, and logging filters."""

import logging
from typing import Any, Dict, List, Optional
from packages.shared.masking import (
    MASK_STRING,
    mask_sensitive_data,
    mask_secrets_in_dict,
    mask_text,
    is_sensitive_key,
)


class MaskingLogFilter(logging.Filter):
    """Logging filter that ensures sensitive tokens and passwords are redacted from application logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_text(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = mask_sensitive_data(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    mask_text(a) if isinstance(a, str) else a
                    for a in record.args
                )
        return True


def mask_dict_response(data: dict, secrets: Optional[List[str]] = None) -> dict:
    """Masks a dictionary response before JSON serialization."""
    return mask_sensitive_data(data, secrets=secrets)


__all__ = [
    "MASK_STRING",
    "mask_sensitive_data",
    "mask_secrets_in_dict",
    "mask_text",
    "is_sensitive_key",
    "MaskingLogFilter",
    "mask_dict_response",
]
