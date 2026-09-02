# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""NVIDIA Cloud Functions (NVCF) gRPC client helpers."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import grpc

# Keep in sync with cai/lib/deploy_mode.py (AMP scripts resolve IDs before PYTHONPATH setup).
DEFAULT_ASD_NVCF_FUNCTION_ID = "f286f937-05c4-454b-8312-fba67a2a6fa7"
# LipSync has no public gRPC Try API page today (AI for Media gated). Leave blank
# until NVIDIA publishes a catalog ID or provides one via the private access program.
DEFAULT_LIPSYNC_NVCF_FUNCTION_ID = ""


def resolve_nvcf_function_id(env_var: str, default: str = "") -> str:
    """Return an env override or the baked-in NVCF function ID default."""
    return os.environ.get(env_var, "").strip() or default


def lipsync_nvcf_function_id() -> str:
    return resolve_nvcf_function_id(
        "LIPSYNC_NVIDIA_FUNCTION_ID",
        DEFAULT_LIPSYNC_NVCF_FUNCTION_ID,
    )


def asd_nvcf_function_id() -> str:
    return resolve_nvcf_function_id(
        "ASD_NVIDIA_FUNCTION_ID",
        DEFAULT_ASD_NVCF_FUNCTION_ID,
    )


def nvcf_grpc_metadata(ngc_api_key: str, function_id: str) -> tuple[tuple[str, str], ...]:
    """Build gRPC metadata required by NVCF serverless NIM endpoints."""
    return (
        ("authorization", f"Bearer {ngc_api_key}"),
        ("function-id", function_id),
    )


class _MetadataClientInterceptor(
    grpc.UnaryUnaryClientInterceptor,
    grpc.UnaryStreamClientInterceptor,
    grpc.StreamUnaryClientInterceptor,
    grpc.StreamStreamClientInterceptor,
):
    """Attach fixed metadata to every outbound client RPC."""

    def __init__(self, metadata: tuple[tuple[str, str], ...]) -> None:
        self._metadata = metadata

    def _inject(
        self,
        continuation: Callable[..., Any],
        client_call_details: grpc.ClientCallDetails,
        request_or_iterator: Any,
    ) -> Any:
        metadata = list(client_call_details.metadata or [])
        metadata.extend(self._metadata)
        details = grpc.interceptors.ClientCallDetails(
            client_call_details.method,
            client_call_details.timeout,
            metadata,
            client_call_details.credentials,
            client_call_details.wait_for_ready,
            client_call_details.compression,
        )
        return continuation(details, request_or_iterator)

    def intercept_unary_unary(self, continuation, client_call_details, request):
        return self._inject(continuation, client_call_details, request)

    def intercept_unary_stream(self, continuation, client_call_details, request):
        return self._inject(continuation, client_call_details, request)

    def intercept_stream_unary(self, continuation, client_call_details, request_iterator):
        return self._inject(continuation, client_call_details, request_iterator)

    def intercept_stream_stream(self, continuation, client_call_details, request_iterator):
        return self._inject(continuation, client_call_details, request_iterator)


def intercept_channel_with_metadata(
    channel: grpc.Channel,
    metadata: tuple[tuple[str, str], ...],
) -> grpc.Channel:
    """Wrap a channel so NVCF auth metadata is sent on every RPC."""
    if not metadata:
        return channel
    return grpc.intercept_channel(channel, _MetadataClientInterceptor(metadata))
