/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

export class Logger {
  private serviceName: string;

  constructor(serviceName: string) {
    this.serviceName = serviceName;
  }

  private formatMessage(level: string, message: string, ...args: any[]): string {
    const timestamp = new Date().toISOString();
    return `[${timestamp}] [${this.serviceName}] [${level}] ${message}`;
  }

  info(message: string, ...args: any[]): void {
    console.log(this.formatMessage("INFO", message), ...args);
  }

  error(message: string, ...args: any[]): void {
    console.error(this.formatMessage("ERROR", message), ...args);
  }

  warn(message: string, ...args: any[]): void {
    console.warn(this.formatMessage("WARN", message), ...args);
  }

  debug(message: string, ...args: any[]): void {
    if (process.env.NEXT_PUBLIC_LOG_LEVEL !== "DEBUG") return;
    console.debug(this.formatMessage("DEBUG", message), ...args);
  }
}

// Create default logger instance
const logger = new Logger("DEMO-APP-API");

export default logger;
