# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""ElevenLabs-specific argument parsing for the S2S client.

Extracted from ``args.py`` so that ElevenLabs CLI flags live in their
own file — easy to add, modify, or remove without touching shared args.
"""

import argparse

from nvidia.ai4m.s2s.v1.s2s_pb2 import SpeechToSpeechConfig


def add_elevenlabs_config_args_to_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    """Add ElevenLabs dubbing CLI arguments to *parser*.

    All flags are prefixed with ``--elevenlabs-`` so they are clearly
    scoped to the ElevenLabs backend.

    Args:
        parser (argparse.ArgumentParser): Parser to extend.

    Returns:
        argparse.ArgumentParser: The same parser with ElevenLabs arguments added.

    Examples:
        >>> parser = argparse.ArgumentParser()
        >>> add_elevenlabs_config_args_to_parser(parser)
        >>> args = parser.parse_args([])
        >>> args.elevenlabs_num_speakers
        0
    """
    parser.add_argument(
        "--elevenlabs-num-speakers",
        type=int,
        default=0,
        help="Number of speakers for ElevenLabs dubbing. 0 = auto-detect (default: 0)",
    )
    parser.add_argument(
        "--elevenlabs-drop-background-audio",
        action="store_true",
        help="Drop background audio from the final dub (ElevenLabs)",
    )
    parser.add_argument(
        "--elevenlabs-use-profanity-filter",
        action="store_true",
        help="[BETA] Censor profanities in transcripts (ElevenLabs)",
    )
    parser.add_argument(
        "--elevenlabs-target-accent",
        type=str,
        default=None,
        help="[Experimental] Accent to apply when selecting voices (ElevenLabs)",
    )
    parser.add_argument(
        "--elevenlabs-highest-resolution",
        action="store_true",
        help="Use the highest resolution available (ElevenLabs)",
    )
    parser.add_argument(
        "--elevenlabs-watermark",
        action="store_true",
        help="Apply watermark to the output (ElevenLabs)",
    )
    parser.add_argument(
        "--elevenlabs-dubbing-studio",
        action="store_true",
        help="Prepare dub for edits in dubbing studio (ElevenLabs)",
    )
    return parser


def apply_elevenlabs_args_to_config(
    args: argparse.Namespace,
    config: SpeechToSpeechConfig,
) -> None:
    """Populate the ``elevenlabs_*`` proto fields on *config* from *args*.

    Args:
        args (argparse.Namespace): Parsed CLI args (must include the
            ``elevenlabs_*`` attributes added by
            ``add_elevenlabs_config_args_to_parser``).
        config (SpeechToSpeechConfig): Protobuf config to populate in-place.

    Examples:
        >>> config = SpeechToSpeechConfig()
        >>> args = argparse.Namespace(
        ...     elevenlabs_num_speakers=2,
        ...     elevenlabs_drop_background_audio=True,
        ...     elevenlabs_use_profanity_filter=False,
        ...     elevenlabs_target_accent=None,
        ...     elevenlabs_highest_resolution=False,
        ...     elevenlabs_watermark=False,
        ...     elevenlabs_dubbing_studio=False,
        ... )
        >>> apply_elevenlabs_args_to_config(args, config)
        >>> config.elevenlabs_num_speakers
        2
    """
    config.elevenlabs_num_speakers = getattr(args, "elevenlabs_num_speakers", 0)
    config.elevenlabs_drop_background_audio = getattr(
        args, "elevenlabs_drop_background_audio", False
    )
    config.elevenlabs_use_profanity_filter = getattr(args, "elevenlabs_use_profanity_filter", False)
    accent = getattr(args, "elevenlabs_target_accent", None)
    if accent:
        config.elevenlabs_target_accent = accent
    config.elevenlabs_highest_resolution = getattr(args, "elevenlabs_highest_resolution", False)
    config.elevenlabs_watermark = getattr(args, "elevenlabs_watermark", False)
    config.elevenlabs_dubbing_studio = getattr(args, "elevenlabs_dubbing_studio", False)
