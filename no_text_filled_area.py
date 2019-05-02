"""Replacing barcode_wheel.text_filled_area() with manual calculations"""

import sys
import svgwrite
from collections import namedtuple
import pathlib

import barcode_wheel


def main():
    file_name = pathlib.Path(sys.argv[0]).with_suffix(".svg")
    text = "Ooogie boogie!" if len(sys.argv) <= 1 else sys.argv[1]
    Window = namedtuple("Window", "width, height")
    window = Window(100, 30)
    font_family="sans-serif"
    stroke_width = 10


    drawing = svgwrite.Drawing(filename=str(file_name), size=("100%", "100%"))

    text_area = drawing.defs.add(
        barcode_wheel.text_filled_area(text=text, font_family=font_family)
    )

    use_area = drawing.add(
        drawing.use(
            href=text_area,
            insert=(0, 0),
            size=(window.width / 2, window.height),
        )
    )

    scaled_font_size = barcode_wheel.font_size_in_box(
        target_box=(use_area.attribs["width"], use_area.attribs["height"]),
        text=text,
        font_family=font_family,
    )

    scaled_bounding_box = barcode_wheel.scaled_text_bounding_box(
        target_box=(use_area.attribs["width"], use_area.attribs["height"]),
        string=text,
        font_family=font_family,
    )

    scaled_dimensions = barcode_wheel.box_in_box(
        starting_box=(scaled_bounding_box.width, scaled_bounding_box.height),
        target_box=(window.width / 2, window.height),
    )

    drawing.add(
        drawing.rect(
            insert=(window.width / 2 + stroke_width + scaled_dimensions.x_offset, scaled_dimensions.y_offset),
            size=(scaled_dimensions.width, scaled_dimensions.height),
            fill="yellow",
        )
    )

    drawing.add(
        drawing.text(
            text=text,
            insert=(
                window.width / 2 + stroke_width + scaled_bounding_box.x_offset,
                window.height / 2 + scaled_bounding_box.y_offset - scaled_bounding_box.height / 2,
            ),
            font_size=scaled_font_size,
            font_family=font_family,
        )
    )

    drawing.add(
        drawing.rect(
            insert=(-stroke_width / 2, -stroke_width / 2),
            size=(window.width + stroke_width * 2, window.height + stroke_width),
            fill="none",
            stroke="black",
            stroke_width=stroke_width,
        )
    )

    #drawing.add(
    #    drawing.rect(
    #        insert=(0, 0),
    #        size=(window.width / 2, window.height),
    #        fill="grey",
    #        opacity=0.5,
    #    )
    #)

    drawing.add(
        drawing.line(
            start=(window.width / 2 + stroke_width / 2, 0),
            end=(window.width / 2 + stroke_width / 2, window.height),
            stroke="black",
            stroke_width=stroke_width,
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
    drawing.viewbox(-stroke_width, -stroke_width, window.width + stroke_width * 3, window.height + stroke_width * 1.5)
    drawing.fit()
    drawing.save(pretty=True)


if __name__ == "__main__":
    main()
