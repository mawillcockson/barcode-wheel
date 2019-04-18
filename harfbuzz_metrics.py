"""freetype_metrics.py but for HarfBuzz"""

import sys
from gi.repository import HarfBuzz, GLib
import array
import fontconfig
import freetype
import svgpathtools
import svgwrite
from collections import namedtuple
from typing import Dict, Optional, TextIO, Tuple, Iterable
from barcode_wheel import get_font_file


Extents = namedtuple("Extents", ["x_bearing", "y_bearing", "width", "height"])
Positions = namedtuple("Positions", "x_advance, yadvance, x_offset, y_offset")
Metrics = namedtuple("Metrics", "positions, extents, units_per_em")


def setup_harfbuzz() -> Tuple[HarfBuzz.font_t, HarfBuzz.buffer_t]:
    """
    Finds a font for HarfBuzz to use, and creates a buffer
    
    Because this is wrapped with functools.lru_cache, the buffer returned
    may have text still in it, which means
    gi.repository.HarfBuzz.buffer_clear_contents()
    will need to be called on the buffer to return it to its empty state
    """
    font_file = get_font_file()
    font_blob = HarfBuzz.glib_blob_create(GLib.Bytes.new(font_file.read_bytes()))
    face = HarfBuzz.face_create(font_blob, 0)
    del font_blob
    font = HarfBuzz.font_create(face)
    upem = HarfBuzz.face_get_upem(face)
    del face
    HarfBuzz.font_set_scale(font, 100, 100)
    HarfBuzz.ot_font_set_funcs(font)
    buffer = HarfBuzz.buffer_create()
    # HarfBuzz.buffer_set_message_func(
    #    buffer,
    #    lambda *args: True,
    #    1,
    #    0,
    # )

    return (font, upem, buffer)


def glyphs_extents(
    font: HarfBuzz.font_t, codepoints: Iterable[int]
) -> Iterable[Extents]:
    for extent in (
        HarfBuzz.font_get_glyph_extents(font, codepoint)[1] for codepoint in codepoints
    ):
        yield Extents(extent.x_bearing, extent.y_bearing, extent.width, extent.height)


def glyph_metrics(string: str) -> Iterable[Metrics]:
    font, upem, buffer = setup_harfbuzz()
    HarfBuzz.buffer_clear_contents(buffer)

    if False:
        HarfBuzz.buffer_add_utf8(buffer, string.encode("utf-8"), 0, -1)
    elif sys.maxunicode == 0x10FFFF:
        HarfBuzz.buffer_add_utf32(
            buffer, array.array("I", string.encode("utf-32"))[1:], 0, -1
        )
    else:
        HarfBuzz.buffer_add_utf16(
            buffer, array.array("H", string.encode("utf-16"))[1:], 0, -1
        )

    # If this doesn't get run, the Python interpreter crashes
    HarfBuzz.buffer_guess_segment_properties(buffer)

    HarfBuzz.shape(font, buffer, [])
    codepoints = [info.codepoint for info in HarfBuzz.buffer_get_glyph_infos(buffer)]
    positions = HarfBuzz.buffer_get_glyph_positions(buffer)

    for extents, pos in zip(glyphs_extents(font, codepoints), positions):
        yield Metrics(
            Positions(pos.x_advance, pos.y_advance, pos.x_offset, pos.y_offset),
            extents,
            upem,
        )


def text_bounding_box(string: str) -> Tuple[int, int]:
    metrics = list(glyph_metrics(string))
    max_character_height = max(abs(metric.extents.height) for metric in metrics)
    string_width = sum(metric.positions.x_advance for metric in metrics[:-1])
    string_width += metrics[-1].extents.width
    return (string_width, max_character_height)


def scale_factor(bounding_box: Tuple[int, int], target_box: Tuple[int, int]) -> float:
    """By what factor should a given bounding box be scaled by so that it would fit perfectly
    inside a given target box?
    """
    if any(x <= 0 for x in chain(bounding_box, target_box)):
        raise ValueError("scale_factor takes only positive numbers")

    scale_width = target_box[0] / bounding_box[0]
    scale_height = target_box[1] / bounding_box[1]

    return min(scale_width, scale_height)


def text_filled_area(text: str, **kwargs) -> svgwrite.container.Symbol:
    """Creates a container with the given text filling the container"""
    bounding_box = text_bounding_box(text)

    symbol = svgwrite.container.Symbol()
    symbol.add(
        svgwrite.text.Text(
            text=text,
            insert=(0, 0),
            font_size=bounding_box[1] * scale_factor(bounding_box, (2048, 2048)),
            **kwargs,
        )
    )
    symbol.viewbox(0, 0, bounding_box[0], bounding_box[1])
    symbol.fit(horiz="center", vert="middle", scale="meet")
    return symbol


def main():
    drawing = svgwrite.Drawing(
        filename="harfbuzz_metrics.svg",
        size=("100%", "100%"),
    )
    Window = namedtuple("Window", "width, height")
    window = Window(100, 100)
    text = "ffi"

    bounding_box = text_bounding_box(text)
    text_metrics = list(glyph_metrics(text))
    left_pad = text_metrics[0].extents.x_bearing

    drawing.add(
        drawing.rect(
            insert=(left_pad, window.height - bounding_box[1]),
            size=bounding_box,
            fill="none",
            stroke="black",
            stroke_width=1
        )
    )

    drawing.add(
        drawing.text(
            text,
            insert=(0, window.height),
            font_size=100,
            font_family="sans-serif",
        )
    )


    # CSS styling
    drawing.defs.add(
        drawing.style(
            f"""
            svg {{
                margin: 0px;
                padding: 0px;
            }}
            """
        )
    )
    drawing.viewbox(0, 0, window.width, window.height)
    drawing.fit()
    drawing.save(pretty=True)


if __name__ == "__main__":
    main()
