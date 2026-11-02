"""Autonomous UI Audit & Source Inspection Service.

Coordinates source AST parsing, automated background dev server launch (Mode B),
seeded crawler exploration, synthetic form test generation & execution, resilient self-healing,
and automated teardown/cleanup.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.db.models import Project, TestCase, TestRun, DiscoveryReport, utc_now
from app.schemas.project import AutonomousAuditRequest, AutonomousAuditResponse
from app.services.source_parser import SourceCodeParser
from app.services.dev_server import DevServerRunner
from apps.worker.runner.crawler import WebCrawler
from apps.worker.runner.engine import BrowserExecutionEngine
from packages.shared.constants import RunStatus

logger = logging.getLogger("ghost-user")


class AutonomousAuditService:
    """Executes end-to-end autonomous source analysis, server lifecycle, and UI auditing."""

    def __init__(self, db: Session):
        self.db = db

    def execute_audit(
        self,
        project: Project,
        request: AutonomousAuditRequest,
    ) -> AutonomousAuditResponse:
        logger.info(f"Starting Autonomous UI Audit for project {project.id} ({project.name})")

        frameworks: List[str] = []
        static_routes: List[str] = []
        source_forms: List[Dict[str, Any]] = []
        source_path = project.source_code_path

        # 1. Source Code Inspection
        if source_path and Path(source_path).is_dir():
            try:
                parser = SourceCodeParser(source_path)
                scan_res = parser.parse()
                frameworks = [f.name for f in scan_res.frameworks]
                static_routes = [r.path for r in scan_res.routes]
                source_forms = [f.model_dump() for f in scan_res.forms]
                logger.info(
                    f"Discovered {len(static_routes)} static routes, {len(source_forms)} forms, frameworks: {frameworks}"
                )
            except Exception as e:
                logger.warning(f"Failed to parse source code during audit: {e}")

        # 2. Dev Server Lifecycle (Mode B)
        dev_server_running = False
        dev_server_url: Optional[str] = None
        if request.auto_start_server and source_path and Path(source_path).is_dir():
            try:
                status = DevServerRunner.get_status(project.id)
                if not status.is_running:
                    server_info = DevServerRunner.start_server(
                        project_id=project.id,
                        local_path=source_path,
                        timeout_seconds=45,
                    )
                    dev_server_running = server_info.is_running
                    dev_server_url = server_info.target_url
                else:
                    dev_server_running = True
                    dev_server_url = status.target_url

                if dev_server_url:
                    project.base_url = dev_server_url
                    project.allow_local_loopback = True
                    self.db.commit()
                    self.db.refresh(project)
            except Exception as e:
                logger.warning(f"Could not auto-start dev server: {e}")

        # 3. Seeded Live UI Crawl & Discovery
        # Filter static routes to valid web paths
        seed_paths = [r for r in static_routes if r.startswith("/") and not r.startswith("/api/")]
        crawler = WebCrawler(
            base_url=project.base_url,
            max_pages=request.max_pages,
            allow_local=project.allow_local_loopback,
            seed_paths=seed_paths,
        )

        crawl_result = crawler.crawl()

        # Persist Discovery Report record
        discovery_report = DiscoveryReport(
            project_id=project.id,
            status="completed",
            base_url=project.base_url,
            pages_count=crawl_result.get("pages_count", 0),
            broken_links_count=crawl_result.get("broken_links_count", 0),
            forms_count=crawl_result.get("forms_count", 0),
            pages_json=crawl_result.get("pages", []),
            suggested_tests_json=crawl_result.get("suggested_tests", []),
            error_message=None,
            created_at=utc_now(),
            finished_at=utc_now(),
        )
        self.db.add(discovery_report)
        self.db.commit()
        self.db.refresh(discovery_report)

        # 4. Auto-Generate & Execute UI Tests
        executed_runs: List[Dict[str, Any]] = []
        passed_count = 0
        failed_count = 0

        if request.run_form_tests and crawl_result.get("suggested_tests"):
            engine = BrowserExecutionEngine(self.db)
            # Execute up to 3 high-value discovered tests
            tests_to_run = crawl_result["suggested_tests"][:3]

            for test_def in tests_to_run:
                test_name = test_def.get("name", "Auto-Discovery Test")
                # Create or locate test case
                tc = TestCase(
                    project_id=project.id,
                    name=test_name,
                    description=test_def.get("description", "Auto-generated during Autonomous UI Audit"),
                    definition_json=test_def,
                    enabled=True,
                )
                self.db.add(tc)
                self.db.commit()
                self.db.refresh(tc)

                # Create test run
                test_run = TestRun(
                    test_case_id=tc.id,
                    status=RunStatus.QUEUED.value,
                    trigger_type="api",
                )
                self.db.add(test_run)
                self.db.commit()
                self.db.refresh(test_run)

                try:
                    final_status = engine.execute_run(test_run.id)
                    self.db.refresh(test_run)

                    if final_status == RunStatus.PASSED:
                        passed_count += 1
                    else:
                        failed_count += 1

                    executed_runs.append({
                        "id": test_run.id,
                        "test_case_id": tc.id,
                        "name": tc.name,
                        "status": test_run.status,
                        "duration_ms": test_run.duration_ms,
                        "error_summary": test_run.error_summary,
                    })
                except Exception as e:
                    logger.error(f"Failed to execute audit test run {test_run.id}: {e}")
                    failed_count += 1
                    executed_runs.append({
                        "id": test_run.id,
                        "test_case_id": tc.id,
                        "name": tc.name,
                        "status": "error",
                        "duration_ms": 0,
                        "error_summary": str(e),
                    })

        summary_msg = (
            f"Autonomous audit finished. Inspected {len(crawl_result.get('pages', []))} live pages, "
            f"{len(static_routes)} static routes. Found {crawl_result.get('broken_links_count', 0)} broken links, "
            f"{crawl_result.get('forms_count', 0)} forms. Executed {len(executed_runs)} automated test runs "
            f"({passed_count} passed, {failed_count} failed)."
        )

        return AutonomousAuditResponse(
            project_id=project.id,
            base_url=project.base_url,
            status="completed",
            frameworks=frameworks,
            source_code_path=source_path,
            dev_server_running=dev_server_running,
            dev_server_url=dev_server_url,
            static_routes_count=len(static_routes),
            pages_audited_count=crawl_result.get("pages_count", 0),
            broken_links_count=crawl_result.get("broken_links_count", 0),
            forms_detected_count=crawl_result.get("forms_count", 0),
            console_errors_count=len(crawl_result.get("console_errors", [])),
            tests_executed_count=len(executed_runs),
            tests_passed_count=passed_count,
            tests_failed_count=failed_count,
            test_runs=executed_runs,
            discovery_report_id=discovery_report.id,
            audit_summary=summary_msg,
        )
