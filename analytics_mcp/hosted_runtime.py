# Copyright 2026 Cuan Insight contributors.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
"""Bounded, Cuan-authorized GA4 operations for the separate hosted MCP service."""

import hashlib
import json
import re
import time
from datetime import date
from typing import Any

import httpx

KEY = re.compile(r"^ci_mcp_ck_[0-9a-f]{64}$")
ID = re.compile(r"^[1-9][0-9]{0,18}$")
EVENT = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,39}$")
OPAQUE = re.compile(r"^[A-Za-z0-9._:-]{1,256}$")
EXECUTION = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
METHODS = {"ONCE_PER_EVENT", "ONCE_PER_SESSION"}
READ_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
EDIT_SCOPE = "https://www.googleapis.com/auth/analytics.edit"
PREVIEW_TTL_MS = 300_000


class HostedGa4Error(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def deny() -> HostedGa4Error:
    return HostedGa4Error("NOT_AUTHORIZED", "Cuan GA4 authorization was not available")


def invalid() -> HostedGa4Error:
    return HostedGa4Error("INVALID_INPUT", "Invalid GA4 property, date, or key-event input")


def numeric(value: Any) -> str:
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise invalid()
    return value


def opaque(value: Any) -> bool:
    return isinstance(value, str) and OPAQUE.fullmatch(value) is not None


def binding_equal(actual: dict, expected: dict) -> bool:
    return all(actual.get(key) == value for key, value in expected.items())


def same_grant_identity(before: dict, after: dict) -> bool:
    fields = ("provider", "operation", "propertyId", "keyEventId", "scope",
              "disposableTestProperty", "ownedTestProperty", "grantId", "credentialRef")
    return all(before.get(field) == after.get(field) for field in fields)


def digest(change: dict, grant: dict, expires_at: int) -> str:
    values = ["update_key_event", change["propertyId"], change["keyEventId"],
              change["expectedEventName"], change["expectedCountingMethod"],
              change["newCountingMethod"], grant["policyRevision"],
              grant["grantId"], grant["credentialRef"], expires_at]
    return hashlib.sha256(json.dumps(values, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


class CuanGa4Control:
    """Never store provider credentials; Cuan validates the key on every action."""

    def __init__(self, endpoint: str, service_id: str, service_secret: str,
                 client: httpx.AsyncClient | None = None):
        if not endpoint.startswith("https://") or not service_id or len(service_id) > 128 or len(service_secret) < 32:
            raise ValueError("Cuan GA4 private runtime configuration is invalid")
        self.endpoint, self.service_id, self.service_secret = endpoint, service_id, service_secret
        self.client = client or httpx.AsyncClient(timeout=10.0, follow_redirects=False)

    async def call(self, key: str, action: str, request: dict) -> dict:
        if not isinstance(key, str) or not KEY.fullmatch(key):
            raise deny()
        try:
            response = await self.client.post(self.endpoint, json={"action": action, "request": request},
                headers={"x-cuan-ga4-service-id": self.service_id,
                         "x-cuan-ga4-service-secret": self.service_secret,
                         "x-cuan-mcp-connection-key": key})
            response.raise_for_status()
            value = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise deny() from exc
        if not isinstance(value, dict) or value.get("ok") is False:
            raise deny()
        return value


class GoogleGa4Rest:
    """Only server-built GA4 requests; no caller-supplied URL, dimensions, or metrics."""

    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client or httpx.AsyncClient(timeout=15.0, follow_redirects=False)

    async def request(self, token: str, method: str, url: str, body: dict | None = None) -> dict:
        if not isinstance(token, str) or not token or len(token) > 8192:
            raise deny()
        try:
            response = await self.client.request(method, url, json=body,
                headers={"authorization": f"Bearer {token}"})
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HostedGa4Error("PROVIDER_FAILURE", "GA4 request failed") from exc
        if not isinstance(data, dict):
            raise HostedGa4Error("PROVIDER_RESPONSE_INVALID", "GA4 response was invalid")
        return data

    async def report(self, token: str, property_id: str, since: str, until: str) -> dict:
        return await self.request(token, "POST",
            f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport",
            {"dateRanges": [{"startDate": since, "endDate": until}],
             "dimensions": [{"name": "date"}], "metrics": [{"name": "activeUsers"}],
             "limit": "31", "offset": "0"})

    async def key_event(self, token: str, property_id: str, event_id: str) -> dict:
        return await self.request(token, "GET",
            f"https://analyticsadmin.googleapis.com/v1beta/properties/{property_id}/keyEvents/{event_id}")

    async def update_event(self, token: str, property_id: str, event_id: str, method: str) -> dict:
        name = f"properties/{property_id}/keyEvents/{event_id}"
        return await self.request(token, "PATCH",
            f"https://analyticsadmin.googleapis.com/v1beta/{name}?updateMask=counting_method",
            {"name": name, "countingMethod": method})


class HostedGa4Service:
    def __init__(self, control: CuanGa4Control, google: GoogleGa4Rest,
                 now: Any = None):
        self.control, self.google, self.now = control, google, now or (lambda: int(time.time() * 1000))

    async def grant(self, key: str, operation: str, property_id: str,
                    event_id: str | None = None) -> dict:
        request = {"operation": operation, "propertyId": property_id}
        if event_id is not None:
            request["keyEventId"] = event_id
        grant = await self.control.call(key, "authorize", request)
        if (grant.get("allowed") is not True or grant.get("provider") != "google_analytics" or
            grant.get("operation") != operation or grant.get("propertyId") != property_id or
            grant.get("keyEventId") != event_id or grant.get("scope") !=
            (READ_SCOPE if operation == "run_daily_report" else EDIT_SCOPE) or
            not all(opaque(grant.get(field)) for field in ("grantId", "policyRevision", "credentialRef")) or
            (operation == "update_key_event" and (grant.get("disposableTestProperty") is not True or
                                                  grant.get("ownedTestProperty") is not True))):
            raise deny()
        return grant

    async def token(self, key: str, property_id: str, grant: dict) -> str:
        result = await self.control.call(key, "resolveCredential",
            {"provider": "google_analytics", "operation": grant["operation"],
             "propertyId": property_id,
             "credentialRef": grant["credentialRef"]})
        token = result.get("accessToken")
        if not isinstance(token, str) or not token or len(token) > 8192:
            raise deny()
        return token

    async def run_daily_report(self, key: str, property_id: str, since: str, until: str) -> dict:
        numeric(property_id)
        try:
            start, end = date.fromisoformat(since), date.fromisoformat(until)
            if start.isoformat() != since or end.isoformat() != until or not 0 <= (end - start).days <= 30:
                raise ValueError()
        except (TypeError, ValueError):
            raise invalid() from None
        grant = await self.grant(key, "run_daily_report", property_id)
        token = await self.token(key, property_id, grant)
        response = await self.google.report(token, property_id, since, until)
        rows = response.get("rows", [])
        count = response.get("rowCount")
        if not isinstance(rows, list) or len(rows) > 31 or type(count) is not int or not 0 <= count <= 31:
            raise HostedGa4Error("PROVIDER_RESPONSE_INVALID", "GA4 report response was invalid")
        output = []
        for row in rows:
            try:
                if (not isinstance(row["dimensionValues"], list) or
                    not isinstance(row["metricValues"], list) or
                    len(row["dimensionValues"]) != 1 or len(row["metricValues"]) != 1):
                    raise ValueError()
                raw_date = row["dimensionValues"][0]["value"]
                raw_users = row["metricValues"][0]["value"]
                parsed = date(int(raw_date[:4]), int(raw_date[4:6]), int(raw_date[6:8]))
                if not re.fullmatch(r"\d{8}", raw_date) or not re.fullmatch(r"\d+", raw_users):
                    raise ValueError()
                users = int(raw_users)
                if users > 2**53 - 1:
                    raise ValueError()
                output.append({"date": parsed.isoformat(), "activeUsers": users})
            except (KeyError, IndexError, TypeError, ValueError):
                raise HostedGa4Error("PROVIDER_RESPONSE_INVALID", "GA4 report row was invalid") from None
        return {"propertyId": property_id, "rows": output, "rowCount": count}

    @staticmethod
    def validate_change(property_id: str, event_id: str, event_name: str,
                        old: str, new: str) -> dict:
        numeric(property_id); numeric(event_id)
        if not isinstance(event_name, str) or not EVENT.fullmatch(event_name) or old not in METHODS or new not in METHODS or old == new:
            raise invalid()
        return {"propertyId": property_id, "keyEventId": event_id,
                "expectedEventName": event_name, "expectedCountingMethod": old,
                "newCountingMethod": new}

    async def read_event(self, token: str, change: dict) -> dict:
        data = await self.google.key_event(token, change["propertyId"], change["keyEventId"])
        if (data.get("name") != f'properties/{change["propertyId"]}/keyEvents/{change["keyEventId"]}' or
            data.get("custom") is not True or not isinstance(data.get("eventName"), str) or
            data.get("countingMethod") not in METHODS):
            raise HostedGa4Error("PROVIDER_RESPONSE_INVALID", "GA4 key event was invalid")
        return data

    @staticmethod
    def assert_preconditions(current: dict, change: dict) -> None:
        if current["eventName"] != change["expectedEventName"] or current["countingMethod"] != change["expectedCountingMethod"]:
            raise HostedGa4Error("STALE_KEY_EVENT", "GA4 key event changed since preview")

    async def preview(self, key: str, property_id: str, event_id: str, event_name: str,
                      old: str, new: str) -> dict:
        change = self.validate_change(property_id, event_id, event_name, old, new)
        grant = await self.grant(key, "update_key_event", property_id, event_id)
        token = await self.token(key, property_id, grant)
        refreshed_grant = await self.grant(key, "update_key_event", property_id, event_id)
        if not same_grant_identity(grant, refreshed_grant):
            raise deny()
        self.assert_preconditions(await self.read_event(token, change), change)
        expiry = self.now() + PREVIEW_TTL_MS
        binding = {**change, "requestDigest": digest(change, refreshed_grant, expiry), "expiresAt": expiry}
        preview = await self.control.call(key, "issuePreview", binding)
        if not binding_equal(preview, binding) or not opaque(preview.get("previewId")) or not opaque(preview.get("confirmationToken")) or preview.get("expiresAt", 0) <= self.now():
            raise deny()
        return {**binding, "previewId": preview["previewId"],
                "confirmationToken": preview["confirmationToken"], "restoreCountingMethod": old}

    async def execute(self, key: str, property_id: str, event_id: str, event_name: str,
                      old: str, new: str, preview_id: str, confirmation_token: str,
                      expires_at: int, execution_id: str, confirmed: bool) -> dict:
        change = self.validate_change(property_id, event_id, event_name, old, new)
        if confirmed is not True:
            raise HostedGa4Error("CONFIRMATION_REQUIRED", "Explicit key-event confirmation is required")
        if (not opaque(preview_id) or not opaque(confirmation_token) or not isinstance(execution_id, str) or
            not EXECUTION.fullmatch(execution_id) or type(expires_at) is not int or
            not self.now() < expires_at <= self.now() + PREVIEW_TTL_MS):
            raise invalid()
        grant = await self.grant(key, "update_key_event", property_id, event_id)
        binding = {**change, "requestDigest": digest(change, grant, expires_at), "expiresAt": expires_at}
        claim = await self.control.call(key, "claimExecution",
            {**binding, "previewId": preview_id, "confirmationToken": confirmation_token,
             "executionId": execution_id})
        if not binding_equal(claim, binding) or claim.get("claimed") is not True or claim.get("previewId") != preview_id or claim.get("executionId") != execution_id:
            raise deny()
        outcome, error = "not_dispatched", None
        try:
            token = await self.token(key, property_id, grant)
            self.assert_preconditions(await self.read_event(token, change), change)
        except Exception as exc:
            error = exc
        if error is None:
            outcome = "uncertain"
            try:
                updated = await self.google.update_event(token, property_id, event_id, new)
                if updated.get("name") != f"properties/{property_id}/keyEvents/{event_id}" or updated.get("countingMethod") != new:
                    raise ValueError("GA4 write response mismatch")
                after = await self.read_event(token, change)
                if after.get("eventName") != event_name or after.get("countingMethod") != new:
                    raise ValueError("GA4 write readback mismatch")
                outcome = "confirmed"
            except Exception:
                error = HostedGa4Error("UNKNOWN_OUTCOME", "GA4 update outcome is unknown; inspect before another action")
        disposition = {"confirmed": "consume", "not_dispatched": "release", "uncertain": "preserve"}[outcome]
        final = {**binding, "previewId": preview_id, "executionId": execution_id,
                 "outcome": outcome, "reservationDisposition": disposition}
        try:
            ack = await self.control.call(key, "finalizeExecution", final)
            if not binding_equal(ack, final) or ack.get("acknowledged") is not True:
                raise ValueError("Cuan ACK mismatch")
        except Exception:
            raise HostedGa4Error("FINALIZATION_UNKNOWN", "Cuan finalization was not acknowledged; inspect before another action") from None
        if error is not None:
            if isinstance(error, HostedGa4Error):
                raise error
            raise HostedGa4Error("PROVIDER_UNAVAILABLE", "GA4 client was unavailable") from None
        return {"propertyId": property_id, "keyEventId": event_id,
                "eventName": event_name, "oldCountingMethod": old, "countingMethod": new,
                "restoreCountingMethod": old, "executionId": execution_id}
