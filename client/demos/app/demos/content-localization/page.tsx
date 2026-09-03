/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import Header from "@/app/components/atoms/Header";
import PipelineToolbar from "@/app/components/PipelineToolbar";
import VideoUploadContainer from "@/app/components/VideoUploader";

export default function ContentLocalization() {
  return (
    <div>
      <Header
        className="mb-4"
        title="Content Localization"
        description="Localize your content with translation, voice-cloned dubbing and lipsync."
      />
      <PipelineToolbar />
      <VideoUploadContainer />
    </div>
  );
}
