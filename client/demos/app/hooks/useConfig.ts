/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState, useEffect } from "react";

export interface Language {
  code: string;
  label: string;
}

interface ServerConfig {
  [key: string]: string | Language[] | boolean | undefined;
  default_source_language?: string;
  default_target_language?: string;
  supported_source_languages?: Language[];
  supported_target_languages?: Language[];
  enable_preprocessing?: boolean;
}

export const useConfig = () => {
  const [configs, setConfigs] = useState<ServerConfig>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchConfigs = async () => {
      try {
        setLoading(true);
        const response = await fetch("/api/configs/general"); // Adjust the endpoint as needed
        if (!response.ok) {
          throw new Error("Failed to fetch configs");
        }
        const data = await response.json();
        setConfigs(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "An error occurred");
      } finally {
        setLoading(false);
      }
    };

    fetchConfigs();
  }, []);

  return {
    configs,
    loading,
    error,
    sourceLanguages: configs.supported_source_languages || [],
    targetLanguages: configs.supported_target_languages || [],
    defaultSourceLanguage: configs.default_source_language || "auto",
    defaultTargetLanguage: configs.default_target_language || "de",
    enablePreprocessing: configs.enable_preprocessing === true,
  };
};
