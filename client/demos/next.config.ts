/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  output: "standalone",
  async redirects() {
    return [
      {
        source: "/",
        destination: "/demos/configure",
        permanent: false,
      },
      {
        source: "/demos",
        destination: "/demos/configure",
        permanent: false,
      },
      {
        source: "/playgrounds/content-localization",
        destination: "/demos/content-localization",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
