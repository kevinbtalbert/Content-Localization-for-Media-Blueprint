#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Render all Mermaid diagrams in this directory.

This script renders every ``.mmd`` file in ``docs/source/uml_mermaid`` to a
chosen output format using local renderers only.

Rendering modes:
- local: Use Mermaid CLI (``mmdc``) installed on PATH.
- docker: Use Mermaid CLI inside a local Docker container.
- auto: Try local first, then fall back to docker.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_FORMATS: set[str] = {"svg", "png", "pdf"}


@dataclass(slots=True)
class RenderResult:
    """Result for rendering a single diagram."""

    source: Path
    output: Path
    success: bool
    backend: str
    error: str | None = None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render all Mermaid diagrams in a directory.")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Directory containing .mmd files (default: this script directory).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "rendered",
        help="Output directory for rendered files (default: ./rendered).",
    )
    parser.add_argument(
        "--format",
        type=str,
        default="svg",
        choices=sorted(SUPPORTED_FORMATS),
        help="Render output format.",
    )
    parser.add_argument(
        "--renderer",
        type=str,
        default="auto",
        choices=["auto", "local", "docker"],
        help="Rendering backend selection.",
    )
    parser.add_argument(
        "--docker-image",
        type=str,
        default="minlag/mermaid-cli:latest",
        help="Docker image to use for Mermaid CLI rendering.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="Timeout per diagram render operation.",
    )
    parser.add_argument(
        "--puppeteer-config",
        type=Path,
        default=None,
        help=(
            "Path to a Puppeteer JSON config file passed to mmdc via"
            " ``-p``.  Useful in CI to set ``--no-sandbox``."
        ),
    )
    return parser.parse_args()


def _discover_diagrams(source_dir: Path) -> list[Path]:
    return sorted(path for path in source_dir.glob("*.mmd") if path.is_file())


def _render_with_local_mmdc(
    source: Path,
    output: Path,
    timeout_seconds: float,
    puppeteer_config: Path | None = None,
) -> tuple[bool, str | None]:
    """Render a single diagram using a locally installed ``mmdc``.

    Args:
        source: Path to the ``.mmd`` source file.
        output: Desired output file path.
        timeout_seconds: Max seconds to wait for the render.
        puppeteer_config: Optional Puppeteer JSON config passed
            to ``mmdc -p``. Defaults to None.

    Returns:
        A ``(success, error_message)`` tuple.

    Examples:
        >>> ok, err = _render_with_local_mmdc(
        ...     source=Path("diagram.mmd"),
        ...     output=Path("diagram.svg"),
        ...     timeout_seconds=30.0,
        ... )
    """
    mmdc = shutil.which("mmdc")
    if mmdc is None:
        return False, "mmdc not found on PATH"

    cmd = [mmdc, "-i", str(source), "-o", str(output), "-b", "transparent"]
    if puppeteer_config is not None:
        cmd.extend(["-p", str(puppeteer_config)])
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=timeout_seconds)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else str(exc)
        return False, f"mmdc failed: {stderr}"
    except subprocess.TimeoutExpired:
        return False, f"mmdc timed out after {timeout_seconds}s"

    return True, None


def _render_with_docker(
    source: Path, output: Path, timeout_seconds: float, docker_image: str
) -> tuple[bool, str | None]:
    docker = shutil.which("docker")
    if docker is None:
        return False, "docker not found on PATH"

    mount_dir = source.parent.resolve()
    in_name = source.name
    out_name = output.name
    cmd = [
        docker,
        "run",
        "--rm",
        "-u",
        f"{os.getuid()}:{os.getgid()}",
        "-v",
        f"{mount_dir}:/data",
        docker_image,
        "-i",
        f"/data/{in_name}",
        "-o",
        f"/data/{out_name}",
        "-b",
        "transparent",
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=timeout_seconds)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else str(exc)
        return False, f"docker mmdc failed: {stderr}"
    except subprocess.TimeoutExpired:
        return False, f"docker mmdc timed out after {timeout_seconds}s"

    return True, None


def _render_one(
    source: Path,
    output: Path,
    renderer: str,
    timeout_seconds: float,
    docker_image: str,
    puppeteer_config: Path | None = None,
) -> RenderResult:
    if renderer in {"auto", "local"}:
        local_ok, local_error = _render_with_local_mmdc(
            source,
            output,
            timeout_seconds,
            puppeteer_config=puppeteer_config,
        )
        if local_ok:
            return RenderResult(source=source, output=output, success=True, backend="local")
        if renderer == "local":
            return RenderResult(
                source=source,
                output=output,
                success=False,
                backend="local",
                error=local_error,
            )

    docker_ok, docker_error = _render_with_docker(source, output, timeout_seconds, docker_image)
    return RenderResult(
        source=source,
        output=output,
        success=docker_ok,
        backend="docker",
        error=docker_error,
    )


def main() -> int:
    args = _parse_args()
    source_dir: Path = args.source_dir.resolve()
    output_dir: Path = args.output_dir.resolve()
    fmt: str = args.format
    renderer: str = args.renderer
    docker_image: str = args.docker_image
    timeout_seconds: float = args.timeout_seconds
    puppeteer_config: Path | None = args.puppeteer_config

    if not source_dir.exists():
        print(f"Source directory does not exist: {source_dir}")
        return 2

    diagrams = _discover_diagrams(source_dir)
    if not diagrams:
        print(f"No .mmd files found in {source_dir}")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Found {len(diagrams)} Mermaid diagram(s) in {source_dir}")
    print(f"Rendering to {output_dir} as .{fmt} using renderer={renderer}")

    failures = 0
    for source in diagrams:
        output = output_dir / f"{source.stem}.{fmt}"
        result = _render_one(
            source,
            output,
            renderer,
            timeout_seconds,
            docker_image,
            puppeteer_config=puppeteer_config,
        )
        if result.success:
            print(f"[OK]   {source.name} -> {output.name} ({result.backend})")
        else:
            failures += 1
            print(f"[FAIL] {source.name}: {result.error}")

    success_count = len(diagrams) - failures
    print(f"Completed: {success_count}/{len(diagrams)} rendered successfully.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
