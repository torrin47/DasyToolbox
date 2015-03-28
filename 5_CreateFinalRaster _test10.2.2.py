# ---------------------------------------------------------------------------
# CreateFinalRaster.py
# Part 5 of the Intelligent Areal Weighting Dasymetric Mapping Toolset
# Usage: CreateFinalRaster <dasyRaster> <dasyWorkTable> <outputRaster> 
# ---------------------------------------------------------------------------

# Import system modules
import sys, string, os, arcpy, traceback

# Helper function for displaying messages
def AddPrintMessage(msg, severity):
    print msg
    if severity == 0: arcpy.AddMessage(msg)
    elif severity == 1: arcpy.AddWarning(msg)
    elif severity == 2: arcpy.AddError(msg)

# Checks for existing files in the directory with the same name 
# and adds an integer to the end of non-unique filenames 
def NameCheck(name,tableSuffix):
    j,okName = 1,""
    while not okName:
        tList = arcpy.ListDatasets(name + '*')
        if tList:
            name = name[:-2] + "_" + str(j)
        else:
            okName = name
        j = j + 1
    return okName + tableSuffix, okName
    
try:

    # Check out any necessary licenses
    if arcpy.CheckExtension("spatial") == "Available":
        arcpy.CheckOutExtension("spatial")
    else:
        AddPrintMessage("Spatial Analyst license is unavailable", 2)
	
    # Script arguments...
    dasyRaster = arcpy.GetParameterAsText(0) # The combined population and ancillary raster created as the output from step 2.
    dasyWorkTable = arcpy.GetParameterAsText(1) # The dasymetric working table created in step 2 and populated in step 4. This script will use the final column from that table for the output density values. 
    outputRaster = arcpy.GetParameterAsText(2) # Please enter the desired output raster with the full path. When you're not saving to a geodatabase, specify .tif for a TIFF file format, .img for an ERDAS IMAGINE file format, or no extension for an ESRI GRID file format.
    
    arcpy.env.workspace = os.path.dirname(str(outputRaster))
    
    # Make the raster layer and add the join
    arcpy.MakeRasterLayer_management(dasyRaster, "DRL")
    arcpy.AddJoin_management("DRL", "Value", dasyWorkTable, "Value", "KEEP_COMMON")    
    
    # Due to bug NIM066814 we can't use the lookup tool on the joined table, so we have to copy the joined raster.
    joinedRaster = arcpy.CopyRaster_management("DRL", NameCheck("dasyoutrast",'')[0])
    
    lookupRaster = arcpy.sa.Lookup(joinedRaster, "NEWDENSITY") 
    
    lookupRaster.save(outputRaster)
    
    # Clean up the in-memory raster layer and the intermediate joined raster
    arcpy.Delete_management("DRL")
    arcpy.Delete_management("dasyoutrast")
    
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
