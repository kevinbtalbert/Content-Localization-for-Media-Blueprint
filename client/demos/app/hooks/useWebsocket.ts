/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

"use client";
import { useEffect, useCallback, useState, useRef } from "react";
import { promisifyEvent, sleep } from "../utils/promise";

type EventHandlers = {
  [K in keyof WebSocketEventMap]: (ev: WebSocketEventMap[K]) => any;
};

type JsonValue = boolean | number | string | null | JsonArray | JsonObject;
interface JsonObject {
  [key: string]: JsonValue;
}
interface JsonArray extends Array<JsonValue> {}

// Configuration options for the WebSocket hook
interface HookOptions {
  reconnectRetries?: number;
  autoConnect?: boolean;
  formatRequestData?: (value: JsonValue) => JsonValue;
  initialProtocols?: string[];
}

const identityFormat = (value: JsonValue): JsonValue => value;

/**
 * Hook to manage WebSocket event listeners
 * Automatically adds/removes event handlers when socket or events change
 */
export const useWebSocketEvents = (socket: WebSocket | null, events: Partial<EventHandlers> = {}) => {
  useEffect(() => {
    const removeListeners = Object.keys(events).map((name) => {
      const eventName = name as keyof EventHandlers;
      const handler = events[eventName];
      if (handler) {
        socket?.addEventListener(eventName, handler as EventListener);
      }

      return () => {
        if (handler) {
          socket?.removeEventListener(eventName, handler as EventListener);
        }
      };
    });

    return () => {
      removeListeners.forEach((f) => f());
    };
  }, [socket, events]);
};

const socketStatus = {
  [WebSocket.CONNECTING]: "connecting",
  [WebSocket.OPEN]: "open",
  [WebSocket.CLOSING]: "closing",
  [WebSocket.CLOSED]: "closed",
} as const;

type SocketStatus = (typeof socketStatus)[keyof typeof socketStatus];

const getSocketStatus = (socket: WebSocket | null): SocketStatus | null => {
  if (!socket) return null;
  return socketStatus[socket.readyState as keyof typeof socketStatus];
};

/**
 * Exponential backoff calculation for reconnection attempts
 */
export const backoffMs = (baseMs: number, attempts: number) => baseMs * 2 ** attempts;

/**
 * Creates a new WebSocket instance with optional protocols
 */
const createWebSocket = (url: string | URL, protocols?: string[]) => {
  const ws = new WebSocket(url, protocols?.filter(Boolean));

  return ws;
};

export const socketProxyUrl = (path: string) => {
  if (typeof window !== "undefined") {
    return `ws://${window.location.host}${path}`;
  }
  return `ws://${path}`;
  // return new URL([process.env.NEXT_PUBLIC_SOCKET_URL, path].join(""));
};

const useWebsocket = (
  path: string,
  events?: Partial<EventHandlers>,
  { reconnectRetries = 3, autoConnect = false, formatRequestData = identityFormat, initialProtocols }: HookOptions = {},
) => {
  const url = path.startsWith("/") ? socketProxyUrl(path) : path;

  // Initialize WebSocket connection if autoConnect is enabled
  const [socket, setSocket] = useState(() => (autoConnect ? createWebSocket(url, initialProtocols) : null));
  const reconnectAttempts = useRef(0);

  const [status, setStatus] = useState(() => getSocketStatus(socket));

  /**
   * Establishes WebSocket connection with reconnection logic
   * Uses exponential backoff for failed connection attempts
   */
  const connect = useCallback(
    async (protocols: string[] | undefined = initialProtocols) => {
      const url = path.startsWith("/") ? socketProxyUrl(path) : path;
      const nextSocket = createWebSocket(url, protocols);
      setSocket(nextSocket);
      setStatus(getSocketStatus(nextSocket));

      // Wait for either open or close event
      const ev = await Promise.race([
        promisifyEvent(nextSocket, "open") as Promise<WebSocketEventMap["open"]>,
        promisifyEvent(nextSocket, "close") as Promise<WebSocketEventMap["close"]>,
      ]);

      if (ev.type === "open") {
        reconnectAttempts.current = reconnectRetries;
      }

      if (ev.type === "close") {
        const result = ev as WebSocketEventMap["close"];

        // Normal close - don't attempt reconnection
        if (result.code === 1000) return;

        // Attempt reconnection with exponential backoff
        if (reconnectAttempts.current < reconnectRetries) {
          await sleep(backoffMs(1000, reconnectAttempts.current));

          reconnectAttempts.current += 1;
          return connect(protocols);
        }
      }

      return nextSocket;
    },
    [initialProtocols, reconnectRetries, path],
  );

  /**
   * Closes the WebSocket connection
   */
  const disconnect = useCallback(() => {
    socket?.close();
  }, [socket]);

  // Update status when WebSocket state changes
  useWebSocketEvents(socket, {
    open: () => setStatus(getSocketStatus(socket)),
    close: () => setStatus(getSocketStatus(socket)),
  });

  useEffect(() => {
    setStatus(getSocketStatus(socket));
  }, [socket]);

  // Apply custom event handlers to the WebSocket
  useWebSocketEvents(socket, events);

  /**
   * Sends JSON data through the WebSocket connection
   * Applies optional data formatting before sending
   */
  const sendJSON = useCallback(
    (data: JsonValue) => {
      socket?.send(JSON.stringify(formatRequestData(data)));
    },
    [formatRequestData, socket],
  );

  return { sendJSON, connect, disconnect, socket, status };
};

export default useWebsocket;
