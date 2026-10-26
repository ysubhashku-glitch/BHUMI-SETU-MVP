"""
Kaithi Document Layout Analysis and Text-Region Segmentation Module
Analyzes document layout, isolates text blocks and tabular columns in Bihar Khatiyans,
and extracts line and glyph bounding boxes with normalized coordinates.
"""

import time
from typing import List, Dict, Any, Tuple, Optional
from PIL import Image

class SegmentedBoundingBox:
    def __init__(self, x_min: float, y_min: float, x_max: float, y_max: float):
        self.x_min = round(max(0.0, min(1.0, x_min)), 4)
        self.y_min = round(max(0.0, min(1.0, y_min)), 4)
        self.x_max = round(max(0.0, min(1.0, x_max)), 4)
        self.y_max = round(max(0.0, min(1.0, y_max)), 4)

    def to_dict(self) -> Dict[str, float]:
        return {
            "x_min": self.x_min,
            "y_min": self.y_min,
            "x_max": self.x_max,
            "y_max": self.y_max
        }


class SegmentedGlyphRegion:
    def __init__(
        self,
        glyph_index: int,
        bbox: SegmentedBoundingBox,
        aspect_ratio: float,
        pixel_density: float
    ):
        self.glyph_index = glyph_index
        self.bbox = bbox
        self.aspect_ratio = round(aspect_ratio, 2)
        self.pixel_density = round(pixel_density, 3)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "glyph_index": self.glyph_index,
            "bbox": self.bbox.to_dict(),
            "aspect_ratio": self.aspect_ratio,
            "pixel_density": self.pixel_density
        }


class SegmentedLineRegion:
    def __init__(
        self,
        line_index: int,
        bbox: SegmentedBoundingBox,
        region_type: str = "TEXT_LINE",  # HEADER, TABULAR_ROW, MARGIN, TEXT_LINE
        glyphs: Optional[List[SegmentedGlyphRegion]] = None
    ):
        self.line_index = line_index
        self.bbox = bbox
        self.region_type = region_type
        self.glyphs = glyphs or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "line_index": self.line_index,
            "bbox": self.bbox.to_dict(),
            "region_type": self.region_type,
            "glyph_count": len(self.glyphs),
            "glyphs": [g.to_dict() for g in self.glyphs]
        }


class SegmentationResult:
    def __init__(
        self,
        width: int,
        height: int,
        lines: List[SegmentedLineRegion],
        columns: List[SegmentedBoundingBox],
        duration_sec: float
    ):
        self.width = width
        self.height = height
        self.lines = lines
        self.columns = columns
        self.duration_sec = round(duration_sec, 3)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_width": self.width,
            "image_height": self.height,
            "total_lines": len(self.lines),
            "total_columns": len(self.columns),
            "duration_sec": self.duration_sec,
            "lines": [l.to_dict() for l in self.lines],
            "columns": [c.to_dict() for c in self.columns]
        }


class KaithiDocumentSegmenter:
    """
    Layout and region segmenter for historical cursive documents.
    Operates on binarized images (ink=0, background=255).
    """

    @classmethod
    def segment(
        cls,
        binary_image: Image.Image,
        min_line_height_px: int = 12,
        min_glyph_width_px: int = 8
    ) -> SegmentationResult:
        start_time = time.time()
        w, h = binary_image.size
        pixels = binary_image.load()

        # Step 1: Horizontal Projection Profile (detect line boundaries)
        # Sum dark pixels (0) per row
        row_density = [0] * h
        for y in range(h):
            row_density[y] = sum(1 for x in range(w) if pixels[x, y] == 0)

        # Detect line segments using density threshold
        avg_density = sum(row_density) / max(h, 1)
        line_threshold = max(2, int(avg_density * 0.15))

        line_spans: List[Tuple[int, int]] = []
        in_line = False
        start_y = 0

        for y in range(h):
            if row_density[y] >= line_threshold:
                if not in_line:
                    in_line = True
                    start_y = y
            else:
                if in_line:
                    in_line = False
                    if (y - start_y) >= min_line_height_px:
                        line_spans.append((start_y, y))

        if in_line and (h - start_y) >= min_line_height_px:
            line_spans.append((start_y, h))

        # If no distinct lines found (e.g. sparse document), fallback to full height or uniform grid
        if not line_spans:
            line_spans = [(0, h)]

        # Step 2: Vertical Profile per line to isolate glyph/word clusters
        line_regions: List[SegmentedLineRegion] = []
        for line_idx, (y1, y2) in enumerate(line_spans, start=1):
            lh = y2 - y1
            col_density = [0] * w
            for x in range(w):
                col_density[x] = sum(1 for y in range(y1, y2) if pixels[x, y] == 0)

            # Determine glyph bounding spans
            in_glyph = False
            start_x = 0
            glyphs: List[SegmentedGlyphRegion] = []
            glyph_idx = 1

            for x in range(w):
                if col_density[x] > 0:
                    if not in_glyph:
                        in_glyph = True
                        start_x = x
                else:
                    if in_glyph:
                        in_glyph = False
                        gw = x - start_x
                        if gw >= min_glyph_width_px:
                            # Refine vertical extent for this glyph
                            glyph_y_pixels = [
                                y for y in range(y1, y2)
                                for gx in range(start_x, x)
                                if pixels[gx, y] == 0
                            ]
                            gy1 = min(glyph_y_pixels) if glyph_y_pixels else y1
                            gy2 = max(glyph_y_pixels) + 1 if glyph_y_pixels else y2
                            aspect = gw / max(gy2 - gy1, 1)
                            total_ink = len(glyph_y_pixels)
                            density = total_ink / max(gw * (gy2 - gy1), 1)

                            g_bbox = SegmentedBoundingBox(
                                x_min=start_x / w,
                                y_min=gy1 / h,
                                x_max=x / w,
                                y_max=gy2 / h
                            )
                            glyphs.append(
                                SegmentedGlyphRegion(
                                    glyph_index=glyph_idx,
                                    bbox=g_bbox,
                                    aspect_ratio=aspect,
                                    pixel_density=density
                                )
                            )
                            glyph_idx += 1

            # Determine line horizontal bounds
            if glyphs:
                lx1 = min(g.bbox.x_min for g in glyphs)
                lx2 = max(g.bbox.x_max for g in glyphs)
            else:
                lx1, lx2 = 0.05, 0.95

            # Classify line region based on vertical position
            norm_y = (y1 + y2) / (2.0 * h)
            if norm_y < 0.25:
                reg_type = "HEADER"
            elif norm_y > 0.85:
                reg_type = "FOOTER_OR_SIGNATURE"
            else:
                reg_type = "TABULAR_ROW"

            line_bbox = SegmentedBoundingBox(
                x_min=lx1,
                y_min=y1 / h,
                x_max=lx2,
                y_max=y2 / h
            )

            line_regions.append(
                SegmentedLineRegion(
                    line_index=line_idx,
                    bbox=line_bbox,
                    region_type=reg_type,
                    glyphs=glyphs
                )
            )

        # Step 3: Column layout approximation for tabular Khatiyan
        # Standard CS Khatiyan table columns: [Khesra (Plot), Nature, Rakba (Area), Lagan (Rent)]
        columns = [
            SegmentedBoundingBox(x_min=0.05, y_min=0.25, x_max=0.28, y_max=0.85),
            SegmentedBoundingBox(x_min=0.28, y_min=0.25, x_max=0.52, y_max=0.85),
            SegmentedBoundingBox(x_min=0.52, y_min=0.25, x_max=0.75, y_max=0.85),
            SegmentedBoundingBox(x_min=0.75, y_min=0.25, x_max=0.95, y_max=0.85),
        ]

        return SegmentationResult(
            width=w,
            height=h,
            lines=line_regions,
            columns=columns,
            duration_sec=time.time() - start_time
        )
