"""Exploring the font metrics in the freetype-py API to enable proper character placement"""

import freetype
import svgpathtools
import svgwrite
from freetype import Face
from svgpathtools import Line, Path, QuadraticBezier, wsvg
import re

import barcode_wheel

if __name__ == "__main__":
    drawing = svgwrite.Drawing(filename="font_metrics.svg", size=("100%", "100%"))
    path, metrics = barcode_wheel.char_to_path("a")
    drawing.add(drawing.path(d=path.d()))

    names = [
        "width",
        "height",
        "horiAdvance",
        "horiBearingX",
        "horiBearingY",
        "vertAdvance",
        "vertBearingX",
        "vertBearingY",
    ]

    metrics_re = re.compile(r"(?i)(height)|(width)|(hori.*)|(vert.*)")

    interesting_metrics = filter(None, map(metrics_re.match, dir(metrics)))

    interesting_metric_names = [
        match_group.string for match_group in interesting_metrics
    ]

    metrics_values = {name: getattr(metrics, name) for name in interesting_metric_names}

    max_metric = max(metrics_values.values())

    min_metric = min(metrics_values.values())

    character_top_right = {"x": metrics.horiBearingX, "y": metrics.horiBearingY}

    character_bbox = {
        "tr": (metrics.horiBearingX + metrics.width, 0),
        "tl": (metrics.horiBearingX, 0),
        "br": (metrics.horiBearingX + metrics.width, metrics.height),
        "bl": (metrics.horiBearingX, metrics.height),
    }

    for x, y in character_bbox.values():
        drawing.add(
            drawing.circle(
                center=(x, y),
                r=((max_metric - min_metric) * 0.01),
                opacity=0.5,
                fill="blue",
            )
        )

    face = barcode_wheel.get_font_face()
    face.set_char_size(2 ** 16)
    face.load_char("a")
    bbox = face.glyph.outline.get_bbox()
    drawing.viewbox(0, 0, bbox.xMax - bbox.xMin, bbox.yMax - bbox.yMin)

    drawing.fit()
    drawing.save()
