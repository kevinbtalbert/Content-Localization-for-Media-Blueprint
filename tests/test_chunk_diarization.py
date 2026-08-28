# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for chunk_diarization_info and request generator diarization ordering."""

import pytest
from nvidia.ai4m.activespeakerdetection.v1.activespeakerdetection_pb2 import AudioDiarizationInfo
from nvidia.ai4m.activespeakerdetection.v1.activespeakerdetection_pb2 import AudioSegmentInfo

from client.controller.request_generators import chunk_diarization_info

pytestmark = pytest.mark.unit


def _make_diarization(num_segments: int) -> AudioDiarizationInfo:
    """Create an AudioDiarizationInfo with N dummy segments."""
    segments = [
        AudioSegmentInfo(
            start_time=i * 100,
            end_time=(i + 1) * 100,
            speaker_id=i % 2,
            word=f"word_{i}",
        )
        for i in range(num_segments)
    ]
    return AudioDiarizationInfo(segments=segments)


class TestChunkDiarizationInfo:
    """Tests for the chunk_diarization_info function."""

    def test_rows_per_chunk_splits_evenly(self) -> None:
        """6 segments with rows_per_chunk=3 yields 2 chunks."""
        info = _make_diarization(num_segments=6)
        chunks = chunk_diarization_info(info, rows_per_chunk=3)
        assert len(chunks) == 2
        assert len(chunks[0].segments) == 3
        assert len(chunks[1].segments) == 3

    def test_rows_per_chunk_splits_with_remainder(self) -> None:
        """5 segments with rows_per_chunk=2 yields 3 chunks (last has 1)."""
        info = _make_diarization(num_segments=5)
        chunks = chunk_diarization_info(info, rows_per_chunk=2)
        assert len(chunks) == 3
        assert len(chunks[0].segments) == 2
        assert len(chunks[1].segments) == 2
        assert len(chunks[2].segments) == 1

    def test_none_rows_sends_all_at_once(self) -> None:
        """rows_per_chunk=None returns all segments in a single chunk."""
        info = _make_diarization(num_segments=10)
        chunks = chunk_diarization_info(info, rows_per_chunk=None)
        assert len(chunks) == 1
        assert len(chunks[0].segments) == 10

    def test_default_rows_per_chunk_is_none(self) -> None:
        """Default rows_per_chunk is None (send all at once)."""
        info = _make_diarization(num_segments=15)
        chunks = chunk_diarization_info(info)
        assert len(chunks) == 1
        assert len(chunks[0].segments) == 15

    def test_empty_segments_returns_empty_list(self) -> None:
        """Diarization with no segments returns empty list."""
        info = AudioDiarizationInfo()
        chunks = chunk_diarization_info(info, rows_per_chunk=5)
        assert chunks == []

    def test_chunk_preserves_segment_data(self) -> None:
        """Chunked segments retain their original field values."""
        info = _make_diarization(num_segments=3)
        chunks = chunk_diarization_info(info, rows_per_chunk=2)
        # First chunk has first two segments
        assert chunks[0].segments[0].word == "word_0"
        assert chunks[0].segments[1].word == "word_1"
        # Second chunk has the third
        assert chunks[1].segments[0].word == "word_2"

    def test_rows_per_chunk_one_creates_individual_messages(self) -> None:
        """rows_per_chunk=1 creates one chunk per segment."""
        info = _make_diarization(num_segments=4)
        chunks = chunk_diarization_info(info, rows_per_chunk=1)
        assert len(chunks) == 4
        for chunk in chunks:
            assert len(chunk.segments) == 1
