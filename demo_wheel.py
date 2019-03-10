import svgwrite
import subprocess
import shlex
from io import StringIO


file_contents = StringIO(
    """22001,Money Order Principal,
    12345678901,Test Product (Name Here),./test_product_picture.png
    9,Mardi Gras,"""
)


def make_barcode_group(value: str) -> svgwrite.container.Group:
    zint_output = subprocess.run(
        shlex.split(f"zint --direct --filetype=svg --barcode=34 --notext -d '{value}'"),
        stdout=subprocess.PIPE,
    )

    zint_barcode = StringIO(zint_output.stdout.decode("utf8"))


def draw_pie(num_slices: int) -> svgwrite.path.Path:
    pass


def decorate_pie(pieces: object) -> svgwrite.Drawing:
    pass


def make_wheel(contents: pathlib.Path) -> svgwrite.Drawing:
    pass
