from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def client_address(request: Request) -> str:
    """
    The visitor's address, for rate limiting.

    In production the API is only reachable through nginx (the container
    publishes no port), so the TCP peer is always nginx itself. Keying the
    limiter on that made every limit global: five wrong logins by anyone
    locked out everybody for 15 minutes. nginx sets X-Real-IP to the real
    visitor address and overwrites anything the client sent, so it can be
    trusted here. Without the header (local development) fall back to the
    TCP peer.
    """
    real_ip = request.headers.get("x-real-ip")
    return real_ip.strip() if real_ip else get_remote_address(request)


limiter = Limiter(key_func=client_address)
