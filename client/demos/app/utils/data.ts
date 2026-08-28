/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

export function base64ToArrayBuffer(base64: string) {
  const binaryString = atob(base64);

  const length = binaryString.length;
  const bytes = new Uint8Array(length);

  for (let i = 0; i < length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }

  return bytes.buffer;
}

export const convertFileToBase64 = async (file: File) => {
  const arr = file.arrayBuffer();
  const buffer = Buffer.from(await arr);
  const base64 = buffer.toString("base64");

  return base64;
};
