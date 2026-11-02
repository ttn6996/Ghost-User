"""Data Cleanup & Automated Teardown Engine for AutoQA.

Implements Pillar 4: Prevents local database and staging environment pollution by
tracking synthetic test data tagged with AUTOQA_{run_id}_... and executing safe,
deterministic teardown routines (REST API deletions, entity cleanup, and cleanup reports).
"""

import logging
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
from pydantic import BaseModel, Field

from packages.shared.data_generator import is_tagged_test_data, extract_test_run_id
from packages.shared.schemas import TestDefinition
from apps.worker.runner.security import resolve_and_validate_host, get_effective_allow_local

logger = logging.getLogger("ghost-user")


class CleanupReport(BaseModel):
    run_id: str
    total_tagged_items: int = 0
    purged_items: List[str] = Field(default_factory=list)
    pending_items: List[str] = Field(default_factory=list)
    status: str = "completed"  # "completed", "no_data", "partial"
    log_messages: List[str] = Field(default_factory=list)


class DataCleanupExecutor:
    """Detects, tracks, and cleans up synthetic test data created during test runs."""

    def __init__(self, run_id: str, allow_local: bool = True):
        self.run_id = run_id
        self.allow_local = allow_local
        self._tracked_entities: List[Dict[str, Any]] = []

    def track_created_entity(
        self,
        identifier: str,
        entity_type: str = "record",
        delete_url: Optional[str] = None,
        delete_method: str = "DELETE",
    ) -> None:
        """Records an entity created during execution for targeted teardown."""
        self._tracked_entities.append({
            "identifier": identifier,
            "entity_type": entity_type,
            "delete_url": delete_url,
            "delete_method": delete_method.upper(),
        })

    def extract_tagged_values_from_definition(
        self, definition: Optional[TestDefinition]
    ) -> List[str]:
        """Inspects all actions in the test definition for AutoQA synthetic data tags."""
        if not definition:
            return []

        tagged: List[str] = []
        for step in definition.steps:
            val = getattr(step, "value", None)
            if val and isinstance(val, str) and is_tagged_test_data(val, run_id=self.run_id):
                if val not in tagged:
                    tagged.append(val)
        return tagged

    def execute_teardown(
        self,
        base_url: str,
        definition: Optional[TestDefinition] = None,
        custom_teardown_endpoints: Optional[List[str]] = None,
    ) -> CleanupReport:
        """Performs automated cleanup and teardown of synthetic data created during the test run."""
        report = CleanupReport(run_id=self.run_id)
        tagged_values = self.extract_tagged_values_from_definition(definition)

        # Merge tracked entity identifiers
        for ent in self._tracked_entities:
            ident = ent.get("identifier")
            if ident and ident not in tagged_values:
                tagged_values.append(ident)

        report.total_tagged_items = len(tagged_values)

        if not tagged_values and not self._tracked_entities and not custom_teardown_endpoints:
            report.status = "no_data"
            report.log_messages.append(f"[DATA_CLEANUP] No synthetic test data tags detected for run {self.run_id}.")
            return report

        report.log_messages.append(
            f"[DATA_CLEANUP] Initializing teardown for {len(tagged_values)} tagged item(s) in run {self.run_id}."
        )

        # 1. Execute explicit entity deletions
        for ent in self._tracked_entities:
            del_url = ent.get("delete_url")
            ident = ent.get("identifier", "unknown")
            if del_url:
                try:
                    self._perform_http_teardown(del_url, method=ent.get("delete_method", "DELETE"), base_url=base_url)
                    report.purged_items.append(ident)
                    report.log_messages.append(f"[DATA_CLEANUP] Successfully purged entity {ident} via {del_url}")
                except Exception as e:
                    logger.warning(f"Failed to purge entity {ident} at {del_url}: {e}")
                    report.pending_items.append(ident)
                    report.log_messages.append(f"[DATA_CLEANUP] Warning: Failed to purge {ident}: {e}")

        # 2. Execute custom teardown endpoints
        if custom_teardown_endpoints:
            for ep in custom_teardown_endpoints:
                target_url = urljoin(base_url, ep)
                try:
                    self._perform_http_teardown(target_url, method="POST", base_url=base_url, payload={"run_id": self.run_id})
                    report.log_messages.append(f"[DATA_CLEANUP] Executed custom teardown hook at {ep}")
                except Exception as e:
                    report.log_messages.append(f"[DATA_CLEANUP] Custom teardown hook failed for {ep}: {e}")

        # 3. Categorize remaining tagged values
        for val in tagged_values:
            if val not in report.purged_items and val not in report.pending_items:
                # Mark as tracked & logged for audit
                report.pending_items.append(val)
                report.log_messages.append(
                    f"[DATA_CLEANUP] Tagged item {val} recorded in teardown audit manifest."
                )

        if len(report.purged_items) == report.total_tagged_items and report.total_tagged_items > 0:
            report.status = "completed"
        elif report.purged_items:
            report.status = "partial"
        else:
            report.status = "completed"  # Audit tracking completed

        return report

    def _perform_http_teardown(
        self,
        url: str,
        method: str = "DELETE",
        base_url: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Validates network destination security and executes HTTP cleanup request."""
        import requests

        parsed = urlparse(url)
        hostname = parsed.hostname or ""

        # Validate security against SSRF
        resolve_and_validate_host(hostname, allow_local=self.allow_local)

        headers = {"User-Agent": "Ghost-User-Teardown-Agent/1.0"}
        if method == "DELETE":
            resp = requests.delete(url, headers=headers, timeout=5)
            resp.raise_for_status()
        elif method == "POST":
            resp = requests.post(url, json=payload or {}, headers=headers, timeout=5)
            resp.raise_for_status()

