"""
Health and readiness check endpoints for observability.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import threading
import time
import structlog
import httpx

logger = structlog.get_logger()
_HEALTH_SERVERS = {}


class ReusableHTTPServer(HTTPServer):
    """HTTP server that tolerates rapid test restarts."""

    allow_reuse_address = True


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler for health and readiness checks."""

    def __init__(self, *args, llm_config=None, **kwargs):
        self.llm_config = llm_config
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle GET requests for health/readiness."""
        if self.path == "/healthz":
            self.send_health_response()
        elif self.path == "/readyz":
            self.send_readiness_response()
        else:
            self._send_json(404, {"error": "Not Found", "timestamp": time.time()})

    def send_health_response(self):
        """Send health check response."""
        # Health check: is the service running?
        response = {
            "status": "healthy",
            "service": "digest-core",
            "timestamp": time.time(),
        }
        self._send_json(200, response)

    def send_readiness_response(self):
        """Send readiness check response."""
        # Readiness check: is the service ready to accept requests?
        checks = {"service": "digest-core", "checks": {}}

        # Check LLM Gateway connectivity if config is available
        if self.llm_config:
            llm_status = self._check_llm_gateway()
            checks["checks"]["llm_gateway"] = llm_status
        else:
            checks["checks"]["llm_gateway"] = {
                "status": "unknown",
                "reason": "no_config",
            }

        # Determine overall readiness
        all_healthy = all(
            check.get("status") in {"healthy", "unknown"} for check in checks["checks"].values()
        )

        checks["status"] = "ready" if all_healthy else "not_ready"
        checks["timestamp"] = time.time()

        status_code = 200 if all_healthy else 503
        self._send_json(status_code, checks)

    def _check_llm_gateway(self) -> dict:
        """Check LLM Gateway connectivity."""
        try:
            # Simple connectivity check
            with httpx.Client(timeout=5.0) as client:
                # Try to make a simple request to check connectivity
                # This is a basic check - in production you might want a dedicated health endpoint
                response = client.get(
                    self._get_llm_health_endpoint(),
                    headers={"Authorization": f"Bearer {self.llm_config.get_token()}"},
                )

                if response.status_code == 200:
                    return {"status": "healthy", "endpoint": self.llm_config.endpoint}
                else:
                    return {
                        "status": "unhealthy",
                        "endpoint": self.llm_config.endpoint,
                        "status_code": response.status_code,
                    }

        except httpx.ConnectError:
            return {
                "status": "unhealthy",
                "endpoint": self.llm_config.endpoint,
                "reason": "connection_failed",
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "endpoint": self.llm_config.endpoint,
                "reason": str(e),
            }

    def _get_llm_health_endpoint(self) -> str:
        """Map known chat endpoints to the gateway health endpoint."""
        endpoint = self.llm_config.endpoint.rstrip("/")
        for suffix in ("/api/v1/chat", "/chat"):
            if endpoint.endswith(suffix):
                return endpoint[: -len(suffix)] + "/health"
        return endpoint + "/health"

    def _send_json(self, status_code: int, payload: dict) -> None:
        """Write a JSON response with a stable envelope."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def log_message(self, format, *args):
        """Override to suppress default logging."""
        pass


def start_health_server(port: int = 9109, llm_config=None):
    """Start health check HTTP server in background thread."""
    if port in _HEALTH_SERVERS:
        return _HEALTH_SERVERS[port]

    def handler_factory(*args, **kwargs):
        return HealthCheckHandler(*args, llm_config=llm_config, **kwargs)

    server = ReusableHTTPServer(("0.0.0.0", port), handler_factory)

    def serve():
        logger.info("Health check server started", port=port)
        server.serve_forever()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    _HEALTH_SERVERS[port] = server
    return server
