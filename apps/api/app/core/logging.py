"""Structured logging configuration."""

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    from app.core.masking import MaskingLogFilter

    mask_filter = MaskingLogFilter()
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(mask_filter)

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d) - %(message)s",
        handlers=[handler],
        force=True,
    )

    root_logger = logging.getLogger()
    if not any(isinstance(f, MaskingLogFilter) for f in root_logger.filters):
        root_logger.addFilter(mask_filter)

    app_logger = logging.getLogger("ghost-user")
    if not any(isinstance(f, MaskingLogFilter) for f in app_logger.filters):
        app_logger.addFilter(mask_filter)


logger = logging.getLogger("ghost-user")
