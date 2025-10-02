"""
Example demonstrating how to bypass rate limiting for specific routes.

This example shows three different ways to bypass rate limiting:
1. Using the simple bypass=True parameter
2. Using a bypass_function for conditional bypassing
3. Using enabled=False to disable rate limiting entirely
"""

from fastapi import FastAPI, Request

from fastrict import KeyExtractionType, RateLimitStrategyName, throttle

app = FastAPI()


@app.get("/")
async def root():
    """Root endpoint with normal rate limiting."""
    return {"message": "This endpoint has normal rate limiting"}


@throttle(bypass=True)
@app.get("/unrestricted")
async def unrestricted_endpoint():
    """Endpoint that completely bypasses rate limiting using bypass=True."""
    return {"message": "This endpoint bypasses all rate limiting"}


def is_admin_user(request: Request) -> bool:
    """Example bypass function that checks if user is an admin."""
    # In real implementation, you would check authentication/authorization
    api_key = request.headers.get("X-API-Key")
    return api_key == "admin-key-123"


@throttle(strategy=RateLimitStrategyName.SHORT, bypass_function=is_admin_user)
@app.get("/admin-or-limited")
async def admin_or_limited():
    """Endpoint that bypasses rate limiting for admin users only."""
    return {"message": "Rate limited for regular users, unrestricted for admins"}


def is_internal_request(request: Request) -> bool:
    """Example bypass function that checks if request is from internal network."""
    client_host = request.client.host if request.client else ""
    # Allow internal network (in real implementation, check actual IP ranges)
    return client_host.startswith("192.168.") or client_host == "127.0.0.1"


@throttle(
    limit=5, ttl=60, key_type=KeyExtractionType.IP, bypass_function=is_internal_request
)
@app.get("/internal-or-limited")
async def internal_or_limited():
    """Endpoint that bypasses rate limiting for internal requests."""
    return {"message": "Rate limited for external requests, unrestricted for internal"}


@throttle(enabled=False)
@app.get("/disabled")
async def disabled_rate_limiting():
    """Endpoint with rate limiting completely disabled."""
    return {"message": "Rate limiting is disabled for this endpoint"}


# Example of combining multiple conditions
def complex_bypass_logic(request: Request) -> bool:
    """Complex bypass function with multiple conditions."""
    # Check for admin API key
    api_key = request.headers.get("X-API-Key")
    if api_key == "admin-key-123":
        return True

    # Check for internal network
    client_host = request.client.host if request.client else ""
    if client_host.startswith("192.168.") or client_host == "127.0.0.1":
        return True

    # Check for special bypass header
    bypass_header = request.headers.get("X-Bypass-Rate-Limit")
    if bypass_header == "secret-bypass-token":
        return True

    return False


@throttle(strategy=RateLimitStrategyName.MEDIUM, bypass_function=complex_bypass_logic)
@app.get("/complex-bypass")
async def complex_bypass():
    """Endpoint with complex bypass logic."""
    return {"message": "Complex bypass conditions applied"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
