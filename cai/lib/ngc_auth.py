"""Resolve and validate NGC credentials for NIM model downloads."""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


NGC_TOKEN_STATUS_URL = "https://api.ngc.nvidia.com/v2/token/status"
NGC_AUTHN_URL = "https://authn.nvidia.com/token"
NVCR_REGISTRY = "https://nvcr.io/v2"


@dataclass(frozen=True)
class NgcAuthResult:
    bearer_token: str
    method: str
    detail: str


def _http_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: float = 30.0,
) -> tuple[int, dict[str, Any] | str]:
    req = urllib.request.Request(url, data=data, method=method)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw


def _decode_client_credentials(raw_key: str) -> tuple[str, str] | None:
    """Return (client_id, client_secret) when raw_key is base64-encoded id:secret."""
    try:
        padded = raw_key + "=" * (-len(raw_key) % 4)
        decoded = base64.b64decode(padded).decode("utf-8")
    except Exception:
        return None
    if ":" not in decoded:
        return None
    client_id, client_secret = decoded.split(":", 1)
    if not client_id or not client_secret:
        return None
    return client_id, client_secret


def _basic_oauth_header(token: str) -> str:
    encoded = base64.b64encode(f"$oauthtoken:{token}".encode()).decode("ascii")
    return f"Basic {encoded}"


def _exchange_client_credentials(client_id: str, client_secret: str) -> tuple[NgcAuthResult | None, str]:
    body = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
    ).encode()
    status, payload = _http_json(
        NGC_AUTHN_URL,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=body,
    )
    if status != 200 or not isinstance(payload, dict):
        return None, f"client_credentials exchange: HTTP {status} {payload!r}"
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        return None, f"client_credentials exchange: missing access_token in {payload!r}"
    return (
        NgcAuthResult(
            bearer_token=token,
            method="client_credentials",
            detail="Exchanged base64 client_id:secret via authn.nvidia.com",
        ),
        "",
    )


def _token_status_ok(token: str, *, auth_scheme: str) -> tuple[bool, str]:
    if auth_scheme == "basic":
        headers = {"Authorization": _basic_oauth_header(token)}
    else:
        headers = {"Authorization": f"Bearer {token}"}
    status, payload = _http_json(NGC_TOKEN_STATUS_URL, headers=headers)
    if status == 200:
        return True, ""
    return False, f"HTTP {status} {payload!r}"


def resolve_ngc_bearer_token(raw_key: str | None = None) -> NgcAuthResult:
    """
    Resolve a usable NGC bearer token from NGC_API_KEY.

    Accepts:
      - Portal API key (Bearer auth works directly)
      - Base64-encoded client_id:client_secret (NGC CLI config format)
    """
    api_key = (raw_key or os.environ.get("NGC_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError(
            "NGC_API_KEY is not set. Add it in AMP Configure Project or "
            "Project Settings → Advanced → Environment."
        )

    errors: list[str] = []
    candidates: list[NgcAuthResult] = []

    creds = _decode_client_credentials(api_key)
    if creds:
        exchanged, exchange_error = _exchange_client_credentials(*creds)
        if exchanged:
            candidates.append(exchanged)
        elif exchange_error:
            errors.append(exchange_error)

    candidates.append(
        NgcAuthResult(
            bearer_token=api_key,
            method="portal_api_key",
            detail="Portal API key from NGC Setup",
        )
    )

    for candidate in candidates:
        for scheme in ("bearer", "basic"):
            ok, detail = _token_status_ok(candidate.bearer_token, auth_scheme=scheme)
            label = f"{candidate.method}/{scheme}"
            if ok:
                return NgcAuthResult(
                    bearer_token=candidate.bearer_token,
                    method=label,
                    detail=candidate.detail,
                )
            errors.append(f"{label}: {detail}")

    raise RuntimeError(
        "NGC authentication failed. "
        "Generate an API key at https://org.ngc.nvidia.com/setup/api-key and set NGC_API_KEY. "
        f"Attempts: {'; '.join(errors)}"
    )


def _registry_bearer_token(api_token: str, repository: str) -> tuple[str | None, str]:
    scope = f"repository:{repository}:pull"
    auth_url = f"https://nvcr.io/proxy/v2/auth?service=nvcr.io&scope={urllib.parse.quote(scope, safe='')}"
    attempts = [
        ("bearer", {"Authorization": f"Bearer {api_token}"}),
        ("basic", {"Authorization": _basic_oauth_header(api_token)}),
    ]
    last_error = ""
    for label, headers in attempts:
        status, payload = _http_json(auth_url, headers=headers)
        if status == 200 and isinstance(payload, dict):
            registry_token = payload.get("token") or payload.get("access_token")
            if isinstance(registry_token, str) and registry_token:
                return registry_token, ""
        last_error = f"{label} registry auth HTTP {status}: {payload!r}"
    return None, last_error


def verify_nvcr_pull_access(bearer_token: str, repository: str, tag: str = "latest") -> tuple[bool, str]:
    """Check registry access by fetching a manifest from nvcr.io."""
    registry_token, auth_error = _registry_bearer_token(bearer_token, repository)
    if not registry_token:
        return False, auth_error

    manifest_url = f"{NVCR_REGISTRY}/{repository}/manifests/{tag}"
    status, manifest_payload = _http_json(
        manifest_url,
        headers={
            "Authorization": f"Bearer {registry_token}",
            "Accept": "application/vnd.docker.distribution.manifest.v2+json",
        },
    )
    if status == 200:
        return True, f"pull OK for {repository}:{tag}"
    if status == 403:
        return False, (
            f"manifest HTTP 403 for {repository}:{tag} — authenticated but not entitled "
            "(AI for Media private access may be required for LipSync)"
        )
    return False, f"manifest HTTP {status}: {manifest_payload!r}"


def verify_nim_model_access() -> list[tuple[str, bool, str]]:
    """Verify NGC auth and pull access for LipSync and ASD NIM images."""
    auth = resolve_ngc_bearer_token()
    checks: list[tuple[str, bool, str]] = [
        ("NGC token status", True, auth.detail),
    ]
    repos = [
        ("LipSync NIM image", "nim/nvidia/lipsync", "1.3.0"),
        ("ASD NIM image", "nim/nvidia/active-speaker-detection", "1.1.0"),
    ]
    for label, repo, tag in repos:
        ok, detail = verify_nvcr_pull_access(auth.bearer_token, repo, tag)
        checks.append((label, ok, detail))
    return checks
