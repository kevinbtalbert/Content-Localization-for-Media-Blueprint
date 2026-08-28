/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import logger from "../../utils/logger";
import contentLocalization from "./content-localization";
import type { WebSocket } from "ws";

const handlers = {
  "/content-localization": contentLocalization,
};

export default function socketHandlers(path: string, ws: WebSocket) {
  if (handlers[path as keyof typeof handlers]) {
    handlers[path as keyof typeof handlers](ws, path);
  } else {
    logger.error(`[WS] Invalid connection request, url: ${path}`);
    ws.send("404");
  }
}
