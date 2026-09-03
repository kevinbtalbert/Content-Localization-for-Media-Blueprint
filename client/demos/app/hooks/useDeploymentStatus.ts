/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type StepStatus = "pending" | "running" | "done" | "skipped" | "error";

export type BuildStep = {
  id: string;
  label: string;
  status: StepStatus;
  detail?: string;
};

export type BuildProgress = {
  in_progress?: boolean;
  success?: boolean;
  error?: string | null;
  message?: string;
  mode?: string;
  finished_at?: number;
  steps?: BuildStep[];
};

export type ServiceStatus = {
  name: string;
  configured: boolean;
  skipped_reason?: string;
  application: { id: string; status: string; subdomain: string | null } | null;
};

export type FailedService = {
  key: string;
  name: string;
  status: string;
};

export type DeploymentStatus = {
  config_saved: boolean;
  config: Record<string, string | boolean> | null;
  secrets_set: Record<string, boolean>;
  nim_deploy_mode: string | null;
  mode_summary: { headline: string; detail: string };
  build_plan_preview: BuildStep[];
  services: Record<string, ServiceStatus>;
  endpoints_ready: boolean;
  controller_address: string | null;
  pipeline_ready: boolean;
  pipeline_failed: boolean;
  failed_services: FailedService[];
  pending_services: string[];
  build: BuildProgress | null;
  build_in_progress: boolean;
  error?: string;
};

const STATUS_TIMEOUT_MS = 45_000;

async function fetchDeploymentStatus(): Promise<DeploymentStatus> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), STATUS_TIMEOUT_MS);
  try {
    const response = await fetch("/api/deployment", { signal: controller.signal, cache: "no-store" });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Failed to load deployment status");
    }
    return data as DeploymentStatus;
  } finally {
    clearTimeout(timeout);
  }
}

type Options = {
  /** Poll while build is active or services are still starting (default: true). */
  pollWhilePending?: boolean;
};

export function useDeploymentStatus(options: Options = {}) {
  const { pollWhilePending = true } = options;
  const [status, setStatus] = useState<DeploymentStatus | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [polling, setPolling] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const hasLoadedRef = useRef(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(
    async (silent = false) => {
      const showInitialLoader = !hasLoadedRef.current && !silent;
      if (showInitialLoader) {
        setInitialLoading(true);
      }
      try {
        const data = await fetchDeploymentStatus();
        hasLoadedRef.current = true;
        setStatus(data);
        setFetchError(null);

        const failed = Boolean(data.pipeline_failed || (data.failed_services?.length ?? 0) > 0);
        const pending = (data.pending_services?.length ?? 0) > 0;
        if (pollWhilePending && !failed && (data.build_in_progress || pending)) {
          setPolling(true);
        } else {
          setPolling(false);
        }
        return data;
      } catch (err) {
        const message =
          err instanceof Error && err.name === "AbortError"
            ? "Timed out loading deployment status. Try again or check application logs."
            : err instanceof Error
              ? err.message
              : "Failed to load deployment status";
        setFetchError(message);
        setPolling(false);
        return null;
      } finally {
        if (showInitialLoader || !silent) {
          setInitialLoading(false);
        }
      }
    },
    [pollWhilePending],
  );

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (!polling) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    pollRef.current = setInterval(() => {
      void refresh(true);
    }, 4000);
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
      }
    };
  }, [polling, refresh]);

  const pipelineReady = Boolean(status?.pipeline_ready);
  const pipelineFailed = Boolean(status?.pipeline_failed || (status?.failed_services?.length ?? 0) > 0);
  const hasPriorBuild = Boolean(
    status?.config_saved &&
      (status?.endpoints_ready || status?.build?.finished_at || (status?.build?.steps?.length ?? 0) > 0),
  );

  const startPolling = useCallback(() => setPolling(true), []);

  return {
    status,
    initialLoading,
    polling,
    fetchError,
    refresh,
    startPolling,
    pipelineReady,
    pipelineFailed,
    hasPriorBuild,
  };
}
