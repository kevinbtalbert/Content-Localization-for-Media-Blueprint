/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import { NextRequest } from "next/server";
import path from "path";
import { nextFileServe } from "@/app/api/utils/nextFileServe";

export async function GET(request: NextRequest, { params }: { params: Promise<{ filename: string }> }) {
  const { filename } = await params;

  const INPUT_DIR = process.env.INPUT_DIR ? `${process.env.INPUT_DIR}` : path.join(process.cwd(), "../../", "assets");

  const filePath = path.join(INPUT_DIR, path.basename(filename));

  return nextFileServe(filePath, request);
}
