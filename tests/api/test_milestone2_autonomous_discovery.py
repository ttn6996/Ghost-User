"""Tests for Milestone 2: Source Code Parser, Dev Server Runner, and Tagged Synthetic Data.

Validates:
1. SourceCodeParser accurately extracts Next.js, React, FastAPI, Spring Boot routes & forms
2. SyntheticDataGenerator produces correctly tagged, typed, and verifiable test values
3. is_tagged_test_data reliably tags and isolates run IDs for automated teardown/cleanup
4. DevServerRunner command detection and process status tracking
5. Project API endpoints (/scan-source, /dev-server/status)
"""

import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Project
from app.services.source_parser import SourceCodeParser, DiscoveredRoute
from app.services.dev_server import DevServerRunner, DevServerInfo
from packages.shared.data_generator import (
    SyntheticDataGenerator,
    is_tagged_test_data,
    extract_test_run_id,
    TAG_PREFIX,
)


@pytest.fixture
def mock_project_workspace(tmp_path: Path):
    """Creates a temporary realistic project structure for source parsing."""
    root = tmp_path / "mock_app"
    root.mkdir()

    # 1. package.json for Next.js app
    pkg_json = root / "package.json"
    pkg_json.write_text(json.dumps({
        "name": "mock-next-app",
        "scripts": {
            "dev": "next dev",
            "build": "next build",
            "start": "next start"
        },
        "dependencies": {
            "next": "14.2.0",
            "react": "^18.2.0",
            "react-dom": "^18.2.0"
        }
    }), encoding="utf-8")

    # 2. Next.js App Router pages
    app_dir = root / "app"
    app_dir.mkdir()
    (app_dir / "page.tsx").write_text("export default function Home() { return <h1>Home</h1>; }", encoding="utf-8")

    auth_dir = app_dir / "(auth)" / "login"
    auth_dir.mkdir(parents=True)
    (auth_dir / "page.tsx").write_text("""
    export default function LoginPage() {
        return (
            <form>
                <input name="email" type="email" placeholder="Enter your email" />
                <input name="password" type="password" placeholder="Password" />
                <button type="submit">Sign In</button>
            </form>
        );
    }
    """, encoding="utf-8")

    users_dir = app_dir / "dashboard" / "users" / "[id]"
    users_dir.mkdir(parents=True)
    (users_dir / "page.tsx").write_text("export default function UserDetail() { return <div>User</div>; }", encoding="utf-8")

    # 3. FastAPI backend files
    backend_dir = root / "api"
    backend_dir.mkdir()
    (backend_dir / "routes.py").write_text("""
from fastapi import APIRouter
router = APIRouter()

@router.get("/api/v1/users")
def list_users(): pass

@router.post("/api/v1/users")
def create_user(): pass
    """, encoding="utf-8")

    # 4. Spring Boot controller file
    java_dir = root / "src" / "main" / "java" / "com" / "example"
    java_dir.mkdir(parents=True)
    (java_dir / "LockerController.java").write_text("""
package com.example;

@RestController
@RequestMapping("/api/lockers")
public class LockerController {
    @GetMapping("/{id}")
    public Locker getLocker() { return null; }

    @PostMapping
    public Locker createLocker() { return null; }
}
    """, encoding="utf-8")

    return root


# ==============================================================================
# Group 1: SourceCodeParser Tests
# ==============================================================================

def test_source_parser_detects_nextjs_framework(mock_project_workspace: Path):
    parser = SourceCodeParser(str(mock_project_workspace))
    result = parser.parse()

    framework_names = [f.name for f in result.frameworks]
    assert "Next.js" in framework_names
    assert result.suggested_dev_command == "npm run dev"
    assert result.default_port == 3000


def test_source_parser_extracts_nextjs_app_routes(mock_project_workspace: Path):
    parser = SourceCodeParser(str(mock_project_workspace))
    result = parser.parse()

    route_paths = [r.path for r in result.routes if r.route_type == "frontend"]
    assert "/" in route_paths
    assert "/login" in route_paths  # (auth) group normalized
    assert "/dashboard/users/:id" in route_paths  # [id] dynamic route


def test_source_parser_extracts_fastapi_and_spring_routes(mock_project_workspace: Path):
    parser = SourceCodeParser(str(mock_project_workspace))
    result = parser.parse()

    api_routes = [r for r in result.routes if r.route_type == "api"]
    api_paths = [(r.path, r.http_method) for r in api_routes]

    # FastAPI routes
    assert ("/api/v1/users", "GET") in api_paths
    assert ("/api/v1/users", "POST") in api_paths

    # Spring Boot routes
    assert ("/api/lockers/{id}", "GET") in api_paths
    assert ("/api/lockers", "POST") in api_paths


def test_source_parser_extracts_forms_and_input_fields(mock_project_workspace: Path):
    parser = SourceCodeParser(str(mock_project_workspace))
    result = parser.parse()

    assert len(result.forms) >= 1
    login_form = next((f for f in result.forms if f.form_type == "login"), None)
    assert login_form is not None

    input_names = [i["name"] for i in login_form.inputs]
    assert "email" in input_names
    assert "password" in input_names
    assert "Sign In" in login_form.buttons


# ==============================================================================
# Group 2: SyntheticDataGenerator Tests (Pillar 4)
# ==============================================================================

def test_synthetic_data_generator_tags():
    generator = SyntheticDataGenerator(run_id="run_12345")

    # Email generation
    email = generator.email()
    assert "@testqa.local" in email
    assert "autoqa_run_12345_" in email
    assert is_tagged_test_data(email)
    assert is_tagged_test_data(email, run_id="run_12345")
    assert not is_tagged_test_data(email, run_id="other_run")

    # Text generation
    text_val = generator.generate("username_field", "text")
    assert text_val.startswith("AUTOQA_run_12345_username_field_")
    assert is_tagged_test_data(text_val)
    assert is_tagged_test_data(text_val, run_id="run_12345")
    assert not is_tagged_test_data(text_val, run_id="different_run")
    assert extract_test_run_id(text_val) == "run_12345"

    # Phone generation
    phone = generator.phone()
    assert phone.startswith("+84901")
    assert len(phone) == 12

    # Password generation
    pwd = generator.password()
    assert "AutoQA!" in pwd
    assert len(pwd) >= 12


def test_is_tagged_test_data_negative_cases():
    assert not is_tagged_test_data("user@example.com")
    assert not is_tagged_test_data("normal_admin_user")
    assert not is_tagged_test_data("")
    assert not is_tagged_test_data(None)
    assert not is_tagged_test_data(12345)


# ==============================================================================
# Group 3: DevServerRunner Command Detection Tests
# ==============================================================================

def test_dev_server_runner_command_detection(tmp_path: Path):
    # Case 1: Node.js project
    node_dir = tmp_path / "node_proj"
    node_dir.mkdir()
    (node_dir / "package.json").write_text("{}", encoding="utf-8")
    assert DevServerRunner._detect_command(node_dir) == "npm run dev"

    # Case 2: Spring Boot project
    spring_dir = tmp_path / "spring_proj"
    spring_dir.mkdir()
    (spring_dir / "pom.xml").write_text("<project></project>", encoding="utf-8")
    assert DevServerRunner._detect_command(spring_dir) == "mvn spring-boot:run"

    # Case 3: Python FastAPI project
    py_dir = tmp_path / "py_proj"
    py_dir.mkdir()
    (py_dir / "requirements.txt").write_text("fastapi", encoding="utf-8")
    (py_dir / "main.py").write_text("# main", encoding="utf-8")
    assert DevServerRunner._detect_command(py_dir) == "python main.py"


# ==============================================================================
# Group 4: API Endpoints for Source Scan & Dev Server
# ==============================================================================

def test_api_scan_source_code(client: TestClient, db_session: Session, mock_project_workspace: Path):
    # Create project pointing to mock source directory
    project = Project(
        name="Scan Test Project",
        base_url="http://localhost:3000",
        source_code_path=str(mock_project_workspace),
        allow_local_loopback=True,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    resp = client.post(f"/api/v1/projects/{project.id}/scan-source")
    assert resp.status_code == 200
    data = resp.json()

    assert data["local_path"] == str(mock_project_workspace.resolve())
    assert data["total_files_scanned"] > 0
    assert any(f["name"] == "Next.js" for f in data["frameworks"])
    assert any(r["path"] == "/login" for r in data["routes"])


def test_api_dev_server_status(client: TestClient, db_session: Session):
    project = Project(
        name="Dev Server Status Project",
        base_url="http://localhost:3000",
        allow_local_loopback=True,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    resp = client.get(f"/api/v1/projects/{project.id}/dev-server/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project.id
    assert data["is_running"] is False
