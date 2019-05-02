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
    window = Window(100, 100)
    text = "Ty,gM`Ǖ" if len(sys.argv) <= 1 else sys.argv[1]
    font_family = "sans-serif"

    drawing.add(
        drawing.rect(
            insert=(0, 0),
            size=window,
            fill="orange",
            opacity=0.5,
        )
    )

    scaled_bounding_box = barcode_wheel.scaled_text_bounding_box(
        target_box=window,
        string=text,
        font_family=font_family,
    )

    bounding_box = barcode_wheel.text_bounding_box(text, font_family=font_family)

    scaled_dimensions = barcode_wheel.box_in_box(starting_box=(bounding_box.width, bounding_box.height), target_box=window)

    drawing.add(
        drawing.rect(
            insert=(scaled_dimensions.x_offset, scaled_dimensions.y_offset),
            size=(scaled_dimensions.width, scaled_bounding_box.height),
            fill="grey",
            opacity=0.5,
        )
    )

    tfa = drawing.defs.add(
        barcode_wheel.text_filled_area(text, font_family)
    )

    drawing.add(
        drawing.use(
            href=tfa,
            insert=(0, 0),
            size=window,
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
    drawing.viewbox(-window.width * 0.1, -window.height * 0.1, window.width * 1.2, window.height * 1.2)
    drawing.fit()
    drawing.save(pretty=True)


if __name__ == "__main__":
    main()
