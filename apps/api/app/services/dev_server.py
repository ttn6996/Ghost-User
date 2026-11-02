"""Background Dev Server Process Manager for Mode B Autonomous Auditing.

Allows AutoQA to:
1. Detect project dev startup commands (npm run dev, mvn spring-boot:run, uvicorn, etc.)
2. Launch dev servers as managed background subprocesses
3. Parse stdout/stderr to detect bound port and URL (e.g., http://localhost:3000)
4. Poll healthcheck until the server is ready to accept HTTP connections
5. Gracefully or forcefully terminate server process trees on stop/teardown
"""

import os
import re
import time
import signal
import socket
import urllib.request
import subprocess
from pathlib import Path
from typing import Dict, Optional, Any
from pydantic import BaseModel

from app.core.logging import logger


RE_PORT_SNIFF = re.compile(r"""(?:localhost|127\.0\.0\.1|0\.0\.0\.0|:\s*)\s*:?(\d{4,5})""", re.IGNORECASE)
RE_URL_SNIFF = re.compile(r"""(http://(?:localhost|127\.0\.0\.1):\d{2,5})""", re.IGNORECASE)


class DevServerInfo(BaseModel):
    project_id: str
    local_path: str
    command: str
    pid: Optional[int] = None
    target_url: Optional[str] = None
    port: Optional[int] = None
    is_running: bool = False
    start_time: Optional[float] = None
    last_log: Optional[str] = None


class DevServerRunner:
    """Singleton process registry managing active local development servers."""
    
    _active_servers: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def start_server(
        cls,
        project_id: str,
        local_path: str,
        command: Optional[str] = None,
        port: Optional[int] = None,
        timeout_seconds: int = 45,
    ) -> DevServerInfo:
        """Launches a dev server process, waits for HTTP healthcheck, and returns active server info."""
        path = Path(local_path).resolve()
        if not path.is_dir():
            raise ValueError(f"Local path does not exist: {local_path}")

        # If already running for this project, stop it first
        if project_id in cls._active_servers:
            cls.stop_server(project_id)

        # Detect command if not specified
        if not command:
            command = cls._detect_command(path)

        logger.info(f"Starting dev server for project '{project_id}' at '{path}' using command: '{command}'")

        # Spawn non-blocking background process
        process = subprocess.Popen(
            command,
            shell=True,
            cwd=str(path),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        detected_url = None
        detected_port = port
        start_t = time.time()
        log_lines = []

        # Non-blocking poll for startup URL
        deadline = start_t + timeout_seconds
        while time.time() < deadline:
            if process.poll() is not None:
                err_out = "\n".join(log_lines[-20:])
                raise RuntimeError(f"Dev server process exited prematurely with code {process.returncode}:\n{err_out}")

            # Read available line without blocking forever
            try:
                line = process.stdout.readline()
                if line:
                    log_lines.append(line.strip())
                    url_m = RE_URL_SNIFF.search(line)
                    if url_m and not detected_url:
                        detected_url = url_m.group(1).replace("0.0.0.0", "localhost")
                        port_m = re.search(r":(\d+)$", detected_url)
                        if port_m:
                            detected_port = int(port_m.group(1))

                    if not detected_port:
                        pm = RE_PORT_SNIFF.search(line)
                        if pm:
                            p_candidate = int(pm.group(1))
                            if 1024 <= p_candidate <= 65535:
                                detected_port = p_candidate
            except Exception:
                pass

            # If we know the port, test socket connection
            target_port_to_test = detected_port or (port or 3000)
            if cls._is_port_open("127.0.0.1", target_port_to_test):
                detected_port = target_port_to_test
                detected_url = detected_url or f"http://localhost:{detected_port}"
                break

            time.sleep(0.5)

        if not detected_url:
            detected_port = detected_port or port or 3000
            detected_url = f"http://localhost:{detected_port}"

        # Register server
        server_record = {
            "process": process,
            "project_id": project_id,
            "local_path": str(path),
            "command": command,
            "pid": process.pid,
            "target_url": detected_url,
            "port": detected_port,
            "start_time": start_t,
            "log_lines": log_lines,
        }
        cls._active_servers[project_id] = server_record

        logger.info(f"Dev server for '{project_id}' started on {detected_url} (PID={process.pid})")

        return DevServerInfo(
            project_id=project_id,
            local_path=str(path),
            command=command,
            pid=process.pid,
            target_url=detected_url,
            port=detected_port,
            is_running=True,
            start_time=start_t,
            last_log=log_lines[-1] if log_lines else None,
        )

    @classmethod
    def stop_server(cls, project_id: str) -> bool:
        """Terminates dev server process tree cleanly."""
        record = cls._active_servers.pop(project_id, None)
        if not record:
            return False

        proc: subprocess.Popen = record["process"]
        pid = proc.pid
        logger.info(f"Stopping dev server for project '{project_id}' (PID={pid})")

        try:
            if os.name == "nt":
                # Windows: kill process tree forcefully
                subprocess.run(
                    f"taskkill /F /T /PID {pid}",
                    shell=True,
                    capture_output=True,
                    check=False,
                )
            else:
                # Unix
                os.killpg(os.getpgid(pid), signal.SIGTERM)
        except Exception as e:
            logger.warning(f"Error terminating process PID {pid}: {e}")

        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            pass

        return True

    @classmethod
    def get_status(cls, project_id: str) -> DevServerInfo:
        """Returns the current running status of a dev server."""
        record = cls._active_servers.get(project_id)
        if not record:
            return DevServerInfo(
                project_id=project_id,
                local_path="",
                command="",
                is_running=False,
            )

        proc: subprocess.Popen = record["process"]
        is_running = proc.poll() is None

        return DevServerInfo(
            project_id=project_id,
            local_path=record["local_path"],
            command=record["command"],
            pid=proc.pid,
            target_url=record["target_url"],
            port=record["port"],
            is_running=is_running,
            start_time=record["start_time"],
            last_log=record["log_lines"][-1] if record.get("log_lines") else None,
        )

    @staticmethod
    def _detect_command(path: Path) -> str:
        """Infers the start command from directory contents."""
        pkg_json = path / "package.json"
        if pkg_json.exists():
            return "npm run dev"

        pom_xml = path / "pom.xml"
        if pom_xml.exists():
            return "mvn spring-boot:run"

        if (path / "requirements.txt").exists():
            if (path / "main.py").exists():
                return "python main.py"
            elif (path / "app" / "main.py").exists():
                return "uvicorn app.main:app --reload"

        return "npm run dev"

    @staticmethod
    def _is_port_open(host: str, port: int) -> bool:
        """Tests whether a TCP socket can connect to host:port."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex((host, port)) == 0

