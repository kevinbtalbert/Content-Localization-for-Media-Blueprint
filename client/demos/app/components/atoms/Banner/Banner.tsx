/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

export enum BannerType {
  Info = "info",
  Warning = "warning",
  Error = "error",
}

const BannerStyle = {
  [BannerType.Info]:
    "bg-[color:var(--color-feedback-info-background)] border-1 border-[color:var(--color-feedback-info-border)] text-[color:var(--color-feedback-info-foreground)]",
  [BannerType.Warning]:
    "bg-[color:var(--color-feedback-warning-background)] border-1 border-[color:var(--color-feedback-warning-border)] text-[color:var(--color-feedback-warning-foreground)]",
  [BannerType.Error]:
    "bg-[color:var(--color-feedback-danger-background)] border-1 border-[color:var(--color-feedback-danger-border)] text-[color:var(--color-feedback-danger-foreground)]",
};

const Banner = ({ children, type = BannerType.Info }: { children: React.ReactNode; type: BannerType }) => {
  return (
    <div className={`p-4 ${BannerStyle[type]} rounded-lg`}>
      <p className="text-sm">{children}</p>
    </div>
  );
};

export default Banner;
