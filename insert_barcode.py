import svgwrite
from lxml.etree import parse
import subprocess
import shlex
import re
from collections import namedtuple
from io import StringIO

zint_output = subprocess.run(
    shlex.split("zint --direct --filetype=svg --barcode=34 --notext -d '12345678901'"),
    stdout=subprocess.PIPE,
)
zint_barcode = StringIO(zint_output.stdout.decode("utf8"))

tree = parse(zint_barcode)
root = tree.getroot()
g = [x for x in root.getchildren() if x.tag == "{http://www.w3.org/2000/svg}g"][0]

barcode = svgwrite.Drawing(
    filename="read_zint.svg",
    size=(root.attrib["width"], int(root.attrib["height"]) - 9),
    profile="tiny",
    preserveAspectRatio="xMidyMid meet",
    viewBox=f'0 0 {root.attrib["width"]} {int(root.attrib["height"]) - 9}',
)  # Magic number to crop text

tag_re = re.compile(r"(?<=svg})\w+$")

group = barcode.g(id="barcode", fill=g.attrib["fill"])

for elem in g:
    if "text" in elem.tag:
        continue

    tag_name = tag_re.search(elem.tag)
    if not tag_name:
        breakpoint()

    tag_name = tag_name.group()

    if tag_name not in ["rect"]:
        breakpoint()

    Rect = namedtuple("Rect", "x, y, width, height, fill")

    if "fill" in elem.attrib:
        fill = elem.attrib.pop("fill")
    else:
        fill = "#000000"

    rect_tuple = Rect(fill=fill, **elem.attrib)

    if tag_name == "rect":
        group.add(
            barcode.rect(
                insert=(rect_tuple.x, rect_tuple.y),
                size=(rect_tuple.width, rect_tuple.height),
                fill=rect_tuple.fill,
            )
        )

barcode.add(group)
barcode.save()
