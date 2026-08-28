/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

"use client";

import Accordion from "../atoms/Accordion";
import DiarizationUpload from "./DiarizationUpload";

interface AdvancedSettingsProps {
  voiceIsolation: boolean;
  onVoiceIsolationChange: (enabled: boolean) => void;
  diarizationFile: File | null;
  onDiarizationFileChange: (file: File | null) => void;
  diarizationError: string | null;
  onDiarizationErrorChange: (error: string | null) => void;
  disabled: boolean;
}

/**
 * Collapsible panel for preprocessing options: diarization file upload
 * and voice isolation toggle. Shown only when preprocessing is enabled.
 */
const AdvancedSettings = ({
  voiceIsolation,
  onVoiceIsolationChange,
  diarizationFile,
  onDiarizationFileChange,
  diarizationError,
  onDiarizationErrorChange,
  disabled,
}: AdvancedSettingsProps) => {
  return (
    <div className="mt-4">
      <Accordion title="Advanced Settings">
        <div className="space-y-6 mt-4">
          <DiarizationUpload
            diarizationFile={diarizationFile}
            onFileChange={onDiarizationFileChange}
            error={diarizationError}
            onErrorChange={onDiarizationErrorChange}
            disabled={disabled}
          />

          {/* Voice Isolation */}
          <div>
            <div className="text-sm text-[color:var(--color-primary-foreground)]">Voice isolation</div>
            <div className="text-xs text-gray-400 mb-3">
              Extracts clear speech from background noise and ambient sounds.
            </div>
            <label className="flex items-center gap-2 cursor-pointer w-fit">
              <input
                type="checkbox"
                checked={voiceIsolation}
                onChange={(e) => onVoiceIsolationChange(e.target.checked)}
                disabled={disabled}
                className="w-4 h-4 rounded border-[color:var(--color-base-border)] bg-[color:var(--color-surface-base-background)] text-[color:var(--color-interaction-primary-base-background)] focus:ring-2 focus:ring-[color:var(--color-brand-border)] accent-[color:var(--color-interaction-primary-base-background)]"
              />
              <span className="text-sm font-regular text-[color:var(--color-primary-foreground)]">
                Enable Voice Isolation
              </span>
            </label>
          </div>
        </div>
      </Accordion>
    </div>
  );
};

export default AdvancedSettings;
