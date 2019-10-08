#!/usr/bin/env python2
# -*- encoding:utf-8 -*-

"""
Helper functions and classes
Original plugin for cutting machine (2 axes)
modified by GIPAT srl - www.polyshaper.eu
and then from Boris Landoni - www.futurashop.it - www.open-electronics.org
"""

from itertools import count, izip # pylint: disable=no-name-in-module
import math
import os
import re
from errors import InvalidCuttingPath, foamcutterIOError # pylint: disable=import-error,no-name-in-module

def gcode_filename(basename, path):
    """ Returns the full path and filename of the g-code file

    This function appends to basename three digits to make sure files are not
    overwritten
    :param basename: the base name of the file to generate
    :type basename: string
    :param path: the path where to save the file
    :type path: string
    :return: the name of the file where to write the g-code
    :rtype: string
    """

    # Filtering files in target dir
    all_files = os.listdir(path)
    reg_expr = re.escape(basename) + "-(\\d{3}).gcode"
    filtered = [f for f in all_files if re.match(reg_expr, f)]
    filtered.sort()

    # Getting the highest sequence number
    sequence_number = 0
    if filtered:
        match = re.match(reg_expr, filtered[-1])
        sequence_number = int(match.group(1)) + 1

    return os.path.join(path, basename + "-{:03}.gcode".format(sequence_number))

def write_gcode_file(gcode, filename):
    """ Writes the gcode to file

    In case of errors, throws an exception of type foamcutterIOError
    :param gcode: the gcode to save
    :type gcode: string
    :param filename: the full path to the file in which gcode is written
    :type filename: string
    """

    try:
        outfile = open(filename, "w")
        try:
            outfile.write(gcode)
        except IOError:
            raise foamcutterIOError(filename,
                                    _("Error when trying to write file, it might be corrupted"))
        finally:
            outfile.close()
    except IOError:
        raise foamcutterIOError(filename, _("Error when trying to open file"))

def squared_length(vector):
    """ Computes the squared length of a 2D vector

    This is more efficient than length in case only length comparisons are needed
    :param vector: the vector whose length is needed
    :type vector: a 2-tuple or a list with 2 elements, both floats
    :return: the length of the vector
    :rtype: float greater or equal to 0
    """

    return vector[0]**2 + vector[1]**2

def length(vector):
    """ Computes the length of a 2D vector

    :param vector: the vector whose length is needed
    :type vector: a 2-tuple or a list with 2 elements, both floats
    :return: the length of the vector
    :rtype: float greater or equal to 0
    """

    return math.sqrt(squared_length(vector))

def squared_distance(point1, point2):
    """ Computes the squared distance between point1 and point2

    This is more efficient than distance in case only length comparisons are needed
    :param point1: The first point
    :type point1: a 2-tuple or a list with 2 elements, both floats
    :param point2: The second point
    :type point2: a 2-tuple or a list with 2 elements, both floats
    :return: the squared distance between the two points
    :rtype: float
    """

    vector = [point1[0] - point2[0], point1[1] - point2[1]]
    return squared_length(vector)

def distance(point1, point2):
    """ Computes the distance between point1 and point2

    :param point1: The first point
    :type point1: a 2-tuple or a list with 2 elements, both floats
    :param point2: The second point
    :type point2: a 2-tuple or a list with 2 elements, both floats
    :return: the distance between the two points
    :rtype: float
    """

    vector = [point1[0] - point2[0], point1[1] - point2[1]]
    return length(vector)

def verify_path_closed(path, close_distance):
    """ Verifies that the given 2D path is closed

    If the path is not closed, an exception is thrown
    :param path: the path to test
    :type path: a list of points (couples of floats)
    :param close_distance: the max allowed distance between the initial and final point
    :type close_distance: float
    """

    if path and (len(path) > 1) and (distance(path[0], path[-1]) > close_distance):
        raise InvalidCuttingPath(_("path is not closed"))

def point_path_squared_distance(point, path):
    """ Computes the distance between a point and a path

    The distance between a point and a path is the distance between the point in the path that
    is nearer to the point. The function returns the squared distance (for efficency) and the
    index of the nearest point in the path
    :param point: a 2D point
    :type point: a couple of floats
    :param path: a 2D path (must not be empty)
    :type path: a list of points (couples of floats)
    :return: the squared distance and the index of the point in the path nearest to point
    :rtype: a couple (squared distance, point index). Squared distance is a float, point index
        is an int
    """

    nearest_index = 0
    nearest_distance = squared_distance(point, path[0])
    for (idx, path_point) in izip(count(1), path[1:]):
        dist = squared_distance(point, path_point)
        if dist < nearest_distance:
            nearest_index = idx
            nearest_distance = dist

    return (nearest_distance, nearest_index)

def rotate_closed_path(path, new_start):
    """ Given a closed path, returns a new path with the starting point at new_start

    This function assumes that the path is closed (i.e. that the first and last point are the same)
    :param path: the 2D path to rotate. This must be closed
    :type path: a list of points (couples of floats)
    :param new_start: the index of the new starting point
    :type new_start: an index (int)
    """

    new_path = []

    if not path:
        return new_path

    # If closest point is the first or the last, we can return the input path as it is
    if (new_start == 0) or (new_start >= len(path) - 1):
        return path

    # From start_point to end
    new_path += path[new_start:]
    # From beginning to start_point (skip the first, re-add start_point to close path)
    new_path += path[1:(new_start + 1)]

    return new_path
