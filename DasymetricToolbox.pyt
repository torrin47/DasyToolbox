"""
Source Name:   DasymetricToolbox.pyt
Version:       ArcGIS Pro / 10.3
Author:        Torrin Hultgren, GISP
Description:   This toolbox contains a number of scripts that assist 
			   preparing vector population and raster ancillary datasets 
			   for intelligent dasymetric mapping, performs the dasymetric 
			   calculations, and then generates a floating point output 
			   raster of revised population density.  Please see the 
			   documentation on the individual tools for more information.
"""

import arcpy


class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "Toolbox"
        self.alias = ""

        # List of tool classes associated with this toolbox
        self.tools = [Tool]


class Tool(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Tool"
        self.description = ""
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        params = None
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        return
