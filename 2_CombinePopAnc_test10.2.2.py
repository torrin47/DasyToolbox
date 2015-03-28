# ---------------------------------------------------------------------------
# CombinePopAnc.py
# Part 2 of the Intelligent Areal Weighting Dasymetric Mapping Toolset
# Used by "Step 2 - Combine Population and Ancillary Rasters"
# Usage: CombinePopAnc <popRaster> <ancRaster> <dasyRaster> <dasyWorkTable>
# ---------------------------------------------------------------------------

# Import system modules
import sys, string, os, arcpy, traceback
from arcpy.sa import *

arcpy.env.overwriteOutput = True

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
    # Check out any necessary licenses
    if arcpy.CheckExtension("spatial") == "Available":
        arcpy.CheckOutExtension("spatial")
    else:
        AddPrintMessage("Spatial Analyst license is unavailable", 2)

#    # TEST Script arguments...
#    popRaster = r'G:\DASY_10.2.2_Test\OutputData.gdb\CT_popr_TEST1022' #arcpy.GetParameterAsText(0) # A population raster dataset. This raster should have population unit IDs as the "value" field, and an attribute table that contains population counts for the associated population units. It is recommended that you use population raster created by the "Population Features to Raster" tool in this toolbox.
#    ancRaster = r'G:\DASY_10.2.2_Test\InputData.gdb\CT_lc' #arcpy.GetParameterAsText(1) # The ancillary raster dataset to be used to redistribute population. This should be the same input as the ancillary dataset used in the Population Features to Raster tool. Land-use or land-cover are the most frequently used ancillary datasets, but any dataset that has classes of relatively homogenous population density could be used here.
#    dasyRaster = r'G:\DASY_10.2.2_Test\OutputData.gdb\CT_poplc_TEST1022' #arcpy.GetParameterAsText(2) # The name and full path of the output dasymetric raster that will be created. This raster will have a single value for each unique combination of population units and ancillary classes. When you're not saving to a geodatabase, specify .tif for a TIFF file format, .img for an ERDAS IMAGINE file format, or no extension for a GRID file format.
#    dasyWorkTable = r'G:\DASY_10.2.2_Test\OutputData.gdb\CT_dasywork_TEST1022' #arcpy.GetParameterAsText(3) # A stand-alone working table will be created that will be used for subsequent dasymetric calculations. Performing calculations on a standalone table is more predictable than trying to perform calculations on a raster value attribute table.

    # Script arguments...
    popRaster = arcpy.GetParameterAsText(0) # A population raster dataset. This raster should have population unit IDs as the "value" field, and an attribute table that contains population counts for the associated population units. It is recommended that you use population raster created by the "Population Features to Raster" tool in this toolbox.
    ancRaster = arcpy.GetParameterAsText(1) # The ancillary raster dataset to be used to redistribute population. This should be the same input as the ancillary dataset used in the Population Features to Raster tool. Land-use or land-cover are the most frequently used ancillary datasets, but any dataset that has classes of relatively homogenous population density could be used here.
    dasyRaster = arcpy.GetParameterAsText(2) # The name and full path of the output dasymetric raster that will be created. This raster will have a single value for each unique combination of population units and ancillary classes. When you're not saving to a geodatabase, specify .tif for a TIFF file format, .img for an ERDAS IMAGINE file format, or no extension for a GRID file format.
    dasyWorkTable = arcpy.GetParameterAsText(3) # A stand-alone working table will be created that will be used for subsequent dasymetric calculations. Performing calculations on a standalone table is more predictable than trying to perform calculations on a raster value attribute table.

    # Derived arguments...
    inputRasters = [popRaster,ancRaster]

    # Save current environment variables so they can be reset after the process
    #tempMask = arcpy.env.mask
    arcpy.env.mask = popRaster

    arcpy.env.workspace = GetPath(dasyRaster)

    # Process: Combine...
    AddPrintMessage("Combining rasters...", 0)
    outCombine = arcpy.sa.CombinatorialOr(popRaster,ancRaster)
    #outCombine = Combine(inputRasters)     #Combine works with 10.2.2, however for greatest compatibility 
    AddPrintMessage("Saving combined rasters...", 0)
    outCombine.save(dasyRaster)

    ##Build attribute table for single band raster dataset (not always built automatically)
    '''removed these steps as they resulted in the removal of the popIDField and ancIDField'''
    #AddPrintMessage("Building raster value attribute table...", 0)
    #arcpy.BuildRasterAttributeTable_management(dasyRaster, "Overwrite")

    # Return environment variables to previous values
    #arcpy.env.mask = tempMask

    workTablePath = GetPath(dasyWorkTable)
    dasyWorkTable = os.path.join(workTablePath,GetName(dasyWorkTable)) # In case the folder was a grid.

    AddPrintMessage("Creating the standalone working table...",0)
    # Raster Value Attribute Tables (VATs) tend to be quirky for calculations, depending on the raster format.
    # It is much more reliable and predictable to work with a standalone table.
    arcpy.TableToTable_conversion(dasyRaster, workTablePath, GetName(dasyWorkTable))

    AddPrintMessage("Adding new fields and creating indices...",0)
    # Add necessary fields to the new table
    for field in ["POP_COUNT","POP_AREA","POP_EST","REM_AREA","TOTALFRACT","NEW_POP","NEWDENSITY"]:
        arcpy.AddField_management(dasyWorkTable, field, "DOUBLE")

    # Need to derive ID fields from input raster table...
    fieldsList = arcpy.ListFields(dasyRaster)
    popIDField = fieldsList[-2].name # Should always be the second-to-last field
    ancIDField = fieldsList[-1].name # Should always be the last field

    # Make sure if fieldnames were truncated in the new workspace, it's handled gracefully
    popIDField = arcpy.ValidateFieldName(popIDField, workTablePath)
    ancIDField = arcpy.ValidateFieldName(ancIDField, workTablePath)

    # Create an index on both source unit ID and ancillary ID to speed processing
    # This tool is only supported for shapefiles and file geodatabases
    # not standalone dbf files or personal geodatabases
    if GetPath(dasyWorkTable)[-3:] == "gdb":
        arcpy.AddIndex_management(dasyWorkTable, popIDField, "PopID_atx")
        arcpy.AddIndex_management(dasyWorkTable, ancIDField, "AncID_atx")

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
