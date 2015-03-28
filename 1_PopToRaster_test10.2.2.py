# ---------------------------------------------------------------------------
# PopToRaster.py
# Part 1 of the Intelligent Areal Weighting Dasymetric Mapping Toolset
# Converts a vector dataset with population count data to raster, and
# creates a standalone working table for further calculations
# Usage: PopToRaster <popFeatures> <popCountField> <popKeyField>
#                    <ancRaster> <cellAssignmentType> <popRaster> <popWorkTable>
# ---------------------------------------------------------------------------

# Import system modules
import sys, string, os, arcpy, traceback
from arcpy import env
from arcpy.sa import *
arcpy.CheckOutExtension("Spatial")

env.pyramid = 'NONE'
env.overwriteOutput = True

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
    AddPrintMessage("Beginning the population polygon to raster conversion...",0)

    # TEST Script arguments...
    popFeatures = r'G:\DASY_10.2.2_Test\InputData.gdb\CT_blk' #arcpy.GetParameterAsText(0)  # The population input polygon FeatureClass to be converted to a raster.
    popCountField = 'POP10' #arcpy.GetParameterAsText(1) # The field in the population dataset that contains count data.
    popKeyField = '' #arcpy.GetParameterAsText(2) # Optional - Since the tool will always use the system-recognized ObjectID field for the output raster Values, this is for reference only and is not used by the tool. It can be helpful to have another key field (commonly census FIPS code) for joining the outuput raster to other tables.
    ancRaster = r'G:\DASY_10.2.2_Test\InputData.gdb\CT_lc' #arcpy.GetParameterAsText(3) # The ancillary raster dataset to be used to redistribute population. The output raster from this tool will be snapped to the ancillary raster and have matching spatial reference and cell size.
    cellAssignmentType = 'CELL_CENTER' #arcpy.GetParameterAsText(4) # The method to determine how the cell will be assigned a value when more than one feature falls within a cell. Valid values:
                                                        # CELL_CENTER?The polygon in which the center of the cell yields the attribute to assign to the cell.
                                                        # MAXIMUM_AREA?The single feature with the largest area within the cell yields the attribute to assign to the cell.
                                                        # MAXIMUM_COMBINED_AREA?Features with common attributes are combined to produce a single area within the cell in question for consideration when determining the largest area.
    popRaster = r'G:\DASY_10.2.2_Test\OutputData.gdb\CT_popr_TEST1022' #arcpy.GetParameterAsText(5) # The output population raster dataset that will be created, inlcuding the full path. When you're not saving to a geodatabase, specify .tif for a TIFF file format, .img for an ERDAS IMAGINE file format, or no extension for a GRID file format.
    popWorkTable = r'G:\DASY_10.2.2_Test\OutputData.gdb\CT_popwork_TEST1022' #arcpy.GetParameterAsText(6) # The tool will create a standalone table for performing calcluations. Please enter a name and path for the output table.


#    # Script arguments...
#    popFeatures = arcpy.GetParameterAsText(0)  # The population input polygon FeatureClass to be converted to a raster.
#    popCountField = arcpy.GetParameterAsText(1) # The field in the population dataset that contains count data.
#    popKeyField = arcpy.GetParameterAsText(2) # Optional - Since the tool will always use the system-recognized ObjectID field for the output raster Values, this is for reference only and is not used by the tool. It can be helpful to have another key field (commonly census FIPS code) for joining the outuput raster to other tables.
#    ancRaster = arcpy.GetParameterAsText(3) # The ancillary raster dataset to be used to redistribute population. The output raster from this tool will be snapped to the ancillary raster and have matching spatial reference and cell size.
#    cellAssignmentType = arcpy.GetParameterAsText(4) # The method to determine how the cell will be assigned a value when more than one feature falls within a cell. Valid values:
#                                                        # CELL_CENTER?The polygon in which the center of the cell yields the attribute to assign to the cell.
#                                                        # MAXIMUM_AREA?The single feature with the largest area within the cell yields the attribute to assign to the cell.
#                                                        # MAXIMUM_COMBINED_AREA?Features with common attributes are combined to produce a single area within the cell in question for consideration when determining the largest area.
#    popRaster = arcpy.GetParameterAsText(5) # The output population raster dataset that will be created, inlcuding the full path. When you're not saving to a geodatabase, specify .tif for a TIFF file format, .img for an ERDAS IMAGINE file format, or no extension for a GRID file format.
#    popWorkTable = arcpy.GetParameterAsText(6) # The tool will create a standalone table for performing calcluations. Please enter a name and path for the output table.
    # Derived variables...
    popFeatDesc = arcpy.Describe(popFeatures)
    valueField = popFeatDesc.OIDFieldName

    ancRastDesc = arcpy.Describe(ancRaster)
    outCoordSys = ancRastDesc.SpatialReference
    AddPrintMessage("The output coordinate system is: " + outCoordSys.Name ,0)
    outCellSize = ancRastDesc.MeanCellWidth
    AddPrintMessage("The output cell size is: " + str(outCellSize) ,0)

    # Save current environment variables so they can be reset after the process
    tempCoordSys = arcpy.env.outputCoordinateSystem
    tempSnapRaster = arcpy.env.snapRaster

    arcpy.env.outputCoordinateSystem = outCoordSys
    arcpy.env.snapRaster = ancRaster

    # Process: Polygon to Raster...
    AddPrintMessage("Converting polygons to raster...",0)
    arcpy.PolygonToRaster_conversion(popFeatures, valueField, popRaster, cellAssignmentType, "NONE", outCellSize)

	##Build attribute table for single band raster dataset (not always built automatically)
    arcpy.CalculateStatistics_management(popRaster,"1","1","#")
    arcpy.BuildRasterAttributeTable_management(popRaster, "Overwrite")

    # Return environment variables to previous values
    arcpy.env.outputCoordinateSystem = tempCoordSys
    arcpy.env.snapRaster = tempSnapRaster

    # Create Field Info map for population feature table
    fieldInfo = '"'
    for field in [popCountField,popKeyField]:
        if (field):
            fieldInfo += field + ' ' + field + ' VISIBLE NONE;'
    fieldInfo += '"'

    # Create Table Views for the join
    popRasterTableView = arcpy.MakeTableView_management(popRaster, "popRasterView")
    popFeatureTableView = arcpy.MakeTableView_management(popFeatures, "popFeatureView", "", "", fieldInfo)

    # The join uses the "OIDField" from the input population feature class and the Value field of the output raster
    arcpy.AddJoin_management("popRasterView", "Value", "popFeatureView", valueField, "KEEP_COMMON")

    # The section below creates a "Field Mapping" that permits all fields from the population raster table
    # and only the Key and Count fields from the population feature table to be carried to the output table.
    AddPrintMessage("Mapping fields...",0)
    fieldMappings = arcpy.CreateObject("FieldMappings")
    fieldMappings.addTable("popRasterView")
    popFeaturesName = GetName(popFeatures).split(".")[0] # Need to strip file extension if there is one
    popRasterViewName = arcpy.Describe("popRasterView").Name
    popRasterViewName = popRasterViewName.replace(".","_").replace("dbf","vat")
    removeList = []
    for i in range(fieldMappings.fieldCount):
        fieldMap = fieldMappings.getFieldMap(i)
        field = fieldMap.outputField
        fieldName = field.name
        #AddPrintMessage(fieldName + " - " + field.Type,0)
        if field.type == 'Integer': field.type = 'Long'
        if fieldName[:len(popRasterViewName)] == popRasterViewName:
            newFieldName = arcpy.ValidateFieldName(fieldName[(len(popRasterViewName)+1):],GetPath(popWorkTable))
            field.name = newFieldName
            field.aliasName = newFieldName
            fieldMap.outputField = field
            fieldMappings.replaceFieldMap(i,fieldMap)
        elif fieldName[:len(popFeaturesName)] == popFeaturesName:
            newFieldName = fieldName[(len(popFeaturesName)+1):]
            if newFieldName in [popCountField,popKeyField]:
                newFieldName = arcpy.ValidateFieldName(newFieldName,GetPath(popWorkTable))
                field.name = newFieldName
                field.aliasName = newFieldName
                fieldMap.outputField = field
                fieldMappings.replaceFieldMap(i,fieldMap)
            else:
                removeList.append(i)
    removeList.reverse() # Removing a fieldmap changes the index of all successive fieldmap entries - so go backwards.
    for i in removeList:
        fieldMappings.removeFieldMap(i)

    AddPrintMessage("Creating the standalone working table",0)
    workTablePath = GetPath(popWorkTable)
    # Raster Value Attribute Tables (VATs) tend to be quirky for calculations, depending on the raster format.
    # It is much more reliable and predictable to work with a standalone table.
    arcpy.TableToTable_conversion("popRasterView", workTablePath, GetName(popWorkTable), '#', fieldMappings, '#')

    # Cleanup the join for memory management
    arcpy.RemoveJoin_management("popRasterView", popFeaturesName)

    AddPrintMessage("Adding and populating new fields",0)
    # Add necessary fields to the new table
    arcpy.AddField_management(popWorkTable, "REP_CAT", "LONG")
    for Field in ["CELL_DENS","POP_AREA","POP_DENS"]:
        arcpy.AddField_management(popWorkTable, Field, "DOUBLE")

    # Calculate the cell density as the population divided by the cell count
    arcpy.CalculateField_management(popWorkTable, "CELL_DENS", "!" + popCountField + "! / !Count!", 'PYTHON')

    # Create an index on the "Value" field which will be used for joins.
    # This tool is only supported for shapefiles and file geodatabases
    # not standalone dbf files or personal geodatabases
    if GetPath(popWorkTable)[-3:] == "gdb":
        arcpy.AddIndex_management(popWorkTable, "Value", "PopVal_atx")

    # Clean up the in-memory views to avoid collisions if the tool is re-run.
    arcpy.Delete_management("popRasterView")
    arcpy.Delete_management("popFeatureView")

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
