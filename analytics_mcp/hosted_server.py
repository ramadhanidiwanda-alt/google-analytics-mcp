# Copyright 2026 Cuan Insight contributors.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""Private, stateless GA4 MCP endpoint. The upstream stdio server remains separate."""

import contextvars
import hmac
import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from analytics_mcp.hosted_runtime import (KEY, CuanGa4Control, GoogleGa4Rest,
                                          HostedGa4Error, HostedGa4Service)

_connection_key: contextvars.ContextVar[str] = contextvars.ContextVar("cuan_ga4_connection_key", default="")


def create_hosted_server(control: Any = None, google: Any = None,
                         allowed_host: str | None = None) -> FastMCP:
    if control is None:
        control = CuanGa4Control(os.environ["CUAN_GA4_RUNTIME_URL"],
            os.environ["GA4_PRIVATE_SERVICE_ID"], os.environ["GA4_PRIVATE_SERVICE_SECRET"])
    service = HostedGa4Service(control, google or GoogleGa4Rest())
    hosts = [allowed_host] if allowed_host else ["127.0.0.1:*", "localhost:*"]
    server = FastMCP("Cuan Google Analytics", json_response=True, stateless_http=True,
                     max_request_body_size=65536, max_sessions=100,
                     transport_security=TransportSecuritySettings(
                         enable_dns_rebinding_protection=True,
                         allowed_hosts=hosts, allowed_origins=[]))

    def key() -> str:
        value = _connection_key.get()
        if not KEY.fullmatch(value):
            raise ValueError("Cuan Connection Key is missing")
        return value

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def analytics_run_daily_report(property_id: str, since: str, until: str) -> dict:
        """Read at most 31 daily active-user rows from an exact Cuan-granted GA4 property."""
        try:
            return await service.run_daily_report(key(), property_id, since, until)
        except HostedGa4Error as exc:
            raise ValueError(f"{exc.code}: {exc}") from None

    @server.tool()
    async def analytics_preview_key_event_update(
        property_id: str, key_event_id: str, expected_event_name: str,
        expected_counting_method: str, new_counting_method: str,
    ) -> dict:
        """Get a five-minute Cuan preview for a custom key event on an owned test property."""
        try:
            return await service.preview(key(), property_id, key_event_id,
                expected_event_name, expected_counting_method, new_counting_method)
        except HostedGa4Error as exc:
            raise ValueError(f"{exc.code}: {exc}") from None

    @server.tool(annotations=ToolAnnotations(destructiveHint=True))
    async def analytics_update_key_event(
        property_id: str, key_event_id: str, expected_event_name: str,
        expected_counting_method: str, new_counting_method: str,
        preview_id: str, confirmation_token: str, expires_at: int,
        execution_id: str, confirmed: bool,
    ) -> dict:
        """Claim a Cuan preview, update one test key event, verify, and finalize."""
        try:
            return await service.execute(key(), property_id, key_event_id,
                expected_event_name, expected_counting_method, new_counting_method,
                preview_id, confirmation_token, expires_at, execution_id, confirmed)
        except HostedGa4Error as exc:
            raise ValueError(f"{exc.code}: {exc}") from None

    server.hosted_service = service
    return server


class PrivateIngress:
    """Authenticate transport requests before MCP parsing or any provider action."""

    def __init__(self, app: Any, secret: str):
        if len(secret) < 32:
            raise ValueError("GA4_INGRESS_SECRET must contain at least 32 characters")
        self.app, self.secret = app, secret

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return
        headers = {name.lower(): value for name, value in scope.get("headers", [])}
        supplied = headers.get(b"x-cuan-ga4-ingress-secret", b"").decode("ascii", "ignore")
        key = headers.get(b"x-cuan-mcp-connection-key", b"").decode("ascii", "ignore")
        length = headers.get(b"content-length", b"0")
        allowed = (scope["type"] == "http" and scope.get("path") == "/mcp" and
                   scope.get("method") == "POST" and KEY.fullmatch(key) is not None and
                   hmac.compare_digest(supplied, self.secret) and
                   length.isdigit() and int(length) <= 65536)
        if not allowed:
            await send({"type": "http.response.start", "status": 403,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"cache-control", b"no-store")]})
            await send({"type": "http.response.body", "body": b'{"error":"denied"}'})
            return
        marker = _connection_key.set(key)
        try:
            await self.app(scope, receive, send)
        finally:
            _connection_key.reset(marker)


def create_app(server: FastMCP | None = None, ingress_secret: str | None = None) -> PrivateIngress:
    server = server or create_hosted_server()
    secret = ingress_secret or os.environ["GA4_INGRESS_SECRET"]
    return PrivateIngress(server.streamable_http_app(), secret)


def run_hosted_server() -> None:
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT is invalid")
    host = os.environ["GA4_MCP_ALLOWED_HOST"]
    if not host or "*" in host or "/" in host or len(host) > 255:
        raise ValueError("GA4_MCP_ALLOWED_HOST must be one exact Host header")
    uvicorn.run(create_app(create_hosted_server(allowed_host=host)),
                host="0.0.0.0", port=port, access_log=False)


if __name__ == "__main__":
    run_hosted_server()
