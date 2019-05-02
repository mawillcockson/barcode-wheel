"""freetype_metrics.py but for HarfBuzz"""

import sys
import svgwrite
from collections import namedtuple
import pathlib

import barcode_wheel


def main():
    file_name = pathlib.Path(sys.argv[0]).with_suffix(".svg")
    drawing = svgwrite.Drawing(filename=str(file_name), size=("100%", "100%"))
    Window = namedtuple("Window", "width, height")
    window = Window(0, 0)
    #text = "Ty,gM`Ǖ"
    #text = "Ty"
    text = "M" if len(sys.argv) <= 1 else sys.argv[1]

    metrics = list(barcode_wheel.glyph_metrics(text, "sans-serif"))[0]
    bounding_box = barcode_wheel.text_bounding_box(text, "sans-serif")

    drawing.add(
        drawing.text(
            text=text,
            insert=(0, 0),
            font_size=metrics.units_per_em,
            font_family="sans-serif",
        )
    )

    def vert_line(x_pos):
        drawing.add(
            drawing.line(
                start=(x_pos, metrics.extents.height * 1.2),
                end=(x_pos, metrics.extents.height * 0.2),
                stroke="black",
                stroke_width=10,
            )
        )

    def hori_line(y_pos):
        drawing.add(
            drawing.line(
                start=(metrics.extents.x_bearing * 0.2, y_pos),
                end=(metrics.positions.x_advance, y_pos),
                stroke="black",
                stroke_width=10,
            )
        )

                   # x_bearing is the left side of the bounding box of the character relative to x=0
    for metric in [metrics.extents.x_bearing,
                   # since width is the absolute width of the character, we add x_bearing to get the right side
                   # of the characters bounding box relative to x=0
                   metrics.extents.width + metrics.extents.x_bearing,
                   # x_advance is unlikely to be useful, as it's the measurment from x=0 to where the next character should start
                   #metrics.positions.x_advance,
                   # Don't know about x_offset
                   #0,
                   ]:
        vert_line(metric)

                   # y_bearing is where the top of the character sits compared to y=0
    for metric in [-metrics.extents.y_bearing,
                   # height is still the actual height of the character, but this is the absolute height,
                   # so to get the bottom of the character relative to y=0, take the y_bearing - height
                   -metrics.extents.y_bearing - metrics.extents.height,
                   0,
                   # Don't know about y_advance or y_offset
                   ]:
        hori_line(metric)

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
