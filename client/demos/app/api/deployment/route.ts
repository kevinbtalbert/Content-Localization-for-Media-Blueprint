/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import { execFile, spawn } from "child_process";
import fs from "fs";
import path from "path";
import { promisify } from "util";
import { NextResponse } from "next/server";

const execFileAsync = promisify(execFile);

function projectRoot(): string {
  return process.env.CDSW_PROJECT_DIR || "/home/cdsw";
}

function pythonPath(): string {
  const root = projectRoot();
  const candidates = [
    process.env.PYTHON_PATH,
    path.join(root, ".venv", "bin", "python"),
    path.join(root, ".venv", "bin", "python3"),
    "/opt/content-localization/.venv/bin/python",
    "python3",
  ].filter(Boolean) as string[];
  for (const candidate of candidates) {
    try {
      if (candidate.includes("/") && !fs.existsSync(candidate)) {
        continue;
      }
      return candidate;
    } catch {
      continue;
    }
  }
  return "python3";
}

function controlPlaneScript(): string {
  return path.join(projectRoot(), "cai/amp/7_deploy/control_plane_cli.py");
}

async function runControlPlane(command: string, extraArgs: string[] = []): Promise<unknown> {
  const root = projectRoot();
  const { stdout } = await execFileAsync(pythonPath(), [controlPlaneScript(), command, ...extraArgs], {
    cwd: root,
    env: process.env,
    maxBuffer: 10 * 1024 * 1024,
    timeout: command === "build" || command === "deploy" ? 30 * 60 * 1000 : 120 * 1000,
  });
  return JSON.parse(stdout);
}

async function runControlPlaneAllowFailure(
  command: string,
  extraArgs: string[] = [],
): Promise<{ ok: boolean; data: unknown; exitCode: number }> {
  const root = projectRoot();
  try {
    const { stdout } = await execFileAsync(pythonPath(), [controlPlaneScript(), command, ...extraArgs], {
      cwd: root,
      env: process.env,
      maxBuffer: 10 * 1024 * 1024,
      timeout: 120 * 1000,
    });
    return { ok: true, data: JSON.parse(stdout), exitCode: 0 };
  } catch (error) {
    const execError = error as { stdout?: string; code?: number };
    const raw = execError.stdout?.trim();
    let data: unknown = { error: "Validation failed" };
    if (raw) {
      try {
        data = JSON.parse(raw);
      } catch {
        data = { error: raw };
      }
    }
    return { ok: false, data, exitCode: execError.code ?? 1 };
  }
}

function startBackgroundBuild(): void {
  const root = projectRoot();
  const child = spawn(pythonPath(), [controlPlaneScript(), "build"], {
    cwd: root,
    env: process.env,
    detached: true,
    stdio: "ignore",
  });
  child.unref();
}

export async function GET() {
  try {
    const status = await runControlPlane("status");
    return NextResponse.json(status);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to load pipeline status";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const action = body.action as string;

    if (action === "save-config") {
      const configJson = JSON.stringify(body.config ?? {});
      const result = await runControlPlane("save-config", ["--config-json", configJson]);
      return NextResponse.json(result);
    }

    if (action === "validate") {
      const configJson = JSON.stringify(body.config ?? {});
      const result = await runControlPlaneAllowFailure("validate", ["--config-json", configJson]);
      if (!result.ok) {
        return NextResponse.json(result.data, { status: 400 });
      }
      return NextResponse.json(result.data);
    }

    if (action === "build" || action === "deploy") {
      const configJson = body.config ? JSON.stringify(body.config) : "";
      if (configJson) {
        await runControlPlane("save-config", ["--config-json", configJson]);
      }
      const validation = await runControlPlaneAllowFailure(
        "validate",
        configJson ? ["--config-json", configJson] : [],
      );
      if (!validation.ok) {
        return NextResponse.json(validation.data, { status: 400 });
      }
      startBackgroundBuild();
      return NextResponse.json({
        started: true,
        message: "Pipeline build started. Stay on this page for live progress.",
        validation: validation.data,
      });
    }

    return NextResponse.json({ error: `Unknown action: ${action}` }, { status: 400 });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Pipeline action failed";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
