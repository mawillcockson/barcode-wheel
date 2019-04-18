import barcode_wheel
import svgwrite
from io import StringIO
import pathlib
import logging


file_contents = StringIO(
    "22001,Money Order Principal,\n12345678901,Test Product (Name Here),./test_product_picture.png\n9,Mardi Gras,"
)

demo_file = pathlib.Path("./demo_barcode_wheel_contents.csv")
demo_svg = pathlib.Path("./demo_wheel.svg")


def main():
    logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)
    log = logging.getLogger("demo_wheel")

    if demo_file.exists():
        log.info(f"Using contents of '{demo_file}'")
    else:
        log.info(f"Creating '{demo_file}'")
        demo_file.write_text(file_contents.read())

    drawing = svgwrite.Drawing(
        filename=str(demo_svg),
        size=("100%", "100%"),
        profile="tiny",
        preserveAspectRatio="xMidyMid meet",
        viewBox="0 0 200 200",
    )

    pie, placeholders = barcode_wheel.draw_pie(
        center=(100, 100), radius=100, num_slices=9
    )
    drawing.add(pie)
    drawing.save()


if __name__ == "__main__":
    main()
