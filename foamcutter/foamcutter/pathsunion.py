#!/usr/bin/env python2
# -*- encoding:utf-8 -*-

"""
FoamCutter union of closed paths to generate a single closed path
Original plugin for cutting machine (2 axes)
modified by GIPAT srl - www.polyshaper.eu
and then from Boris Landoni - www.futurashop.it - www.open-electronics.org
"""

from itertools import count, izip # pylint: disable=no-name-in-module
from foamcutter.helpers import verify_path_closed, point_path_squared_distance, rotate_closed_path # pylint: disable=import-error,no-name-in-module

def compute_paths_distance(path1, path2):
    """ Returns the distance between two paths and the nearest points

    :param path1: the first path
    :type path1: a list of points (couples of floats)
    :param path2: the second path
    :type path2: a list of points (couples of floats)
    :return: the distance and the index of the nearest points of the paths
    :rtype: a triple (distance, index_point_path1, index_point_path2)
    """

    index_path1 = 0
    (paths_distance, index_path2) = point_path_squared_distance(path1[index_path1], path2)

    for (idx1, point) in izip(count(1), path1[1:]):
        (distance, idx2) = point_path_squared_distance(point, path2)
        if distance < paths_distance:
            paths_distance = distance
            index_path1 = idx1
            index_path2 = idx2

    return (paths_distance, index_path1, index_path2)

class PathsJoiner(object):
    """ Takes a list of paths and creates a single path

    All input paths must be closed. This class generates a single closed path that connects all
    points of all paths
    """

    def __init__(self, input_paths, close_distance):
        """ Constructor

        Input paths must be closed (i.e. their initial and final point must be closer than
        close_distance
        :param input_paths: the list of paths to join. They must be closed paths, otherwise an
            exception is thrown
        :type input_paths: a list of paths. Each path is a list of points (couples of floats)
        :param close_distance: the max allowed distance between the initial and final point
        :type close_distance: float
        """

        # Verifying that all paths are closed
        for path in input_paths:
            verify_path_closed(path, close_distance)

        self.input_paths = input_paths
        self.remaining_paths = []
        self.path = []

    def unite(self):
        """ Unites all paths to generate a single closed path
        """

        if not self.input_paths:
            return
        else:
            self.path = self.input_paths[0]
            self.remaining_paths = self.input_paths[1:]

            nearest_path_info = self.extract_nearest_path()
            while nearest_path_info:
                (path, idx1, idx2) = nearest_path_info
                self.join_two_paths(path, idx1, idx2)
                nearest_path_info = self.extract_nearest_path()

    def join_two_paths(self, path_to_add, index_path, index_path_to_add):
        """ Joins path_to_add to the current path

        :param index_path: the index of the point of path to use in the union
        :type index_path: index (int)
        :param index_path_to_add: the index of the point of path_to_add to use in the union
        :type index_path_to_add: index (int)
        :param path_to_add: the path to add to self.path
        :type path_to_add: a list of 2D points (couples of floats)
        """

        rotated_path = rotate_closed_path(path_to_add, index_path_to_add)
        self.path = self.path[:(index_path + 1)] + rotated_path + self.path[index_path:]

    def extract_nearest_path(self):
        """ Extracts from self.remaining_paths the path nearest to self.path and returns it

        :return: the path closest to self.path and the index of the nearest points (first of the
            point of self.path and then of the other path) or None if no more paths are available
        :rtype: a triple (list of points (couples of floats), index_path1, index_path2) where both
            index_path1 and index_path2 are indices (ints) or None
        """

        if not self.remaining_paths:
            return None

        path_index = 0
        (path_distance, index_path, index_other_path) = compute_paths_distance(
            self.path,
            self.remaining_paths[0])

        for (path_idx, path) in izip(count(1), self.remaining_paths[1:]):
            (dist, idx1, idx2) = compute_paths_distance(self.path, path)
            if dist < path_distance:
                path_distance = dist
                index_path = idx1
                index_other_path = idx2
                path_index = path_idx

        # Removing nearest path
        path_to_return = self.remaining_paths.pop(path_index)

        return (path_to_return, index_path, index_other_path)

    def union_path(self):
        """ Returns the path connecting all input paths

        :return: the closed path containg all points of all paths
        :rtype: a list of points (couples of floats)
        """

        return self.path
