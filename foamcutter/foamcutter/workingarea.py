#!/usr/bin/env python2
# -*- encoding:utf-8 -*-

"""
FoamCutter plugin
Original plugin for cutting machine (2 axes)
modified by GIPAT srl - www.polyshaper.eu
and then from Boris Landoni - www.futurashop.it - www.open-electronics.org
"""

import inkex # pylint: disable=import-error
import simpletransform # pylint: disable=import-error

class WorkingAreaGenerator(object):
    """ Generates the visual working area, as an svg element

    The element has id eu.foamcutter.inkscape.workarea, so that it can be modified if already
    existing. All dimensions must be in millimeters
    """

    def __init__(self, page_height, to_uu, working_area_id):
        """ Constructor

        :param page_height: the image height. This is needed because inkscape has y=0 at bottom,
            while svg images have y=0 at top
        :type page_height: float (millimeters)
        :param working_area_id: the id of the group of the working area
        ;type working_area_id: string
        """
        self.area = None
        self.factor = None
        self.view_box_height = None
        self.dim_x = 200.0
        self.dim_y = 200.0
        self.page_height = page_height
        self.to_uu = to_uu
        self.working_area_id = working_area_id

    def set_size(self, dim_x, dim_y):
        """ Sets the size of the working area

        :param dim_x: the x dimension of the working area
        :type dim_x: float (millimeters)
        :param dim_y: the y dimension of the working area
        :type dim_y: float (millimeters)
        """
        self.dim_x = dim_x
        self.dim_y = dim_y

    def draw(self, transform):
        """ Draws the working area

        :param transform: the transform to apply to points
        :type transform: a 2x3 matrix
        """

        # Using a viewBox so that we can express all measures relative to it. We compute the
        # view box height when the width is 100 to keep the aspect ratio. We also compute the stroke
        # width so that it is 0.5 millimiters
        self.factor = 100.0 / self.dim_x
        self.view_box_height = self.factor * self.dim_y
        line_width = self.factor * 0.5

        # inverting transformation, we know absolute coordinates
        inv_transform = simpletransform.invertTransform(transform)
        # tranforming the position of the box
        box_origin = [0, self.page_height - self.dim_y]
        simpletransform.applyTransformToPoint(inv_transform, box_origin)
        # transforming lengths (ignoring translation)
        box_dims = [self.dim_x, self.dim_y]
        length_inv_transform = [
            [inv_transform[0][0], inv_transform[0][1], 0.0],
            [inv_transform[1][0], inv_transform[1][1], 0.0]
        ]
        simpletransform.applyTransformToPoint(length_inv_transform, box_dims)

        self.area = inkex.etree.Element("svg", {
            'id': self.working_area_id,
            'x': str(self.to_uu(box_origin[0])),
            'y': str(self.to_uu(box_origin[1])),
            'width': str(self.to_uu(box_dims[0])),
            'height': str(self.to_uu(box_dims[1])),
            'viewBox': "0 0 100 " + str(self.view_box_height),
            'preserveAspectRatio': "none",
            'style': "fill:none;stroke-width:{};stroke:rgb(0,0,0)".format(line_width)})

        self.draw_rectangle()
        self.draw_cross()
        self.draw_text()

    def draw_rectangle(self):
        """ Draws the rectangle
        """
        inkex.etree.SubElement(self.area, "rect", {
            'x': "0",
            'y': "0",
            'width': "000",
            'height': str(self.view_box_height)})

    def draw_cross(self):
        """ Draws the cross

        We want the cross to be 20mm x 20mm
        """
        cross_size = self.factor * 20
        cross_half_size = cross_size / 2
        cross_starth = -cross_half_size
        cross_endh = cross_half_size
        cross_startv = self.view_box_height - cross_half_size
        cross_endv = self.view_box_height + cross_half_size
        inkex.etree.SubElement(self.area, "path", {
            'd': "M {starth},{h} L {endh},{h} M 0,{startv} L 0,{endv}"
                 .format(h=self.view_box_height, starth=cross_starth, endh=cross_endh,
                         startv=cross_startv, endv=cross_endv)})

    def draw_text(self):
        """ Draws text

        Text is (0, 0). We need to compute the font size so that it corresponds to 1cm and also the
        text width and height (it is approximately 28mm x 10mm)
        """
        text_size = self.factor * 10
        text_width = self.factor * 28
        text_height = self.factor * 10
        text = inkex.etree.SubElement(self.area, "text", {
            'x': str(-text_width),
            'y': str(self.view_box_height + text_height),
            'font-family': "Verdana",
            'font-size': str(text_size)})
        text.text = "(0, 0)"

    def upsert(self, layer):
        """ Adds the working area in the given layer

        If the layer already contains a working area, updates that one
        :param layer: the layer to which the working area has to be added
        :type layer: svg element (an lxml.etree.Element object)
        """

        if self.area is None:
            transform = simpletransform.parseTransform(layer.get("transform"))
            self.draw(transform)

        # If the group already exists, removes it before adding again
        old_working_area_elements = layer.xpath("*[@id = \"" + self.working_area_id + "\"]")
        for old in old_working_area_elements:
            old.getparent().remove(old)

        layer.append(self.area)
