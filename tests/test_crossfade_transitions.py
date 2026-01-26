#!/usr/bin/env python3
"""Test script for crossfade transitions."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.video_transitions import (
    TransitionConfig,
    TransitionType,
    crossfade_two_videos,
    concatenate_with_crossfades,
    concatenate_with_smart_transitions,
    detect_scene_changes_by_image,
)
from src.utils.ffmpeg import get_video_info


async def test_crossfade_two_videos():
    """Test crossfading two videos together."""
    print("\n" + "=" * 60)
    print("TEST 1: Sequential Transition (No Speech Overlap)")
    print("=" * 60)

    # Use existing segment videos
    video1 = Path("output/v3_video/segment_00_video.mp4")
    video2 = Path("output/v3_video/segment_01_video.mp4")
    output = Path("output/test_transitions/crossfade_two.mp4")

    if not video1.exists() or not video2.exists():
        print(f"ERROR: Test videos not found")
        print(f"  video1: {video1} (exists: {video1.exists()})")
        print(f"  video2: {video2} (exists: {video2.exists()})")
        return False

    # Get input video info
    info1 = await get_video_info(video1)
    info2 = await get_video_info(video2)
    print(f"Input video 1: {info1['duration']:.2f}s")
    print(f"Input video 2: {info2['duration']:.2f}s")

    # Test with sequential transition (no speech overlap)
    gap = 0.5
    transition = TransitionConfig(
        type=TransitionType.FADE,
        duration=0.5,
        audio_crossfade=False,  # Sequential mode
        audio_gap=gap,
        audio_fade_duration=0.15,
    )

    print(f"\nApplying sequential transition with {gap}s gap...")

    result = await crossfade_two_videos(
        video1_path=video1,
        video2_path=video2,
        output_path=output,
        transition=transition,
    )

    # Verify output - sequential mode ADDS gap time
    output_info = await get_video_info(result)
    expected_duration = info1['duration'] + info2['duration'] + gap

    print(f"\nOutput video: {result}")
    print(f"Output duration: {output_info['duration']:.2f}s")
    print(f"Expected duration: ~{expected_duration:.2f}s")

    # Check if duration is roughly correct (within 0.5s tolerance)
    duration_ok = abs(output_info['duration'] - expected_duration) < 0.5
    print(f"Duration check: {'PASS' if duration_ok else 'FAIL'}")

    return duration_ok


async def test_multiple_transitions():
    """Test concatenating multiple videos with transitions."""
    print("\n" + "=" * 60)
    print("TEST 2: Multiple Videos with Sequential Transitions")
    print("=" * 60)

    # Use 3 segment videos
    videos = [
        Path("output/v3_video/segment_00_video.mp4"),
        Path("output/v3_video/segment_01_video.mp4"),
        Path("output/v3_video/segment_02_video.mp4"),
    ]
    output = Path("output/test_transitions/multi_crossfade.mp4")

    for v in videos:
        if not v.exists():
            print(f"ERROR: Video not found: {v}")
            return False

    # Get durations
    total_input = 0
    for i, v in enumerate(videos):
        info = await get_video_info(v)
        print(f"Input video {i}: {info['duration']:.2f}s")
        total_input += info['duration']

    # Use sequential transitions (no speech overlap)
    gap = 0.5
    transitions = [
        TransitionConfig(type=TransitionType.FADE, duration=0.25, audio_crossfade=False, audio_gap=gap),
        TransitionConfig(type=TransitionType.FADE, duration=0.5, audio_crossfade=False, audio_gap=gap),
    ]

    print(f"\nApplying sequential transitions with {gap}s gaps...")

    result = await concatenate_with_crossfades(
        video_paths=videos,
        output_path=output,
        transitions=transitions,
    )

    # Verify output - sequential mode ADDS gap time
    output_info = await get_video_info(result)
    total_gap_time = gap * len(transitions)
    expected_duration = total_input + total_gap_time

    print(f"\nOutput video: {result}")
    print(f"Output duration: {output_info['duration']:.2f}s")
    print(f"Expected duration: ~{expected_duration:.2f}s")

    duration_ok = abs(output_info['duration'] - expected_duration) < 1.0
    print(f"Duration check: {'PASS' if duration_ok else 'FAIL'}")

    return duration_ok


async def test_smart_transitions():
    """Test smart transitions with scene detection."""
    print("\n" + "=" * 60)
    print("TEST 3: Smart Sequential Transitions with Scene Detection")
    print("=" * 60)

    # Use 4 segment videos
    videos = [
        Path("output/v3_video/segment_00_video.mp4"),
        Path("output/v3_video/segment_01_video.mp4"),
        Path("output/v3_video/segment_02_video.mp4"),
        Path("output/v3_video/segment_03_video.mp4"),
    ]
    output = Path("output/test_transitions/smart_crossfade.mp4")

    for v in videos:
        if not v.exists():
            print(f"ERROR: Video not found: {v}")
            return False

    # Simulate image paths where some segments share the same image
    # (segments 0-1 same image, 2-3 different)
    image_paths = [
        "image_a.png",  # segment 0
        "image_a.png",  # segment 1 - same as 0
        "image_b.png",  # segment 2 - different
        "image_c.png",  # segment 3 - different
    ]

    same_scene_indices = detect_scene_changes_by_image(image_paths)
    print(f"Detected same-scene indices: {same_scene_indices}")
    print(f"  0->1: {'same scene' if 0 in same_scene_indices else 'scene change'}")
    print(f"  1->2: {'same scene' if 1 in same_scene_indices else 'scene change'}")
    print(f"  2->3: {'same scene' if 2 in same_scene_indices else 'scene change'}")

    # Get durations
    total_input = 0
    for i, v in enumerate(videos):
        info = await get_video_info(v)
        print(f"Input video {i}: {info['duration']:.2f}s")
        total_input += info['duration']

    # Sequential transitions with different gap sizes
    same_scene_gap = 0.3
    scene_change_gap = 0.5

    result = await concatenate_with_smart_transitions(
        video_paths=videos,
        output_path=output,
        same_scene_indices=same_scene_indices,
        same_scene_transition=TransitionConfig(
            type=TransitionType.FADE,
            duration=0.25,
            audio_crossfade=False,
            audio_gap=same_scene_gap,
        ),
        scene_change_transition=TransitionConfig(
            type=TransitionType.FADE,
            duration=0.5,
            audio_crossfade=False,
            audio_gap=scene_change_gap,
        ),
    )

    # Verify output - sequential mode ADDS gap time
    output_info = await get_video_info(result)
    # 1 same-scene gap (0.3s) + 2 scene-change gaps (0.5s each) = 1.3s total added
    total_gap_time = same_scene_gap * 1 + scene_change_gap * 2
    expected_duration = total_input + total_gap_time

    print(f"\nOutput video: {result}")
    print(f"Output duration: {output_info['duration']:.2f}s")
    print(f"Expected duration: ~{expected_duration:.2f}s")

    duration_ok = abs(output_info['duration'] - expected_duration) < 1.5
    print(f"Duration check: {'PASS' if duration_ok else 'FAIL'}")

    return duration_ok


async def test_transition_types():
    """Test different visual transition types (all sequential, no speech overlap)."""
    print("\n" + "=" * 60)
    print("TEST 4: Different Visual Transition Types")
    print("=" * 60)

    video1 = Path("output/v3_video/segment_00_video.mp4")
    video2 = Path("output/v3_video/segment_01_video.mp4")

    if not video1.exists() or not video2.exists():
        print("ERROR: Test videos not found")
        return False

    # All use sequential mode (no speech overlap)
    # The visual fade type affects the look but not the audio
    all_passed = True
    gap = 0.5

    for trans_type in [TransitionType.FADE]:
        output = Path(f"output/test_transitions/type_{trans_type.value}.mp4")

        transition = TransitionConfig(
            type=trans_type,
            duration=0.5,
            audio_crossfade=False,  # Sequential mode
            audio_gap=gap,
            audio_fade_duration=0.15,
        )

        print(f"\nTesting sequential {trans_type.value}...", end=" ")

        try:
            result = await crossfade_two_videos(
                video1_path=video1,
                video2_path=video2,
                output_path=output,
                transition=transition,
            )

            info = await get_video_info(result)
            print(f"OK ({info['duration']:.2f}s)")
        except Exception as e:
            print(f"FAILED: {e}")
            all_passed = False

    return all_passed


async def main():
    """Run all tests."""
    print("=" * 60)
    print("CROSSFADE TRANSITIONS TEST SUITE")
    print("=" * 60)

    # Create output directory
    output_dir = Path("output/test_transitions")
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []

    # Run tests
    results.append(("Crossfade Two Videos", await test_crossfade_two_videos()))
    results.append(("Multiple Transitions", await test_multiple_transitions()))
    results.append(("Smart Transitions", await test_smart_transitions()))
    results.append(("Transition Types", await test_transition_types()))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print("=" * 60)
    print(f"OVERALL: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    print("=" * 60)

    print(f"\nOutput files in: {output_dir.absolute()}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
