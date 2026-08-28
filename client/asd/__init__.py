# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""ASD (Active Speaker Detection) client package.

This package provides a client for the ASD service, which identifies speaking faces
in video content and provides speaker info data.

Components
----------

- app: Main application module with client implementation
- args: Command-line argument parsing and configuration

Usage
-----

.. code-block:: python

   from client.asd.app import main
   from client.asd.args import argsfactory

   # Parse command line arguments
   args = argsfactory()

   # Run the ASD client
   main(args)

Features
--------

- Real-time speaker detection in video streams
- Speaker info data output with confidence scores
- Configurable detection parameters
- Support for various video formats
"""
