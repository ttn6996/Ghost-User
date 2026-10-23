"""Security validation for URLs, origins, and network destinations (SSRF defense)."""

import ipaddress
import socket
from urllib.parse import urljoin, urlparse
from typing import Optional, Tuple

from app.core.config import settings

# Comprehensive list of disallowed private, special-use, loopback, and metadata network ranges (IPv4 & IPv6)
BLOCKED_IP_NETWORKS = [
    # IPv4
    ipaddress.ip_network("0.0.0.0/8"),          # Current network
    ipaddress.ip_network("10.0.0.0/8"),         # RFC 1918 Private Class A
    ipaddress.ip_network("100.64.0.0/10"),      # Shared address space (Carrier-grade NAT)
    ipaddress.ip_network("127.0.0.0/8"),        # Loopback
    ipaddress.ip_network("169.254.0.0/16"),     # Link-local & Cloud Metadata (169.254.169.254)
    ipaddress.ip_network("172.16.0.0/12"),      # RFC 1918 Private Class B
    ipaddress.ip_network("192.0.0.0/24"),       # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),       # TEST-NET-1
    ipaddress.ip_network("192.88.99.0/24"),     # 6to4 Relay Anycast
    ipaddress.ip_network("192.168.0.0/16"),     # RFC 1918 Private Class C
    ipaddress.ip_network("198.18.0.0/15"),      # Network benchmark testing
    ipaddress.ip_network("198.51.100.0/24"),    # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),     # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),        # Multicast
    ipaddress.ip_network("240.0.0.0/4"),        # Reserved / Future use
    ipaddress.ip_network("255.255.255.255/32"), # Broadcast
    # IPv6
    ipaddress.ip_network("::/128"),             # Unspecified
    ipaddress.ip_network("::1/128"),            # Loopback
    ipaddress.ip_network("64:ff9b::/96"),       # IPv4/IPv6 translation
    ipaddress.ip_network("100::/64"),           # Discard-only
    ipaddress.ip_network("2001::/23"),          # IETF protocol
    ipaddress.ip_network("2001:db8::/32"),      # Documentation
    ipaddress.ip_network("2002::/16"),          # 6to4
    ipaddress.ip_network("fc00::/7"),           # Unique local address (ULA / private)
    ipaddress.ip_network("fe80::/10"),          # Link-local unicast
    ipaddress.ip_network("ff00::/8"),           # Multicast
]


class SecurityValidationError(Exception):
    """Raised when a URL violates security or origin policies."""
    pass


def is_production_mode() -> bool:
    """Returns True if running in production mode."""
    return settings.ENVIRONMENT.strip().lower() == "production"


def get_effective_allow_local(requested_allow_local: Optional[bool] = None) -> bool:
    """Never allows local target exceptions in production mode."""
    if is_production_mode():
        return False
    if requested_allow_local is not None:
        return requested_allow_local
    return bool(settings.ALLOW_LOCAL_TARGETS)


def is_ip_blocked(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Checks if an IP address belongs to any blocked private/special/metadata network."""
    # Check for IPv4-mapped IPv6 addresses (e.g. ::ffff:127.0.0.1 or ::ffff:169.254.169.254)
    if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
        ip_obj = ip_obj.ipv4_mapped

    return any(ip_obj in net for net in BLOCKED_IP_NETWORKS)


def validate_ip_address(ip_str: str, allow_local: bool = False) -> None:
    """Validates an IP string against blocked ranges."""
    effective_allow_local = get_effective_allow_local(allow_local)
    try:
        ip = ipaddress.ip_address(ip_str.strip())
    except ValueError:
        raise SecurityValidationError(f"Invalid IP address format: {ip_str}")

    if ip.is_loopback:
        if not effective_allow_local:
            raise SecurityValidationError(f"Target IP '{ip_str}' is loopback and blocked.")
        return

    if is_ip_blocked(ip):
        raise SecurityValidationError(f"Target IP '{ip_str}' belongs to a blocked private or reserved network.")


def resolve_and_validate_host(hostname: str, allow_local: bool = False) -> None:
    """Validates that hostname does not resolve to private/internal/cloud metadata addresses."""
    if not hostname:
        raise SecurityValidationError("Target hostname cannot be empty")

    effective_allow_local = get_effective_allow_local(allow_local)
    lower_host = hostname.lower().strip()

    if lower_host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        if not effective_allow_local:
            raise SecurityValidationError(f"Target host '{hostname}' is a local loopback address and blocked.")
        return

    # Check for literal IP
    try:
        ip = ipaddress.ip_address(lower_host)
        validate_ip_address(str(ip), allow_local=effective_allow_local)
        return
    except ValueError:
        pass

    # Resolve hostname via DNS to verify all returned IPv4 and IPv6 records
    try:
        addr_info = socket.getaddrinfo(lower_host, None)
        if not addr_info:
            raise SecurityValidationError(f"Could not resolve destination host '{hostname}'.")

        for family, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            try:
                ip_obj = ipaddress.ip_address(ip_str)
                if ip_obj.is_loopback and effective_allow_local:
                    continue
                if is_ip_blocked(ip_obj):
                    raise SecurityValidationError(
                        f"Target host '{hostname}' resolved to blocked private destination ({ip_str})."
                    )
            except ValueError:
                raise SecurityValidationError(f"Invalid address resolved for '{hostname}': {ip_str}")

    except socket.gaierror as e:
        raise SecurityValidationError(f"Could not resolve destination host '{hostname}': {e}")


def resolve_target_url(raw_url: str, base_url: str, allow_local: bool = False) -> str:
    """Resolves relative or absolute URLs, ensures origin matching and SSRF protection."""
    if not base_url:
        raise SecurityValidationError("Project base URL is required")

    effective_allow_local = get_effective_allow_local(allow_local)

    # Resolve against base_url
    target_url = urljoin(base_url, raw_url)
    parsed_target = urlparse(target_url)
    parsed_base = urlparse(base_url)

    # 1. Protocol check: strictly http or https
    if parsed_target.scheme not in ("http", "https"):
        raise SecurityValidationError(f"Unsupported URL protocol '{parsed_target.scheme}'. Only http/https permitted.")

    # 2. Origin check: Target must stay on same origin as base_url
    if parsed_target.netloc.lower() != parsed_base.netloc.lower():
        raise SecurityValidationError(
            f"Navigation out-of-bounds: target origin '{parsed_target.netloc}' does not match base origin '{parsed_base.netloc}'."
        )

    # 3. Host and SSRF check
    resolve_and_validate_host(parsed_target.hostname, allow_local=effective_allow_local)

    return target_url


def check_browser_request_security(
    url: str,
    base_url: str,
    is_navigation: bool = False,
    allow_local: bool = False,
) -> Tuple[bool, str]:
    """Inspects a browser request (navigation or subresource) in real-time.
    
    Returns (True, '') if safe to proceed, or (False, reason) if blocked.
    """
    effective_allow_local = get_effective_allow_local(allow_local)

    parsed = urlparse(url)
    scheme = parsed.scheme.lower()

    # Safe data: or blob: URIs are allowed only for subresources (e.g. inline images/fonts), never navigations
    if scheme in ("data", "blob", "about"):
        if is_navigation and url != "about:blank":
            return False, f"Navigation to '{scheme}:' URI is not permitted."
        return True, ""

    if scheme not in ("http", "https"):
        return False, f"Disallowed scheme '{scheme}'."

    hostname = parsed.hostname
    if not hostname:
        return False, "Request has missing or empty hostname."

    # Origin restriction for navigations: Must match base_url netloc
    if is_navigation:
        parsed_base = urlparse(base_url)
        if parsed.netloc.lower() != parsed_base.netloc.lower():
            return False, f"Navigation out-of-bounds to '{parsed.netloc}'. Must match authorized origin '{parsed_base.netloc}'."

    # SSRF / IP restriction for all network requests (navigations AND subresources)
    try:
        resolve_and_validate_host(hostname, allow_local=effective_allow_local)
    except SecurityValidationError as e:
        return False, str(e)

    return True, ""
