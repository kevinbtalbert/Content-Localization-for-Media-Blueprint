/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import { execFile } from "child_process";
import path from "path";
import { promisify } from "util";
import { NextResponse } from "next/server";

const execFileAsync = promisify(execFile);

function projectRoot(): string {
  return process.env.CDSW_PROJECT_DIR || "/home/cdsw";
}

function pythonPath(): string {
  const root = projectRoot();
  const venv = path.join(root, ".venv", "bin", "python");
  return process.env.PYTHON_PATH || venv;
}

async function runControlPlane(command: string, extraArgs: string[] = []): Promise<unknown> {
  const root = projectRoot();
  const script = path.join(root, "cai/amp/7_deploy/control_plane_cli.py");
  const { stdout } = await execFileAsync(pythonPath(), [script, command, ...extraArgs], {
    cwd: root,
    env: process.env,
    maxBuffer: 10 * 1024 * 1024,
    timeout: 30 * 60 * 1000,
  });
  return JSON.parse(stdout);
}

export async function GET() {
  try {
    const status = await runControlPlane("status");
    return NextResponse.json(status);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to load deployment status";
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

    if (action === "deploy") {
      const result = await runControlPlane("deploy");
      return NextResponse.json(result);
    }

    return NextResponse.json({ error: `Unknown action: ${action}` }, { status: 400 });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Deployment action failed";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
