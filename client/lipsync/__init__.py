# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""LipSync client package.

This package provides a client for the LipSync service, which synchronizes
lip movements with translated audio to create natural-looking localized content.

Components
----------

- app: Main application module with LipSync client implementation
- args: Command-line argument parsing and configuration
- config: Configuration management for LipSync parameters
- constants: Constants and default values for LipSync operations

Usage
-----

.. code-block:: python

   from client.lipsync.app import main
   from client.lipsync.args import argsfactory
   from client.lipsync.config import LipSyncConfig
   from client.lipsync.constants import DEFAULT_CONFIG

   # Parse command line arguments
   args = argsfactory()

   # Run the LipSync client
   main(args)

Features
--------

- Lip synchronization with translated audio
- Support for multiple video and audio formats
- Configurable synchronization parameters
- Advanced encoding options
- GPU/CPU processing support
"""
