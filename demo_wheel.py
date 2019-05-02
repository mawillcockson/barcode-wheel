"""Demonstrates how an application might use the barcode_wheel library"""
import sys
import barcode_wheel
import svgwrite
import pathlib
import logging
import tempfile
import csv
from time import sleep


demo_contents = (
"""
22001,Money Order (Principal),
22101,Money Order (Fee),
10502,Club Card Savings,
12345678901,Test Product (Name Here),./4094485-random-picture.gif
9,Mardi Gras,
"""
)

PROG_NAME = pathlib.Path(sys.argv[0])


def main():
    demo_file = pathlib.Path(f"./{PROG_NAME.with_suffix('.csv')}")
    demo_svg = pathlib.Path(f"./{PROG_NAME.with_suffix('.svg')}")

    logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)
    log = logging.getLogger(f"{PROG_NAME.stem}")

    log.info(
"""
This demo file includes a demo dataset.

To use your own dataset, make a file called 'demo_wheel.csv' and put it in the same folder
as this file.

The format for each line is:

PLU/UPC,Name,filepath to picture
"""
    )

    if demo_file.exists():
        log.info(f"Using contents of '{demo_file}'")
    else:
        temp_file = tempfile.NamedTemporaryFile(mode="w+t", encoding="utf-8", dir=str(pathlib.Path.cwd()))
        log.info(f"No file found\nUsing default demo contents in temporary file:\n{temp_file.name}")
        demo_file = pathlib.Path(temp_file.name)
        with demo_file.open(mode="w", newline="") as demo:
            csv_writer = csv.writer(demo)
            for row in demo_contents.split("\n"):
                if not row:
                    continue
                csv_writer.writerow(row.split(","))

    num_slices = 0
    with demo_file.open() as demo:
        reader = csv.DictReader(
            f=demo,
            fieldnames=["PLU", "NAME", "PICTURE"],
        )
        for line in reader:
            continue


    drawing = svgwrite.Drawing(
        filename=str(demo_svg),
        size=("100%", "100%"),
        #profile="tiny",
        preserveAspectRatio="xMidyMid meet",
        viewBox="0 0 200 200",
    )

    wheel, placeholders, defs = barcode_wheel.wheel_template(
        center=(100, 100), radius=100, num_slices=9
    )
    drawing.add(wheel)
    for def_item in defs:
        drawing.defs.add(def_item)


    drawing.save()


if __name__ == "__main__":
    main()
