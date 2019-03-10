import svgwrite
from svgwrite import cm
from svgwrite.shapes import Circle, Rect
from svgwrite.path import Path

import functools
import math
from math import sin, cos, tan, pi

drawing = svgwrite.Drawing(filename='svgwrite_test.svg', profile='tiny', debug=True)

# Globals
width = height = 1000

# Draw bounding box
drawing.add(Rect(insert=(0, 0), size=(width, height), fill='none', stroke='black', stroke_width=1))

# Highlight points
points = [(0, 0),
          (0, width),
          (width, 0),
          (0, height),
          (width, height)]

highlighter = functools.partial(Circle, opacity=0.5, r=20)
for point in points:
    drawing.add(highlighter(center=point))


# Tutorial

def draw_slice(center, radius, start_angle, stop_angle, **kwargs):
    p_a = Path(**kwargs)
    angle = math.radians(stop_angle-start_angle)/2.0
    p_a.push(f'''M {center[0]} {center[1]}
                 l {cos(-1*angle)*radius} {sin(-1*angle)*radius}''')
    p_a.push_arc(target=(cos(angle)*radius + center[0], sin(angle)*radius + center[1]),
                 rotation=0,
                 r=radius,
                 large_arc=True if stop_angle-start_angle > 180 else False,
                 angle_dir='+',
                 absolute=True)
    p_a.push('Z')

    p_a.rotate(angle=(min([start_angle, stop_angle]) + (stop_angle - start_angle)/2.0), center=center)

    return p_a

#drawing.add(draw_slice(center=(width/4.0, height/2.0),
#                       radius=width/2.0,
#                       start_angle=(-20),
#                       stop_angle=(20),
#                       fill='none',
#                       stroke='black',
#                       stroke_width=2))


slices = drawing.defs.add(drawing.g(id='slices'))
slices.add(draw_slice(center=(0, 0),
                      radius=width/2.0 - 50,
                      start_angle=(-3),
                      stop_angle=3,
                      fill='none',
                      stroke='black',
                      stroke_width=2))

for angle in range(0, 360, 10):
    u = drawing.use(slices, insert=(width/2.0+40, height/2.0))
    u.rotate(angle, center=(width/2.0, height/2.0))
    drawing.add(u)

# Render SVG as text
drawing.viewbox(0, 0, width=width, height=height)
drawing.save()
