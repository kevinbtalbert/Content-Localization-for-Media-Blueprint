/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import fs from "fs";
import path from "path";

export type PersistedAppConfig = {
  nim_deploy_mode?: string;
  s2s_service?: string;
  ngc_api_key?: string;
  elevenlabs_api_key?: string;
  camb_api_key?: string;
  lipsync_nim_tags_selector?: string;
  s2s_default_target_language?: string;
  default_source_language?: string;
  default_target_language?: string;
  lipsync_nvidia_function_id?: string;
  asd_nvidia_function_id?: string;
  nvidia_serverless_grpc_host?: string;
  nvidia_serverless_grpc_port?: string;
  reference_app_enable_preprocessing?: boolean;
  voice_name?: string;
  target_language_label?: string;
};

const ENV_MAP: Record<keyof PersistedAppConfig, string> = {
  nim_deploy_mode: "NIM_DEPLOY_MODE",
  s2s_service: "S2S_SERVICE",
  ngc_api_key: "NGC_API_KEY",
  elevenlabs_api_key: "ELEVENLABS_API_KEY",
  camb_api_key: "CAMB_API_KEY",
  lipsync_nim_tags_selector: "LIPSYNC_NIM_TAGS_SELECTOR",
  s2s_default_target_language: "S2S_DEFAULT_TARGET_LANGUAGE",
  default_source_language: "DEFAULT_SOURCE_LANGUAGE",
  default_target_language: "DEFAULT_TARGET_LANGUAGE",
  lipsync_nvidia_function_id: "LIPSYNC_NVIDIA_FUNCTION_ID",
  asd_nvidia_function_id: "ASD_NVIDIA_FUNCTION_ID",
  nvidia_serverless_grpc_host: "NVIDIA_SERVERLESS_GRPC_HOST",
  nvidia_serverless_grpc_port: "NVIDIA_SERVERLESS_GRPC_PORT",
  reference_app_enable_preprocessing: "REFERENCE_APP_ENABLE_PREPROCESSING",
  voice_name: "VOICE_NAME",
  target_language_label: "TARGET_LANGUAGE_LABEL",
};

function projectRoot(): string {
  return process.env.CDSW_PROJECT_DIR || "/home/cdsw";
}

export function configFilePath(): string {
  return path.join(projectRoot(), "cai/config/deployment_config.json");
}

export function loadPersistedConfig(): PersistedAppConfig | null {
  const filePath = configFilePath();
  if (!fs.existsSync(filePath)) {
    return null;
  }
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8")) as PersistedAppConfig;
  } catch {
    return null;
  }
}

/** Apply persisted Setup page configuration to process.env (survives app restarts). */
export function applyPersistedConfigToProcessEnv(): PersistedAppConfig | null {
  const config = loadPersistedConfig();
  if (!config) {
    return null;
  }

  for (const [jsonKey, envKey] of Object.entries(ENV_MAP) as [keyof PersistedAppConfig, string][]) {
    const value = config[jsonKey];
    if (value === undefined || value === null || value === "") {
      continue;
    }
    if (jsonKey === "reference_app_enable_preprocessing") {
      process.env[envKey] = value ? "true" : "false";
      continue;
    }
    process.env[envKey] = String(value);
  }

  if (config.default_target_language) {
    process.env.DEFAULT_TARGET_LANGUAGE = config.default_target_language;
  }
  if (config.s2s_default_target_language) {
    process.env.S2S_DEFAULT_TARGET_LANGUAGE = config.s2s_default_target_language;
  }

  return config;
}

export function envOrPersisted(envKey: string, jsonKey: keyof PersistedAppConfig): string | undefined {
  if (process.env[envKey]) {
    return process.env[envKey];
  }
  const config = loadPersistedConfig();
  const value = config?.[jsonKey];
  if (value === undefined || value === null || value === "") {
    return undefined;
  }
  if (jsonKey === "reference_app_enable_preprocessing") {
    return value ? "true" : "false";
  }
  return String(value);
}

applyPersistedConfigToProcessEnv();
