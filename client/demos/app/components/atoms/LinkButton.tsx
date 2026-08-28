/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

const BASE_STYLES = "cursor-pointer font-semibold px-2 py-1 rounded transition-colors";

const LinkButton: React.FC<{
  children: React.ReactNode;
  onClick: () => void;
  variant?: "primary" | "secondary";
}> = ({ children, onClick, variant = "primary" }) => {
  const variantClasses =
    variant === "primary"
      ? "text-[color:var(--color-interaction-primary-base-background)] hover:bg-[color:var(--color-interaction-hover-background)] focus-visible:bg-[color:var(--color-interaction-hover-background)]"
      : "text-[color:var(--color-text-secondary)] hover:bg-[color:var(--color-interaction-hover-background)] focus-visible:bg-[color:var(--color-interaction-hover-background)] opacity-80 hover:opacity-100";

  return (
    <button className={`${BASE_STYLES} ${variantClasses}`} onClick={onClick}>
      {children}
    </button>
  );
};

export default LinkButton;
