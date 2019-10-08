#!/usr/bin/env python2
# -*- encoding:utf-8 -*-

"""
FoamCutter tool path generation
Original plugin for cutting machine (2 axes)
modified by GIPAT srl - www.polyshaper.eu
and then from Boris Landoni - www.futurashop.it - www.open-electronics.org
"""

import math
from helpers import length, distance, verify_path_closed, point_path_squared_distance  # pylint: disable=import-error,no-name-in-module
from helpers import rotate_closed_path # pylint: disable=import-error,no-name-in-module

def normalize(angle):
    """ Normalizes angle between 0 and pi

    :param angle: the angle to normalize
    :type angle: float (angle in randiants)
    :return: the normalized angle
    :rtype: float (angle in randiants)
    """

    normalized = math.fmod(angle, math.pi)
    if normalized < 0.0:
        normalized += math.pi
    return normalized


def compute_tool_angle_for_direction(direction): # pylint: disable=invalid-name
    """ Computes the angle of the tool for the given direction
    """

    angle = math.atan2(direction[1], direction[0])
    return normalize(angle + math.pi/2.0)


class ToolAngleGenerator(object):
    """ This class generates and keeps track of the tool angle

    The tool angle at instant t depends on the tool angle at instant (t - 1). This class helps
    generating the correct angles by keeping track of the previous angle and the current turn
    """

    def __init__(self):
        """ Constructor
        """

        # Angles are computed between 0 and pi, but tool angle should go outside these limits to
        # have better movements. Given the value of this variable, the next angle will be in
        # [current_turn*pi, (current_turn+1)*pi]
        self.current_turn = 0
        # This is the value of the previous angle in [0, pi]
        self.prev_angle = None
        # This is the previous direction (needed to compute the  direction of the rotation)
        self.prev_dir = None

    def next_angle(self, direction):
        """ Returns the next angle given the direction of movement

        :param direction: the direction of movement
        :type direction: a vector with two elements (floats)
        """

        angle = None
        if self.prev_dir is None:
            angle = compute_tool_angle_for_direction(direction)
        else:
            angle = self.compute_next_tool_angle(direction)

        self.prev_angle = angle
        self.prev_dir = direction

        # When returning the angle, we have to return it in the correct turn
        return angle + math.pi * self.current_turn

    def compute_next_tool_angle(self, direction):
        """ Computes the correct tool_angle taking into account the direction of rotation
        """

        angle = compute_tool_angle_for_direction(direction)
        # Computing the Z component of the cross product of prev_dir and direction
        cross = self.prev_dir[0]*direction[1] - self.prev_dir[1]*direction[0]
        # Now checking if we have to modify angle to perform the correct rotation
        if cross > 0:
            # angle must be greater than prev_angle
            if angle < self.prev_angle:
                self.current_turn += 1
        elif cross < 0:
            # angle must be less than prev_angle
            if angle > self.prev_angle:
                self.current_turn -= 1
        else:
            # prev_Dir and direction are aligned
            angle = self.prev_angle

        return angle


def discretize_path(path, discretization_step):
    """ A function to discretize a path

    This function takes a path and a discretization step and returns the same path with all segments
    shorter than or long as the discretizazion path. To avoid having very small segments,
    discretization is not uniform. For example a segment 9.03mm long with a discretization step of
    1mm is not divided in 10 parts, nine of which are 1mm long and one 0.03mm long; insteatd it is
    divided in 10 parts, all 0.903mm long

    :param path: the path to discretize
    :type path: a list of points (couples of floats)
    :param discretization_step: the discretization step
    :type discretization_step: float
    :return: the discretized path
    :rtype: a list of points (couples of floats)
    """

    def point_for_step(start, versor, step_length, step):
        """ Returns the point for the given step

        The formula is point_for_step = start + versor*step
        """

        return [start[0] + versor[0] * step_length * step,
                start[1] + versor[1] * step_length * step]

    if discretization_step == float('inf') or len(path) < 2:
        return path

    prev_point = path[0]
    discretized_path = [prev_point]
    for point in path[1:]:
        dist = distance(prev_point, point)
        if dist > discretization_step:
            # Generating the direction vector
            versor = [(point[0] - prev_point[0]) / dist, (point[1] - prev_point[1]) / dist]
            num_steps = int(math.ceil(dist / discretization_step))
            step_length = dist / num_steps
            for i in range(1, num_steps):
                discretized_path.append(point_for_step(prev_point, versor, step_length, i))

        # Adding the last point of this segment
        discretized_path.append(point)

        prev_point = point

    return discretized_path


class PointAndDirection(object): # pylint: disable=too-few-public-methods
    """ A simple data structure with a point and a direction

    This is used by ToolPathsGenerator to keep a point and the direction of movement from the point
    to the next point. This has two members you should access: point and direction
    """

    def __init__(self, point, next_point, min_distance):
        """ Constructor

        :param point: the points
        :type point: a 2-tuple or a list with 2 elements, both floats
        :param next_point: the subsequent point
        :type next_point: a 2-tuple or a list with 2 elements, both floats
        :param min_distance: if the distance between the two points is less than this value, they
            are considered conincident and direction is set to (0, 0)
        :type min_distance: float
        """

        self.point = (point[0], point[1])
        vector = [next_point[0] - point[0], next_point[1] - point[1]]
        vector_length = length(vector)
        if vector_length < min_distance:
            self.direction = (0.0, 0.0)
        else:
            self.direction = (vector[0] / vector_length, vector[1] / vector_length)


class EngravingToolPathsGenerator(object):
    """ The class to generate the path and orientation of the tool for the engraving machine

    Both input and outputs values are in millimeters or radiants. Angles are positive
    counterclockwise starting from the x axis. Tool orientation refers to the orientation the tool
    must have to perform the movement from the point where it is defined to the next one. If for
    example yopu have this tool path:
        [(x1, y1, z, a1), (x2, y2, z, a2), (x3, y3, z, a3)]
    the the tool should have orientation a1 when moving from (x1, y1) to (x2, y2) and orientation a2
    when moving from (x2, y2) to (x3, y3). The last angle (a3) is always set to the same value as
    the preceeding angle (a2 in this case). If a discretization step is specified (different from
    infinite), the path is divided in steps that are long, at most, as the discretization step
    """

    def __init__(self, input_paths, tool_z, min_distance, discretization_step):
        """ Constructor

        :param input_paths: bidimensional input paths
        :type input_paths: a list of lists of couples of points (in millimeters)
        :param tool_z: the z coordinate of the tool (equal for all points)
        :type tool_z: float (millimeters)
        :param min_distance: if the distance between the two points is less than this value, they
            are considered conincident
        :type min_distance: float
        :param discretization_step: the longest distance in the resulting path. Set to float('inf')
            (the python for infinite) to disable discretization
        :type discretization_step: float
        """

        self.input_paths = input_paths
        self.tool_z = tool_z
        self.min_distance = min_distance
        self.tool_paths = []
        self.discretization_step = discretization_step

    def generate(self):
        """ Generates the tool paths
        """

        self.tool_paths = [self.generate_single_path(p) for p in self.input_paths]

    def generate_single_path(self, path):
        """ Generates and returns  single path

        :param path: the path to transform in tool path
        :type path: a list of couples of floats (points)
        """

        def create_tool_point(point_and_direction, angle):
            """ Creates a point in our format (x, y, z, a)
            """

            return (point_and_direction.point[0], point_and_direction.point[1], self.tool_z, angle)

        # Removing points that are too near to each other
        simplified_path = self.generate_simplified_path(path)

        # Discretizing path
        discretized_path = discretize_path(simplified_path, self.discretization_step)

        # Generating directions
        points_and_directions = self.generate_directions(discretized_path)

        if not points_and_directions:
            return []
        if len(points_and_directions) == 1:
            return [create_tool_point(points_and_directions[0], 0)]

        tool_path = []

        # The object to keep track of tool angles
        tool_angle_generator = ToolAngleGenerator()

        for point in points_and_directions[:-1]:
            angle = tool_angle_generator.next_angle(point.direction)
            tool_path.append(create_tool_point(point, angle))

        # Adding the last point with the same angle as the last but one
        tool_path.append(create_tool_point(points_and_directions[-1], tool_path[-1][3]))

        return tool_path

    def generate_simplified_path(self, path):
        """ Returns the path without duplicated points

        All points that are nearer than min_distance are removed
        :param path: the path to simplify
        :type path: a list of points (couples of floats)
        :return: the simplified path
        :rtype: a list of points (couples of floats)
        """

        if not path:
            return []

        simplified_path = []
        prev_point = path[0]
        for point in path[1:]:
            if distance(point, prev_point) > self.min_distance:
                simplified_path.append(prev_point)
                prev_point = point

        # Adding the last point
        simplified_path.append(prev_point)

        return simplified_path

    def generate_directions(self, path):
        """ Returns a list of PointAndDirection

        The list stores a point and the direction of movement (a versor) towards the subsequent
        point. The last point has a direction of (0, 0)
        :param path: the path to convert
        :type path: a list of points (couples of floats)
        :return: the list of points and directions
        :rtype: a list of PointAndDirection instances
        """

        if not path:
            return []
        elif len(path) == 1:
            return [PointAndDirection(path[0], path[0], self.min_distance)]

        points_and_directions = []
        prev_point = path[0]
        for point in path[1:]:
            points_and_directions.append(PointAndDirection(prev_point, point, self.min_distance))
            prev_point = point

        points_and_directions.append(PointAndDirection(prev_point, prev_point, self.min_distance))

        return points_and_directions


    def paths(self):
        """ Returns the list of tool paths

        :return: the list of tool paths
        :rtype: a list of lists of triplets of floats (x, y, z, angle)
        """

        return self.tool_paths


class CuttingToolPathsGenerator(object):
    """ The class to generate the path of the tool for the cutting machine

    Both input and outputs values are in millimeters or radiants. This class accepts only a single
    closed path (the is considered closed if the distance between the first and last point is less
    than close_distance). If the path is not closed an exception is thrown. This returns a path
    identical to the initial one where the first point is the closest to (0, 0).
    """

    def __init__(self, input_path, close_distance):
        """ Constructor

        :param input_path: bidimensional input path
        :type input_path: a list of couples of points (in millimeters)
        :param close_distance: the max allowed distance between the initial and final point
        :type close_distance: float
        """

        # Verifying that the path is closed
        verify_path_closed(input_path, close_distance)

        self.input_path = input_path
        self.tool_path = None

    def generate(self):
        """ Generates the tool path
        """

        if not self.input_path:
            self.tool_path = None
            return

        start_point = point_path_squared_distance((0.0, 0.0), self.input_path)[1]
        self.tool_path = rotate_closed_path(self.input_path, start_point)

    def path(self):
        """ Returns the tool path
        """

        return self.tool_path
