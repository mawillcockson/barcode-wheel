import sys
import gi

# gi.require_version("HarfBuzz", "2.4.0")
from gi.repository import HarfBuzz
from gi.repository import GLib
import array

import barcode_wheel


def main():
    font_file = barcode_wheel.get_font_file()
    font_blob = HarfBuzz.glib_blob_create(GLib.Bytes.new(font_file.read_bytes()))
    face = HarfBuzz.face_create(font_blob, 0)
    del font_blob
    font = HarfBuzz.font_create(face)
    upem = HarfBuzz.face_get_upem(face)
    del face
    HarfBuzz.font_set_scale(font, upem, upem)

    text = sys.argv[1]
    HarfBuzz.ot_font_set_funcs(font)

    buf = HarfBuzz.buffer_create()
    HarfBuzz.buffer_set_message_func(
        buf,
        # lambda *args: [print(x) for x in args] and True,
        lambda *args: True,
        1,
        0,
    )

    if False:
        HarfBuzz.buffer_add_utf8(buf, text.encode("utf-8"), 0, -1)
    elif sys.maxunicode == 0x10FFFF:
        HarfBuzz.buffer_add_utf32(
            buf, array.array("I", text.encode("utf-32"))[1:], 0, -1
        )
    else:
        HarfBuzz.buffer_add_utf16(
            buf, array.array("H", text.encode("utf-16"))[1:], 0, -1
        )

    HarfBuzz.buffer_guess_segment_properties(buf)
    HarfBuzz.shape(font, buf, [])
    del font

    infos = HarfBuzz.buffer_get_glyph_infos(buf)
    positions = HarfBuzz.buffer_get_glyph_positions(buf)

    for info, pos in zip(infos, positions):
        gid = info.codepoint
        cluster = info.cluster

        print(f"gid {gid} = {cluster} @ {pos.x_advance}, {pos.x_offset}+{pos.y_offset}")


if __name__ == "__main__":
    main()
