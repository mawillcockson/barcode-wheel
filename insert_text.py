import svgwrite


def main():
    drawing = svgwrite.Drawing(
        filename="temp.svg",
        size=("100%", "100%"),
        profile="tiny",
        preserveAspectRatio="xMidyMid meet",
        viewBox="0 0 200 200",
    )

    text_group = drawing.add(drawing.g(id="text", font_size=10))

    test_text = drawing.text(text="test", insert=(50, 100))

    test_text.text = "123"

    text_group.add(test_text)

    test_text.text = "works"

    drawing.save()


if __name__ == "__main__":
    main()
