"""Image utilities for mosaic splitting and processing."""

import logging
from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)


def split_mosaic(
    mosaic_bytes: bytes,
    output_dir: Optional[Path] = None,
    rows: int = 2,
    cols: int = 3,
    padding: int = 0,
) -> list[bytes]:
    """Split a mosaic image into individual cell images.

    Args:
        mosaic_bytes: The mosaic image as bytes
        output_dir: Optional directory to save individual images
        rows: Number of rows in the grid (default: 2)
        cols: Number of columns in the grid (default: 3)
        padding: Pixels to trim from each cell edge (default: 0)

    Returns:
        List of image bytes, one per cell (left-to-right, top-to-bottom)
    """
    # Load the mosaic image
    mosaic = Image.open(BytesIO(mosaic_bytes))
    width, height = mosaic.size

    # Calculate cell dimensions
    cell_width = width // cols
    cell_height = height // rows

    logger.info(
        f"Splitting {width}x{height} mosaic into {rows}x{cols} grid "
        f"(cell size: {cell_width}x{cell_height})"
    )

    cells = []
    for row in range(rows):
        for col in range(cols):
            # Calculate cell boundaries
            left = col * cell_width + padding
            upper = row * cell_height + padding
            right = (col + 1) * cell_width - padding
            lower = (row + 1) * cell_height - padding

            # Crop the cell
            cell = mosaic.crop((left, upper, right, lower))

            # Convert to bytes
            buffer = BytesIO()
            cell.save(buffer, format="PNG")
            cell_bytes = buffer.getvalue()
            cells.append(cell_bytes)

            # Save to file if output_dir provided
            if output_dir:
                output_dir.mkdir(parents=True, exist_ok=True)
                cell_index = row * cols + col
                cell_path = output_dir / f"cell_{cell_index:02d}.png"
                cell_path.write_bytes(cell_bytes)
                logger.info(f"Saved cell {cell_index} to {cell_path}")

    logger.info(f"Split mosaic into {len(cells)} cells")
    return cells


def resize_image(
    image_bytes: bytes,
    max_size: int = 1024,
    quality: int = 85,
) -> bytes:
    """Resize an image to fit within max dimensions while preserving aspect ratio.

    Args:
        image_bytes: The image as bytes
        max_size: Maximum dimension (width or height) in pixels
        quality: JPEG quality for output (1-100)

    Returns:
        Resized image as bytes (JPEG format)
    """
    img = Image.open(BytesIO(image_bytes))

    # Calculate new dimensions
    width, height = img.size
    if width > max_size or height > max_size:
        if width > height:
            new_width = max_size
            new_height = int(height * (max_size / width))
        else:
            new_height = max_size
            new_width = int(width * (max_size / height))

        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        logger.info(f"Resized image from {width}x{height} to {new_width}x{new_height}")

    # Convert to RGB if necessary (for JPEG)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Save to bytes
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()


def get_image_dimensions(image_bytes: bytes) -> tuple[int, int]:
    """Get the dimensions of an image.

    Args:
        image_bytes: The image as bytes

    Returns:
        Tuple of (width, height)
    """
    img = Image.open(BytesIO(image_bytes))
    return img.size


def apply_segment_pattern(
    images: list[bytes],
    pattern: list[int],
) -> list[bytes]:
    """Apply a reuse pattern to map images to segments.

    Args:
        images: List of available images (0-indexed)
        pattern: List of image indices for each segment (1-indexed for user friendliness)
                 e.g., [1, 1, 2, 2, 3] means segments 0-1 use image 0,
                 segments 2-3 use image 1, segment 4 uses image 2

    Returns:
        List of image bytes, one per segment

    Raises:
        ValueError: If pattern references invalid image index
    """
    result = []
    for segment_idx, image_num in enumerate(pattern):
        # Convert from 1-indexed (user-friendly) to 0-indexed
        image_idx = image_num - 1

        if image_idx < 0 or image_idx >= len(images):
            raise ValueError(
                f"Pattern index {image_num} is out of range "
                f"(have {len(images)} images, indices 1-{len(images)})"
            )

        result.append(images[image_idx])
        logger.debug(f"Segment {segment_idx}: using image {image_num}")

    logger.info(f"Applied pattern {pattern} to {len(images)} images -> {len(result)} segments")
    return result


# Default pattern for 5 segments using 3 images
DEFAULT_PATTERN_5_SEGMENTS = [1, 1, 2, 2, 3]

# Alternative patterns
PATTERNS = {
    3: [1, 2, 3],           # 3 segments, 3 images - one each
    4: [1, 1, 2, 2],        # 4 segments, 2 images
    5: [1, 1, 2, 2, 3],     # 5 segments, 3 images (default)
    6: [1, 1, 2, 2, 3, 3],  # 6 segments, 3 images
    7: [1, 1, 2, 2, 3, 3, 3],  # 7 segments, 3 images
    8: [1, 1, 2, 2, 3, 3, 3, 3],  # 8 segments, 3 images
}


def get_default_pattern(num_segments: int) -> list[int]:
    """Get the default image reuse pattern for a given number of segments.

    Args:
        num_segments: Number of segments in the video

    Returns:
        List of image indices (1-indexed) for each segment
    """
    if num_segments in PATTERNS:
        return PATTERNS[num_segments]

    # For other counts, distribute 3 images evenly
    pattern = []
    images_per_segment = [0, 0, 0]
    for i in range(num_segments):
        # Round-robin with preference for earlier images
        idx = min(i // ((num_segments + 2) // 3), 2)
        images_per_segment[idx] += 1

    # Build pattern
    for img_idx, count in enumerate(images_per_segment):
        pattern.extend([img_idx + 1] * count)

    return pattern
