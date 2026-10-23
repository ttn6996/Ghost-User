"""Security validation for URLs, origins, and network destinations (SSRF defense)."""

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

from app.core.config import settings

# Disallowed private and special network ranges
BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local & Cloud Metadata (169.254.169.254)
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


class SecurityValidationError(Exception):
    """Raised when a URL violates security or origin policies."""
    pass


def is_ip_blocked(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in net for net in BLOCKED_IP_NETWORKS)
    except ValueError:
        return True


def resolve_and_validate_host(hostname: str, allow_local: bool = False) -> None:
    """Validates that hostname does not resolve to private/internal/cloud metadata addresses."""
    if not hostname:
        raise SecurityValidationError("Target hostname cannot be empty")

    lower_host = hostname.lower().strip()

    if lower_host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        if not allow_local:
            raise SecurityValidationError(f"Target host '{hostname}' is a local loopback address and blocked.")
        return

    # Check for literal IP
    try:
        ip = ipaddress.ip_address(lower_host)
        if not allow_local and is_ip_blocked(str(ip)):
            raise SecurityValidationError(f"Direct IP access to '{lower_host}' is blocked for security.")
        return
    except ValueError:
        pass

    # Resolve hostname via DNS
    try:
        addr_info = socket.getaddrinfo(lower_host, None)
        for family, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            if not allow_local and is_ip_blocked(ip_str):
                raise SecurityValidationError(
                    f"Target host '{hostname}' resolved to blocked private destination ({ip_str})."
                )
    except socket.gaierror as e:
        raise SecurityValidationError(f"Could not resolve destination host '{hostname}': {e}")


def resolve_target_url(raw_url: str, base_url: str, allow_local: bool = False) -> str:
    """Resolves relative or absolute URLs, ensures origin matching and SSRF protection."""
    if not base_url:
        raise SecurityValidationError("Project base URL is required")

    # Resolve against base_url
    target_url = urljoin(base_url, raw_url)
    parsed_target = urlparse(target_url)
    parsed_base = urlparse(base_url)

    # 1. Protocol check
    if parsed_target.scheme not in ("http", "https"):
        raise SecurityValidationError(f"Unsupported URL protocol '{parsed_target.scheme}'. Only http/https permitted.")

    # 2. Origin check: Target must stay on same origin as base_url
    if parsed_target.netloc.lower() != parsed_base.netloc.lower():
        raise SecurityValidationError(
            f"Navigation out-of-bounds: target origin '{parsed_target.netloc}' does not match base origin '{parsed_base.netloc}'."
        )

    # 3. Host and SSRF check
    resolve_and_validate_host(parsed_target.hostname, allow_local=allow_local)

    return target_url
