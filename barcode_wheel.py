"""Makes barcode-wheels"""
import array
import base64
import csv
import pathlib
import re
import shlex
import subprocess
import sys
from collections import OrderedDict, deque, namedtuple
from functools import lru_cache, partial, reduce
from io import StringIO
from itertools import chain, islice
from math import asin, cos, radians, sin
from typing import Dict, Iterable, Mapping, NewType, Optional, List
from typing import OrderedDict as OrderedDictT
from typing import TextIO, Tuple, Union

import fontconfig
import freetype
import svgwrite
from freetype import Face
from gi.repository import GLib, HarfBuzz
from lxml.etree import parse
from svgpathtools import Line, Path, QuadraticBezier

if sys.version_info < (3, 6):
    raise Exception("OrderedDicts only remember insertion order for Python 3.6 and up")

# Default placeholders and their dimensions for each slice of the wheel
PLACEHOLDER_DEFAULTS = OrderedDict(
    [
        ("barcode", {"padding": 0.1, "width": 0.15, "rotation": 0.0}),
        ("upc", {"padding": 0.05, "width": 0.2, "rotation": 0.0}),
        ("name", {"padding": 0.05, "width": 0.2, "rotation": 90.0}),
        ("picture", {"padding": 0.02, "width": 1.0, "rotation": 90.0}),
    ]
)
# Set to largest size that *probably* won't overflow
CHAR_SIZE = 2 ** 16  # 48 * 64
# namedtuples used as argument and return values, for easy grouping of values
# NOTE: Are these cheaper to maintain than using dataclass?
Extents = namedtuple("Extents", "x_bearing, y_bearing, width, height")
Positions = namedtuple("Positions", "x_advance, y_advance, x_offset, y_offset")
Metrics = namedtuple("Metrics", "positions, extents, units_per_em")
BBox = namedtuple("BBox", "width, height, y_offset, x_offset")
UPC = NewType("UPC", str)


def upc_value(value: Union[str, int]) -> UPC:
    """
    Converts a str or int into a UPC string:

    >>> upc_value(123)
    '00000000123'
    >>> upc_value("12101")
    '00000012101'
    """
    error_message = "upc_value() only takes positive integer values"
    try:
        integer = int(value)
    except ValueError as err:
        raise ValueError(error_message) from err

    if integer < 0:
        raise ValueError(error_message)

    if integer > int("9" * 11):
        raise ValueError("UPC values must be 11 or fewer digits long")

    # String formatting is used to left-pad the value to at least 11 digits long
    # using 0's for padding, and formatting the result as an integer decimal
    return UPC(f"{integer:0>11d}")


def zint_barcode(value: Union[str, int]) -> StringIO:
    """Runs zint to produce a barcode as an SVG, which it returns as io.StringIO"""
    padded_value = upc_value(value)

    zint_output = subprocess.run(
        shlex.split(
            f"zint --direct --filetype=svg --barcode=34 --notext -d '{padded_value}'"
        ),
        stdout=subprocess.PIPE,
    )

    return StringIO(zint_output.stdout.decode("utf8"))


# NOTE: This should use an SVG parsing library instead, so that any inconsistencies between output in different zint barcode types don't result in hard-to-fix lxml errors
def barcode_group(
    value: Union[str, int],
    clip_path: Optional[str] = None,
    background: Optional[str] = None,
) -> svgwrite.container.Group:
    """Build an svgwrite.container.Group object by parsing SVG as XML on hopes and dreams"""
    tree = parse(zint_barcode(value))
    root = tree.getroot()
    group = [x for x in root.getchildren() if x.tag == "{http://www.w3.org/2000/svg}g"][
        0
    ]

    barcode_group = svgwrite.container.Group(id=f"barcode-{value}")
    if clip_path:
        barcode_group.update(dict(clip_path=clip_path))
    # else:
    #    barcode_group.update(
    #        dict(
    #            clip="rect(0, 0, 9, 0)",
    #        )
    #    )

    if background:
        barcode_group.update(dict(fill=background))

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
            rectangle = barcode_group.add(
                svgwrite.shapes.Rect(
                    insert=(rect_tuple.x, rect_tuple.y),
                    size=(rect_tuple.width, rect_tuple.height),
                )
            )
            if fill == "#FFFFFF":
                rectangle.update(dict(class_="background"))
            elif fill:
                rectangle.update(dict(fill=fill))
            else:
                rectangle.update(dict(class_="foreground"))

    return barcode_group


def barcode(value: Union[str, int]) -> svgwrite.container.Symbol:
    """
    Build a barcode that can be placed in a <defs> and then <use>d

    Has whitespace on left and right side so the barcode reader can read it
    """
    # Zint barcodes by default are 115x59 and chopping off the bottom 9 removes the blank space where the text would go, making them perfect rectangles
    # To chop this off, we make the clip path, which are floats of 0 to 1, fill the width, but only the percentage of the height that shows everything
    # but this unneeded margin area.
    barcode_clip = svgwrite.masking.ClipPath(clipPathUnits="objectBoundingBox")
    barcode_clip.add(svgwrite.shapes.Rect(insert=(0, 0), size=(1, 50 / 59)))

    barcode_symbol = svgwrite.container.Symbol()
    barcode_symbol.add(barcode_group(value=value, clip_path=barcode_clip.get_funciri()))

    # The viewbox is restricted to the same size as the resulting clipPath
    barcode_symbol.viewbox(0, 0, 115, 50)
    barcode_symbol.fit(horiz="center", vert="middle", scale="meet")

    return (barcode_symbol, barcode_clip)


def get_font_file_in_current_directory() -> freetype.Face:
    font_paths = list(pathlib.Path(".").glob("*.ttf"))
    font_paths.extend(pathlib.Path(".").glob("*.otf"))
    if not font_paths:
        raise FileNotFoundError(
            "Can't find font file.\nPlease download .ttf font file into project root"
        )

    return Face(str(font_paths[0].resolve(strict=True)))


def get_font_file(pattern: str = "sans-serif") -> pathlib.Path:
    """Uses fontconfig to return a pathlib.Path object pointing to the font file fontconfig found for the given pattern"""
    current_font_config = fontconfig.Config.get_current()
    fontconfig_pattern = fontconfig.Pattern.name_parse(pattern)
    current_font_config.substitute(fontconfig_pattern, fontconfig.FC.MatchPattern)
    fontconfig_pattern.default_substitute()

    font, status = current_font_config.font_match(fontconfig_pattern)
    file_path = font.get(fontconfig.PROP.FILE, 0)[0]
    if not file_path:
        raise FileNotFoundError(
            "No font file found for family '{pattern}'\nTry:\nfc-match sans-serif file family"
        )

    return pathlib.Path(file_path).resolve(strict=True)


@lru_cache(maxsize=1, typed=False)
def setup_harfbuzz(font_family: str) -> Tuple[HarfBuzz.font_t, int, HarfBuzz.buffer_t]:
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
    """
    Takes a HarfBuzz font object and a list of codepoints within that font, and generates
    the glyph extents HarfBuzz finds for that codepoint
    """
    for extent in (
        HarfBuzz.font_get_glyph_extents(font, codepoint)[1] for codepoint in codepoints
    ):
        yield Extents(extent.x_bearing, extent.y_bearing, extent.width, extent.height)


def glyph_metrics(string: str, font_family: str) -> Iterable[Metrics]:
    """Generates a metrics object describing the metrics of each character group in a string, for a particular font"""
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
    """
    Returns the bounding box of a given string of text, for a given font, as seen by HarfBuzz

    This bounding box should perfectly enclose all drawn areas of the text, except:

    - if the unicode codepoints aren't all in one font file
    - the string contains mixed direction text (Arabic and English)
    - the string contains linebreaks (HarfBuzz sees 1 long string of text)


    This bounding box is in unite of units_per_em, which by default is CHAR_SIZE
    """
    # First, get a list of the metrics of each character from HarfBuzz
    metrics = list(glyph_metrics(string, font_family))

    # The maximum height of the characters from y=0
    # HarfBuzz draws characters y-axis up, and measures each character's height as the distance from the y-axis top of the character,
    # down to the y-axis bottom of the character
    # This means the height is negative, but the y_bearing (top of the character from y=0) is positive
    max_character_height = max((metric.extents.y_bearing) for metric in metrics)

    # Find the lowest point on the y-axis for any character by taking the y_bearing and "subtracting" the height of the character, to get the y-axis up y height of the lowest point on the character on the y-axis, from y=0:
    # The character 'y' extends below y=0, so the y_bearing is less than abs(height), so taking y_bearing + height gives the y-axis position of the lowest point of the character 'y', with the y-axis pointing up
    min_character_height = min((metric.extents.y_bearing + metric.extents.height) for metric in metrics)

    # The true height of the string of characters is the highest character height - lowest character drawing point
    true_height = max_character_height - min_character_height

    # Each character has an x_advance, which is how much distance it takes on the x-axis to get from the current characters x_bearing position to the start of the next characters x_bearing position
    # Using this, we can add up all but the last character's x_advances to get the x-axis position of where to measure the last character's x_bearing from
    string_width = sum(metric.positions.x_advance for metric in metrics[:-1])

    # The left side of the current character is the sum of the x_advances of the characters left of the current character, plus this character's x_bearing
    # Then, the right side is that plus the width of the last character
    string_width += metrics[-1].extents.x_bearing + metrics[-1].extents.width
    return BBox(
        width=string_width,
        height=true_height,
        # Here, the y_offset and x_offset of the bounding box for the string is where to put the SVG text insertion point so that the top left of the first character's bounding box will be at (0, 0)
        y_offset=max_character_height,
        # We use x_bearing here so that the entire string is scooted to the left so that the first character starts at 0 on the x-axis
        x_offset=-metrics[0].extents.x_bearing,
    )


def scale_factor(starting_box: Tuple[int, int], target_box: Tuple[int, int]) -> float:
    """By what factor should a given box be scaled by so that it would fit perfectly
    inside a given target box?
    """
    if any(x <= 0 for x in chain(starting_box, target_box)):
        raise ValueError("scale_factor takes only positive numbers")

    scale_width = target_box[0] / starting_box[0]
    scale_height = target_box[1] / starting_box[1]

    return min(scale_width, scale_height)


def scaled_text_bounding_box(target_box: Tuple[float, float], string: str, font_family: str) -> BBox:
    """Takes a text BBox and a target (width, height) and returns a BBox scaled to fit inside those dimensions"""
    if any(x <= 0 for x in target_box):
        raise ValueError("scaled_text_bounding_box() takes only positive numbers")

    bounding_box = text_bounding_box(string=string, font_family=font_family)

    scale = scale_factor(
        starting_box=(bounding_box.width, bounding_box.height),
        target_box=target_box,
    )

    # These were originally to calculate an offset that would center the scaled bounding box
    # inside the target box
    #y_offset = (target_box[1] - (bounding_box.height * scale)) / 2
    #x_offset = (target_box[0] - (bounding_box.width * scale)) / 2

    return BBox(
        width=bounding_box.width * scale,
        height=bounding_box.height * scale,
        x_offset=bounding_box.x_offset * scale,
        y_offset=bounding_box.y_offset * scale,
    )


def box_in_box(starting_box: Tuple[float, float], target_box: Tuple[float, float]) -> BBox:
    """
    What are the dimensions of a box inside another box, if it fills the area completely
    while maintaining its aspect ratio, and what is the top left corner's offsets from the starting box's?
    """
    scale = scale_factor(starting_box=starting_box, target_box=target_box)

    y_offset = (target_box[1] - starting_box[1] * scale) / 2
    x_offset = (target_box[0] - starting_box[0] * scale) / 2

    return BBox(
        width=starting_box[0] * scale,
        height=starting_box[1] * scale,
        x_offset=x_offset,
        y_offset=y_offset,
    )


def font_size_in_box(target_box: Tuple[float, float], text: str, font_family: str) -> float:
    """
    What is the maximum font size that a given string of text can have to make it completely
    fill a box without overflowing it, or breaking/wrapping the line?
    """
    bounding_box = text_bounding_box(string=text, font_family=font_family)
    scale = scale_factor(starting_box=(bounding_box.width, bounding_box.height), target_box=target_box)
    original_font_size = list(glyph_metrics(string=text, font_family=font_family))[0].units_per_em
    return original_font_size * scale


def text_filled_area(
    text: str, font_family: str, **kwargs
) -> svgwrite.container.Symbol:
    """
    Creates a container which can be <use>d with the given text filling the width and height of the <use> area, respecting the aspect ratio of the text

    font_family must be specified both for HarfBuzz and the renderer that render the SVG containing this so that the text actually fills the box
    
    If the renderer uses a different font, the resulting image is most likely going to have text that does not fit where it's been told to
    """
    if "font_size" in kwargs:
        raise TypeError(
            "text_filled_area() cannot be passed font_size, as this is used to make sure the text is scaled properly\nInstead, use svgwrite.text.Text() to make a new <text> tag"
        )

    metrics = list(glyph_metrics(text, font_family))
    bounding_box = text_bounding_box(text, font_family)

    symbol = svgwrite.container.Symbol()
    symbol.add(
        svgwrite.text.Text(
            text=text,
            insert=(bounding_box.x_offset, bounding_box.y_offset),
            font_size=metrics[0].units_per_em,
            font_family=font_family,
            **kwargs,
        )
    )

    symbol.viewbox(
        0,
        0,
        bounding_box.width,
        bounding_box.height,
    )
    symbol.fit(horiz="center", vert="middle", scale="meet")
    return symbol


def svg_uri_embed(file_like: TextIO) -> StringIO:
    """Takes an SVG file in a TextIO and returns a StringIO with that SVG embedded in a data uri that can be put in an <img href="...">"""
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


def csv_contents(csvfile: str) -> Iterable[OrderedDictT[str, str]]:
    """Generates a list of dictionaries containing the values from CSVs the barcode_wheel should use"""
    path = pathlib.Path(csvfile).resolve(strict=True)
    fieldnames = "UPC NAME PICTURE".split()
    with path.open(mode="r", newline="") as file:
        reader = csv.DictReader(file, fieldnames=fieldnames)
        yield from reader


def csv_by_upc(
    row_list: Iterable[Dict[str, str]]
) -> Iterable[Dict[str, Mapping[str, str]]]:
    """
    Reformats the dictionary returned by csv_contents() to have a dictionary with the key as the UPC and the rest of the row contents as the value

    This can be used with a new dictionary's .update() method to make a dictionary of the CSV contents
    organized by UPC.

    Duplicate UPCs would overwirte the values of the prior, identical UPC
    """
    for row in row_list:
        yield {row.pop("UPC"): row}


def clean_upcs(
    row_list: Iterable[Mapping[str, str]]
) -> Iterable[OrderedDictT[str, Union[str, UPC]]]:
    """Runs the return of csv_contents() UPC values through upc_value()"""
    for row in row_list:
        if "UPC" in row:
            row["UPC"] = upc_value(row["UPC"])
        yield row


def add_barcode(
    row_list: Iterable[Mapping[str, Union[str, UPC]]]
) -> Iterable[Mapping[str, Union[str, UPC, svgwrite.container.Group]]]:
    """Adds a barcode SVG element to the contents returned by csv_contents() using the UPC values"""
    for row in row_list:
        if "UPC" in row:
            row["BARCODE"] = barcode(row["UPC"])
        yield row


def gen_vertices(
        num_slices: int,
        center: Tuple[float, float],
        radius: float,
) -> Iterable[Tuple[float, float]]:
    """Generates the coordinates of where each slice of the wheel intersects the circumference"""
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
    num_slices: int,
    center: Tuple[float, float],
    radius: float,
) -> Iterable[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """
    Generates the coordinate pairs used to draw each slice of the pie

    Takes the list of points given by gen_vertices and returns ([0], [-1]), ([1], [0]), ([2], [1]), etc...
    """
    vertices = deque(
        gen_vertices(
            num_slices=num_slices,
            center=center,
            radius=radius,
        )
    )
    rotated_vertices = deque(
        gen_vertices(
            num_slices=num_slices,
            center=center,
            radius=radius,
        )
    )
    rotated_vertices.rotate(-1)
    yield from zip(vertices, rotated_vertices)


def box_height(
    percent_distance_from_center: float, radius: float, num_slices: int
) -> float:
    """Compute the maximum height of a rectangle positioned on the midline of a slice based on the distance from the center of the pie, and the number of slices of pie"""
    half_angle = radians((360 / num_slices) / 2)
    return sin(half_angle) * percent_distance_from_center * radius * 2


def placeholder_last(
    num_slices: int,
    center: Tuple[float, float],
    radius: float,
    placeholder: svgwrite.container.Symbol,
    percent_distance_from_center: float,
    **kwargs) -> svgwrite.container.Use:
    """Used to compute the correct <use> width, height, and insert coordinates so that the area perfectly fills what's left of the slice, meeting the slice's arc segment"""

    height = box_height(
        percent_distance_from_center = percent_distance_from_center,
        radius=radius,
        num_slices=num_slices,
    )

    half_angle = radians((360 / num_slices) / 2)
    width = cos(asin(height / (2 * radius))) * radius - percent_distance_from_center * radius * cos(half_angle)

    x = center[0] + percent_distance_from_center * cos(half_angle) * radius
    y = center[1] - height / 2

    last_use = svgwrite.container.Use(
        href=placeholder,
        insert=(x, y),
        size=(width, height),
        **kwargs,
    )

    last_use.rotate(
        90,
        center=(
            x + width / 2,
            y + height / 2,
        ),
    )

    return last_use


def placeholder_use(
    num_slices: int,
    center: Tuple[float, float],
    radius: float,
    placeholder: svgwrite.container.Symbol,
    placeholder_layout: Iterable[Dict[str, float]],
    **kwargs) -> Iterable[svgwrite.container.Use]:
    """Generates the appropriate <use>s for the requested placeholder layout"""

    placeholder_dicts = list(placeholder_layout.values())
    if len(placeholder_dicts) <= 0:
        return
    elif len(placeholder_dicts) == 1:
        yield placeholder_last(
            num_slices=num_slices,
            center=center,
            radius=radius,
            placeholder=placeholder,
            percent_distance_from_center=placeholder_dict[0]["padding"],
            **kwargs,
        )
        return

    left_percent_distance_from_center = float(0)
    right_percent_distance_from_center = float(0)
    for placeholder_dict in placeholder_dicts[:-1]:
        left_percent_distance_from_center = right_percent_distance_from_center + placeholder_dict["padding"]
        right_percent_distance_from_center += placeholder_dict["padding"] + placeholder_dict["width"]

        height = box_height(
            percent_distance_from_center=left_percent_distance_from_center,
            radius=radius,
            num_slices=num_slices,
        )

        half_angle = radians((360 / num_slices) / 2)

        width = placeholder_dict["width"] * radius * cos(half_angle)

        placeholder_use = svgwrite.container.Use(
            href=placeholder,
            insert=(
                center[0] + left_percent_distance_from_center * cos(half_angle) * radius,
                center[1] - height / 2,
            ),
            size=(width, height),
            **kwargs,
        )

        placeholder_use.rotate(
            placeholder_dict["rotation"],
            center=(
                center[0] + left_percent_distance_from_center * cos(half_angle) * radius + width / 2,
                center[1],
            ),
        )

        yield placeholder_use

    last_left_padding = right_percent_distance_from_center + placeholder_dicts[-1]["padding"]

    yield placeholder_last(
        num_slices=num_slices,
        center=center,
        radius=radius,
        placeholder=placeholder,
        percent_distance_from_center=last_left_padding,
        **kwargs,
    )
    return


def placeholder_group(
    num_slices: int,
    center: Tuple[float, float],
    radius: float,
    placeholder: svgwrite.container.Symbol,
    # NOTE: Would love to make this able to take an Iterable[Dict[str, float]]
    placeholder_layout: OrderedDictT[str, Dict[str, float]],
    **kwargs,
) -> Tuple[List[svgwrite.container.Use], svgwrite.container.Group]:
    """
    Returns the slice <g> group and the list of the placeholder <use>s within that group

    The placeholder <use>s can be used to update the href of the use are within that group, so even after the
    slice group has been placed within another group, what that <use> uses can be changed
    """
    slice_group = svgwrite.container.Group()
    placeholder_list = list()
    for holder in placeholder_use(
        num_slices=num_slices,
        center=center,
        radius=radius,
        placeholder=placeholder,
        placeholder_layout=placeholder_layout,
        **kwargs,
    ):
        slice_group.add(holder)
        placeholder_list.append(holder)

    return (placeholder_list, slice_group)


def wheel_template(
    num_slices: int,
    center: Tuple[float, float],
    radius: float,
    **kwargs,
) -> Tuple[svgwrite.container.Group, List[List[svgwrite.container.Use]], List[svgwrite.container.Symbol]]:
    """
    Returns a

    - <g> group with the wheel <path> and all the placeholders inserted appropriately, with dimensions matching the ones
    passed in
    - A list containing each slice groups placeholders in their order of appearance in the group
    - The default placeholder element used, that should be added to the SVGs <defs>, as it is <use>d in the wheel
    """
    # NOTE: This should have the actual generation of the wheel <path> be split out into its own function.
    #       This would make changing it so that the wheel slice "widths" can be varied depending on the contents
    
    spacing_name_re = re.compile(r"^(?P<name>[a-z]+)_(?P<kind>(padding)|(width))$")

    placeholder_layout = {
        name: value.copy() for name, value in PLACEHOLDER_DEFAULTS.items()
    }
    keys = kwargs.copy().keys()
    for arg in keys:
        variable = spacing_name_re.match(arg)
        if not variable:
            continue
        name = variable.group("name")
        kind = variable.group("kind")
        if name not in placeholder_layout:
            continue
        placeholder_layout[name][kind] = kwargs.pop(arg)

    #if reduce(sum, [sum(x.values()) for x in placeholder_layout.values()]) - 1 > 1:
    if sum(map(lambda x: sum(y for z, y in x.items() if z in ["padding", "width"]), placeholder_layout.values())) - 1 > 1:
        raise ValueError(
            f"The paddings and widths of the slice components took up more than 100% of the length of the slice:\n{placeholder_layout}"
        )


    wheel = svgwrite.container.Group()

    wheel_slices = svgwrite.path.Path(
        d=f"M {center[0]} {center[1]}",
        fill="none",
        stroke="black",
        stroke_width=1.0,
    )

    for ((line_to_x, line_to_y), (arc_to_x, arc_to_y)) in gen_slice_points(
        num_slices=num_slices,
        center=center,
        radius=radius
    ):
        wheel_slices.push(
            f"L {line_to_x} {line_to_y}"
        )  # For each step, draw line to point1...
        wheel_slices.push_arc(  # Draw arc to point2...
            target=(arc_to_x, arc_to_y),
            rotation=0,
            r=radius,
            large_arc=False,
            angle_dir="+",
            absolute=True,
        )
        wheel_slices.push(f"M {center[0]} {center[1]}")  # Move back to center...
        # Repeat with point2 as point1

    wheel_slices.push(f"Z")  # Close path

    wheel.add(wheel_slices)

    placeholders = list()
    placeholder = text_filled_area("placeholder", "sans-serif")

    for slice_num in range(num_slices):
        placeholder_list, slice_group = placeholder_group(
            placeholder=placeholder,
            placeholder_layout=placeholder_layout,
            center=center,
            radius=radius,
            num_slices=num_slices,
            **kwargs,
        )

        slice_group.rotate(
            angle=((360 / num_slices) * (slice_num - 0.5)),
            center=center,
        )
        placeholders.append(placeholder_list)
        wheel.add(slice_group)

    return (wheel, placeholders, [placeholder])


def decorate_pie(pieces: object) -> svgwrite.Drawing:
    raise NotImplementedError(":(")


def make_wheel(contents: pathlib.Path) -> svgwrite.Drawing:
    raise NotImplementedError(":(")
