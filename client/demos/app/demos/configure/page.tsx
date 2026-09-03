/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import Header from "@/app/components/atoms/Header";
import Card from "@/app/components/atoms/Card";
import {
  type BuildStep,
  type DeploymentStatus,
  type StepStatus,
  useDeploymentStatus,
} from "@/app/hooks/useDeploymentStatus";

type NimDeployMode = "SERVERLESS" | "BUNDLED";
type S2sService = "EL_DUBBING" | "CAMB_DUBBING";

type SecretsSet = {
  ngc_api_key?: boolean;
  elevenlabs_api_key?: boolean;
  camb_api_key?: boolean;
};

type SetupForm = {
  nim_deploy_mode: NimDeployMode;
  s2s_service: S2sService;
  ngc_api_key: string;
  elevenlabs_api_key: string;
  camb_api_key: string;
  lipsync_nim_tags_selector: string;
  s2s_default_target_language: string;
  default_source_language: string;
  default_target_language: string;
  lipsync_nvidia_function_id: string;
  asd_nvidia_function_id: string;
  nvidia_serverless_grpc_host: string;
  nvidia_serverless_grpc_port: string;
  reference_app_enable_preprocessing: boolean;
  voice_name: string;
  target_language_label: string;
};

const defaultForm: SetupForm = {
  nim_deploy_mode: "SERVERLESS",
  s2s_service: "EL_DUBBING",
  ngc_api_key: "",
  elevenlabs_api_key: "",
  camb_api_key: "",
  lipsync_nim_tags_selector: "language=de",
  s2s_default_target_language: "de",
  default_source_language: "auto",
  default_target_language: "de",
  lipsync_nvidia_function_id: "",
  asd_nvidia_function_id: "",
  nvidia_serverless_grpc_host: "grpc.nvcf.nvidia.com",
  nvidia_serverless_grpc_port: "443",
  reference_app_enable_preprocessing: false,
  voice_name: "",
  target_language_label: "",
};

const inputClass = "rounded border border-neutral-600 bg-neutral-900 px-3 py-2";

function stepIcon(status: StepStatus): string {
  switch (status) {
    case "done":
      return "✓";
    case "running":
      return "◌";
    case "error":
      return "✕";
    case "skipped":
      return "—";
    default:
      return "○";
  }
}

function stepClass(status: StepStatus): string {
  switch (status) {
    case "done":
      return "text-green-400";
    case "running":
      return "text-[#76b900] animate-pulse";
    case "error":
      return "text-red-400";
    case "skipped":
      return "text-neutral-500";
    default:
      return "text-neutral-500";
  }
}

export default function ConfigurePage() {
  const {
    status,
    initialLoading,
    polling,
    fetchError,
    refresh,
    startPolling,
    pipelineReady,
    pipelineFailed,
    hasPriorBuild,
  } = useDeploymentStatus({ pollWhilePending: true });

  const [form, setForm] = useState(defaultForm);
  const [busy, setBusy] = useState(false);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [validationWarnings, setValidationWarnings] = useState<string[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const applyStatusToForm = useCallback((data: DeploymentStatus) => {
    if (data.config) {
      setForm((prev) => ({
        ...prev,
        nim_deploy_mode: (data.config!.nim_deploy_mode as NimDeployMode) || prev.nim_deploy_mode,
        s2s_service: (data.config!.s2s_service as S2sService) || prev.s2s_service,
        lipsync_nim_tags_selector: String(data.config!.lipsync_nim_tags_selector || prev.lipsync_nim_tags_selector),
        s2s_default_target_language: String(
          data.config!.s2s_default_target_language || prev.s2s_default_target_language,
        ),
        default_source_language: String(data.config!.default_source_language || prev.default_source_language),
        default_target_language: String(data.config!.default_target_language || prev.default_target_language),
        lipsync_nvidia_function_id: String(data.config!.lipsync_nvidia_function_id || ""),
        asd_nvidia_function_id: String(data.config!.asd_nvidia_function_id || ""),
        nvidia_serverless_grpc_host: String(
          data.config!.nvidia_serverless_grpc_host || prev.nvidia_serverless_grpc_host,
        ),
        nvidia_serverless_grpc_port: String(data.config!.nvidia_serverless_grpc_port || prev.nvidia_serverless_grpc_port),
        reference_app_enable_preprocessing: Boolean(data.config!.reference_app_enable_preprocessing),
        voice_name: String(data.config!.voice_name || ""),
        target_language_label: String(data.config!.target_language_label || ""),
      }));
    }
  }, []);

  const applyBuildMessages = useCallback((data: DeploymentStatus | null) => {
    if (!data) {
      return;
    }
    const failed = Boolean(data.pipeline_failed || (data.failed_services?.length ?? 0) > 0);
    const ready = Boolean(data.pipeline_ready);
    const pending = (data.pending_services?.length ?? 0) > 0;

    if (failed) {
      const summary =
        data.build?.error ||
        data.failed_services?.map((svc) => `${svc.name} (${svc.status})`).join("; ") ||
        "One or more backend applications failed.";
      setPageError(summary);
      setMessage(null);
    } else if (ready && !data.build_in_progress && !pending) {
      setPageError(null);
      setMessage("Pipeline is ready. Return to Content Localization to process video.");
    } else if (data.build?.error && !data.build_in_progress) {
      setPageError(data.build.error);
      setMessage(null);
    } else if (!data.build_in_progress && !pending) {
      setPageError(null);
    }
  }, []);

  useEffect(() => {
    if (status) {
      applyStatusToForm(status);
      applyBuildMessages(status);
    }
  }, [status, applyStatusToForm, applyBuildMessages]);

  const formPayload = () => ({
    ...form,
    s2s_default_target_language: form.default_target_language,
  });

  const saveConfig = async () => {
    setBusy(true);
    setMessage(null);
    setPageError(null);
    setValidationErrors([]);
    try {
      const response = await fetch("/api/deployment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "save-config", config: formPayload() }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Failed to save configuration");
      }
      setMessage("Configuration saved.");
      await refresh(true);
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "Failed to save configuration");
    } finally {
      setBusy(false);
    }
  };

  const buildPipeline = async () => {
    setBusy(true);
    setMessage(null);
    setPageError(null);
    setValidationErrors([]);
    setValidationWarnings([]);
    try {
      const validateResponse = await fetch("/api/deployment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "validate", config: formPayload() }),
      });
      const validation = await validateResponse.json();
      if (!validateResponse.ok) {
        setValidationErrors(validation.errors || [validation.error || "Validation failed"]);
        setValidationWarnings(validation.warnings || []);
        return;
      }
      setValidationWarnings(validation.warnings || []);

      const response = await fetch("/api/deployment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "build", config: formPayload() }),
      });
      const data = await response.json();
      if (!response.ok) {
        setValidationErrors(data.errors || [data.error || "Build could not start"]);
        setValidationWarnings(data.warnings || []);
        return;
      }
      setMessage(data.message || "Pipeline build started.");
      startPolling();
      const updated = await refresh(true);
      applyBuildMessages(updated);
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "Build failed to start");
    } finally {
      setBusy(false);
    }
  };

  const secretPlaceholder = (key: keyof SecretsSet, label: string) => {
    if (status?.secrets_set?.[key]) {
      return `${label} saved (leave blank to keep)`;
    }
    return `Required — ${label}`;
  };

  const buildSteps: BuildStep[] = status?.build?.steps?.length
    ? status.build.steps
    : (status?.build_plan_preview || []).map((step) => ({
        id: step.id,
        label: step.label,
        status: step.status ?? ("pending" as StepStatus),
        detail: step.detail,
      }));

  const showProgress = polling || status?.build_in_progress || (status?.build?.steps?.length ?? 0) > 0;
  const buildActionLabel = hasPriorBuild ? "Redeploy pipeline" : "Build pipeline";
  const displayError = pageError || fetchError;
  const progressBorderClass = pipelineFailed
    ? "border border-red-500/40"
    : pipelineReady
      ? "border border-green-500/40"
      : "border border-[#76b900]/30";
  const progressSummary = pipelineFailed
    ? "Pipeline build incomplete — check backend application status below."
    : pipelineReady
      ? "Pipeline build completed successfully."
      : status?.build?.message || "Build in progress…";
  const modeHeadline =
    form.nim_deploy_mode === "SERVERLESS"
      ? "Serverless: LipSync & ASD use NVIDIA NVCF — not apps in this project."
      : "Bundled: LipSync & ASD are GPU apps created in this project.";

  return (
    <div className="flex flex-col gap-4">
      <Header
        title="Content Localization Launchpad"
        description={
          hasPriorBuild
            ? "Reconfigure settings and redeploy the backend pipeline. Content Localization opens by default once built."
            : "Configure your pipeline here, then build it. After the first successful deploy, the app opens to Content Localization."
        }
      />

      {hasPriorBuild && (
        <p className="text-sm">
          <Link href="/demos/content-localization" className="text-[#76b900] underline">
            ← Back to Content Localization
          </Link>
        </p>
      )}

      {(initialLoading || polling || status?.build_in_progress) && !fetchError && (
        <Card padding="p-3" className="border border-neutral-700">
          <p className="text-sm text-neutral-400">
            {initialLoading ? "Loading deployment status…" : "Refreshing build status…"}
          </p>
        </Card>
      )}

      {displayError && (
        <Card padding="p-4" className="border border-red-500/40">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-red-400">{displayError}</p>
            <button
              type="button"
              className="text-sm text-neutral-300 underline"
              onClick={() => {
                void refresh();
              }}
            >
              Retry
            </button>
          </div>
        </Card>
      )}

      {validationErrors.length > 0 && (
        <Card padding="p-4" className="border border-red-500/40">
          <p className="mb-2 text-sm font-medium text-red-400">Fix these before building:</p>
          <ul className="list-inside list-disc text-sm text-red-300">
            {validationErrors.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Card>
      )}

      {validationWarnings.length > 0 && (
        <Card padding="p-4" className="border border-amber-500/30">
          <ul className="list-inside list-disc text-sm text-amber-200">
            {validationWarnings.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Card>
      )}

      {message && pipelineReady && !pipelineFailed && (
        <Card padding="p-4" className="border border-green-500/40">
          <p className="text-sm text-green-400">{message}</p>
        </Card>
      )}

      <Card padding="p-6" className="flex flex-col gap-2 border border-neutral-700">
        <p className="text-sm font-medium text-neutral-200">{modeHeadline}</p>
        <p className="text-sm text-neutral-400">
          {status?.mode_summary?.detail ||
            "Build runs in the background from this page. Speech-to-Speech and Controller always start as project applications."}
        </p>
      </Card>

      <Card padding="p-6" className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">NIM deployment mode</h3>
            <div className="flex flex-col gap-2">
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="radio"
                  className="mt-1"
                  name="nim_deploy_mode"
                  checked={form.nim_deploy_mode === "SERVERLESS"}
                  onChange={() => setForm({ ...form, nim_deploy_mode: "SERVERLESS" })}
                />
                <span>
                  <strong>Serverless</strong> — LipSync &amp; ASD call NVIDIA NVCF. Build only starts
                  Speech-to-Speech + Controller here.
                </span>
              </label>
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="radio"
                  className="mt-1"
                  name="nim_deploy_mode"
                  checked={form.nim_deploy_mode === "BUNDLED"}
                  onChange={() => setForm({ ...form, nim_deploy_mode: "BUNDLED" })}
                />
                <span>
                  <strong>Bundled</strong> — LipSync &amp; ASD run as GPU applications in this project
                  (longer build).
                </span>
              </label>
            </div>
          </Card>

          <Card padding="p-6" className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">API keys</h3>
            <label className="flex flex-col gap-1 text-sm">
              NGC API key
              <input
                className={inputClass}
                type="password"
                value={form.ngc_api_key}
                onChange={(e) => setForm({ ...form, ngc_api_key: e.target.value })}
                placeholder={secretPlaceholder("ngc_api_key", "NGC key")}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              S2S backend
              <select
                className={inputClass}
                value={form.s2s_service}
                onChange={(e) => setForm({ ...form, s2s_service: e.target.value as S2sService })}
              >
                <option value="EL_DUBBING">ElevenLabs dubbing</option>
                <option value="CAMB_DUBBING">CambAI dubbing</option>
              </select>
            </label>
            {form.s2s_service === "EL_DUBBING" && (
              <label className="flex flex-col gap-1 text-sm">
                ElevenLabs API key
                <input
                  className={inputClass}
                  type="password"
                  value={form.elevenlabs_api_key}
                  onChange={(e) => setForm({ ...form, elevenlabs_api_key: e.target.value })}
                  placeholder={secretPlaceholder("elevenlabs_api_key", "ElevenLabs key")}
                />
              </label>
            )}
            {form.s2s_service === "CAMB_DUBBING" && (
              <label className="flex flex-col gap-1 text-sm">
                CambAI API key
                <input
                  className={inputClass}
                  type="password"
                  value={form.camb_api_key}
                  onChange={(e) => setForm({ ...form, camb_api_key: e.target.value })}
                  placeholder={secretPlaceholder("camb_api_key", "CambAI key")}
                />
              </label>
            )}
          </Card>

          <Card padding="p-6" className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">Pipeline defaults</h3>
            <label className="flex flex-col gap-1 text-sm">
              Default source language
              <input
                className={inputClass}
                value={form.default_source_language}
                onChange={(e) => setForm({ ...form, default_source_language: e.target.value })}
                placeholder="auto (ElevenLabs) or language code / CambAI ID"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              Default target language
              <input
                className={inputClass}
                value={form.default_target_language}
                onChange={(e) => setForm({ ...form, default_target_language: e.target.value })}
                placeholder="de or CambAI language ID (e.g. 26)"
              />
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.reference_app_enable_preprocessing}
                onChange={(e) =>
                  setForm({ ...form, reference_app_enable_preprocessing: e.target.checked })
                }
              />
              Enable voice isolation and diarization preprocessing
            </label>
            <label className="flex flex-col gap-1 text-sm">
              Voice name (optional UI label)
              <input
                className={inputClass}
                value={form.voice_name}
                onChange={(e) => setForm({ ...form, voice_name: e.target.value })}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              Target language label (optional UI label)
              <input
                className={inputClass}
                value={form.target_language_label}
                onChange={(e) => setForm({ ...form, target_language_label: e.target.value })}
              />
            </label>
          </Card>

          {form.nim_deploy_mode === "BUNDLED" && (
            <Card padding="p-6" className="flex flex-col gap-4">
              <h3 className="text-lg font-semibold">Bundled NIM settings</h3>
              <label className="flex flex-col gap-1 text-sm">
                LipSync language model (LIPSYNC_NIM_TAGS_SELECTOR)
                <input
                  className={inputClass}
                  value={form.lipsync_nim_tags_selector}
                  onChange={(e) => setForm({ ...form, lipsync_nim_tags_selector: e.target.value })}
                />
              </label>
            </Card>
          )}

          <Card padding="p-6" className="flex flex-col gap-4">
            <button
              type="button"
              className="text-left text-sm text-neutral-400 hover:text-neutral-200"
              onClick={() => setShowAdvanced((v) => !v)}
            >
              {showAdvanced ? "Hide" : "Show"} advanced serverless overrides
            </button>
            {showAdvanced && (
              <div className="flex flex-col gap-4">
                <label className="flex flex-col gap-1 text-sm">
                  LipSync NVCF function ID (optional)
                  <input
                    className={inputClass}
                    value={form.lipsync_nvidia_function_id}
                    onChange={(e) => setForm({ ...form, lipsync_nvidia_function_id: e.target.value })}
                  />
                </label>
                <label className="flex flex-col gap-1 text-sm">
                  ASD NVCF function ID (optional)
                  <input
                    className={inputClass}
                    value={form.asd_nvidia_function_id}
                    onChange={(e) => setForm({ ...form, asd_nvidia_function_id: e.target.value })}
                  />
                </label>
                <label className="flex flex-col gap-1 text-sm">
                  NVCF gRPC host
                  <input
                    className={inputClass}
                    value={form.nvidia_serverless_grpc_host}
                    onChange={(e) => setForm({ ...form, nvidia_serverless_grpc_host: e.target.value })}
                  />
                </label>
                <label className="flex flex-col gap-1 text-sm">
                  NVCF gRPC port
                  <input
                    className={inputClass}
                    value={form.nvidia_serverless_grpc_port}
                    onChange={(e) => setForm({ ...form, nvidia_serverless_grpc_port: e.target.value })}
                  />
                </label>
              </div>
            )}
          </Card>

          <Card padding="p-6" className="flex flex-wrap gap-3">
            <button
              type="button"
              className="rounded bg-neutral-700 px-4 py-2 text-sm disabled:opacity-50"
              disabled={busy || polling || status?.build_in_progress}
              onClick={saveConfig}
            >
              Save configuration
            </button>
            <button
              type="button"
              className="rounded bg-[#76b900] px-4 py-2 text-sm font-medium text-black disabled:opacity-50"
              disabled={busy || (!pipelineFailed && (polling || Boolean(status?.build_in_progress)))}
              onClick={buildPipeline}
            >
              {busy ? "Checking…" : !pipelineFailed && (polling || status?.build_in_progress) ? "Deploying…" : buildActionLabel}
            </button>
            {hasPriorBuild && (
              <Link
                href="/demos/content-localization"
                className="rounded border border-[#76b900] px-4 py-2 text-sm text-[#76b900]"
              >
                Open Content Localization →
              </Link>
            )}
          </Card>

          {showProgress && (
            <Card padding="p-6" className={`flex flex-col gap-3 ${progressBorderClass}`}>
              <div className="flex items-center justify-between gap-4">
                <h3 className="text-lg font-semibold">Build progress</h3>
                {(polling || status?.build_in_progress) && (
                  <span className="text-xs text-[#76b900]">Updating every few seconds…</span>
                )}
              </div>
              <p
                className={`text-sm ${
                  pipelineFailed ? "text-red-400" : pipelineReady ? "text-green-400" : "text-neutral-300"
                }`}
              >
                {progressSummary}
              </p>
              {status?.build?.error && pipelineFailed && (
                <p className="text-sm text-red-300">{status.build.error}</p>
              )}
              <ul className="flex flex-col gap-2">
                {buildSteps.map((step) => (
                  <li key={step.id} className={`flex gap-3 text-sm ${stepClass(step.status)}`}>
                    <span className="w-4 shrink-0 font-mono">{stepIcon(step.status)}</span>
                    <div>
                      <p>{step.label}</p>
                      {step.detail && <p className="text-xs text-neutral-500">{step.detail}</p>}
                    </div>
                  </li>
                ))}
              </ul>
              {(polling || status?.build_in_progress) && !pipelineFailed && (
                <div className="mt-2 h-1.5 w-full overflow-hidden rounded bg-neutral-800">
                  <div className="h-full w-1/3 animate-pulse rounded bg-[#76b900]" />
                </div>
              )}
            </Card>
          )}

          {status && (
            <Card padding="p-6">
              <h3 className="mb-3 text-lg font-semibold">Backend applications</h3>
              <ul className="flex flex-col gap-2 text-sm">
                {Object.entries(status.services).map(([key, svc]) => {
                  const appStatus = svc.application?.status || "";
                  const isFailed = /fail/i.test(appStatus);
                  return (
                  <li key={key} className="flex justify-between gap-4 border-b border-neutral-800 py-2">
                    <span>{svc.name}</span>
                    <span className={`text-right ${isFailed ? "text-red-400" : "text-neutral-400"}`}>
                      {svc.skipped_reason ||
                        (svc.application ? svc.application.status : "not started — build pipeline first")}
                    </span>
                  </li>
                  );
                })}
              </ul>
              <p className="mt-4 text-xs text-neutral-500">
                Endpoints connected: {status.endpoints_ready ? "yes" : "no"}
                {status.controller_address ? ` · Controller: ${status.controller_address}` : ""}
              </p>
            </Card>
          )}
    </div>
  );
}
