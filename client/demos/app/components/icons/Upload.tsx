/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

const UploadIcon = () => {
  return (
    <svg
      className="mx-auto h-12 w-12 text-[color:var(--color-primary-foreground)] opacity-60"
      fill="none"
      viewBox="0 0 16 16"
    >
      <path
        fill="currentColor"
        d="M1.848,4.87l0.769,-2.87h10.766l0.77,2.87l-0.967,0.26l-0.57,-2.13h-9.233l-0.57,2.13z"
      />
      <path
        fill="currentColor"
        d="M4.354,9.354l-0.708,-0.708l4.354,-4.353l4.353,4.353l-0.707,0.708l-3.146,-3.147v7.793h-1v-7.793z"
      />
    </svg>
  );
};

export default UploadIcon;
