# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Controller client package.

This package provides a client for the Controller Service, which orchestrates
all downstream AI services (S2S, ASD, LipSync) to provide end-to-end content
localization capabilities.

Components
----------

- app: Main application module with controller client implementation
- args: Command-line argument parsing and configuration

Usage
-----

.. code-block:: python

   from client.controller.app import main
   from client.controller.args import argsfactory

   # Parse command line arguments
   args = argsfactory()

   # Run the controller client
   main(args)

Features
--------

- End-to-end content localization pipeline
- Orchestrates S2S, ASD, and LipSync services
- Supports multiple service modes (pull, pull-transactional, push)
- Real-time streaming and batch processing
- Comprehensive error handling and recovery
"""
