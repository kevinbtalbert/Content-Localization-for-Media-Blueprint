/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import * as grpc from "@grpc/grpc-js";

type ClientCallHandlerOptions = {
  onData: (response: any) => void;
  onEnd: () => void;
  onError: (error: Error) => void;
};

export const clientCallHandler = (
  call: grpc.ClientDuplexStream<any, any>,
  { onData, onEnd, onError }: ClientCallHandlerOptions,
) => {
  call.on("data", onData);
  call.on("end", onEnd);
  call.on("error", onError);
};
