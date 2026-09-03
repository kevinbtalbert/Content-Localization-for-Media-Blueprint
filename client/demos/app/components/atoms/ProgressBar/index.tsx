/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

"use client";

type Props = {
  percent: number;
  label?: string;
  className?: string;
};

const ProgressBar = ({ percent, label, className = "" }: Props) => {
  const clamped = Math.min(100, Math.max(0, Math.round(percent)));

  return (
    <div className={`w-full ${className}`}>
      {(label || clamped < 100) && (
        <div className="mb-1 flex items-center justify-between gap-2 text-xs text-[color:var(--color-secondary-foreground)]">
          <span className="truncate">{label ?? "Transferring"}</span>
          <span className="shrink-0 tabular-nums">{clamped}%</span>
        </div>
      )}
      <div
        className="h-1.5 w-full overflow-hidden rounded-full bg-[color:var(--color-base-border)]"
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label ?? "Transfer progress"}
      >
        <div
          className="h-full rounded-full bg-[color:var(--color-interaction-primary-base-background)] transition-[width] duration-150 ease-out"
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
};

export default ProgressBar;
