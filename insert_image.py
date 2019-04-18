import svgwrite
from barcode_wheel import svg_uri_embed, make_barcode


def main():
    barcode_svg = make_barcode(12345678901)
    barcode_uri = svg_uri_embed(barcode_svg)
    barcode_uri.seek(0, 0)

    drawing = svgwrite.Drawing(
        filename="temp.svg", size=("100%", "100%"), profile="tiny", viewBox="0 0 115 50"
    )

    image = drawing.image(href=barcode_uri.read(), insert=(0, 0), size=(115, 50))

    image.fit()
    drawing.add(image)

    drawing.save()


if __name__ == "__main__":
    main()
