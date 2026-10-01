"""Focused hosted-mode contract tests; never contact Cuan or Google."""

import httpx
import pytest
from starlette.testclient import TestClient

from analytics_mcp.hosted_runtime import (CuanGa4Control, HostedGa4Error,
                                          HostedGa4Service, READ_SCOPE, EDIT_SCOPE)
from analytics_mcp.hosted_server import PrivateIngress, create_app, create_hosted_server

KEY = "ci_mcp_ck_" + "a" * 64
SECRET = "s" * 32


class Control:
    def __init__(self):
        self.actions = []
        self.claimed = False
        self.final = None
        self.grant_ref = "ref:1"

    async def call(self, key, action, request):
        assert key == KEY
        self.actions.append((action, request))
        if action == "authorize":
            write = request["operation"] == "update_key_event"
            return {"allowed": True, "provider": "google_analytics", **request,
                    "scope": EDIT_SCOPE if write else READ_SCOPE,
                    "disposableTestProperty": write, "ownedTestProperty": write,
                    "grantId": "grant:1", "policyRevision": "rev:1",
                    "credentialRef": self.grant_ref}
        if action == "resolveCredential":
            assert request["credentialRef"] == self.grant_ref
            return {"accessToken": "ephemeral"}
        if action == "issuePreview":
            return {**request, "previewId": "preview:1", "confirmationToken": "confirm:1"}
        if action == "claimExecution":
            if self.claimed:
                return {"ok": False}
            self.claimed = True
            return {**request, "claimed": True}
        if action == "finalizeExecution":
            self.final = request
            return {**request, "acknowledged": True}
        raise AssertionError(action)


class Google:
    def __init__(self):
        self.writes = 0
        self.method = "ONCE_PER_EVENT"
        self.fail_after_write = False

    async def report(self, token, property_id, since, until):
        assert (token, property_id) == ("ephemeral", "123")
        return {"rowCount": 1, "rows": [{"dimensionValues": [{"value": "20260930"}],
                                          "metricValues": [{"value": "7"}]}]}

    async def key_event(self, token, property_id, event_id):
        assert token == "ephemeral"
        if self.fail_after_write and self.writes:
            raise RuntimeError("readback unavailable")
        return {"name": f"properties/{property_id}/keyEvents/{event_id}",
                "custom": True, "eventName": "purchase_test", "countingMethod": self.method}

    async def update_event(self, token, property_id, event_id, method):
        self.writes += 1
        self.method = method
        return {"name": f"properties/{property_id}/keyEvents/{event_id}",
                "countingMethod": method}


@pytest.mark.asyncio
async def test_report_is_bounded_and_rechecks_cuan():
    control, google = Control(), Google()
    service = HostedGa4Service(control, google)
    assert await service.run_daily_report(KEY, "123", "2026-09-30", "2026-09-30") == {
        "propertyId": "123", "rows": [{"date": "2026-09-30", "activeUsers": 7}], "rowCount": 1}
    assert [a for a, _ in control.actions] == ["authorize", "resolveCredential"]
    with pytest.raises(HostedGa4Error):
        await service.run_daily_report(KEY, "123", "2026-01-01", "2026-02-02")
    with pytest.raises(HostedGa4Error):
        await service.run_daily_report(KEY, "123", "2026-02-30", "2026-03-01")
    assert len(control.actions) == 2


@pytest.mark.asyncio
async def test_preview_claim_finalize_and_replay_denied():
    control, google = Control(), Google()
    service = HostedGa4Service(control, google, now=lambda: 1_000_000)
    preview = await service.preview(KEY, "123", "456", "purchase_test",
        "ONCE_PER_EVENT", "ONCE_PER_SESSION")
    assert len(preview["requestDigest"]) == 64
    assert preview["expiresAt"] == 1_300_000
    result = await service.execute(KEY, "123", "456", "purchase_test",
        "ONCE_PER_EVENT", "ONCE_PER_SESSION", preview["previewId"],
        preview["confirmationToken"], preview["expiresAt"], "execute_123", True)
    assert result["countingMethod"] == "ONCE_PER_SESSION"
    assert google.writes == 1
    assert (control.final["outcome"], control.final["reservationDisposition"]) == ("confirmed", "consume")
    with pytest.raises(HostedGa4Error) as exc:
        await service.execute(KEY, "123", "456", "purchase_test",
            "ONCE_PER_EVENT", "ONCE_PER_SESSION", preview["previewId"],
            preview["confirmationToken"], preview["expiresAt"], "execute_123", True)
    assert exc.value.code == "NOT_AUTHORIZED"
    assert google.writes == 1


@pytest.mark.asyncio
async def test_uncertain_write_preserves_reservation():
    control, google = Control(), Google()
    google.fail_after_write = True
    service = HostedGa4Service(control, google, now=lambda: 1_000_000)
    preview = await service.preview(KEY, "123", "456", "purchase_test",
        "ONCE_PER_EVENT", "ONCE_PER_SESSION")
    with pytest.raises(HostedGa4Error) as exc:
        await service.execute(KEY, "123", "456", "purchase_test",
            "ONCE_PER_EVENT", "ONCE_PER_SESSION", preview["previewId"],
            preview["confirmationToken"], preview["expiresAt"], "execute_123", True)
    assert exc.value.code == "UNKNOWN_OUTCOME"
    assert (control.final["outcome"], control.final["reservationDisposition"]) == ("uncertain", "preserve")


@pytest.mark.asyncio
async def test_bad_grant_prevents_provider_call():
    control, google = Control(), Google()
    control.grant_ref = "invalid ref"
    service = HostedGa4Service(control, google)
    with pytest.raises(HostedGa4Error) as exc:
        await service.run_daily_report(KEY, "123", "2026-09-30", "2026-09-30")
    assert exc.value.code == "NOT_AUTHORIZED"
    assert len(control.actions) == 1


@pytest.mark.asyncio
async def test_cuan_transport_fails_closed_and_sends_both_proofs():
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"allowed": True})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    control = CuanGa4Control("https://cuan.example/functions/v1/ga4-runtime", "service", SECRET, client)
    assert await control.call(KEY, "authorize", {"propertyId": "123"}) == {"allowed": True}
    assert seen[0].headers["x-cuan-mcp-connection-key"] == KEY
    assert seen[0].headers["x-cuan-ga4-service-secret"] == SECRET
    with pytest.raises(HostedGa4Error):
        await control.call("wrong", "authorize", {})
    assert len(seen) == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_ingress_rejects_missing_secret_before_mcp():
    calls = []
    async def app(scope, receive, send):
        calls.append(scope)
    gate = PrivateIngress(app, SECRET)
    sent = []
    async def send(message):
        sent.append(message)
    scope = {"type": "http", "path": "/mcp", "method": "POST",
             "headers": [(b"x-cuan-mcp-connection-key", KEY.encode()),
                         (b"content-length", b"10")]}
    await gate(scope, None, send)
    assert sent[0]["status"] == 403 and not calls
    scope["headers"].append((b"x-cuan-ga4-ingress-secret", SECRET.encode()))
    await gate(scope, None, send)
    assert len(calls) == 1


def test_stateless_mcp_transports_connection_key_to_tool():
    control, google = Control(), Google()
    app = create_app(create_hosted_server(control, google), SECRET)
    headers = {"x-cuan-ga4-ingress-secret": SECRET,
               "x-cuan-mcp-connection-key": KEY,
               "accept": "application/json, text/event-stream",
               "content-type": "application/json"}
    initialize = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                             "clientInfo": {"name": "test", "version": "1"}}}
    call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "analytics_run_daily_report",
                       "arguments": {"property_id": "123", "since": "2026-09-30",
                                     "until": "2026-09-30"}}}
    with TestClient(app, base_url="http://localhost:8000") as client:
        assert client.post("/mcp", headers=headers, json=initialize).status_code == 200
        result = client.post("/mcp", headers=headers, json=call)
        assert result.status_code == 200
        assert result.json()["result"]["isError"] is False
        denied = client.post("/mcp", headers={k: v for k, v in headers.items()
                                              if k != "x-cuan-ga4-ingress-secret"}, json=call)
        assert denied.status_code == 403
    assert [a for a, _ in control.actions] == ["authorize", "resolveCredential"]


@pytest.mark.asyncio
async def test_confirmation_and_claim_failure_never_dispatch_write():
    control, google = Control(), Google()
    service = HostedGa4Service(control, google, now=lambda: 1_000_000)
    preview = await service.preview(KEY, "123", "456", "purchase_test",
        "ONCE_PER_EVENT", "ONCE_PER_SESSION")
    args = (KEY, "123", "456", "purchase_test", "ONCE_PER_EVENT",
            "ONCE_PER_SESSION", preview["previewId"],
            preview["confirmationToken"], preview["expiresAt"], "execute_123")
    with pytest.raises(HostedGa4Error) as exc:
        await service.execute(*args, False)
    assert exc.value.code == "CONFIRMATION_REQUIRED"
    assert google.writes == 0 and not control.claimed
    control.claimed = True
    with pytest.raises(HostedGa4Error) as exc:
        await service.execute(*args, True)
    assert exc.value.code == "NOT_AUTHORIZED"
    assert google.writes == 0


@pytest.mark.asyncio
async def test_stale_event_releases_claim_without_dispatch():
    control, google = Control(), Google()
    service = HostedGa4Service(control, google, now=lambda: 1_000_000)
    preview = await service.preview(KEY, "123", "456", "purchase_test",
        "ONCE_PER_EVENT", "ONCE_PER_SESSION")
    google.method = "ONCE_PER_SESSION"
    with pytest.raises(HostedGa4Error) as exc:
        await service.execute(KEY, "123", "456", "purchase_test",
            "ONCE_PER_EVENT", "ONCE_PER_SESSION", preview["previewId"],
            preview["confirmationToken"], preview["expiresAt"], "execute_123", True)
    assert exc.value.code == "STALE_KEY_EVENT"
    assert google.writes == 0
    assert (control.final["outcome"], control.final["reservationDisposition"]) == (
        "not_dispatched", "release")
