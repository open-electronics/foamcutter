#!/usr/bin/env python2
# -*- encoding:utf-8 -*-

"""
Original plugin for cutting machine (2 axes)
modified by GIPAT srl - www.polyshaper.eu
and then from Boris Landoni - www.futurashop.it - www.open-electronics.org
"""

import os.path

import inkex # pylint: disable=import-error
from foamcutter.errors import foamcutterError # pylint: disable=import-error,no-name-in-module
from foamcutter.gcode import CuttingGCodeGenerator # pylint: disable=import-error,no-name-in-module
from foamcutter.pathsextraction import FlattenBezier, PathsExtractor # pylint: disable=import-error,no-name-in-module
from foamcutter.pathsunion import PathsJoiner # pylint: disable=import-error,no-name-in-module
from foamcutter.toolpaths import CuttingToolPathsGenerator # pylint: disable=import-error,no-name-in-module
from foamcutter.workingarea import WorkingAreaGenerator # pylint: disable=import-error,no-name-in-module
from foamcutter.helpers import gcode_filename, write_gcode_file # pylint: disable=import-error,no-name-in-module

####################################################################################################
# List of hardwired parameters
####################################################################################################

# The id of the working area element in the svg
WORKING_AREA_ID = "eu.foamcutter.inkscape.workarea"

# If two points are less than this value apart, they are considere conincident. This is measured in
# millimeters (used to check if a path is closed)
CLOSE_DISTANCE = 0.5

####################################################################################################

inkex.localize()


class foamcutter(inkex.Effect):
    """ The main class of the plugin
    """

    def __init__(self):
        """ Constructor
        """

        # Initializing the superclass
        inkex.Effect.__init__(self)

        # More initializations
        # This is the height of the document in millimeters
        self.doc_height = 0
        # The path where the output file is written
        self.gcode_file_path = os.path.expanduser("~/")

        self.define_command_line_options()

    def define_command_line_options(self):
        """ Defines the commandline options accepted by the script
        """

        self.OptionParser.add_option("-f", "--filename", action="store", type="string",
                                     dest="filename", default="foamcutter",
                                     help=("Basename of the generated G-CODE file (will have .nc "
                                           "extension and will be saved on Desktop"))
        self.OptionParser.add_option("-x", "--dim-x", action="store", type="float", dest="dim_x",
                                     default=200.0, help="Plane X dimension in mm")
        self.OptionParser.add_option("-y", "--dim-y", action="store", type="float", dest="dim_y",
                                     default=200.0, help="Plane Y dimension in mm")
        self.OptionParser.add_option("-s", "--speed", action="store", type="float",
                                     dest="speed", default=100.0, help="Cutting speed in mm/min")
        self.OptionParser.add_option("-t", "--temperature", action="store", type="int",
                                     dest="temperature", default=25, help="Wire temperature in percentual")
        self.OptionParser.add_option("-b", "--flatness", action="store", type="float",
                                     dest="flatness", default=1.0,
                                     help="Flatness (for bezier curves)")

        # This is here so we can have tabs - but we do not use it for the moment.
        # Remember to use a legitimate default
        self.OptionParser.add_option("", "--active-tab", action="store", type="string",
                                     dest="active_tab", default='setup', help="Active tab.")

    def effect(self):
        """ Main function
        """

        # A function to convert to millimiters
        to_mm = lambda value: self.uutounit(value, 'mm')
        # A function to convert to user units. This must be used to write units in the svg
        to_uu = lambda value: self.unittouu(str(value) + "mm")

        # Extracting the height of the document. This is needed to flip y axis coordinates (y=0 is
        # at bottom in inkscape but at top in svg...). We get the height in millimeters
        self.doc_height = to_mm(self.unittouu(self.document.getroot().get('height')))

        # Draw the working area
        working_area_generator = WorkingAreaGenerator(self.doc_height, to_uu, WORKING_AREA_ID)
        working_area_generator.set_size(self.options.dim_x, self.options.dim_y)
        working_area_generator.upsert(self.current_layer)

        if not self.options.ids:
            # print info and exit
            # Using error message even if this it not really an error...
            inkex.debug(_(("No path was seletect, only the working area was generated. Now draw a "
                           "path inside the working area and select it to generate the g-code")))
        else:
            # Extracting paths in machine coordinates
            paths_extractor = PathsExtractor(self.selected.values(), self.doc_height, to_mm,
                                             WORKING_AREA_ID, FlattenBezier(self.options.flatness))
            paths_extractor.extract()

            # Joining paths. This will also check that all paths are closed
            paths_joiner = PathsJoiner(paths_extractor.paths(), CLOSE_DISTANCE)
            paths_joiner.unite()

            # Generate tool positions and orientations
            tool_path_generator = CuttingToolPathsGenerator(paths_joiner.union_path(),
                                                            CLOSE_DISTANCE)
            tool_path_generator.generate()

            # Generating g-code
            gcode_generator = CuttingGCodeGenerator(tool_path_generator.path(), self.options.speed, self.options.temperature)
            gcode_generator.generate()

            # Writing to file
            filename = gcode_filename(self.options.filename, self.gcode_file_path)
            write_gcode_file(gcode_generator.gcode(), filename)

            inkex.debug(_("The generate g-code has been save to ") + filename)


if __name__ == '__main__':
    try:
        e = foamcutter() # pylint: disable=invalid-name
        e.affect()
    except foamcutterError as error:
        inkex.errormsg(error.to_string())
        exit(error.exit_code())
