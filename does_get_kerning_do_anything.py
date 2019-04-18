from freetype import Face
import pathlib
from itertools import combinations, starmap, chain


def main():
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890~`!@#$%^&*()_-+={[}]|\\:;\"'<,>.?/"

    font_paths = list(pathlib.Path(".").glob("*.ttf"))
    if font_paths:
        face = Face(str(font_paths[0].resolve(strict=True)))
    else:
        raise FileNotFoundError(
            "Can't find font file.\nPlease download .ttf font file into project root"
        )

    # Compute all kerning vectors for different characters next to each other
    vectors = starmap(face.get_kerning, combinations(alphabet, 2))

    # Extract all the x and y values into a single, flat list
    flat_vectors = list(chain.from_iterable([(vec.x, vec.y) for vec in vectors]))

    # Find and print the max and min
    print(
        f"The maximum value found was: {max(flat_vectors)}\nThe minimum value found was: {min(flat_vectors)}"
    )


if __name__ == "__main__":
    main()
