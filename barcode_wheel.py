"""Makes barcode-wheels"""
import base64
import pathlib
import re
import shlex
import subprocess
import sys
from collections import OrderedDict, deque, namedtuple
from functools import partial
from itertools import islice
from io import StringIO
from math import asin, cos, radians, sin, tan
from typing import Dict, TextIO, Tuple

import svgwrite
from lxml.etree import parse

if sys.version_info < (3, 6):
    raise Exception("OrderedDicts only remember insertion order for Python 3.6 and up")

placeholder_defaults = OrderedDict(
    [
        ("barcode", {"padding": 0.1, "width": 0.15}),
        ("plu", {"padding": 0.05, "width": 0.3}),
        ("name", {"padding": 0.05, "width": 0.05}),
        ("picture", {"padding": 0.02, "width": 1.0}),
    ]
)


def zint_barcode(value: int) -> StringIO:
    """Runs zint to produce barcode SVG, which it returns as io.StringIO"""
    # String formatting is used to left-pad the value to at least 11 digits long
    # using 0's for padding, and formatting the result as an integer decimal
    padded_value = f"{value:0>11d}"
    if len(padded_value) > 11:
        raise TypeError(f"'{value}' is too long; 11 digits max")

    zint_output = subprocess.run(
        shlex.split(
            f"zint --direct --filetype=svg --barcode=34 --notext -d '{padded_value}'"
        ),
        stdout=subprocess.PIPE,
    )

    return StringIO(zint_output.stdout.decode("utf8"))


# NOTE: This should use an SVG parsing library instead, so that any inconsistencies between output in different zint barcode types don't result in hard-to-fix lxml errors
def barcode_group(value: int) -> svgwrite.container.Group:
    """Build an svgwrite.container.Group object by parsing SVG as XML on hopes and dreams"""
    tree = parse(zint_barcode(value))
    root = tree.getroot()
    group = [x for x in root.getchildren() if x.tag == "{http://www.w3.org/2000/svg}g"][
        0
    ]

    barcode = svgwrite.container.Group(id="barcode", fill=group.attrib["fill"])

    tag_re = re.compile(r"(?<=svg})\w+$")

    for elem in group:
        if "text" in elem.tag:
            continue

        tag_name_search = tag_re.search(elem.tag)
        if not tag_name_search:
            raise NameError("tag name does not match")

        tag_name = tag_name_search.group()

        if tag_name not in ["rect"]:
            raise TypeError("zint made something else, other than a rectangle group")

        Rect = namedtuple("Rect", "x, y, width, height, fill")

        if "fill" in elem.attrib:
            fill = elem.attrib.pop("fill")
        else:
            fill = "#000000"

        rect_tuple = Rect(fill=fill, **elem.attrib)

        if tag_name == "rect":
            barcode.add(
                svgwrite.shapes.Rect(
                    insert=(rect_tuple.x, rect_tuple.y),
                    size=(rect_tuple.width, rect_tuple.height),
                    fill=rect_tuple.fill,
                )
            )

    return barcode


def make_barcode(value: int) -> StringIO:
    barcode = svgwrite.Drawing(
        filename="temp.svg",
        size=(115, 50),  # Magic number dimensions that zint always makes
        profile="tiny",
        preserveAspectRatio="xMidyMid meet",
        viewBox=f"0 0 115 50",
    )
    barcode.add(barcode_group(value))
    barcode_svg = StringIO()
    barcode.write(barcode_svg)

    return barcode_svg


def svg_uri_embed(file_like: TextIO) -> StringIO:
    mime_type = "data:image/svg+xml;base64,"
    uri = StringIO(mime_type)
    uri.seek(0, 2)  # Move to end of "file"
    file_like.seek(0, 0)  # Move to beginning of "file"
    uri.write(
        base64.b64encode(
            file_like.read().encode("utf8")
        ).decode()  # Don't want bytes, want strings
    )
    return uri


def gen_vertices(
    center: Tuple[float, float], radius: int, num_slices: int
) -> Tuple[float, float]:
    angle = 0.0
    while True:
        yield (
            cos(radians(angle)) * radius + center[0],
            sin(radians(angle)) * radius + center[1],
        )

        angle += 360 / num_slices

        if angle >= 360:
            break


def gen_slice_points(
    center: Tuple[float, float], radius: int, num_slices: int
) -> object:
    vertices = deque(gen_vertices(center, radius, num_slices))
    rotated_vertices = deque(gen_vertices(center, radius, num_slices))
    rotated_vertices.rotate(-1)
    yield from zip(vertices, rotated_vertices)


def box_height(percent_distance_from_center: float, radius: float, num_slices: int) -> float:
    """Compute the maximum height of a rectangle positioned on the midline of a slice based on the distance from the center of the pie, and the number of slices of pie"""
    half_angle = radians((360 / num_slices) / 2)
    return sin(half_angle) * percent_distance_from_center * radius * 2


def placeholder_group(
    slice_num: int,
    center: Tuple[float, float],
    radius: float,
    num_slices: int,
    placeholder_layout: Dict[str, Dict[str, float]],
    **kwargs,
) -> svgwrite.container.Group:
    # Create group for placeholders for this slice
    slice_group = svgwrite.container.Group(id=f"slice{slice_num}-placeholders")

    # Every placeholder is rotated the same way, so make a function to make that easier
    primary_angle = 360 / num_slices
    rotate = partial(
        svgwrite.mixins.Transform.rotate,
        # Rotate the placeholder by the angle of each slice, plus a half-angle so it sits in the center
        angle=(primary_angle * (slice_num - 0.5)),
        center=center,
    )

    placeholder_list = list()

    for i, placeholder in enumerate(placeholder_layout):
        # Add up the total space taken up by padding and widths of all components to the left of this component
        # OrderedDict ensures items are returned following insertion order
        percent_distance_from_center = sum(
            map(
                lambda spacings: sum(spacings.values()),
                islice(placeholder_layout.values(), i),
            )
        )
        # Then add the padding for this component
        # This number represents the percentage of the length of the slice away from the center of the pie where this component will be placed
        percent_distance_from_center += placeholder_layout[placeholder]["padding"]

        # Compute the maximum height of a box with an edge in the slice, perpendicular to the radius, at that distance from the pie center
        height = box_height(
            percent_distance_from_center=percent_distance_from_center,
            radius=radius,
            num_slices=num_slices,
        )

        half_angle = radians((360 / num_slices) / 2)

        if i == len(placeholder_layout) - 1:
            # The top side of the box this component will go inside must meet both the height above the slice's midline that we've already calculated as height/2, and the arc of the curve at the same height, and since the curve is described by (cos(a), sin(a)), a triangle can be drawn from the top right of the box, to the point where the right side of the box is bisected by the slice's midline, to the center of the pie. This lets us use sin(a) == (height / 2) / r to describe the coordinate for the top right of the box
            # Solving for the angle, we get a == asin(height / (2 * r))
            # This lets us use cos(a) * r as the distance from the center of the pie to the right side of the box, and subtracting the distance to the left, we get its width
            width = cos(asin(height / (2 * radius))) * radius - percent_distance_from_center * radius * cos(half_angle)
        else:
            width = placeholder_layout[placeholder]["width"] * radius * cos(half_angle)

        placeholder_list.append(
            slice_group.add(
                svgwrite.shapes.Rect(
                    insert=(center[0] + percent_distance_from_center * cos(half_angle) * radius, center[1] - height / 2),
                    size=(width, height),
                    **kwargs,
                )
            )
        )

        rotate(placeholder_list[-1])

    return (placeholder_list, slice_group)


def draw_pie(
    center: Tuple[float, float],
    radius: int,
    num_slices: int,
    # barcode_padding: Optional[float]=None,
    # barcode_width: Optional[float]=None,
    # plu_padding: Optional[float]=None,
    # plu_width: Optional[float]=None,
    # name_padding: Optional[float]=None,
    # name_width: Optional[float]=None,
    # picture_padding: Optional[float]=None,
    **kwargs,
) -> svgwrite.path.Path:
    spacing_name_re = re.compile(r"^(?P<name>[a-z]+)_(?P<kind>(padding)|(width))$")
    placeholder_layout = {
        name: value.copy() for name, value in placeholder_defaults.items()
    }
    keys = kwargs.copy().keys()
    for arg in keys:
        if not spacing_name_re.match(arg):
            continue
        variable = spacing_name_re.match(arg)
        name = variable.group("name")
        kind = variable.group("kind")
        if name not in placeholder_layout:
            continue
        if name == "picture" and kind == "width":
            raise ValueError(
                "Cannot change width of picture; it will fill as much space as is left"
            )
        placeholder_layout[name][kind] = kwargs.pop(
            arg
        )  # Remove from dictionary so that they aren't passed as SVG attributes to functions

    # Check if the layout doesn't overlap by adding up all the paddings and widths, then subtracting 1 for the picture_width, and making sure less than 100% of the length of the slice has been used
    if sum(map(lambda x: sum(x.values()), placeholder_layout.values())) - 1 > 1:
        raise ValueError(
            f"The paddings and widths of the slice components took up more than 100% of the length of the slice:\n{placeholder_layout}"
        )

    pie = svgwrite.container.Group(id="pie")

    pie_cuts = svgwrite.path.Path(
        d=f"M {center[0]} {center[1]}", **kwargs
    )  # Start in the center of the pie

    for ((line_to_x, line_to_y), (arc_to_x, arc_to_y)) in gen_slice_points(
        center, radius, num_slices
    ):
        pie_cuts.push(
            f"L {line_to_x} {line_to_y}"
        )  # For each step, draw line to point1...
        pie_cuts.push_arc(  # Draw arc to point2...
            target=(arc_to_x, arc_to_y),
            rotation=0,
            r=radius,
            large_arc=False,
            angle_dir="+",
            absolute=True,
        )
        pie_cuts.push(f"M {center[0]} {center[1]}")  # Move back to center...
        # Repeat with point2 as point1

    pie_cuts.push(f"Z")  # Close path

    pie.add(pie_cuts)

    placeholders = list()

    for slice_num in range(num_slices):
        placeholder_list, slice_group = placeholder_group(
            placeholder_layout=placeholder_layout,
            slice_num=slice_num,
            center=center,
            radius=radius,
            num_slices=num_slices,
            **kwargs,
        )

        placeholders.append(placeholder_list)
        pie.add(slice_group)

    return (pie, placeholders)


def decorate_pie(pieces: object) -> svgwrite.Drawing:
    pass


def make_wheel(contents: pathlib.Path) -> svgwrite.Drawing:
    pass
