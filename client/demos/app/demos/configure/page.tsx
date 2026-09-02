/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import Header from "@/app/components/atoms/Header";
import Card from "@/app/components/atoms/Card";
import Loader from "@/app/components/atoms/Loader";

type NimDeployMode = "SERVERLESS" | "BUNDLED";
type S2sService = "EL_DUBBING" | "CAMB_DUBBING";

type ServiceStatus = {
  name: string;
  configured: boolean;
  application: { id: string; status: string; subdomain: string | null } | null;
};

type SecretsSet = {
  ngc_api_key?: boolean;
  elevenlabs_api_key?: boolean;
  camb_api_key?: boolean;
};

type DeploymentStatus = {
  config_saved: boolean;
  config: Record<string, string | boolean> | null;
  secrets_set: SecretsSet;
  nim_deploy_mode: string | null;
  services: Record<string, ServiceStatus>;
  endpoints_ready: boolean;
  controller_address: string | null;
  ready_for_demo: boolean;
  error?: string;
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

export default function ConfigurePage() {
  const [status, setStatus] = useState<DeploymentStatus | null>(null);
  const [form, setForm] = useState(defaultForm);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/deployment");
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Failed to load status");
      }
      setStatus(data);
      if (data.config) {
        setForm((prev) => ({
          ...prev,
          nim_deploy_mode: (data.config.nim_deploy_mode as NimDeployMode) || prev.nim_deploy_mode,
          s2s_service: (data.config.s2s_service as S2sService) || prev.s2s_service,
          lipsync_nim_tags_selector: String(data.config.lipsync_nim_tags_selector || prev.lipsync_nim_tags_selector),
          s2s_default_target_language: String(
            data.config.s2s_default_target_language || prev.s2s_default_target_language,
          ),
          default_source_language: String(data.config.default_source_language || prev.default_source_language),
          default_target_language: String(data.config.default_target_language || prev.default_target_language),
          lipsync_nvidia_function_id: String(data.config.lipsync_nvidia_function_id || ""),
          asd_nvidia_function_id: String(data.config.asd_nvidia_function_id || ""),
          nvidia_serverless_grpc_host: String(
            data.config.nvidia_serverless_grpc_host || prev.nvidia_serverless_grpc_host,
          ),
          nvidia_serverless_grpc_port: String(data.config.nvidia_serverless_grpc_port || prev.nvidia_serverless_grpc_port),
          reference_app_enable_preprocessing: Boolean(data.config.reference_app_enable_preprocessing),
          voice_name: String(data.config.voice_name || ""),
          target_language_label: String(data.config.target_language_label || ""),
        }));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load status");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const saveConfig = async () => {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const payload = {
        ...form,
        s2s_default_target_language: form.default_target_language,
      };
      const response = await fetch("/api/deployment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "save-config", config: payload }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Failed to save configuration");
      }
      setMessage("Configuration saved. Settings persist across app restarts.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save configuration");
    } finally {
      setBusy(false);
    }
  };

  const deploy = async () => {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      await saveConfig();
      const response = await fetch("/api/deployment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "deploy" }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Deploy failed");
      }
      setMessage("Deployment started. Services may take several minutes to become ready.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Deploy failed");
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

  return (
    <div className="flex flex-col gap-4">
      <Header
        title="Setup & Deployment"
        description="Configure API keys, languages, and deployment mode here. Settings are saved to the project and restored when the app restarts."
      />

      {loading && (
        <Card padding="p-6">
          <Loader />
        </Card>
      )}

      {error && (
        <Card padding="p-4" className="border border-red-500/40">
          <p className="text-sm text-red-400">{error}</p>
        </Card>
      )}

      {message && (
        <Card padding="p-4" className="border border-green-500/40">
          <p className="text-sm text-green-400">{message}</p>
        </Card>
      )}

      {!loading && (
        <>
          <Card padding="p-6" className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">NIM deployment mode</h3>
            <div className="flex flex-col gap-2">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name="nim_deploy_mode"
                  checked={form.nim_deploy_mode === "SERVERLESS"}
                  onChange={() => setForm({ ...form, nim_deploy_mode: "SERVERLESS" })}
                />
                Serverless — use NVIDIA hosted NVCF APIs (no GPU NIM apps)
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name="nim_deploy_mode"
                  checked={form.nim_deploy_mode === "BUNDLED"}
                  onChange={() => setForm({ ...form, nim_deploy_mode: "BUNDLED" })}
                />
                Bundled — deploy LipSync and ASD GPU NIM applications in this project
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
            <h3 className="text-lg font-semibold">Demo defaults</h3>
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
                    placeholder="Only if NVIDIA provided one via AI for Media"
                  />
                </label>
                <label className="flex flex-col gap-1 text-sm">
                  ASD NVCF function ID (optional)
                  <input
                    className={inputClass}
                    value={form.asd_nvidia_function_id}
                    onChange={(e) => setForm({ ...form, asd_nvidia_function_id: e.target.value })}
                    placeholder="Defaults to built-in ASD function when empty"
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
              disabled={busy}
              onClick={saveConfig}
            >
              Save configuration
            </button>
            <button
              type="button"
              className="rounded bg-[#76b900] px-4 py-2 text-sm font-medium text-black disabled:opacity-50"
              disabled={busy}
              onClick={deploy}
            >
              {busy ? "Working…" : "Deploy services"}
            </button>
            {status?.ready_for_demo && (
              <Link
                href="/demos/content-localization"
                className="rounded border border-[#76b900] px-4 py-2 text-sm text-[#76b900]"
              >
                Open demo →
              </Link>
            )}
          </Card>

          {status && (
            <Card padding="p-6">
              <h3 className="mb-3 text-lg font-semibold">Service status</h3>
              {!status.config_saved && (
                <p className="mb-3 text-sm text-amber-400">
                  No saved configuration yet. Save settings above before deploying.
                </p>
              )}
              <ul className="flex flex-col gap-2 text-sm">
                {Object.entries(status.services).map(([key, svc]) => (
                  <li key={key} className="flex justify-between gap-4 border-b border-neutral-800 py-2">
                    <span>{svc.name}</span>
                    <span className="text-neutral-400">
                      {!svc.configured
                        ? "skipped (serverless)"
                        : svc.application
                          ? svc.application.status
                          : "not deployed"}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-4 text-xs text-neutral-500">
                Endpoints wired: {status.endpoints_ready ? "yes" : "no"}
                {status.controller_address ? ` · Controller: ${status.controller_address}` : ""}
              </p>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
