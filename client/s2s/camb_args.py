# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""CambAI-specific argument parsing for the S2S client.

CambAI supports optional ``chosen_dictionaries`` (array of unique
dictionary IDs) and ``ai_optimization`` (bool, default ``True``).
These are per-invocation parameters passed through the proto config.
"""

import argparse

from nvidia.ai4m.s2s.v1.s2s_pb2 import SpeechToSpeechConfig


def add_camb_config_args_to_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    """Add CambAI dubbing CLI arguments to *parser*.

    All flags are prefixed with ``--camb-`` so they are clearly
    scoped to the CambAI backend.

    Args:
        parser (argparse.ArgumentParser): Parser to extend.

    Returns:
        argparse.ArgumentParser: The same parser with CambAI arguments added.

    Examples:
        >>> parser = argparse.ArgumentParser()
        >>> add_camb_config_args_to_parser(parser)
        >>> args = parser.parse_args([])
        >>> args.camb_ai_optimization
        True
    """
    parser.add_argument(
        "--camb-ai-optimization",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable CambAI AI optimization (default: True)",
    )
    parser.add_argument(
        "--camb-chosen-dictionaries",
        type=str,
        default=None,
        help=(
            "Comma-separated CambAI dictionary IDs for custom terminology "
            "(e.g. '1,5,12'). Optional."
        ),
    )
    return parser


def apply_camb_args_to_config(
    args: argparse.Namespace,
    config: SpeechToSpeechConfig,
) -> None:
    """Populate CambAI-specific proto fields on *config* from *args*.

    Args:
        args (argparse.Namespace): Parsed CLI args with ``camb_*``
            attributes from ``add_camb_config_args_to_parser``.
        config (SpeechToSpeechConfig): Protobuf config to populate in-place.

    Examples:
        >>> config = SpeechToSpeechConfig()
        >>> args = argparse.Namespace(
        ...     camb_ai_optimization=False,
        ...     camb_chosen_dictionaries="1,5",
        ... )
        >>> apply_camb_args_to_config(args, config)
        >>> config.camb_ai_optimization
        False
    """
    ai_opt = getattr(args, "camb_ai_optimization", True)
    config.camb_ai_optimization = ai_opt

    dict_str = getattr(args, "camb_chosen_dictionaries", None)
    if dict_str:
        ids = [int(x.strip()) for x in dict_str.split(",") if x.strip()]
        config.camb_chosen_dictionaries.extend(ids)
