"""Deterministic local HTTP test fixture server for Playwright verification."""

import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PORT = 8899


class TestFixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress noisy HTTP logs during testing
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """<!DOCTYPE html>
<html>
<head><title>Ghost-User Fixture Site</title></head>
<body>
  <h1>Autonomous Test Fixture</h1>
  <p id="description">A deterministic test environment for browser testing.</p>
  <a id="nav-search" href="/search">Go to Search</a>
  <a id="nav-login" href="/login">Go to Login</a>
</body>
</html>"""
            self.wfile.write(html.encode("utf-8"))

        elif path == "/search":
            query = parse_qs(parsed.query).get("q", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            results_html = f'<div data-testid="search-results">Results for: <span id="query-result">{query}</span></div>' if query else ""
            html = f"""<!DOCTYPE html>
<html>
<head><title>Search Page</title></head>
<body>
  <h2>Search Products</h2>
  <form action="/search" method="GET">
    <input name="q" id="search-input" value="{query}" placeholder="Search..." />
    <button type="submit" id="search-btn">Search</button>
  </form>
  {results_html}
</body>
</html>"""
            self.wfile.write(html.encode("utf-8"))

        elif path == "/login":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """<!DOCTYPE html>
<html>
<head><title>Login Page</title></head>
<body>
  <h2>Sign In</h2>
  <form action="/login" method="POST">
    <label>Email: <input id="email" name="email" type="email" /></label><br/><br/>
    <label>Role: 
      <select id="role" name="role">
        <option value="user">Standard User</option>
        <option value="admin">Administrator</option>
      </select>
    </label><br/><br/>
    <label><input type="checkbox" id="terms" name="terms" /> Accept terms</label><br/><br/>
    <button type="submit" id="login-btn">Log In</button>
  </form>
</body>
</html>"""
            self.wfile.write(html.encode("utf-8"))

        elif path == "/dashboard":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """<!DOCTYPE html>
<html>
<head><title>User Dashboard</title></head>
<body>
  <h1>Welcome to Your Dashboard</h1>
  <div id="welcome-banner">Authentication Successful</div>
  <p id="status-message">Account Active</p>
</body>
</html>"""
            self.wfile.write(html.encode("utf-8"))

        elif path == "/external-link":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """<!DOCTYPE html>
<html>
<head><title>External Link</title></head>
<body>
  <h1>External Link Test</h1>
  <a id="ext-link" href="https://example.com/external-target">Go to External</a>
</body>
</html>"""
            self.wfile.write(html.encode("utf-8"))

        elif path == "/popup-external":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """<!DOCTYPE html>
<html>
<head><title>Popup Test</title></head>
<body>
  <h1>Popup External Test</h1>
  <a id="popup-link" href="https://example.com/external-popup" target="_blank">Open External Popup</a>
</body>
</html>"""
            self.wfile.write(html.encode("utf-8"))

        elif path == "/redirect-to-metadata":
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
            self.end_headers()

        elif path == "/metadata-subresource":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """<!DOCTYPE html>
<html>
<head><title>Metadata Subresource</title></head>
<body>
  <h1>Metadata Subresource Test</h1>
  <img id="metadata-img" src="http://169.254.169.254/latest/meta-data/img.png" />
  <script>
    fetch('http://169.254.169.254/latest/meta-data/').catch(() => {});
  </script>
</body>
</html>"""
            self.wfile.write(html.encode("utf-8"))

        elif path == "/broken":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """<!DOCTYPE html>
<html>
<head>
  <title>Broken Page</title>
  <script>
    console.error("Critical simulated frontend error on broken page!");
    window.addEventListener("load", () => {
      throw new Error("Simulated unhandled exception on page load");
    });
  </script>
</head>
<body>
  <h1>Broken Page</h1>
  <p>This page deliberately contains console errors.</p>
</body>
</html>"""
            self.wfile.write(html.encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/login":
            # Redirect to dashboard on POST /login
            self.send_response(303)
            self.send_header("Location", "/dashboard")
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()


def run_fixture_server(port=PORT):
    server = HTTPServer(("127.0.0.1", port), TestFixtureHandler)
    server.serve_forever()


def start_fixture_server_in_background(port=PORT):
    server = HTTPServer(("127.0.0.1", port), TestFixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)
    return server
