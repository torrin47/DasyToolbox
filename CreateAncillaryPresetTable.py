# ---------------------------------------------------------------------------
# CreateAncillaryPresetTable.py
# Part 5 of the Intelligent Areal Weighting Dasymetric Mapping Toolset
# Usage: CreateAncillaryPresetTable <ancRaster> <ancPresetTable>                
# ---------------------------------------------------------------------------

# Import system modules
import sys, string, os, arcpy, traceback

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
    ancRaster = arcpy.GetParameterAsText(0) # The ancillary raster dataset.
    ancPresetTable = arcpy.GetParameterAsText(1) # The output standalone table with full path that will be created.

    whereClause = arcpy.AddFieldDelimiters(GetPath(ancRaster),"Count") + " > 0"

    ancRasterTableView = arcpy.MakeTableView_management(ancRaster, "ancRasterView", whereClause)
    
    AddPrintMessage("Creating the standalone table",0)
    arcpy.TableToTable_conversion("ancRasterView", GetPath(ancPresetTable), GetName(ancPresetTable))

    ancPresetTable = os.path.join(GetPath(ancPresetTable),GetName(ancPresetTable)) # In case the folder was a grid.
    
    # Add preset field to the new table
    arcpy.AddField_management(ancPresetTable, "PRESETDENS", "DOUBLE")

    AddPrintMessage("The table is ready - please populate the PRESETDENS field with the appropriate preset density values, and remove any ancillary classes whose density should be obtained empirically.",0)

    # Clean up the in-memory view
    arcpy.Delete_management("ancRasterView")

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

