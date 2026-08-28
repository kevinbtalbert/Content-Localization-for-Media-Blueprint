# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Direct client package.

This package provides a direct client that interacts with all services individually,
giving full control over the orchestration and processing flow.

Components
----------

- app: Main application module with direct client implementation
- args: Command-line argument parsing and configuration

Usage
-----

.. code-block:: python

   from client.direct.app import main
   from client.direct.args import argsfactory

   # Parse command line arguments
   args = argsfactory()

   # Run the direct client
   main(args)

Features
--------

- Direct control over all services (S2S, ASD, LipSync)
- Custom orchestration logic
- Detailed monitoring and debugging
- Performance optimization capabilities
- Full control over service interactions
- Pre-translated audio bypass (``--translated-audio``) to skip S2S and feed
  a WAV file directly to LipSync while ASD still runs for speaker detection
"""
