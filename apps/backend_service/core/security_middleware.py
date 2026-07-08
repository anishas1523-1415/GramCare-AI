from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Protect against clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        # Prevent MIME-sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Enforce HTTPS
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        # Cross-site scripting (XSS) protection filter (legacy but still useful defense-in-depth)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Note: Content-Security-Policy (CSP) is typically enforced on the frontend
        # (Next.js/Vite) that serves HTML. Since this is an API that serves JSON,
        # a strict CSP on the API endpoints ensures browsers won't execute scripts 
        # from here.
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        
        return response
