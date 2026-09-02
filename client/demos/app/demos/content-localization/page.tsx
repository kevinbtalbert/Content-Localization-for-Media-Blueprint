/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import Header from "@/app/components/atoms/Header";
import VideoUploadContainer from "@/app/components/VideoUploader";

export default function ContentLocalization() {
  return (
    <div>
      <Header
        className="mb-4"
        title="Content Localization"
        description="Localize your content with translation, voice-cloned dubbing and lipsync."
      />
      <p className="mb-4 text-sm text-neutral-400">
        <a href="/demos/configure" className="text-[#76b900] underline">
          Setup &amp; deployment
        </a>
        {" — configure API keys and deploy services before running the pipeline."}
      </p>
      <VideoUploadContainer />
    </div>
  );
}
