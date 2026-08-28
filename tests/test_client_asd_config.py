# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for ASDConfig dataclass."""

import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from client.asd.config import ASDConfig


@pytest.mark.unit
class TestASDConfig(unittest.TestCase):
    def setUp(self):
        self.args = MagicMock()
        self.args.asd_server = "localhost:50055"
        self.args.input_mp4 = "video.mp4"
        self.args.input_audio = "audio.wav"
        self.args.output_speaker_info = "output.csv"
        self.args.chunk_size_video_bytes = 1048576
        self.args.chunk_size_audio_secs = 1.0
        self.args.asd_input_audio_codec = "WAV"
        self.args.asd_input_video_codec = None
        self.args.diarization_file = None

    def test_from_args(self):
        config = ASDConfig.from_args(self.args)
        self.assertEqual(config.asd_server, "localhost:50055")
        self.assertEqual(config.input_mp4, "video.mp4")
        self.assertEqual(config.input_audio, "audio.wav")
        self.assertEqual(config.output_speaker_info, "output.csv")
        self.assertEqual(config.chunk_size_video_bytes, 1048576)
        self.assertEqual(config.chunk_size_audio_secs, 1.0)
        self.assertEqual(config.input_audio_codec, "WAV")
        self.assertIsNone(config.input_video_codec)
        self.assertIsNone(config.diarization_file)

    def test_str(self):
        config = ASDConfig.from_args(self.args)
        output = str(config)
        self.assertIn("ASD Configuration", output)
        self.assertIn("localhost:50055", output)
        self.assertIn("video.mp4", output)
        self.assertIn("audio.wav", output)

    @patch("client.asd.config.is_file_available")
    def test_validate_asd_config_success(self, mock_is_file_available):
        mock_is_file_available.return_value = True
        config = ASDConfig.from_args(self.args)
        self.assertTrue(config.validate_asd_config())

    @patch("client.asd.config.is_file_available")
    def test_validate_asd_config_invalid_video(self, mock_is_file_available):
        mock_is_file_available.side_effect = lambda path, _exts: path != "video.mp4"
        config = ASDConfig.from_args(self.args)
        with self.assertRaises(RuntimeError):
            config.validate_asd_config()

    @patch("client.asd.config.is_file_available")
    def test_validate_asd_config_invalid_audio(self, mock_is_file_available):
        mock_is_file_available.side_effect = lambda path, _exts: path != "audio.wav"
        config = ASDConfig.from_args(self.args)
        with self.assertRaises(RuntimeError):
            config.validate_asd_config()

    @patch("client.asd.config.is_file_available")
    def test_validate_asd_config_unsupported_codec(self, mock_is_file_available):
        mock_is_file_available.return_value = True
        self.args.asd_input_audio_codec = "FLAC"
        config = ASDConfig.from_args(self.args)
        with self.assertRaises(RuntimeError):
            config.validate_asd_config()

    @patch("client.asd.config.is_file_available")
    def test_validate_asd_config_invalid_diarization(self, mock_is_file_available):
        mock_is_file_available.side_effect = lambda path, _exts: path != "diar.json"
        self.args.diarization_file = "diar.json"
        config = ASDConfig.from_args(self.args)
        with self.assertRaises(RuntimeError):
            config.validate_asd_config()


if __name__ == "__main__":
    unittest.main()
