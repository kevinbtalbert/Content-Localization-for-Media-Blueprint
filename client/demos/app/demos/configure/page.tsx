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

type DeploymentStatus = {
  config: Record<string, string> | null;
  nim_deploy_mode: string | null;
  services: Record<string, ServiceStatus>;
  endpoints_ready: boolean;
  controller_address: string | null;
  ready_for_demo: boolean;
  error?: string;
};

const defaultForm = {
  nim_deploy_mode: "SERVERLESS" as NimDeployMode,
  s2s_service: "EL_DUBBING" as S2sService,
  ngc_api_key: "",
  elevenlabs_api_key: "",
  camb_api_key: "",
  lipsync_nim_tags_selector: "language=de",
  s2s_default_target_language: "de",
  lipsync_nvidia_function_id: "",
};

export default function ConfigurePage() {
  const [status, setStatus] = useState<DeploymentStatus | null>(null);
  const [form, setForm] = useState(defaultForm);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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
          lipsync_nim_tags_selector: data.config.lipsync_nim_tags_selector || prev.lipsync_nim_tags_selector,
          s2s_default_target_language:
            data.config.s2s_default_target_language || prev.s2s_default_target_language,
          lipsync_nvidia_function_id: data.config.lipsync_nvidia_function_id || "",
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
      const response = await fetch("/api/deployment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "save-config", config: form }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Failed to save configuration");
      }
      setMessage("Configuration saved.");
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

  return (
    <div className="flex flex-col gap-4">
      <Header
        title="Setup & Deployment"
        description="Choose serverless NVIDIA APIs or deploy GPU NIM applications, then start the pipeline from this page."
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
            <h3 className="text-lg font-semibold">API keys & settings</h3>
            <label className="flex flex-col gap-1 text-sm">
              NGC API key
              <input
                className="rounded border border-neutral-600 bg-neutral-900 px-3 py-2"
                type="password"
                value={form.ngc_api_key}
                onChange={(e) => setForm({ ...form, ngc_api_key: e.target.value })}
                placeholder={status?.config?.ngc_api_key ? "Saved (enter to replace)" : "Required"}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              S2S backend
              <select
                className="rounded border border-neutral-600 bg-neutral-900 px-3 py-2"
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
                  className="rounded border border-neutral-600 bg-neutral-900 px-3 py-2"
                  type="password"
                  value={form.elevenlabs_api_key}
                  onChange={(e) => setForm({ ...form, elevenlabs_api_key: e.target.value })}
                />
              </label>
            )}
            {form.s2s_service === "CAMB_DUBBING" && (
              <label className="flex flex-col gap-1 text-sm">
                CambAI API key
                <input
                  className="rounded border border-neutral-600 bg-neutral-900 px-3 py-2"
                  type="password"
                  value={form.camb_api_key}
                  onChange={(e) => setForm({ ...form, camb_api_key: e.target.value })}
                />
              </label>
            )}
            {form.nim_deploy_mode === "BUNDLED" && (
              <label className="flex flex-col gap-1 text-sm">
                LipSync language model (NIM_TAGS_SELECTOR)
                <input
                  className="rounded border border-neutral-600 bg-neutral-900 px-3 py-2"
                  value={form.lipsync_nim_tags_selector}
                  onChange={(e) => setForm({ ...form, lipsync_nim_tags_selector: e.target.value })}
                />
              </label>
            )}
            {form.nim_deploy_mode === "SERVERLESS" && (
              <label className="flex flex-col gap-1 text-sm">
                LipSync NVCF function ID (optional override)
                <input
                  className="rounded border border-neutral-600 bg-neutral-900 px-3 py-2"
                  value={form.lipsync_nvidia_function_id}
                  onChange={(e) => setForm({ ...form, lipsync_nvidia_function_id: e.target.value })}
                  placeholder="Only if NVIDIA provided one via AI for Media"
                />
              </label>
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
