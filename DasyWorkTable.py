# ---------------------------------------------------------------------------
# DasyWorkTable.py
# Helper script for Step 2 - Alternate Combine Population and Ancillary Rasters
# Used by Helper Tools/Create Dasymetric Working Table Helper script
# Not intended to be used as a standlone script - use CombinePopAnc.py instead.
# of the Intelligent Areal Weighting Dasymetric Mapping Toolset
# Usage: DasyWorkTable <dasyRaster> <dasyWorkTable>   
# ---------------------------------------------------------------------------

# Import system modules
import sys, string, os, arcpy, traceback
from arcpy.sa import *

# Helper function for displaying messages
def AddPrintMessage(msg, severity):
    print msg
    if severity == 0: arcpy.AddMessage(msg)
    elif severity == 1: arcpy.AddWarning(msg)
    elif severity == 2: arcpy.AddError(msg)

def GetName(datasetName):
    # Strips path from dataset
    return os.path.basename(datasetName)

def GetPath(datasetName):
    # Returns path to dataset
    # Because of bug #NIM050483 it's necessary to confirm that this path is not a GRID folder - the Geoprocessing Tool Validator sometimes autopopulates this.
    datasetPath = os.path.dirname(datasetName)
    desc = arcpy.Describe(datasetPath)
    if (desc.datatype == 'RasterDataset'):
      # Get parent folder, which is probably what the user intended.
      datasetPath = os.path.dirname(datasetPath)
    return datasetPath
    
try:
    # Script arguments...
    dasyRaster = arcpy.GetParameterAsText(0) # Raster dataset that is the combination of the population and ancillary datasets
    dasyWorkTable = arcpy.GetParameterAsText(1) # Output working table that will contain dasymetric population calculations

    # Derive appropriate tool parameters
    workTablePath = GetPath(dasyWorkTable)
    dasyWorkTable = os.path.join(workTablePath,GetName(dasyWorkTable)) # In case the folder was a grid.
    
    # Raster Value Attribute Tables (VATs) tend to be quirky for calculations, depending on the raster format.
    # It is much more reliable and predictable to work with a standalone table.
    AddPrintMessage("Creating the standalone working table...",0)
    arcpy.TableToTable_conversion(dasyRaster, workTablePath, GetName(dasyWorkTable))
    
    AddPrintMessage("Adding new fields and creating indices...",0)
    # Add necessary fields to the new table
    for field in ["POP_COUNT","POP_AREA","POP_EST","REM_AREA","TOTALFRACT","NEW_POP","NEWDENSITY"]:
        arcpy.AddField_management(dasyWorkTable, field, "DOUBLE")

    # Need to derive ID fields from input raster table...
    fieldsList = arcpy.ListFields(dasyWorkTable)
    popIDField = fieldsList[3].name # Should always be the fourth field
    ancIDField = fieldsList[4].name # Should always be the fifth field

    # Create an index on both source unit ID and ancillary ID to speed processing
    # This tool is only supported for shapefiles and file geodatabases
    # not standalone dbf files or personal geodatabases
    if os.path.dirname(dasyWorkTable)[-3:] == "gdb":
        arcpy.AddIndex_management(dasyWorkTable, popIDField, "PopID_atx")
        arcpy.AddIndex_management(dasyWorkTable, ancIDField, "AncID_atx")  
    else:
       AddPrintMessage("The Add Index tool does not support .dbf files.  Please manually add indices to the two fields in this table representing population and ancillary raster values by editing the properties of the table.",0) 
    
# Geoprocessing Errors will be caught here
except Exception as e:
    print e.message
    arcpy.AddError(e.message)

# other errors caught here
except:
    # Cycle through Geoprocessing tool specific errors
    for msg in range(0, arcpy.GetMessageCount()):
        if arcpy.GetSeverity(msg) == 2:
            arcpy.AddReturnMessage(msg)
			
	# Return Python specific errors
    tb = sys.exc_info()[2]
    tbinfo = traceback.format_tb(tb)[0]
    pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n    " + \
            str(sys.exc_type)+ ": " + str(sys.exc_value) + "\n"
    AddPrintMessage(pymsg, 2)
