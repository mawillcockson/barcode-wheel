import logging
import pathlib
import shlex
import subprocess
import tempfile
from io import StringIO
import fontconfig

import svgwrite

import barcode_wheel

test_svg = pathlib.Path("./test_wheel.svg")


def main():
    # Logging
    logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)
    log = logging.getLogger("test_wheel")

    # svgwrite canvas
    drawing = svgwrite.Drawing(
        filename=str(test_svg),
        size=("100%", "100%"),
        # profile="tiny",
        preserveAspectRatio="xMidyMid meet",
        viewBox="0 0 200 200",
    )

    # Barcodes
    def add_to_defs(*args):
        for arg in args:
            drawing.defs.add(arg)

    barcode1_symbol, barcode1_clip = barcode_wheel.barcode(22001)
    barcode2_symbol, barcode2_clip = barcode_wheel.barcode(22101)

    add_to_defs(barcode1_symbol, barcode1_clip, barcode2_symbol, barcode2_clip)

    drawing.add(drawing.use(href=barcode1_symbol, insert=(0, 0), size=(100, 100)))

    drawing.add(drawing.use(href=barcode2_symbol, insert=(100, 0), size=(100, 100)))

    # Picture
    image = drawing.add(
        drawing.image(
            href="4094485-random-picture.gif", insert=(0, 100), size=(100, 100)
        )
    )
    image.fit()

    # Text
    text_container = drawing.defs.add(
        barcode_wheel.text_filled_area(text="Does this fit?", font_family="sans-serif")
    )
    drawing.add(drawing.use(href=text_container, insert=(100, 100), size=(100, 100)))
    drawing.add(
        drawing.rect(
            insert=(100, 100),
            size=(100, 100),
            fill="none",
            stroke_width=0.25,
            stroke="black",
        )
    )

    # CSS styling
    drawing.defs.add(
        drawing.style(
            f"""
            .background {{
                fill: white;
                stroke: none;
            }}
            #{barcode1_symbol.get_id()} .foreground {{
                fill: blue;
                stroke: none;
            }}
            #{barcode2_symbol.get_id()} .foreground {{
                fill: red;
                stroke: none;
            }}
            """
        )
    )

    # Border
    drawing.add(
        drawing.path(
            d="M 0 0 L 200 0 L 200 200 L 0 200 Z",
            stroke="black",
            stroke_width=2,
            fill="none",
        )
    )

    drawing.save(pretty=True)


if __name__ == "__main__":
    main()
