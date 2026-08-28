/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

// Health check interface
interface HealthServiceClient extends grpc.Client {
  Check(
    request: { service: string },
    callback: (error: grpc.ServiceError | null, response?: { status: number }) => void,
  ): void;
}
