#!/usr/bin/env python2
# -*- encoding:utf-8 -*-

"""
FoamCutter gcode generation
Original plugin for cutting machine (2 axes)
modified by GIPAT srl - www.polyshaper.eu
and then from Boris Landoni - www.futurashop.it - www.open-electronics.org
"""

import math

def distance(point1, point2):
    """ Computes the distance between the two 3D points

    :param point1: the first point
    :type point1: list of 3 floats
    :param point2: the second point
    :type point2: list of 3 floats
    :return: the distance between the two points
    :type: float
    """

    vector = [point1[0] - point2[0], point1[1] - point2[1], point1[2] - point2[2]]
    return math.sqrt(vector[0]**2 + vector[1]**2 + vector[2]**2)


class EngravingGCodeGenerator(object):
    """ The class generating the g-code for engraving

    This must have in input a list of tool paths (each element of the path must be (x, y, z, a)).
    All measures must be in millimeters and all angles in radiants. The small_distance and
    small_angle constructor parameters define the theshold below which displacement and rotations
    are performed together. This means that if a movement is both shorter than small_distance and
    the tool movement is smalled than small_angle, linear movement and tool movement are performed
    in a single instruction; otherwise first the tool rotates to obtain the final orientation, then
    it moves linearly
    """

    def __init__(self, tool_paths, mm_per_degree, safe_z, small_distance, small_angle): # pylint: disable=too-many-arguments
        """ Constructor

        :param tool_paths: the tool paths to use to generate the g-code
        :type tool_paths: a list of tool paths (list of tool points)
        :param mm_per_degree: the number of degrees for each millimiter of extrusion
        :type mm_per_degree: float
        :param safe_z: the value of z to use when not engraving
        :type safe_x: float (millimeters)
        :param small_distance: the distance below which linear and tool movements are performed
            together
        :type small_distance: float (millimeters)
        :param small_angle: the angle below which linear and tool movements are performed together
        :type small_angle: float (radiants)
        """

        # Removing empty paths
        self.tool_paths = [p for p in tool_paths if len(p) != 0]
        self.mm_per_degree = mm_per_degree
        self.safe_z = safe_z
        self.small_distance = small_distance
        self.small_angle = small_angle
        self.gcode_str = None

    def generate(self):
        """ Generates the g-code
        """

        if not self.tool_paths:
            self.gcode_str = None
            return

        # Initializing the gcode string
        self.gcode_str = ""

        self.append_to_gcode("M3")
        self.append_to_gcode("G01 F300")
        

        
        
        self.append_to_gcode("G00", z=self.safe_z)
        for path in self.tool_paths:
            self.generate_single_path(path)
        self.append_to_gcode("G00", x=0, y=0, e=0)
        self.append_to_gcode("G00", z=0)
        self.append_to_gcode("M4")

    def generate_single_path(self, path):
        """ Generates the g-code for a single path

        :param path: a path to transform
        :type path: a list of points (x, y, z, a)
        """

        first_point = path[0]
        self.append_to_gcode("G00", x=first_point[0], y=first_point[1], e=first_point[3])
        self.append_to_gcode("G01", z=first_point[2])

        prev_point = path[0]
        for point in path[1:]:
            if self.points_nearby(prev_point, point):
                self.append_to_gcode("G01", x=point[0], y=point[1], z=point[2], e=point[3])
            else:
                self.append_to_gcode("G01", x=point[0], y=point[1], z=point[2])
                self.append_to_gcode("G01", e=point[3])

            prev_point = point

        self.append_to_gcode("G01", z=self.safe_z)

    def to_extrusion(self, angle):
        """ Transforms an angle in radiants to millimiters of extrusion

        This is needed because 3D printers firmwares use this unit of measure for the fourth
        axis.
        """

        return math.degrees(angle) / self.mm_per_degree

    def points_nearby(self, point1, point2):
        """ Returns true if the two path points are near to each other

        Two points are near to each other if the linear distance is smaller than small_distance and
        the difference of the angles is less than small_angle
        :param point1: the first point
        :type point1: list of 4 floats
        :param point2: the second point
        :type point2: list of 4 floats
        :return: true if points are near to each other
        :type: boolean
        """

        linear_distance = distance(point1[:3], point2[:3])
        angular_distance = abs(point1[3] - point2[3])
        return linear_distance < self.small_distance and angular_distance < self.small_angle

    def append_to_gcode(self, command, x=None, y=None, z=None, e=None): # pylint: disable=too-many-arguments,invalid-name
        """ Adds a command to the gcode

        The command is terminated by /n. Only values for axes that are not None are used
        :param x: the movement along the x axis
        :type x: float
        :param y: the movement along the y axis
        :type y: float
        :param z: the movement along the z axis
        :type z: float
        :param e: the movement along the e axis. This is converted using to_extrusion
        :type e: float
        """

        self.gcode_str += command
        if x is not None:
            self.gcode_str += " X{:5.3f}".format(x)
        if y is not None:
            self.gcode_str += " Y{:5.3f}".format(y)
        if z is not None:
            self.gcode_str += " Z{:5.3f}".format(z)
        if e is not None:
            self.gcode_str += " E{:5.3f}".format(self.to_extrusion(e))
        self.gcode_str += "\n"

    def gcode(self):
        """ Returns the generated g-code

        :return: the generated g-code
        :rtype: string
        """

        return self.gcode_str


class CuttingGCodeGenerator(object):
    """ The class generating the g-code for cutting

    This must have in input a paths (each element of the path must be (x, y)). All measures must
    be in millimeters.
    """

    def __init__(self, tool_path, speed, temperature):
        """ Constructor

        :param tool_path: the tool path to use to generate the g-code
        :type tool_path: a list of (x, y) coordinates
        :param speed: the speed of movement of the tool
        :type speed: float (mm/min)
        """

        self.tool_path = tool_path
        self.speed = speed
        self.temperature = (temperature*255)/100
        self.gcode_str = None

    def generate(self):
        """ Generates the g-code
        """

        if not self.tool_path:
            self.gcode_str = None
            return

        self.gcode_str = "M3\n"
        self.gcode_str += "G92 X0 Y0 Z0 \n"
        self.gcode_str += "M106 S{:d}\n".format(self.temperature)
        self.gcode_str += "G4 P10000 ; Dwell for 10 second \n"
        self.gcode_str += "G01 F{:5.3f}\n".format(self.speed)
           
        #self.gcode_str += "G01 X0 Y450\n"
        for point in self.tool_path:
            self.append_to_gcode(point)
        self.gcode_str += "G01 X0.000 Y0.000\n"
        #self.gcode_str += "G01 X0 Y450\n"
        self.gcode_str += "M107\n"
        self.gcode_str += "M4\n"

    def append_to_gcode(self, point):
        """ Appends a move instruction to gcode

        :param point: the point to add
        :type point: a couple of floats
        """

        self.gcode_str += "G01 X{:5.3f} Y{:5.3f}\n".format(point[0], point[1])

    def gcode(self):
        """ Returns the generated g-code

        :return: the generated g-code
        :rtype: string
        """

        return self.gcode_str
