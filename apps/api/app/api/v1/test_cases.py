"""Test Case management endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import TestCase, Project
from app.schemas.test_case import (
    TestCaseCreate,
    TestCaseUpdate,
    TestCaseResponse,
    TestCaseValidateRequest,
    TestCaseValidateResponse,
)
from packages.shared.schemas import TestDefinition

router = APIRouter(prefix="/test-cases", tags=["Test Cases"])


@router.post("/validate", response_model=TestCaseValidateResponse)
def validate_test_definition(payload: TestCaseValidateRequest):
    """Validate a test definition schema without saving it."""
    try:
        parsed = TestDefinition.model_validate(payload.definition_json)
        return TestCaseValidateResponse(
            valid=True,
            step_count=len(parsed.steps),
            errors=[],
        )
    except Exception as e:
        return TestCaseValidateResponse(
            valid=False,
            step_count=0,
            errors=[str(e)],
        )


@router.get("", response_model=List[TestCaseResponse])
def list_test_cases(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    db: Session = Depends(get_db),
):
    query = select(TestCase).order_by(TestCase.created_at.desc())
    if project_id:
        query = query.filter(TestCase.project_id == project_id)
    return db.execute(query).scalars().all()


@router.post("", response_model=TestCaseResponse, status_code=status.HTTP_201_CREATED)
def create_test_case(payload: TestCaseCreate, db: Session = Depends(get_db)):
    # Verify project exists
    project = db.get(Project, payload.project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{payload.project_id}' not found",
        )

    test_case = TestCase(
        project_id=payload.project_id,
        name=payload.name,
        description=payload.description,
        enabled=payload.enabled,
        definition_json=payload.definition_json,
    )
    db.add(test_case)
    db.commit()
    db.refresh(test_case)
    return test_case


@router.get("/{test_case_id}", response_model=TestCaseResponse)
def get_test_case(test_case_id: str, db: Session = Depends(get_db)):
    test_case = db.get(TestCase, test_case_id)
    if not test_case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found")
    return test_case


@router.put("/{test_case_id}", response_model=TestCaseResponse)
def update_test_case(test_case_id: str, payload: TestCaseUpdate, db: Session = Depends(get_db)):
    test_case = db.get(TestCase, test_case_id)
    if not test_case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found")

    if payload.name is not None:
        test_case.name = payload.name
    if payload.description is not None:
        test_case.description = payload.description
    if payload.enabled is not None:
        test_case.enabled = payload.enabled
    if payload.definition_json is not None:
        test_case.definition_json = payload.definition_json

    db.commit()
    db.refresh(test_case)
    return test_case


@router.delete("/{test_case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test_case(test_case_id: str, db: Session = Depends(get_db)):
    test_case = db.get(TestCase, test_case_id)
    if not test_case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found")
    db.delete(test_case)
    db.commit()
    return None
