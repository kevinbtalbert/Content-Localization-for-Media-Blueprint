/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

const Loader = () => {
  return (
    <svg
      className="animate-spin h-10 w-10 mb-4 text-[color:var(--color-interaction-primary-base-background)]"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" className="opacity-25" strokeWidth="4" fill="none"></circle>
      <path stroke="currentColor" className="opacity-75" strokeWidth="4" fill="none" d="M12 2a10 10 0 0 1 10 10"></path>
    </svg>
  );
};

export default Loader;
