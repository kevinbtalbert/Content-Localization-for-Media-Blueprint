/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import { createServer } from "http";
import { parse } from "url";
import next from "next";
import { WebSocketServer } from "ws";
import socketHandlers from "./api/socketHandlers";
import logger from "./utils/logger";

const port = parseInt(process.env.CDSW_APP_PORT || process.env.PORT || "3000", 10);
const dev = process.env.NODE_ENV !== "production";
const app = next({ dev });
const handle = app.getRequestHandler();

const WEBSOCKET_PATH_PREFIX = "/api/ws";

app.prepare().then(() => {
  const server = createServer((req, res) => {
    const parsedUrl = parse(req.url!, true);
    handle(req, res, parsedUrl);
  }).listen(port);

  const wss = new WebSocketServer({
    server,
    maxPayload: 100 * 1024 * 1024,
    perMessageDeflate: false,
  });

  wss.on("connection", function connection(ws, request) {
    const url = request.url!;
    logger.info(`[WS] Connection request received for ${url}`);

    ws.on("error", (error) => {
      logger.error(`[WS] Connection error for ${url}:`, error);
    });

    ws.on("close", function close() {
      logger.info(`[WS] Connection closed for ${url}`);
    });

    const relativePath = url.split(WEBSOCKET_PATH_PREFIX)[1];

    socketHandlers(relativePath, ws);
  });

  logger.info(`> Server listening at http://localhost:${port} as ${dev ? "development" : process.env.NODE_ENV}`);
});
