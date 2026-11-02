"""Static Source Code Parser & Framework Detection Engine.

Analyzes local project directories (without executing unverified code) to extract:
1. Detected frameworks (Next.js, React, Vue, FastAPI, Spring Boot, Express, etc.)
2. Frontend pages & navigation routes (Next.js App/Pages router, React Router)
3. Backend API controllers and endpoints (FastAPI, Spring Boot, Express)
4. Form structures, input fields, and validation constraints
"""

import os
import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


# Directories ignored during recursive traversal
IGNORED_DIRS = {
    ".git", "node_modules", ".venv", "venv", "env", "dist", "build",
    ".next", "out", "target", "__pycache__", ".pytest_cache", ".idea",
    ".vscode", "coverage", "htmlcov", "data", "test_artifacts"
}

# Regex patterns for route detection
RE_FASTAPI_ROUTE = re.compile(r"""@(app|router)\.(get|post|put|delete|patch)\s*\(\s*["']([^"']+)["']""", re.IGNORECASE)
RE_SPRING_CLASS_MAPPING = re.compile(r"""@RequestMapping\s*\(\s*(?:value\s*=\s*)?["']([^"']+)["']""", re.IGNORECASE)
RE_SPRING_METHOD_MAPPING = re.compile(r"""@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)(?:\s*\(\s*(?:value\s*=\s*)?(?:["']([^"']+)["']|\{\s*["']([^"']+)["'])?\s*\))?""", re.IGNORECASE)
RE_REACT_ROUTE_JSX = re.compile(r"""<Route\s+[^>]*path=["']([^"']+)["']""", re.IGNORECASE)
RE_ROUTER_OBJECT_PATH = re.compile(r"""\bpath\s*:\s*["']([^"']+)["']""", re.IGNORECASE)

# Form & input tag matching
RE_INPUT_TAG = re.compile(r"""<input\s+([^>]+)>""", re.IGNORECASE)
RE_INPUT_ATTR_NAME = re.compile(r"""\bname=["']([^"']+)["']""", re.IGNORECASE)
RE_INPUT_ATTR_TYPE = re.compile(r"""\btype=["']([^"']+)["']""", re.IGNORECASE)
RE_INPUT_ATTR_PLACEHOLDER = re.compile(r"""\bplaceholder=["']([^"']+)["']""", re.IGNORECASE)
RE_BUTTON_TAG = re.compile(r"""<button\s*([^>]*)>(.*?)</button>""", re.IGNORECASE | re.DOTALL)


class DiscoveredRoute(BaseModel):
    path: str
    route_type: str = "frontend"  # "frontend" or "api"
    http_method: str = "GET"
    handler_or_component: Optional[str] = None
    source_file: str
    line_number: Optional[int] = None


class DiscoveredForm(BaseModel):
    page_path: str
    source_file: str
    form_type: str = "general"
    inputs: List[Dict[str, str]] = Field(default_factory=list)
    buttons: List[str] = Field(default_factory=list)


class DiscoveredFramework(BaseModel):
    name: str
    category: str  # "frontend", "backend", "fullstack"
    confidence: float
    indicators: List[str] = Field(default_factory=list)


class SourceScanResult(BaseModel):
    local_path: str
    total_files_scanned: int = 0
    frameworks: List[DiscoveredFramework] = Field(default_factory=list)
    routes: List[DiscoveredRoute] = Field(default_factory=list)
    forms: List[DiscoveredForm] = Field(default_factory=list)
    suggested_dev_command: Optional[str] = None
    default_port: Optional[int] = None


class SourceCodeParser:
    """Safely inspects local filesystem directories to extract routes, forms, and framework specs."""

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()

    def parse(self) -> SourceScanResult:
        if not self.root_path.exists() or not self.root_path.is_dir():
            raise ValueError(f"Target path does not exist or is not a directory: {self.root_path}")

        result = SourceScanResult(local_path=str(self.root_path))
        scanned_count = 0

        # Step 1: Detect frameworks & suggested startup commands from manifest files
        self._detect_manifest_frameworks(result)

        # Step 2: Recursively traverse code files
        for root, dirs, files in os.walk(self.root_path):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]

            for file in files:
                scanned_count += 1
                file_path = Path(root) / file
                rel_path = str(file_path.relative_to(self.root_path)).replace("\\", "/")

                ext = file_path.suffix.lower()
                if ext in (".ts", ".tsx", ".js", ".jsx", ".py", ".java", ".vue"):
                    self._parse_code_file(file_path, rel_path, result)

        result.total_files_scanned = scanned_count

        # Step 3: De-duplicate routes
        seen_routes = set()
        deduped = []
        for r in result.routes:
            key = (r.path, r.http_method, r.route_type)
            if key not in seen_routes:
                seen_routes.add(key)
                deduped.append(r)
        result.routes = deduped

        return result

    def _detect_manifest_frameworks(self, result: SourceScanResult):
        """Scans package.json, pom.xml, requirements.txt to detect framework and dev startup command."""
        pkg_json = self.root_path / "package.json"
        if pkg_json.exists():
            try:
                with open(pkg_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                scripts = data.get("scripts", {})

                if "next" in deps:
                    result.frameworks.append(DiscoveredFramework(
                        name="Next.js", category="fullstack", confidence=0.98, indicators=["package.json:next"]
                    ))
                    result.default_port = 3000
                elif "react" in deps:
                    result.frameworks.append(DiscoveredFramework(
                        name="React", category="frontend", confidence=0.95, indicators=["package.json:react"]
                    ))
                    result.default_port = 3000 if "vite" not in deps else 5173
                elif "vue" in deps:
                    result.frameworks.append(DiscoveredFramework(
                        name="Vue", category="frontend", confidence=0.95, indicators=["package.json:vue"]
                    ))
                    result.default_port = 5173

                # Determine suggested dev server command
                if "dev" in scripts:
                    result.suggested_dev_command = "npm run dev"
                elif "start" in scripts:
                    result.suggested_dev_command = "npm start"
                elif "serve" in scripts:
                    result.suggested_dev_command = "npm run serve"

            except Exception:
                pass

        pom_xml = self.root_path / "pom.xml"
        if pom_xml.exists():
            try:
                content = pom_xml.read_text(encoding="utf-8", errors="ignore")
                if "spring-boot" in content:
                    result.frameworks.append(DiscoveredFramework(
                        name="Spring Boot", category="backend", confidence=0.95, indicators=["pom.xml:spring-boot"]
                    ))
                    result.default_port = 8080
                    result.suggested_dev_command = "mvn spring-boot:run"
            except Exception:
                pass

        req_txt = self.root_path / "requirements.txt"
        if req_txt.exists():
            try:
                content = req_txt.read_text(encoding="utf-8", errors="ignore").lower()
                if "fastapi" in content:
                    result.frameworks.append(DiscoveredFramework(
                        name="FastAPI", category="backend", confidence=0.95, indicators=["requirements.txt:fastapi"]
                    ))
                    result.default_port = 8000
                    result.suggested_dev_command = "uvicorn app.main:app --reload"
                elif "flask" in content:
                    result.frameworks.append(DiscoveredFramework(
                        name="Flask", category="backend", confidence=0.90, indicators=["requirements.txt:flask"]
                    ))
                    result.default_port = 5000
                    result.suggested_dev_command = "flask run"
            except Exception:
                pass

    def _parse_code_file(self, file_path: Path, rel_path: str, result: SourceScanResult):
        """Analyzes an individual source code file for routes and forms."""
        # 1. Next.js App Router convention detection based on folder path
        if "app/" in rel_path or rel_path.startswith("app/"):
            file_name = file_path.name.lower()
            if file_name in ("page.tsx", "page.jsx", "page.js"):
                route_path = self._convert_next_app_path_to_route(rel_path)
                result.routes.append(DiscoveredRoute(
                    path=route_path,
                    route_type="frontend",
                    http_method="GET",
                    handler_or_component=file_path.stem,
                    source_file=rel_path,
                    line_number=1,
                ))

        # 2. Next.js Pages Router convention
        if "pages/" in rel_path or rel_path.startswith("pages/"):
            ext = file_path.suffix.lower()
            if ext in (".tsx", ".jsx", ".js"):
                route_path = self._convert_next_pages_path_to_route(rel_path)
                if route_path:
                    result.routes.append(DiscoveredRoute(
                        path=route_path,
                        route_type="frontend",
                        http_method="GET",
                        handler_or_component=file_path.stem,
                        source_file=rel_path,
                        line_number=1,
                    ))

        # Read content for AST / regex inspection
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return

        lines = content.splitlines()

        # 3. Python FastAPI / Flask route decorators
        if file_path.suffix.lower() == ".py":
            for idx, line in enumerate(lines, start=1):
                m = RE_FASTAPI_ROUTE.search(line)
                if m:
                    method = m.group(2).upper()
                    path = m.group(3)
                    result.routes.append(DiscoveredRoute(
                        path=path,
                        route_type="api",
                        http_method=method,
                        handler_or_component=line.strip(),
                        source_file=rel_path,
                        line_number=idx,
                    ))

        # 4. Java Spring Boot controller annotations
        elif file_path.suffix.lower() == ".java":
            class_prefix = ""
            for idx, line in enumerate(lines, start=1):
                cm = RE_SPRING_CLASS_MAPPING.search(line)
                if cm:
                    class_prefix = cm.group(1).rstrip("/")
                    continue

                mm = RE_SPRING_METHOD_MAPPING.search(line)
                if mm:
                    mapping_type = mm.group(1).lower()
                    raw_sub = (mm.group(2) or mm.group(3) or "").lstrip("/")
                    if raw_sub:
                        full_path = f"{class_prefix}/{raw_sub}" if class_prefix else f"/{raw_sub}"
                    else:
                        full_path = class_prefix or "/"

                    method = "GET"
                    if "post" in mapping_type:
                        method = "POST"
                    elif "put" in mapping_type:
                        method = "PUT"
                    elif "delete" in mapping_type:
                        method = "DELETE"
                    elif "patch" in mapping_type:
                        method = "PATCH"

                    result.routes.append(DiscoveredRoute(
                        path=full_path,
                        route_type="api",
                        http_method=method,
                        handler_or_component=line.strip(),
                        source_file=rel_path,
                        line_number=idx,
                    ))

        # 5. React Router JSX / Object routes
        elif file_path.suffix.lower() in (".tsx", ".jsx", ".js"):
            for idx, line in enumerate(lines, start=1):
                rm = RE_REACT_ROUTE_JSX.search(line)
                if rm:
                    path = rm.group(1)
                    if path and not path.startswith(":"):
                        result.routes.append(DiscoveredRoute(
                            path=path if path.startswith("/") else f"/{path}",
                            route_type="frontend",
                            http_method="GET",
                            handler_or_component=line.strip(),
                            source_file=rel_path,
                            line_number=idx,
                        ))

            # 6. Extract forms and interactive inputs from UI components
            self._extract_forms_from_content(content, rel_path, result)

    def _convert_next_app_path_to_route(self, rel_path: str) -> str:
        """Translates Next.js App Router file path to URL route.
        e.g., app/(auth)/login/page.tsx -> /login
        """
        parts = rel_path.split("/")
        route_parts = []
        for p in parts[1:-1]:  # skip 'app' and 'page.tsx'
            # Skip Route Groups like (auth) or (marketing)
            if p.startswith("(") and p.endswith(")"):
                continue
            # Dynamic segments like [id]
            if p.startswith("[") and p.endswith("]"):
                route_parts.append(f":{p[1:-1]}")
            else:
                route_parts.append(p)

        return "/" + "/".join(route_parts)

    def _convert_next_pages_path_to_route(self, rel_path: str) -> Optional[str]:
        """Translates Next.js Pages Router file path to URL route.
        e.g., pages/admin/index.tsx -> /admin
        """
        parts = rel_path.split("/")
        idx = parts.index("pages") if "pages" in parts else -1
        if idx == -1:
            return None

        sub_parts = parts[idx + 1:]
        if not sub_parts:
            return None

        # Remove extension
        sub_parts[-1] = Path(sub_parts[-1]).stem
        if sub_parts[-1].startswith("_"):  # Skip _app.tsx, _document.tsx
            return None

        if sub_parts[-1] == "index":
            sub_parts.pop()

        return "/" + "/".join(sub_parts)

    def _extract_forms_from_content(self, content: str, rel_path: str, result: SourceScanResult):
        """Extracts input tags and classifies forms in JSX/HTML."""
        input_matches = RE_INPUT_TAG.findall(content)
        if not input_matches:
            return

        inputs = []
        for attr_str in input_matches:
            name_m = RE_INPUT_ATTR_NAME.search(attr_str)
            type_m = RE_INPUT_ATTR_TYPE.search(attr_str)
            ph_m = RE_INPUT_ATTR_PLACEHOLDER.search(attr_str)

            name = name_m.group(1) if name_m else ""
            inp_type = (type_m.group(1) if type_m else "text").lower()
            placeholder = ph_m.group(1) if ph_m else ""

            if inp_type not in ("hidden", "submit", "image"):
                inputs.append({
                    "name": name,
                    "type": inp_type,
                    "placeholder": placeholder,
                })

        if not inputs:
            return

        # Classify form
        input_names = [i["name"].lower() for i in inputs] + [i["placeholder"].lower() for i in inputs]
        form_type = "general"
        if any("password" in n or "pwd" in n for n in input_names):
            if any("confirm" in n or "register" in n or "signup" in n for n in input_names):
                form_type = "registration"
            else:
                form_type = "login"
        elif any("search" in n or "query" in n for n in input_names):
            form_type = "search"

        # Buttons
        buttons = []
        for b in RE_BUTTON_TAG.finditer(content):
            b_text = re.sub(r"<[^>]+>", "", b.group(2)).strip()
            if b_text and len(b_text) < 40:
                buttons.append(b_text)

        result.forms.append(DiscoveredForm(
            page_path=rel_path,
            source_file=rel_path,
            form_type=form_type,
            inputs=inputs,
            buttons=buttons,
        ))