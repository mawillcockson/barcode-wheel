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


def outline_wheel(
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
