/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

"use client";

import { useRef } from "react";

const validateDiarizationFile = async (file: File): Promise<{ valid: boolean; error?: string }> => {
  if (file.type !== "application/json" && !file.name.toLowerCase().endsWith(".json")) {
    return { valid: false, error: "Please upload a JSON file." };
  }
  return { valid: true, error: undefined };
};

interface DiarizationUploadProps {
  diarizationFile: File | null;
  onFileChange: (file: File | null) => void;
  error: string | null;
  onErrorChange: (error: string | null) => void;
  disabled: boolean;
}

/**
 * File upload input for custom diarization JSON files.
 * Validates that the uploaded file is JSON and displays the selected filename.
 */
const DiarizationUpload = ({
  diarizationFile,
  onFileChange,
  error,
  onErrorChange,
  disabled,
}: DiarizationUploadProps) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) {
      onFileChange(null);
      return;
    }

    const validation = await validateDiarizationFile(file);
    if (!validation.valid) {
      onErrorChange(validation.error || "Invalid file.");
      e.target.value = "";
      onFileChange(null);
      return;
    }

    onErrorChange(null);
    onFileChange(file);
  };

  const handleRemoveFile = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onFileChange(null);
    onErrorChange(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleLabelKeyDown = (e: React.KeyboardEvent) => {
    if (disabled) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileInputRef.current?.click();
    }
  };

  return (
    <div>
      <div className="text-sm text-[color:var(--color-primary-foreground)]">Diarization file</div>
      <div className="text-xs text-gray-400 mb-3">
        Provide a custom JSON file to override automatic speaker detection.
      </div>
      <div>
        <div className="flex flex-wrap gap-4 items-center">
          <input
            id="diarization-file-input"
            type="file"
            className="hidden"
            ref={fileInputRef}
            onChange={handleFileSelected}
            accept=".json,application/json"
            disabled={disabled}
          />
          <label
            htmlFor="diarization-file-input"
            tabIndex={disabled ? -1 : 0}
            onKeyDown={handleLabelKeyDown}
            className={`flex items-center gap-2 px-4 py-1.5 text-sm rounded-md border border-dashed border-[color:var(--color-interaction-base-border)] bg-[color:var(--color-surface-base-background)] text-[color:var(--color-primary-foreground)] hover:bg-[color:var(--color-interaction-hover-background)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[color:var(--color-brand-border)] flex-1 min-w-[200px] ${
              disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"
            }`}
          >
            {diarizationFile ? (
              <>
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <svg
                    className="w-4 h-4 flex-shrink-0"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                    />
                  </svg>
                  <span className="truncate">{diarizationFile.name}</span>
                </div>
                <button
                  type="button"
                  onClick={handleRemoveFile}
                  className="ml-2 p-0.5 hover:bg-[color:var(--color-interaction-hover-background)] rounded flex-shrink-0"
                  aria-label="Remove file"
                >
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </>
            ) : (
              <>
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
                <span>Upload diarization file</span>
              </>
            )}
          </label>
          <a
            href="/sample_diarization.json"
            download="sample_diarization.json"
            className="text-sm text-gray-400 underline hover:text-gray-300 cursor-pointer"
          >
            Download sample JSON file
          </a>
        </div>
        {error && <p className="text-sm text-[color:var(--color-feedback-danger-foreground)] mt-2">{error}</p>}
      </div>
    </div>
  );
};

export default DiarizationUpload;
