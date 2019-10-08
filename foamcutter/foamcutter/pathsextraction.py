#!/usr/bin/env python2
# -*- encoding:utf-8 -*-

"""
FoamCutter svg paths extraction
"""

import inkex # pylint: disable=import-error
import cspsubdiv # pylint: disable=import-error
import cubicsuperpath # pylint: disable=import-error
import simplepath # pylint: disable=import-error
import simpletransform # pylint: disable=import-error
from errors import UnrecognizedSVGElement  # pylint: disable=import-error,no-name-in-module

class FlattenBezier(object):
    """ Transforms and SVG path with beziers and arcs in a path with only straight segments

    Code is taken from flatten.py in the standard inkscape distribution
    """

    def __init__(self, flatness):
        """ Constructor

        :param flatness: the maximum length of segments that constitute the subdivided curve
        :type flatness: float (millimiters)
        """

        self.flatness = flatness

    def __call__(self, curve):
        """ Flattens the given curve

        Code is taken from flatten.py
        :param curve: the description of the curve to flatten. This must be the value of the "d"
            parameter of the svg path element
        :type curve: string
        :return: the flattened curve
        :rtype: a list containing the flattened curve. The format is the same as the one returned by
            simplepath.parsePath
        """

        p = cubicsuperpath.parsePath(curve) # pylint: disable=invalid-name
        cspsubdiv.cspsubdiv(p, self.flatness)
        np = [] # pylint: disable=invalid-name
        for sp in p: # pylint: disable=invalid-name
            first = True
            for csp in sp:
                cmd = 'L'
                if first:
                    cmd = 'M'
                first = False
                np.append([cmd, [csp[1][0], csp[1][1]]])

        return np

class PathsExtractor(object):
    """ Extracts paths in machine coordinates

    If the working area is among the selected elements, it is ignored. Paths coordinates are given
    in millimeters
    """

    def __init__(self, elements, page_height, to_mm, working_area_id, flatten=None):
        """ Constructor

        :param elements: the list of elements from which paths must be extracted. The working area,
            if present, is ignored
        :type elements: a list of svg elements (lxml.etree.Element objects)
        :param page_height: the image height. This is needed because inkscape has y=0 at bottom,
            while svg images have y=0 at top
        :type page_height: float (millimeters)
        :param to_mm: a function to convert measures to millimeters
        :type to_mm: a function from float to float
        :param working_area_id: the id used by the working area drawing. This must be the same as
            the working_area_id parameter of WorkingAreaGenerator
        :type working_area_id: string
        :param flatten: the object to flatten the curve (e.g. FlattenBezier). If None flattening
            is not performed (bezier curves and arcs will be ignored)
        :type flatten: an instance of a class with a __call__(curve) method (e.g. see FlattenBezier)
        """

        # Taking all elements except the working area
        self.elements = [e for e in elements if e.get("id") != working_area_id]

        self.extracted_paths = []
        self.transform_stack = []
        self.page_height = page_height#0
        self.to_mm = to_mm
        self.flatten = flatten

    def get_elements(self):
        """ Returns the elements that are converted by this object

        :return: the elements from which paths are extracted
        :rtype: a list of svg elements (lxml.etree.Element objects)
        """

        return self.elements

    def extract(self):
        """ Extracts paths

        After this call paths can be retrieved with the paths() method
        :raises: UnrecognizedSVGElement if there was an svg element that was not recognized
        """

        def get_all_ancestors(element):
            """ Returns all ancestors of an svg element

            Ancestors are returned from the most distant one to the direct parent
            """
            ancestors = []
            cur_element = element
            while cur_element.getparent() is not None:
                cur_parent = cur_element.getparent()
                ancestors.append(cur_parent)
                cur_element = cur_parent
            ancestors.reverse()
            return ancestors

        # We need to cycle through all elements, here, to push the transformations of ancestors
        for element in self.elements:
            # Push all ancestors' transformations
            ancestors = get_all_ancestors(element)
            for anc in ancestors:
                self.push_transformation(anc)

            self.generate_path_from_element(element)

            # Remove all transformations
            self.transform_stack = []

    def extract_from_list(self, elements):
        """ Extracs paths from a list of elements

        :param elements: a list of elements from which paths are to be extracted
        :type elements: a list-like of svg elements
        """

        for element in elements:
            self.generate_path_from_element(element)

    def generate_path_from_element(self, element):
        """ Generates and returns a path from the given element

        :param element: the element from which a path has to be extracted
        :type element: an svg element (lxml.etree.Element object)
        :raises: UnrecognizedSVGElement if the element is not recognized
        """

        self.push_transformation(element)

        if element.tag == inkex.addNS("path", "svg"):
            self.path_from_svg_path(element)
        elif element.tag == inkex.addNS("g", "svg"):
            self.extract_from_list(element)
        else:
            raise UnrecognizedSVGElement(element.tag)

        self.pop_transformation()

    def push_transformation(self, element):
        """ Extracts the transformation of an svg element

        If the element has no transformation resets to unit
        :param element: the element from which the transformation has to be extracted
        :type element: an svg element (lxml.etree.Element object)
        :raises: UnrecognizedSVGElement if the element is not recognized
        """

        self.transform_stack.append(simpletransform.parseTransform(element.get("transform"),
                                                                   self.current_transform()))

    def current_transform(self):
        """ Returns the current transformation

        :return: the current transformation
        :rtype: a 2x3 matrix of float
        """

        if not self.transform_stack:
            return [[1, 0, 0], [0, 1, 0]]

        return self.transform_stack[-1]

    def pop_transformation(self):
        """ Removes the last transformation matrix from the list
        """

        self.transform_stack.pop()

    def path_from_svg_path(self, element):
        """ Extracts a path from an svg path

        Extracted paths are added to self.extracted_paths
        :param element: the svg path from which to extract information
        :type element: an svg path element (lxml.etree.Element object)
        """

        def to_point(point):
            """ Extracts a point in our format from a point in simplepath format
            """

            transformed_point = [point[1][0], point[1][1]]
            simpletransform.applyTransformToPoint(self.current_transform(), transformed_point)

            return (self.to_mm(transformed_point[0]),
                    self.page_height - self.to_mm(transformed_point[1]))

        path_string = element.get('d')
        svg_path = self.flatten(path_string) if self.flatten else simplepath.parsePath(path_string)
        path = []

        for point in svg_path:
            if point[0] == 'M':
                if path:
                    self.extracted_paths.append(path)
                    path = []

                path.append(to_point(point))
            elif point[0] == 'L':
                path.append(to_point(point))
            elif point[0] == 'Z':
                if path:
                    path.append(path[0])
                    self.extracted_paths.append(path)
                    path = []
            else:
                raise UnrecognizedSVGElement("path element '{}'".format(point[0]))

        if path:
            self.extracted_paths.append(path)

    def paths(self):
        """ Returns extracted paths

        :return: the list of paths, in absolute coordinates in millimiters
        :rtype: a list of lists of couples of floats
        """

        return self.extracted_paths
