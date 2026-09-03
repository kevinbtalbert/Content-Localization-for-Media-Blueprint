/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

"use client";

import Link from "next/link";
import { useDeploymentStatus } from "@/app/hooks/useDeploymentStatus";

export default function PipelineToolbar() {
  const { status, initialLoading, fetchError, refresh, pipelineReady, pipelineFailed, hasPriorBuild } =
    useDeploymentStatus({
      pollWhilePending: true,
    });

  const launchpadLabel = hasPriorBuild ? "Launchpad — reconfigure & redeploy" : "Launchpad — configure & deploy";

  return (
    <div className="mb-4 flex flex-col gap-2 rounded-lg border border-neutral-700 bg-neutral-900/40 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="text-sm">
        {initialLoading ? (
          <span className="text-neutral-400">Checking pipeline status…</span>
        ) : fetchError ? (
          <span className="text-red-400">{fetchError}</span>
        ) : pipelineReady ? (
          <span className="text-green-400">Pipeline is ready.</span>
        ) : pipelineFailed ? (
          <span className="text-red-400">Pipeline needs attention — redeploy from the Launchpad.</span>
        ) : hasPriorBuild ? (
          <span className="text-amber-300">Pipeline is starting or partially deployed.</span>
        ) : (
          <span className="text-amber-300">Pipeline not built yet — configure and deploy before processing video.</span>
        )}
        {status?.controller_address && !initialLoading && (
          <span className="mt-1 block text-xs text-neutral-500">Controller: {status.controller_address}</span>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-3 text-sm">
        {fetchError && (
          <button
            type="button"
            className="text-neutral-300 underline"
            onClick={() => {
              void refresh();
            }}
          >
            Retry
          </button>
        )}
        <Link href="/demos/configure" className="text-[#76b900] underline">
          {launchpadLabel}
        </Link>
        {hasPriorBuild && !initialLoading && (
          <Link
            href="/demos/configure"
            className="rounded border border-[#76b900] px-3 py-1 text-[#76b900] no-underline hover:bg-[#76b900]/10"
          >
            {pipelineFailed ? "Redeploy pipeline" : "Redeploy"}
          </Link>
        )}
      </div>
    </div>
  );
}
