import io
import os
import shutil
import zipfile
import tarfile
from pathlib import Path
from urllib.parse import urlparse
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.db.session import get_db
from app.db.models import Project, TestCase, TestRun, DiscoveryReport, utc_now
from app.core.config import settings
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectSourceDirectoryRequest,
    ProjectSourceUploadResponse,
    ProjectSourceInfoResponse,
    DiscoveryReportResponse,
    DiscoverySaveTestRequest,
)
from app.schemas.test_case import TestCaseResponse
from apps.worker.runner.crawler import WebCrawler
from apps.worker.runner.security import (
    resolve_and_validate_host,
    get_effective_allow_local,
    is_production_mode,
    SecurityValidationError,
)

router = APIRouter(prefix="/projects", tags=["Projects"])

MAX_ARCHIVE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB


def validate_project_security(
    base_url: str,
    allowed_domains: Optional[List[str]] = None,
    allow_local: Optional[bool] = None,
) -> None:
    """Validates base_url and allowed_domains against SSRF policies at configuration time.
    
    In production mode, SSRF strictly rejects private/loopback/cloud metadata CIDRs.
    In development mode, if allow_local=True (e.g. allow_local_loopback), localhost and
    127.0.0.1 are permitted for Mode A & B local application auditing.
    Private CIDRs (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.169.254) are
    always blocked across all modes.
    """
    parsed = urlparse(base_url)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid base URL scheme '{scheme}'. Only http and https are permitted.",
        )
    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid base URL: missing hostname in '{base_url}'",
        )

    effective_allow_local = False if is_production_mode() else get_effective_allow_local(allow_local)

    try:
        resolve_and_validate_host(hostname, allow_local=effective_allow_local)
    except SecurityValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SSRF validation rejected base URL '{base_url}': {str(e)}",
        )

    if allowed_domains:
        for domain in allowed_domains:
            clean_host = domain.strip().lower()
            if not clean_host:
                continue
            if "://" in clean_host:
                clean_host = urlparse(clean_host).hostname or clean_host
            clean_host = clean_host.split("/")[0].split("?")[0].split("#")[0].split(":")[0]
            if clean_host.startswith("*."):
                clean_host = clean_host[2:]
            elif clean_host.startswith("."):
                clean_host = clean_host[1:]
            try:
                resolve_and_validate_host(clean_host, allow_local=effective_allow_local)
            except SecurityValidationError as e:
                if "could not resolve" in str(e).lower():
                    # Unresolvable hostname at config time for secondary domain is tolerated
                    pass
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"SSRF validation rejected allowed domain '{domain}': {str(e)}",
                    )



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
    effective_allow_local = payload.allow_local_loopback or settings.ALLOW_LOCAL_TARGETS
    validate_project_security(
        base_url=payload.base_url,
        allowed_domains=payload.allowed_domains,
        allow_local=effective_allow_local,
    )

    if payload.source_code_path:
        p = Path(payload.source_code_path.strip()).resolve()
        if not p.exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"source_code_path does not exist: {payload.source_code_path}",
            )

    project = Project(
        name=payload.name,
        base_url=payload.base_url,
        description=payload.description,
        allowed_domains=payload.allowed_domains or [],
        source_code_path=payload.source_code_path,
        allow_local_loopback=payload.allow_local_loopback,
        execution_mode=payload.execution_mode,
        auth_profile_json=payload.auth_profile_json or {},
        secrets_json=payload.secrets_json or {},
        secrets_masked=payload.secrets_masked,
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

    target_base_url = payload.base_url if payload.base_url is not None else project.base_url
    target_domains = payload.allowed_domains if payload.allowed_domains is not None else (project.allowed_domains or [])
    target_allow_local = payload.allow_local_loopback if payload.allow_local_loopback is not None else project.allow_local_loopback

    if payload.base_url is not None or payload.allowed_domains is not None or payload.allow_local_loopback is not None:
        validate_project_security(
            base_url=target_base_url,
            allowed_domains=target_domains,
            allow_local=target_allow_local or settings.ALLOW_LOCAL_TARGETS,
        )

    if payload.source_code_path is not None:
        if payload.source_code_path.strip():
            p = Path(payload.source_code_path.strip()).resolve()
            if not p.exists():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"source_code_path does not exist: {payload.source_code_path}",
                )
        project.source_code_path = payload.source_code_path

    if payload.name is not None:
        project.name = payload.name
    if payload.base_url is not None:
        project.base_url = payload.base_url
    if payload.description is not None:
        project.description = payload.description
    if payload.allowed_domains is not None:
        project.allowed_domains = payload.allowed_domains
    if payload.allow_local_loopback is not None:
        project.allow_local_loopback = payload.allow_local_loopback
    if payload.execution_mode is not None:
        project.execution_mode = payload.execution_mode
    if payload.auth_profile_json is not None:
        project.auth_profile_json = payload.auth_profile_json
    if payload.secrets_json is not None:
        project.secrets_json = payload.secrets_json
    if payload.secrets_masked is not None:
        project.secrets_masked = payload.secrets_masked

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


@router.post("/{project_id}/source-upload", response_model=ProjectSourceUploadResponse)
@router.post("/{project_id}/source/upload", response_model=ProjectSourceUploadResponse)
async def upload_source_archive(
    project_id: str,
    file: UploadFile = File(..., description="Uploaded source archive (.zip, .tar.gz, .tgz, .tar)"),
    db: Session = Depends(get_db),
):
    """Uploads and unpacks a source code archive with strict Zip Slip / Path Traversal guards."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    filename = file.filename or ""
    lower_filename = filename.lower()
    is_zip = lower_filename.endswith(".zip")
    is_tar = lower_filename.endswith((".tar.gz", ".tgz", ".tar"))

    if not (is_zip or is_tar):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported archive format. Supported formats: .zip, .tar.gz, .tgz, .tar",
        )

    content = await file.read()
    file_size = len(content)
    if file_size > MAX_ARCHIVE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Archive file too large ({file_size} bytes). Maximum allowed is {MAX_ARCHIVE_SIZE_BYTES} bytes.",
        )
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded archive is empty.",
        )

    dest_dir = (Path(settings.ARTIFACT_STORAGE_DIR).resolve() / "projects" / project_id / "source").resolve()
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    if is_zip:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                for member in zf.infolist():
                    member_path = (dest_dir / member.filename).resolve()
                    if not member_path.is_relative_to(dest_dir):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Path traversal detected in zip archive member: {member.filename}",
                        )
                zf.extractall(dest_dir)
        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is not a valid zip archive.",
            )
    elif is_tar:
        try:
            with tarfile.open(fileobj=io.BytesIO(content), mode="r:*") as tf:
                for member in tf.getmembers():
                    member_path = (dest_dir / member.name).resolve()
                    if not member_path.is_relative_to(dest_dir):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Path traversal detected in tar archive member: {member.name}",
                        )
                    if member.issym() or member.islnk():
                        link_target = (dest_dir / member.linkname).resolve()
                        if not link_target.is_relative_to(dest_dir):
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Symlink traversal detected in tar archive: {member.name} -> {member.linkname}",
                            )
                if hasattr(tarfile, "data_filter"):
                    tf.extractall(dest_dir, filter="data")
                else:
                    tf.extractall(dest_dir)
        except (tarfile.TarError, tarfile.ReadError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Uploaded file is not a valid tar archive: {str(e)}",
            )

    extracted_files = [f for f in dest_dir.rglob("*") if f.is_file()]

    project.source_code_path = str(dest_dir)
    db.commit()
    db.refresh(project)

    return ProjectSourceUploadResponse(
        project_id=project.id,
        source_code_path=str(dest_dir),
        file_name=filename,
        file_size_bytes=file_size,
        extracted_files_count=len(extracted_files),
        message="Source archive uploaded and unpacked successfully.",
    )


@router.post("/{project_id}/source-directory", response_model=ProjectSourceUploadResponse)
@router.post("/{project_id}/source/directory", response_model=ProjectSourceUploadResponse)
def set_source_directory(
    project_id: str,
    payload: ProjectSourceDirectoryRequest,
    db: Session = Depends(get_db),
):
    """Associates an existing local directory with the project workspace."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    raw_path = payload.source_directory.strip()
    if "\x00" in raw_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source directory path must not contain null bytes.",
        )

    resolved_path = Path(raw_path).resolve()
    if not resolved_path.exists() or not resolved_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Source directory does not exist or is not a directory: {raw_path}",
        )

    files = [f for f in resolved_path.rglob("*") if f.is_file()]

    project.source_code_path = str(resolved_path)
    db.commit()
    db.refresh(project)

    return ProjectSourceUploadResponse(
        project_id=project.id,
        source_code_path=str(resolved_path),
        file_name=resolved_path.name,
        file_size_bytes=0,
        extracted_files_count=len(files),
        message="Source directory linked successfully.",
    )


@router.get("/{project_id}/source", response_model=ProjectSourceInfoResponse)
def get_source_info(project_id: str, db: Session = Depends(get_db)):
    """Retrieves source code metadata and file inventory for the project."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if not project.source_code_path:
        return ProjectSourceInfoResponse(
            project_id=project.id,
            has_source_code=False,
            source_code_path=None,
            files_count=0,
            top_level_directories=[],
        )

    source_path = Path(project.source_code_path)
    if not source_path.exists() or not source_path.is_dir():
        return ProjectSourceInfoResponse(
            project_id=project.id,
            has_source_code=False,
            source_code_path=project.source_code_path,
            files_count=0,
            top_level_directories=[],
        )

    all_files = [f for f in source_path.rglob("*") if f.is_file()]
    top_dirs = [d.name for d in source_path.iterdir() if d.is_dir() and not d.name.startswith(".")]

    return ProjectSourceInfoResponse(
        project_id=project.id,
        has_source_code=True,
        source_code_path=project.source_code_path,
        files_count=len(all_files),
        top_level_directories=top_dirs,
    )


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
