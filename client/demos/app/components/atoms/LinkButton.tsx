/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

const BASE_STYLES = "cursor-pointer font-semibold px-2 py-1 rounded transition-colors";

const LinkButton: React.FC<{
  children: React.ReactNode;
  onClick: () => void;
  variant?: "primary" | "secondary";
  disabled?: boolean;
}> = ({ children, onClick, variant = "primary", disabled = false }) => {
  const variantClasses =
    variant === "primary"
      ? "text-[color:var(--color-interaction-primary-base-background)] hover:bg-[color:var(--color-interaction-hover-background)] focus-visible:bg-[color:var(--color-interaction-hover-background)]"
      : "text-[color:var(--color-text-secondary)] hover:bg-[color:var(--color-interaction-hover-background)] focus-visible:bg-[color:var(--color-interaction-hover-background)] opacity-80 hover:opacity-100";

  return (
    <button
      type="button"
      className={`${BASE_STYLES} ${variantClasses} ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
};

export default LinkButton;
