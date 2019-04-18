import svgwrite

if __name__ == "__main__":
    drawing = svgwrite.Drawing(filename="text_on_line.svg", size=("100%", "100%"))

    path = drawing.add(drawing.path(d="M 0 50 L 100 50", stroke="red", fill="none"))

    text = drawing.add(drawing.text(""))
    text_path = text.add(
        svgwrite.text.TextPath(path.get_iri(), "This text is on a line!")
    )

    drawing.viewbox(0, 0, 100, 100)
    drawing.save()
