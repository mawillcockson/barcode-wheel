"""Makes barcode-wheels"""
import base64
import pathlib
import re
import shlex
import subprocess
import sys
from collections import OrderedDict, deque, namedtuple
from functools import partial, lru_cache
from io import StringIO
from itertools import islice, chain
from math import asin, cos, radians, sin, tan
from typing import Dict, Optional, TextIO, Tuple, Iterable

from gi.repository import HarfBuzz, GLib
import array
import fontconfig
import freetype
import svgpathtools
import svgwrite
from freetype import Face
from lxml.etree import parse
from svgpathtools import Line, Path, QuadraticBezier, wsvg

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
char_size = 2 ** 16  # 48 * 64
Extents = namedtuple("Extents", "x_bearing, y_bearing, width, height")
Positions = namedtuple("Positions", "x_advance, yadvance, x_offset, y_offset")
Metrics = namedtuple("Metrics", "positions, extents, units_per_em")
BBox = namedtuple("BBox", "width, height")


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
def barcode_group(
    value: int, clip_path: Optional[str] = None, background: Optional[str] = None
) -> svgwrite.container.Group:
    """Build an svgwrite.container.Group object by parsing SVG as XML on hopes and dreams"""
    tree = parse(zint_barcode(value))
    root = tree.getroot()
    group = [x for x in root.getchildren() if x.tag == "{http://www.w3.org/2000/svg}g"][
        0
    ]

    barcode = svgwrite.container.Group(id=f"barcode-{value}")
    if clip_path:
        barcode.update(dict(clip_path=clip_path))
    # else:
    #    barcode.update(
    #        dict(
    #            clip="rect(0, 0, 9, 0)",
    #        )
    #    )

    if background:
        barcode.update(dict(fill=background))

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

        Rect = namedtuple("Rect", "x, y, width, height")

        if "fill" in elem.attrib:
            fill = elem.attrib.pop("fill")
        else:
            fill = None

        rect_tuple = Rect(**elem.attrib)

        if tag_name == "rect":
            bar = barcode.add(
                svgwrite.shapes.Rect(
                    insert=(rect_tuple.x, rect_tuple.y),
                    size=(rect_tuple.width, rect_tuple.height),
                )
            )
            if fill == "#FFFFFF":
                bar.update(dict(class_="background"))
            elif fill:
                bar.update(dict(fill=fill))
            else:
                bar.update(dict(class_="foreground"))

    return barcode


def barcode(value: int) -> svgwrite.container.Symbol:
    barcode_clip = svgwrite.masking.ClipPath(clipPathUnits="objectBoundingBox")
    barcode_clip.add(svgwrite.shapes.Rect(insert=(0, 0), size=(1, 50 / 59)))

    barcode_symbol = svgwrite.container.Symbol()
    barcode_symbol.add(barcode_group(value=value, clip_path=barcode_clip.get_funciri()))

    barcode_symbol.viewbox(0, 0, 115, 50)
    barcode_symbol.fit(horiz="center", vert="middle", scale="meet")

    return (barcode_symbol, barcode_clip)


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


def get_font_file_in_current_directory() -> freetype.Face:
    font_paths = list(pathlib.Path(".").glob("*.ttf"))
    font_paths.extend(pathlib.Path(".").glob("*.otf"))
    if not font_paths:
        raise FileNotFoundError(
            "Can't find font file.\nPlease download .ttf font file into project root"
        )

    return Face(str(font_paths[0].resolve(strict=True)))


def get_font_file(pattern: str = "sans-serif") -> pathlib.Path:
    """Working with the python_fontconfig API"""
    current_font_config = fontconfig.Config.get_current()
    pattern = fontconfig.Pattern.name_parse(pattern)
    current_font_config.substitute(pattern, fontconfig.FC.MatchPattern)
    pattern.default_substitute()

    font, status = current_font_config.font_match(pattern)
    file_path = font.get(fontconfig.PROP.FILE, 0)[0]
    if not file_path:
        raise FileNotFoundError(
            "No font file found for family '{pattern}'\nTry:\nfc-match sans-serif file family"
        )

    return pathlib.Path(file_path).resolve(strict=True)


def get_font_face() -> freetype.Face:
    return freetype.Face(str(get_font_file()))


def tuple_to_imag(t: Tuple[float, float]) -> float:
    return t[0] + t[1] * 1j


def outline_to_path(outline: freetype.Outline) -> Path:
    raise NotImplementedError("Hopefully, this isn't needed")


def char_to_path(char: str) -> Tuple[Path, freetype.GlyphMetrics]:
    if len(char) != 1:
        raise ValueError(f'1 character at a time; got {len(char)}\n"{char}"')
    if re.search(r"\s", char):  # Can't handle white-space characters yet
        raise ValueError(f'char cannot be whitespace: "{char}"')

    face = get_font_face()
    # Shamelessly stolen from <http://chatherineh.github.io/programming/2018/02/01/text-to-svg-paths>
    # Request nominal size (in points)
    # The height is set to the width if the height is left as 0
    face.set_char_size(width=char_size)

    # Load character into glyph slot so all methods apply to that glyph
    face.load_char(char)

    # Grab the outline of the glyph, and select only the y coordinate of the points
    outline = face.glyph.outline
    y = [t[1] for t in outline.points]

    # Flip the points
    outline_points = [(p[0], max(y) - p[1]) for p in outline.points]
    start, end = 0, 0
    paths = []

    for i in range(len(outline.contours)):
        end = outline.contours[i]
        points = outline_points[start : end + 1]
        points.append(points[0])
        tags = outline.tags[start : end + 1]
        tags.append(tags[0])

        segments = [[points[0]]]
        for j in range(1, len(points)):
            segments[-1].append(points[j])
            if tags[j] and j < (len(points) - 1):
                segments.append([points[j]])

        for segment in segments:
            if len(segment) == 2:
                paths.append(
                    Line(start=tuple_to_imag(segment[0]), end=tuple_to_imag(segment[1]))
                )

            elif len(segment) == 3:
                paths.append(
                    QuadraticBezier(
                        start=tuple_to_imag(segment[0]),
                        control=tuple_to_imag(segment[1]),
                        end=tuple_to_imag(segment[2]),
                    )
                )

            elif len(semgent) == 4:
                C = (
                    (segment[1][0] + segment[2][0]) / 2.0,
                    (segment[1][1] + segment[2][1]) / 2.0,
                )

                paths.append(
                    QuadraticBezier(
                        start=tuple_to_imag(segment[0]),
                        control=tuple_to_imag(segment[1]),
                        end=tuple_to_imag(C),
                    )
                )

                paths.append(
                    QuadraticBezier(
                        start=tuple_to_imag(C),
                        control=tuple_to_imag(segment[2]),
                        end=tuple_to_imag(segment[3]),
                    )
                )

        start = end + 1

    path = Path(*paths)
    return (path, face.glyph.metrics)


def text_to_path(string: str) -> svgwrite.container.Group:
    if not string:
        raise ValueError("string too short")

    group = svgwrite.container.Group()
    x_position = 0

    for char in string:
        if re.search(r"\s", char):
            face = get_font_face()
            face.set_char_size(char_size)
            face.load_char(char)
            metrics = face.glyph.metrics
            x_position += metrics.horiAdvance

        else:
            path, metrics = char_to_path(char)
            char_path = group.add(svgwrite.path.Path(path.d()))
            char_path.translate(x_position, 0)
            x_position += metrics.horiAdvance

    return group


@lru_cache(maxsize=1, typed=False)
def setup_harfbuzz(font_family: str) -> Tuple[HarfBuzz.font_t, HarfBuzz.buffer_t]:
    """
    Finds a font for HarfBuzz to use, and creates a buffer
    
    Because this is wrapped with functools.lru_cache, the buffer returned
    may have text still in it, which means
    gi.repository.HarfBuzz.buffer_clear_contents()
    will need to be called on the buffer to return it to its empty state
    """
    font_file = get_font_file(font_family)
    font_blob = HarfBuzz.glib_blob_create(GLib.Bytes.new(font_file.read_bytes()))
    face = HarfBuzz.face_create(font_blob, 0)
    del font_blob
    font = HarfBuzz.font_create(face)
    upem = HarfBuzz.face_get_upem(face)
    del face
    HarfBuzz.font_set_scale(font, upem, upem)
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


def glyph_metrics(string: str, font_family: str) -> Iterable[Metrics]:
    font, upem, buffer = setup_harfbuzz(font_family)
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


def text_bounding_box(string: str, font_family: str) -> BBox:
    metrics = list(glyph_metrics(string, font_family))
    max_character_height = max(abs(metric.extents.height) for metric in metrics)
    string_width = sum(metric.positions.x_advance for metric in metrics[:-1])
    #string_width += metrics[0].extents.x_bearing
    string_width += metrics[-1].extents.width
    return BBox(string_width, max_character_height)


def scale_factor(bounding_box: Tuple[int, int], target_box: Tuple[int, int]) -> float:
    """By what factor should a given bounding box be scaled by so that it would fit perfectly
    inside a given target box?
    """
    if any(x <= 0 for x in chain(bounding_box, target_box)):
        raise ValueError("scale_factor takes only positive numbers")

    scale_width = target_box[0] / bounding_box[0]
    scale_height = target_box[1] / bounding_box[1]

    return min(scale_width, scale_height)


def text_filled_area(text: str, font_family: str, **kwargs) -> svgwrite.container.Symbol:
    """
    Creates a container with the given text filling the container
    font_family must be specified both for HarfBuzz and the renderer so that the text actually fills the box
    """
    if "font_size" in kwargs:
        raise TypeError("text_filled_area() cannot be passed font_size, as this is used to make sure the text is scaled properly\nInstead, use svgwrite.text.Text() to make a new <text> tag")

    metrics = list(glyph_metrics(text, font_family))
    bounding_box = text_bounding_box(text, font_family)

    symbol = svgwrite.container.Symbol()
    symbol.add(
        svgwrite.text.Text(
            text=text,
            insert=(metrics[0].extents.x_bearing, bounding_box[1]),
            font_size=metrics[0].units_per_em,
            font_family=font_family,
            **kwargs,
        )
    )
    symbol.viewbox(
        metrics[0].extents.x_bearing,
        0,
        bounding_box[0] + metrics[0].extents.x_bearing,
        bounding_box[1],
    )
    symbol.fit(horiz="center", vert="middle", scale="meet")
    return symbol


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
    uri.seek(0, 0)
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


def box_height(
    percent_distance_from_center: float, radius: float, num_slices: int
) -> float:
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
            width = cos(
                asin(height / (2 * radius))
            ) * radius - percent_distance_from_center * radius * cos(half_angle)
        else:
            width = placeholder_layout[placeholder]["width"] * radius * cos(half_angle)

        placeholder_list.append(
            slice_group.add(
                svgwrite.shapes.Rect(
                    insert=(
                        center[0]
                        + percent_distance_from_center * cos(half_angle) * radius,
                        center[1] - height / 2,
                    ),
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
