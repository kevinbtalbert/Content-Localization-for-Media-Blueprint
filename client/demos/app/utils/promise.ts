/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

export async function promisifyEvent<T extends EventTarget>(
  target: T,
  eventName: string,
  shouldReject = eventName === "error",
) {
  return new Promise((resolve, reject) => {
    target.addEventListener(eventName, shouldReject ? reject : resolve, {
      once: true,
    });
  });
}

export const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
