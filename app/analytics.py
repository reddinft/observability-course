"""Analytics middleware for course interactions."""
import json
import logging
from datetime import datetime
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("analytics")


class AnalyticsMiddleware(BaseHTTPMiddleware):
    """Log course interaction events."""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Log HTTP request and response."""
        method = request.method
        path = request.url.path
        
        # Skip static files and health checks
        if path.startswith("/static") or path == "/health":
            return await call_next(request)
        
        start_time = datetime.utcnow()
        
        # Call the endpoint
        response = await call_next(request)
        
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Log the event
        log_entry = {
            "timestamp": start_time.isoformat(),
            "method": method,
            "path": path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
        }
        
        logger.info(json.dumps(log_entry))
        
        return response
