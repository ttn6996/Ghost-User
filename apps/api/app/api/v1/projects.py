"""Project management endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.db.session import get_db
from app.db.models import Project, TestCase, TestRun, DiscoveryReport, utc_now
from app.core.config import settings
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    DiscoveryReportResponse,
    DiscoverySaveTestRequest,
)
from app.schemas.test_case import TestCaseResponse
from apps.worker.runner.crawler import WebCrawler

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("", response_model=List[ProjectResponse])
def list_projects(
    q: Optional[str] = Query(None, description="Search query by project name"),
    db: Session = Depends(get_db),
):
    query = select(Project).order_by(Project.created_at.desc())
    if q:
        query = query.filter(Project.name.ilike(f"%{q}%"))
    projects = db.execute(query).scalars().all()
    return projects


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(
        name=payload.name,
        base_url=payload.base_url,
        description=payload.description,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: str, payload: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if payload.name is not None:
        project.name = payload.name
    if payload.base_url is not None:
        project.base_url = payload.base_url
    if payload.description is not None:
        project.description = payload.description

    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    db.delete(project)
    db.commit()
    return None


@router.post("/{project_id}/discover", response_model=DiscoveryReportResponse)
def discover_project_pages(
    project_id: str,
    max_pages: int = Query(15, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """Triggers an autonomous website crawl to discover pages, forms, and synthesize test cases."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    crawler = WebCrawler(
        base_url=project.base_url,
        max_pages=max_pages,
        allow_local=settings.ALLOW_LOCAL_TARGETS,
    )

    try:
        results = crawler.crawl()
        report = DiscoveryReport(
            project_id=project.id,
            status="completed",
            base_url=project.base_url,
            pages_count=results["pages_count"],
            broken_links_count=results["broken_links_count"],
            forms_count=results["forms_count"],
            pages_json=results["pages"],
            suggested_tests_json=results["suggested_tests"],
            finished_at=utc_now(),
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report
    except Exception as e:
        report = DiscoveryReport(
            project_id=project.id,
            status="failed",
            base_url=project.base_url,
            error_message=str(e),
            finished_at=utc_now(),
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Auto-discovery crawl failed: {str(e)}",
        )


@router.get("/{project_id}/discover/latest", response_model=Optional[DiscoveryReportResponse])
def get_latest_discovery_report(project_id: str, db: Session = Depends(get_db)):
    """Returns the most recent discovery report for this project."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    query = (
        select(DiscoveryReport)
        .filter(DiscoveryReport.project_id == project_id)
        .order_by(DiscoveryReport.created_at.desc())
        .limit(1)
    )
    return db.execute(query).scalars().first()


@router.post("/{project_id}/discover/save-test", response_model=TestCaseResponse, status_code=status.HTTP_201_CREATED)
def save_discovered_test(
    project_id: str,
    payload: DiscoverySaveTestRequest,
    db: Session = Depends(get_db),
):
    """Converts a suggested test from auto-discovery into a real TestCase."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    test_case = TestCase(
        project_id=project.id,
        name=payload.name,
        description=payload.description or "Auto-generated from site discovery",
        enabled=True,
        definition_json={
            "name": payload.name,
            "description": payload.description,
            "steps": payload.steps,
        },
    )
    db.add(test_case)
    db.commit()
    db.refresh(test_case)
    return test_case
