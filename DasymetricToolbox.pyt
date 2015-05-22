# -*- coding: utf-8 -*-
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

import arcpy, os, sys, traceback

##Global helper functions used by all classes

# Helper function for displaying messages
def AddPrintMessage(msg, severity = 0):
    print(msg)
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

class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "Intelligent Dasymetric Mapping Toolbox"
        self.alias = "IDM"
        # List of tool classes associated with this toolbox
        self.tools = [PopToRaster, CombinePopAnc, CreateAncillaryPresetTable, DasymetricCalculations, CreateFinalRaster, CombinedSteps123]

# Tool implementation code

class PopToRaster(object):
    """
    Part 1 of the Intelligent Areal Weighting Dasymetric Mapping Toolset
    Converts a vector dataset with population count data to raster, and 
    creates a standalone working table for further calculations
    Usage: PopToRaster <popFeatures> <popCountField> <popKeyField>  
                        <ancRaster> <cellAssignmentType> <popRaster> <popWorkTable> 
        METHOD:
        __init__(): Define tool name and class info
        getParameterInfo(): Define parameter definitions in tool
        isLicensed(): Set whether tool is licensed to execute
        updateParameters():Modify the values and properties of parameters
                           before internal validation is performed
        updateMessages(): Modify the messages created by internal validation
                          for each tool parameter.
        execute(): Runtime script for the tool
    """
    def __init__(self):
        self.label = u'Step 1 - Population Features to Raster'
        self.description = "This tool converts a polygon feature class to an integer raster using the ObjectID of the feature class for the value of the output raster. This tool is based upon the \"Polygon to Raster\" conversion tool and is intended to be used for Dasymetric Mapping. The output raster will contain unique population source units and their associated population."
        self.canRunInBackground = False
    def getParameterInfo(self):
        # Population_Features
        param_1 = arcpy.Parameter()
        param_1.name = u'Population_Features'
        param_1.displayName = u'Population Features'
        param_1.parameterType = 'Required'
        param_1.direction = 'Input'
        param_1.datatype = u'Feature Class'

        # Population_Count_Field
        param_2 = arcpy.Parameter()
        param_2.name = u'Population_Count_Field'
        param_2.displayName = u'Population Count Field'
        param_2.parameterType = 'Required'
        param_2.direction = 'Input'
        param_2.datatype = u'Field'
        param_2.parameterDependencies = [param_1.name]

        # Population_Key_Field
        param_3 = arcpy.Parameter()
        param_3.name = u'Population_Key_Field'
        param_3.displayName = u'Population Key Field'
        param_3.parameterType = 'Optional'
        param_3.direction = 'Input'
        param_3.datatype = u'Field'
        param_3.parameterDependencies = [param_1.name]

        # Ancillary_Raster
        param_4 = arcpy.Parameter()
        param_4.name = u'Ancillary_Raster'
        param_4.displayName = u'Ancillary Raster'
        param_4.parameterType = 'Required'
        param_4.direction = 'Input'
        param_4.datatype = u'Raster Dataset'

        # Cell_Assignment_Type
        param_5 = arcpy.Parameter()
        param_5.name = u'Cell_Assignment_Type'
        param_5.displayName = u'Cell Assignment Type'
        param_5.parameterType = 'Optional'
        param_5.direction = 'Input'
        param_5.datatype = u'String'
        param_5.value = u'CELL_CENTER'
        param_5.filter.list = [u'CELL_CENTER', u'MAXIMUM_AREA', u'MAXIMUM_COMBINED_AREA']

        # Population_Raster
        param_6 = arcpy.Parameter()
        param_6.name = u'Population_Raster'
        param_6.displayName = u'Population Raster'
        param_6.parameterType = 'Required'
        param_6.direction = 'Output'
        param_6.datatype = u'Raster Dataset'

        # Population_Working_Table
        param_7 = arcpy.Parameter()
        param_7.name = u'Population_Working_Table'
        param_7.displayName = u'Population Working Table'
        param_7.parameterType = 'Required'
        param_7.direction = 'Output'
        param_7.datatype = u'Table'

        return [param_1, param_2, param_3, param_4, param_5, param_6, param_7]
    def isLicensed(self):
        return True
    def updateParameters(self, parameters):
        validator = getattr(self, 'ToolValidator', None)
        if validator:
             return validator(parameters).updateParameters()
    def updateMessages(self, parameters):
        validator = getattr(self, 'ToolValidator', None)
        if validator:
             return validator(parameters).updateMessages()
    def execute(self, parameters, messages):
        # Import system modules
        import sys, string, os, traceback

        try:
            AddPrintMessage("Beginning the population polygon to raster conversion...",0)
            
            # Script arguments...
            popFeatures = parameters[0].valueAsText  # The population input polygon FeatureClass to be converted to a raster.
            popCountField = parameters[1].valueAsText # The field in the population dataset that contains count data.
            popKeyField = parameters[2].valueAsText # Optional - Since the tool will always use the system-recognized ObjectID field for the output raster Values, this is for reference only and is not used by the tool. It can be helpful to have another key field (commonly census FIPS code) for joining the output raster to other tables. 
            ancRaster = parameters[3].valueAsText # The ancillary raster dataset to be used to redistribute population. The output raster from this tool will be snapped to the ancillary raster and have matching spatial reference and cell size.
            cellAssignmentType = parameters[4].valueAsText # The method to determine how the cell will be assigned a value when more than one feature falls within a cell. Valid values: 
                                                                # CELL_CENTER—The polygon in which the center of the cell yields the attribute to assign to the cell. 
                                                                # MAXIMUM_AREA—The single feature with the largest area within the cell yields the attribute to assign to the cell. 
                                                                # MAXIMUM_COMBINED_AREA—Features with common attributes are combined to produce a single area within the cell in question for consideration when determining the largest area. 
            popRaster = parameters[5].valueAsText # The output population raster dataset that will be created, inlcuding the full path. When you're not saving to a geodatabase, specify .tif for a TIFF file format, .img for an ERDAS IMAGINE file format, or no extension for a GRID file format.
            popWorkTable = parameters[6].valueAsText # The tool will create a standalone table for performing calcluations. Please enter a name and path for the output table.
            
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
            AddPrintMessage("Conversion complete, calculating statistics and building attribute table...",0)
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
            AddPrintMessage(e.message, 2)
        
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
            

class CombinePopAnc(object):
    """---------------------------------------------------------------------------
    # CombinePopAnc.py
    # Part 2 of the Intelligent Areal Weighting Dasymetric Mapping Toolset
    # Used by "Step 2 - Combine Population and Ancillary Rasters"
    # Usage: CombinePopAnc <popRaster> <ancRaster> <dasyRaster> <dasyWorkTable>
    # ---------------------------------------------------------------------------
    """
    
    def __init__(self):
        self.label = u'Step 2 - Combine Population and Ancillary Rasters'
        self.description = "This tool combines a raster of population enumeration units with an ancillary dataset to create an output raster with values that correspond to unique combinations of population units and ancillary classes. A standalone attribute table is exported from the raster attribute table that will be used to use intelligent dasymetric mapping to redistribute population within each source unit according to the ancillary classes."
        self.canRunInBackground = False
    def getParameterInfo(self):
        # Population_Raster
        param_1 = arcpy.Parameter()
        param_1.name = u'Population_Raster'
        param_1.displayName = u'Population Raster'
        param_1.parameterType = 'Required'
        param_1.direction = 'Input'
        param_1.datatype = u'Raster Dataset'

        # Ancillary_Raster
        param_2 = arcpy.Parameter()
        param_2.name = u'Ancillary_Raster'
        param_2.displayName = u'Ancillary Raster'
        param_2.parameterType = 'Required'
        param_2.direction = 'Input'
        param_2.datatype = u'Raster Dataset'

        # Dasymetric_Raster
        param_3 = arcpy.Parameter()
        param_3.name = u'Dasymetric_Raster'
        param_3.displayName = u'Dasymetric Raster'
        param_3.parameterType = 'Required'
        param_3.direction = 'Output'
        param_3.datatype = u'Raster Dataset'

        # Dasymetric_Working_Table
        param_4 = arcpy.Parameter()
        param_4.name = u'Dasymetric_Working_Table'
        param_4.displayName = u'Dasymetric Working Table'
        param_4.parameterType = 'Required'
        param_4.direction = 'Output'
        param_4.datatype = u'Table'

        return [param_1, param_2, param_3, param_4]
    def isLicensed(self):
        """Allow the tool to execute, only if the Spatial Analyst extension 
        is available."""
        try:
            if arcpy.CheckExtension("spatial") != "Available":
                raise Exception
        except Exception:
            return False  # tool cannot be executed
        return True  # tool can be executed
    def updateParameters(self, parameters):
        validator = getattr(self, 'ToolValidator', None)
        if validator:
             return validator(parameters).updateParameters()
    def updateMessages(self, parameters):
        validator = getattr(self, 'ToolValidator', None)
        if validator:
             return validator(parameters).updateMessages()
    def execute(self, parameters, messages):
        try:
            # Check out any necessary licenses
            if arcpy.CheckExtension("spatial") == "Available":
                arcpy.CheckOutExtension("spatial")
            else:
                AddPrintMessage("Spatial Analyst license is unavailable", 2)
            
            # Enable Overwriting
            arcpy.env.overwriteOutput = True
            
            # Script arguments...
            popRaster = parameters[0].valueAsText # A population raster dataset. This raster should have population unit IDs as the "value" field, and an attribute table that contains population counts for the associated population units. It is recommended that you use population raster created by the "Population Features to Raster" tool in this toolbox.
            ancRaster = parameters[1].valueAsText # The ancillary raster dataset to be used to redistribute population. This should be the same input as the ancillary dataset used in the Population Features to Raster tool. Land-use or land-cover are the most frequently used ancillary datasets, but any dataset that has classes of relatively homogenous population density could be used here. 
            dasyRaster = parameters[2].valueAsText # The name and full path of the output dasymetric raster that will be created. This raster will have a single value for each unique combination of population units and ancillary classes. When you're not saving to a geodatabase, specify .tif for a TIFF file format, .img for an ERDAS IMAGINE file format, or no extension for a GRID file format.
            dasyWorkTable = parameters[3].valueAsText # A stand-alone working table will be created that will be used for subsequent dasymetric calculations. Performing calculations on a standalone table is more predictable than trying to perform calculations on a raster value attribute table. 
        
            # Process: Combine...
            AddPrintMessage("Combining rasters...", 0)
            outCombine = arcpy.sa.Combine([popRaster,ancRaster])
            # At ArcGIS 10, the combine tool crashed when run in a python script (bug NIM064542), so this script used the Combinatorial Or tool instead, which is much slower. For 10.2 and above, combine is recommended.
            #outCombine = arcpy.sa.CombinatorialOr(popRaster,ancRaster)
            AddPrintMessage("Saving combined rasters...", 0)
            outCombine.save(dasyRaster)
            
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
            print (e.message)
            messages.AddErrorMessage(e.message)
        
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
            

class CreateAncillaryPresetTable(object):
    '''
    # ---------------------------------------------------------------------------
    # CreateAncillaryPresetTable.py
    # Part 5 of the Intelligent Areal Weighting Dasymetric Mapping Toolset
    # Usage: CreateAncillaryPresetTable <ancRaster> <ancPresetTable>                
    # ---------------------------------------------------------------------------
    '''
    def __init__(self):
        self.label = u'Step 3 - Create Ancillary Class Preset Table'
        self.canRunInBackground = False
    def getParameterInfo(self):
        # Ancillary_Raster
        param_1 = arcpy.Parameter()
        param_1.name = u'Ancillary_Raster'
        param_1.displayName = u'Ancillary Raster'
        param_1.parameterType = 'Required'
        param_1.direction = 'Input'
        param_1.datatype = u'Raster Dataset'

        # Ancillary_Preset_Table
        param_2 = arcpy.Parameter()
        param_2.name = u'Ancillary_Preset_Table'
        param_2.displayName = u'Ancillary Preset Table'
        param_2.parameterType = 'Required'
        param_2.direction = 'Output'
        param_2.datatype = u'Table'

        return [param_1, param_2]
    def isLicensed(self):
        return True
    def updateParameters(self, parameters):
        validator = getattr(self, 'ToolValidator', None)
        if validator:
             return validator(parameters).updateParameters()
    def updateMessages(self, parameters):
        validator = getattr(self, 'ToolValidator', None)
        if validator:
             return validator(parameters).updateMessages()
    def execute(self, parameters, messages):
        try:
            # Allow output to be overwritten
            arcpy.env.overwriteOutput = True
            
            # Script arguments...
            ancRaster = parameters[0].valueAsText # The ancillary raster dataset.
            ancPresetTable = parameters[1].valueAsText # The output standalone table with full path that will be created.
        
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
            print (e.message)
            messages.AddErrorMessage(e.message)
        
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
                      

class DasymetricCalculations(object):
    """
    # ---------------------------------------------------------------------------
    # DasymetricCalculations.py
    # Part 4 of the Intelligent Areal Weighting Dasymetric Mapping Toolset
    # By Torrin Hultgren and Jeremy Mennis
    # For Tim Wade, U.S. EPA
    # For use with ArcGIS 10.3 - 2015
    # Usage: DasymetricCalculations <PopFeatureClass> <popCountField> <areaField>
    # <popIDField> <AncFeatureClass> <ancCatName> <presetTable> <presetField>
    # <OutFeatureClass> <percent> <sampleMin> 
    # ---------------------------------------------------------------------------
    """
    def __init__(self):
        self.label = u'Step 4 - Dasymetric Calculations'
        self.canRunInBackground = False
    def getParameterInfo(self):
        # Population_Working_Table
        param_1 = arcpy.Parameter(
            name = u'Population_Working_Table',
            displayName = u'Population Working Table',
            parameterType = 'Required',
            direction = 'Input',
            datatype = u'Table')
        
        # Population_Count_Field
        param_2 = arcpy.Parameter(
            name = u'Population_Count_Field',
            displayName = u'Population Count Field',
            parameterType = 'Required',
            direction = 'Input',
            datatype = u'Field',
            parameterDependencies = [param_1.name])

        # Population_Area_Field
        param_3 = arcpy.Parameter()
        param_3.name = u'Population_Area_Field'
        param_3.displayName = u'Population Area Field'
        param_3.parameterType = 'Required'
        param_3.direction = 'Input'
        param_3.datatype = u'Field'
        param_3.value = u'Count'
        param_3.parameterDependencies = [param_1.name]

        # Dasymetric_Working_Table
        param_4 = arcpy.Parameter()
        param_4.name = u'Dasymetric_Working_Table'
        param_4.displayName = u'Dasymetric Working Table'
        param_4.parameterType = 'Required'
        param_4.direction = 'Input'
        param_4.datatype = u'Table'

        # Population_ID_Field
        param_5 = arcpy.Parameter()
        param_5.name = u'Population_ID_Field'
        param_5.displayName = u'Population ID Field'
        param_5.parameterType = 'Required'
        param_5.direction = 'Input'
        param_5.datatype = u'Field'
        param_5.parameterDependencies = [param_4.name]

        # Ancillary_Class_Field
        param_6 = arcpy.Parameter()
        param_6.name = u'Ancillary_Class_Field'
        param_6.displayName = u'Ancillary Class Field'
        param_6.parameterType = 'Required'
        param_6.direction = 'Input'
        param_6.datatype = u'Field'
        param_6.parameterDependencies = [param_4.name]

        # Combined_Area_Field
        param_7 = arcpy.Parameter()
        param_7.name = u'Combined_Area_Field'
        param_7.displayName = u'Combined Area Field'
        param_7.parameterType = 'Required'
        param_7.direction = 'Input'
        param_7.datatype = u'Field'
        param_7.value = u'PRESETDENS'
        param_7.parameterDependencies = [param_4.name]

        # Minimum_Sample
        param_8 = arcpy.Parameter()
        param_8.name = u'Minimum_Sample'
        param_8.displayName = u'Minimum Sample'
        param_8.parameterType = 'Required'
        param_8.direction = 'Input'
        param_8.datatype = u'Long'
        param_8.value = u'3'

        # Minimum_Sampling_Area
        param_9 = arcpy.Parameter()
        param_9.name = u'Minimum_Sampling_Area'
        param_9.displayName = u'Minimum Sampling Area'
        param_9.parameterType = 'Required'
        param_9.direction = 'Input'
        param_9.datatype = u'Long'
        param_9.value = u'1'

        # Percent
        param_10 = arcpy.Parameter()
        param_10.name = u'Percent'
        param_10.displayName = u'Percent'
        param_10.parameterType = 'Optional'
        param_10.direction = 'Input'
        param_10.datatype = u'Double'
        param_10.value = u'0.95'

        # Preset_Table
        param_11 = arcpy.Parameter()
        param_11.name = u'Preset_Table'
        param_11.displayName = u'Preset Table'
        param_11.parameterType = 'Optional'
        param_11.direction = 'Input'
        param_11.datatype = u'Table'

        # Preset_Field
        param_12 = arcpy.Parameter()
        param_12.name = u'Preset_Field'
        param_12.displayName = u'Preset Field'
        param_12.parameterType = 'Optional'
        param_12.direction = 'Input'
        param_12.datatype = u'Field'
        param_12.value = u'PRESETDENS'
        param_12.parameterDependencies = [param_11.name]

        return [param_1, param_2, param_3, param_4, param_5, param_6, param_7, param_8, param_9, param_10, param_11, param_12]
    def isLicensed(self):
        return True
    def updateParameters(self, parameters):
        validator = getattr(self, 'ToolValidator', None)
        if validator:
             return validator(parameters).updateParameters()
    def updateMessages(self, parameters):
        validator = getattr(self, 'ToolValidator', None)
        if validator:
             return validator(parameters).updateMessages()
    def execute(self, parameters, messages):
        # Strips extension from filename
        def GetFileName(datasetName):
            return os.path.splitext(datasetName)[0] 
        
        # Pulls all the values from a field in a table into a python list object
        def GetValues(table, field, float="n"):
            if table and table != "#":
                fieldObj = arcpy.ListFields(table, field)[0]
                #Modern List Comprehension using data access module to do the same thing.
                inList = [row[0] for row in arcpy.da.SearchCursor(table, field)]
                if fieldObj.type != "String" and float != "y":  #Convert numeric class values to strings
                    inList = [str(int(val)) for val in inList]
            return inList
        
         # Because NULL values can be problematic in queries and field calculations, replaces all NULLS with zeroess.   
        def RemoveNulls(table,field): 
            whereClause = arcpy.AddFieldDelimiters(table,field) + " IS NULL"
            calculateStaticValue(table,field,"0",whereClause)                
        
        def calculateStaticValue(table,field,value,whereClause=''):
            cursor = arcpy.UpdateCursor(table, whereClause)
            if value: 
                for row in cursor:
                    row.setValue(field, value)
                    cursor.updateRow(row)  
            else: #Set to null.
                for row in cursor:
                    row.setNull(field)
                    cursor.updateRow(row)
        
        # The working tables are frequently reused, so it's necessary to reset fields to zeroes
        def ClearField(tableName,fieldName):
            fields = arcpy.ListFields(tableName, fieldName)
            if (len(fields) > 0):
                field = fields[0]
                if field.type == 'String':
                    calculateStaticValue(tableName,fieldName,"''")
                else:
                    calculateStaticValue(tableName,fieldName,False)
        
        # Convert output from field property into expected input for field creation.
        def FieldProps(tableName, fieldName):
            fieldTypeLookup = {"Integer":"LONG","String":"TEXT","Single":"FLOAT","Double":"DOUBLE","SmallInteger":"SHORT","Date":"DATE"}
            field = arcpy.ListFields(tableName, fieldName)[0]
            return [fieldTypeLookup[field.type],field.length]
        
        # If two .dbf tables are joined, the joined fieldnames all have tablename. as prefix.
        # If two tables of different formats are joined, the first table has tablename: as prefix, and the joined table has tablename. as prefix.
        # If two info or FGDB tables are joined, there are no prefixes, and duplicate tablenames in the joined table have a _1 suffix.
        # Solution - derive from the list of Fields:
        def joinedFieldName(tableView,tableName,fieldName):
            fieldList = [field.name for field in arcpy.ListFields(tableView)]
            if ('.' in fieldList[0]) or (':' in fieldList[0]):
              for field in fieldList:
                  if ((field[-len(fieldName):] == fieldName) and (field[:len(tableName)].lower() == tableName.lower())):
                      return field
            else:
              if (tableName.lower() in arcpy.Describe(tableView).name): 
                return fieldName # If this field is in the base table, the name will not be changed
              else:
                return arcpy.ListFields(tableView,fieldName + "*")[-1].name # If this field is in the joined table, it should be the last match from this function (or first, if there's only 1).
            
        try:
            arcpy.env.overwriteOutput = True
            
            #Script arguments...
            popWorkingTable = parameters[0].valueAsText # the name of the population working table from step 2
            popCountField = parameters[1].valueAsText # the field containing population counts
            popAreaField = parameters[2].valueAsText # the area or cell count field in the population working table
            outWorkTable = parameters[3].valueAsText # Dasymetric output working table from step 2    
            popIDField = parameters[4].valueAsText # the field in the output working table that uniquely identifies population source units.
            ancCatName = parameters[5].valueAsText # the name of the field in the output working layer containing category information
            dasyAreaField = parameters[6].valueAsText # the name of the field in the output working layer containing area (or raster cell count)
            sampleMin = parameters[7].valueAsText # Minimum number of source units to ensure a representative sample - default = 3
            popAreaMin = parameters[8].valueAsText # Minimum number of raster cells required for a source unit to be considered representative - default = 1
            percent = parameters[9].valueAsText # Optional parameter - percent value for percent area method - default = 0.95
            presetTable = parameters[10].valueAsText # Optional parameter - Table with ancillary categorys and preset values from step 5
            presetField = parameters[11].valueAsText # Optional parameter - Field in preset table with preset values - field with class values assumed to be the same as ancCatName
            # popWorkingTable = "D:\\dasy\\tim\\popworktbl.dbf"
            # popCountField = "POP2000"
            # popAreaField = "COUNT"
            # outWorkTable = "D:\\dasy\\tim\\DasyWorkTbl.dbf"
            # popIDField = "BLKRAST"
            # ancCatName = "LC01R"
            # dasyAreaField = "COUNT"
            # sampleMin = "3"
            # popAreaMin = 1
            # percent = "0.95"
            # presetTable = "#"
            # presetField = "#"
            
        #Note for future development:  Anywhere in this script where "Value" is hardcoded as a field name
        #probably needs to be removed for compatibility with vectors as input.
        
            outWorkspace = os.path.split(outWorkTable)[0]
            arcpy.env.workspace = outWorkspace
            tableSuffix = ''
        
            AddPrintMessage("Clearing fields from any previous runs...",0)
            # If either of these tables were previously used in a dasymetric routine, we need to clear the values to make sure they don't impact this run.
            for fieldName in ["REP_CAT","POP_AREA","POP_DENS"]:
                ClearField(popWorkingTable,fieldName)
            for fieldName in ["POP_COUNT","POP_AREA","POP_EST","REM_AREA","TOTALFRACT","NEW_POP","NEWDENSITY"]:
                ClearField(outWorkTable,fieldName)
                
            # Process: gather unique IDs
            # Gather unique ancillary IDs into a table - it might be more efficient to use the source ancillary dataset for this - 
            # the one advantage to this method is that it selects only the classes that occur in the study area - and it minimizes the differences between raster and vector inputs
            AddPrintMessage("Collecting unique ancillary categories...",0)
            # Use SearchCursor with list comprehension to return a
            # unique set of values in the specified field
            ancCatValues = GetValues(outWorkTable, ancCatName)
            inAncCatList = [value for value in set(ancCatValues)]
            outAncCatList = inAncCatList
            ancCatFieldProps = FieldProps(outWorkTable,ancCatName)
            if ancCatFieldProps[0] == "TEXT": #Strings require special treatment in where clauses, integers are fine as is.
                inAncCatList = ["'" + ancCat + "'" for ancCat in inAncCatList]
                outAncCatList = ['"' + ancCat + '"' for ancCat in outAncCatList]

            # Create dictionary object of ancillary classes and their preset densities, as well as list of classes preset to zero
            unSampledList = []
            inPresetCatList = GetValues(presetTable, "Value") #Assumes that the ancillary dataset is raster - might need to be more flexible here.
            outPresetCatList = inPresetCatList
            if ancCatFieldProps[0] == "TEXT":
                inPresetCatList = ["'" + AncCat + "'" for AncCat in inPresetCatList]
                outPresetCatList = ['"' + AncCat + '"' for AncCat in outPresetCatList] 
            presetValList = GetValues(presetTable, presetField, "y")
            # Use List comprehension to grab uninhabited classes
            unInhabList = [presetCat for presetCat,presetVal in zip(inPresetCatList,presetValList) if float(presetVal) == 0]
        
            # Make table view from the output working table for selection purposes
            outWorkTableView = "OutWorkTableView"
            arcpy.MakeTableView_management(outWorkTable,outWorkTableView,"#",outWorkspace)
            outWorkTableName = GetName(GetFileName(outWorkTable))
            # Do the same for the POP_AREA field in the popWorkingTable
            popWorkTableView = "PopWorkTableView"
            arcpy.MakeTableView_management(popWorkingTable, popWorkTableView)
            popWorkTableName = GetName(GetFileName(popWorkingTable))
            
            # Create a summary table of the "populated" area of each population source unit
            AddPrintMessage("Creating summary table with the populated area of each source unit...",0)
            # Initialize counter to store population unit IDs
            from collections import Counter
            inhabCounter = Counter()
            if unInhabList:
                inhabWhereClause = arcpy.AddFieldDelimiters(outWorkTable,ancCatName) + " NOT IN (" + ", ".join(unInhabList) + ")"
            else:
                inhabWhereClause = ""
            with arcpy.da.SearchCursor(outWorkTable, [popIDField, dasyAreaField], inhabWhereClause) as cursor:
                for row in cursor:
                    # this summarizes total area by population unit into a python dictionary
                    inhabCounter.update({row[0]:row[1]})
            # Write the inhabited area of each population unit back to the output and population work tables.
            with arcpy.da.UpdateCursor(outWorkTable, [popIDField,"POP_AREA"], inhabWhereClause) as cursor:
                for row in cursor:
                    row[1] = inhabCounter.get(row[0]) 
                    cursor.updateRow(row)
            with arcpy.da.UpdateCursor(popWorkingTable, ["Value","POP_AREA"]) as cursor:
                for row in cursor:
                    row[1] = inhabCounter.get(row[0])
                    cursor.updateRow(row)                     
    
            # Make sure output working table has population counts
            arcpy.SelectLayerByAttribute_management(outWorkTableView, "CLEAR_SELECTION")
            arcpy.AddJoin_management(outWorkTableView, popIDField, popWorkTableView, "Value", "KEEP_COMMON")
            arcpy.CalculateField_management(outWorkTableView, joinedFieldName(outWorkTableView,outWorkTableName,"POP_COUNT"), "!" + joinedFieldName(outWorkTableView,popWorkTableName,popCountField) + "!", 'PYTHON')
            arcpy.RemoveJoin_management(outWorkTableView, popWorkTableName)
        
            # The default value for a number field is zero in a shapefile, but is null in a geodatabase
            # These nulls cause problems in summary operations, so define a function to set them to zero.
            RemoveNulls(outWorkTableView,"POP_AREA")
            RemoveNulls(popWorkTableView,"POP_AREA")
        
            # Select all non-zero population units (dividing by zero to get density is bad)
            AddPrintMessage("Calculating population density...", 0) 
            popAreawhereClause = arcpy.AddFieldDelimiters(popWorkTableView,"POP_AREA") + " > 0"
            with arcpy.da.UpdateCursor(popWorkingTable, ["POP_DENS", popCountField, "POP_AREA"], popAreawhereClause) as cursor:
                for row in cursor:
                    # Population density = population count / populated area
                    row[0] = row[1] / row[2] 
                    cursor.updateRow(row)
            
            # Begin selection process...
            AddPrintMessage("Selecting representative source units...",0)
            # The goal is to calculate "representative" population density values for each ancillary class
            # - by selecting all population units that "represent" that ancillary class and summing population and area.
            # percent area method
            # Slightly different selection set here - only inhabited classes above the minimum threshold specified by the user.
            for inAncCat, OutAncCat in zip(inAncCatList, outAncCatList):
                catCounter = Counter()
                popAreawhereClause = arcpy.AddFieldDelimiters(outWorkTable,"POP_AREA") + " > " + str(popAreaMin)
                popAreawhereClause = popAreawhereClause + " AND " + arcpy.AddFieldDelimiters(outWorkTable,ancCatName) + " = " + str(inAncCat)
                with arcpy.da.SearchCursor(outWorkTable, [popIDField, "POP_AREA", dasyAreaField], popAreawhereClause) as cursor:
                    for row in cursor:
                        # this summarizes populated area by population unit into a python dictionary
                        catCounter.update({(row[0],row[1]):row[2]})
                # Obtain a list of those population unit IDs whose area of this ancillary class falls above the user-specified percent threshold
                repUnitsList = [str(popInfo[0]) for popInfo,catArea in catCounter.items() if (catArea/popInfo[1]) >= float(percent)]
                # If the number of "representative units" falls above the user-specified threshold
                repCount = len(repUnitsList)
                if repCount > float(sampleMin):
                    # Designate these source units as representative of the current ancillary category by putting the category value in the REP_CAT field
                    repWhereClause = arcpy.AddFieldDelimiters(popWorkingTable,"Value") + " IN (" + ", ".join(repUnitsList) + ")"
                    with arcpy.da.UpdateCursor(popWorkingTable, ["REP_CAT"], repWhereClause) as cursor:
                        for row in cursor:
                            row[0] = OutAncCat
                            cursor.updateRow(row)
                    AddPrintMessage("Class " + str(inAncCat) + " was sufficiently sampled with " + str(repCount) + " representative source units.",0)
                # Flag this class if it was insufficiently sampled and not preset
                elif inAncCat not in inPresetCatList:
                    unSampledList.append(str(inAncCat))
                    AddPrintMessage("Class " + str(inAncCat) + " was not sufficiently sampled with only " + str(repCount) + " representative source units.",0)
            
            # For each ancillary class (listed in the REP_CAT field) calculate sum of population and area and statistics
            # - (count, mean, min, max, stddev) of densities further analysis
            AddPrintMessage("Calculating statistics for selected classes...",0)
            # Make sure there are representative classes.
            whereClause = arcpy.AddFieldDelimiters(popWorkingTable,"REP_CAT") + " IS NOT NULL"
            if ancCatFieldProps[0] == "TEXT":
                whereClause = whereClause + " AND " + arcpy.AddFieldDelimiters(popWorkingTable,"REP_CAT") + " <> ''"
            aPopWorkTableView = "aPopWorkTableView"
            arcpy.MakeTableView_management(popWorkingTable, aPopWorkTableView, whereClause)
            ancDensTable = arcpy.CreateUniqueName("SamplingSummaryTable", outWorkspace)
            ancDensTableName = os.path.split(ancDensTable)[1]
            if arcpy.GetCount_management(aPopWorkTableView):
                arcpy.Statistics_analysis(aPopWorkTableView, ancDensTable, popCountField + " SUM; " + popAreaField + " SUM; CELL_DENS MEAN; CELL_DENS MIN; CELL_DENS MAX; CELL_DENS STD; POP_AREA SUM; POP_DENS MEAN; POP_DENS MIN; POP_DENS MAX; POP_DENS STD;" , "REP_CAT")
                arcpy.AddField_management(ancDensTable, "SAMPLDENS", "DOUBLE")
                # Calculate an initial population estimate for each polygon in this class by multiplying the representative class densities by the polygon areas
                calcExpression = "!" + "SUM_" + popCountField + "! / !SUM_POP_AREA!"
                arcpy.CalculateField_management(ancDensTable, "SAMPLDENS", calcExpression, 'PYTHON')
                # Add a field that designates these classes as "Sampled"
                arcpy.AddField_management(ancDensTable, "METHOD", "TEXT", "", "", "7")
                calculateStaticValue(ancDensTable,"METHOD","Sampled")
                arcpy.AddField_management(ancDensTable, "CLASSDENS", "DOUBLE")    
                arcpy.CalculateField_management(ancDensTable, "CLASSDENS", "!SAMPLDENS!", 'PYTHON')
                # For all sampled classes that are not preset, calculate a population estimate for every intersected polygon by joining the ancDensTable and multiplying the class density by the polygon area.
                AddPrintMessage("Calculating first population estimate for sampled and preset classes...",0)
                arcpy.AddJoin_management(outWorkTableView, ancCatName, ancDensTable, "REP_CAT", "KEEP_COMMON")
                if presetTable and presetTable != "#":
                    whereClause = arcpy.AddFieldDelimiters(outWorkTableView,joinedFieldName(outWorkTableView,outWorkTableName,ancCatName)) + " NOT IN (" + ", ".join(inPresetCatList) + ")"
                    arcpy.SelectLayerByAttribute_management(outWorkTableView, "NEW_SELECTION", whereClause)
                else:
                    arcpy.SelectLayerByAttribute_management(outWorkTableView, "CLEAR_SELECTION")
                expression = "!" + joinedFieldName(outWorkTableView,outWorkTableName,dasyAreaField) + "! * !" + joinedFieldName(outWorkTableView,ancDensTableName,"CLASSDENS") + "!"
                arcpy.CalculateField_management(outWorkTableView, joinedFieldName(outWorkTableView,outWorkTableName,"POP_EST"), expression, 'PYTHON')
                arcpy.RemoveJoin_management(outWorkTableView, ancDensTableName)
            else:
                # CreateTable_management (out_path, out_name, template, config_keyword)
                ancDensTable = CreateTable_management(outWorkspace, ancDensTable)
                arcpy.AddField_management(ancDensTable, "REP_CAT", ancCatFieldProps[0], "", "", ancCatFieldProps[1])
                arcpy.AddField_management(ancDensTable, "SAMPLDENS", "DOUBLE")
                arcpy.AddField_management(ancDensTable, "METHOD", "TEXT", "", "", "7")
                arcpy.AddField_management(ancDensTable, "CLASSDENS", "DOUBLE")
                
            if presetTable and presetTable != "#":
                AddPrintMessage("Adding preset values to the summary table...",0)
                # Now, for the preset classes, calculate a population estimate for every intersected polygon by joining the Preset Table and multiplying the preset density by the polygon area
                arcpy.SelectLayerByAttribute_management(outWorkTableView, "CLEAR_SELECTION")
                arcpy.AddJoin_management(outWorkTableView, ancCatName, presetTable, "Value", "KEEP_COMMON")
                presetTableName = GetName(GetFileName(presetTable))
                arcpy.CalculateField_management(outWorkTableView, joinedFieldName(outWorkTableView,outWorkTableName,"POP_EST"), "!" + joinedFieldName(outWorkTableView,outWorkTableName,dasyAreaField) + "! * !" + joinedFieldName(outWorkTableView,presetTableName,presetField) + "!", 'PYTHON')
                arcpy.RemoveJoin_management(outWorkTableView,presetTableName)
                # Add these preset values to the ancDensTable for comparison purposes, altering the official CLASSDENS field, but not the SAMPLDENS field.
                for inPresetCat,outPresetCat,presetVal in zip(inPresetCatList,outPresetCatList,presetValList):
                    ancDensTableView = "AncDensTableView_" + str(inPresetCat)
                    arcpy.MakeTableView_management(ancDensTable, ancDensTableView, arcpy.AddFieldDelimiters(ancDensTable,"REP_CAT") + " = " + inPresetCat)
                    if int(arcpy.GetCount_management(ancDensTableView).getOutput(0)) > 0:
                        arcpy.CalculateField_management(ancDensTableView, "CLASSDENS", presetVal, 'PYTHON')
                        arcpy.CalculateField_management(ancDensTableView, "METHOD", '"Preset"', 'PYTHON')
                    else:
                        cursorFields = ["CLASSDENS","METHOD","REP_CAT"]
                        cursor = arcpy.da.InsertCursor(ancDensTable,cursorFields)
                        cursor.insertRow([presetVal,"Preset",outPresetCat])
                        del cursor
                outPresetCatList, inPresetCatList = None, None
            RemoveNulls(outWorkTableView,"POP_EST")
                       
            # Intelligent areal weighting for unsampled classes
            # - for every source population unit sum the initial population estimates and compare
            # - the result to the actual count for the unit. Distribute any residual population 
            # - among the remaining unsampled inhabited dasymetric polygons
            AddPrintMessage("Performing intelligent areal weighting for unsampled classes...",0)
            if unSampledList:
                unsampledWhereClause = arcpy.AddFieldDelimiters(outWorkTable,ancCatName) + " IN (" + ", ".join(unSampledList) + ")"
                with arcpy.da.UpdateCursor(outWorkTable, ["REM_AREA",dasyAreaField], unsampledWhereClause) as cursor:
                    for row in cursor:
                        row[0] = row[1]
                        cursor.updateRow(row)
                RemoveNulls(outWorkTableView,"REM_AREA")
                popDiffDict = {}
                with arcpy.da.SearchCursor(outWorkTable, [popIDField, "POP_COUNT", "POP_EST", "REM_AREA"], unsampledWhereClause) as cursor:
                    for row in cursor:
                        pkey = (row[0],row[1])
                        pvalues = (row[2],row[3])
                        # this summarizes populated area by population unit into a python dictionary
                        if popDiffDict.has_key(pkey):
                            # if there is an existing value for this key, sum the values of the associated fields
                            # so that we end up with a cumulative total of estimated population and remaining area for this population unit
                            popDiffDict[pkey] = tuple(map(sum,zip(popDiffDict[pkey],pvalues)))
                        else:
                            popDiffDict[pkey] = pvalues
                # Select only those units whose population difference is greater than zero with nonzero remaining area
                # remainderTable = popUnitID: (PopulationDifference (POP_COUNT - POP_EST),Remainder Area (REM_AREA)
                remainderTable = {key[0]:(key[1] - value[0],value[1]) for key, value in popDiffDict.items() if key[1] - value[0]>0 and value[1] != 0}
                del popDiffDict
                with arcpy.da.UpdateCursor(outWorkTable, [popIDField,"POP_EST","REM_AREA"], unsampledWhereClause) as cursor:
                        for row in cursor:
                            # So many references by index, gets a little confusing.  If this is a population unit of concern:
                            if remainderTable.has_key(row[0]):
                                # The Population Estimate value = the popuation difference from the remainder table * the remaining area of the intersected unit
                                row[1] = remainderTable[row[0]][0] * row[2] / remainderTable[row[0]][1]
                                cursor.updateRow(row)
                del remainderTable                
                # Calculate population density values for these unsampled classes
                # - for every unsampled ancillary class, sum total area and total population estimated using intelligent areal weighting.  
                # Calculate class representative density.
                whereClause = unsampledWhereClause + " AND " + arcpy.AddFieldDelimiters(outWorkTableView,"POP_COUNT") + " <> 0"
                ancDensDict = {}
                with arcpy.da.SearchCursor(outWorkTable, [ancCatName, "POP_EST", "POP_AREA"], whereClause) as cursor:
                    for row in cursor:
                        pkey = row[0]
                        pvalues = (row[1],row[2])
                        # this summarizes populated area and estimated population density by ancillary class into a python dictionary
                        if ancDensDict.has_key(pkey):
                            # if there is an existing value for this key, sum the values of the associated fields
                            # so that we end up with a cumulative total of populated area and estimated population density for this ancillary class
                            ancDensDict[pkey] = tuple(map(sum,zip(ancDensDict[pkey],pvalues)))
                        else:
                            ancDensDict[pkey] = pvalues
                # classDensDict = ancillaryClass: ancillary class density if populated area is greater than zero
                classDensDict = {key:value[0]/value[1] for key, value in ancDensDict.items() if value[1] > 0}
                del ancDensDict
                with arcpy.da.UpdateCursor(outWorkTable, [ancCatName,"POP_EST", dasyAreaField], unsampledWhereClause) as cursor:
                        for row in cursor:
                            # If this is an ancillary class of concern:
                            if classDensDict.has_key(row[0]):
                                # The new Population Estimate value = the polygon area * the ancillary class estimate
                                row[1] = row[2] * classDensDict[row[0]]
                                cursor.updateRow(row)

                # - Lastly, add these IAW values to the ancDensTable
                cursorFields = ['CLASSDENS','METHOD','REP_CAT']
                cursor = arcpy.da.InsertCursor(ancDensTable,cursorFields)
                for ancCat, classDens in classDensDict.items():
                    cursor.insertRow([classDens,"IAW",ancCat])
                del cursor, classDensDict
            # End of intelligent areal weighting
             
            # Perform final calculations to ensure pycnophylactic integrity
            AddPrintMessage("Performing final calculations to ensure pycnophylactic integrity...",0)
            # For each population source unit, sum the population estimates,
            # - which do not necessarily sum to the actual population of the source,
            # - and use the ratio of the estimates to the estimated total to distribute the actual total.
            pycCounter = Counter()
            popAreawhereClause = arcpy.AddFieldDelimiters(outWorkTable,"POP_AREA") + " > 0"
            with arcpy.da.SearchCursor(outWorkTable, [popIDField, "POP_EST"], popAreawhereClause) as cursor:
                for row in cursor:
                    # this summarizes populated area by population unit into a python dictionary
                    pycCounter.update({row[0]:row[1]})
            # Filter non-zero estimated population
            pycCounter = {popID:popEst for popID, popEst in pycCounter.items() if popEst != 0}
            with arcpy.da.UpdateCursor(outWorkTable, [popIDField, "TOTALFRACT", "POP_EST", "POP_COUNT", "NEW_POP", dasyAreaField, "NEWDENSITY"], popAreawhereClause) as cursor:
                for row in cursor:
                    if pycCounter.has_key(row[0]):
                        totalFraction = row[2] / pycCounter[row[0]]
                        row[1] = totalFraction
                        newPop = row[3] * totalFraction
                        row[4] = newPop
                        if row[5] != 0:
                            newDensity = newPop / row[5]
                            row[6] = newDensity 
                        cursor.updateRow(row)
            
            # Lastly create an official output statistics table
            AddPrintMessage("Creating a final summary table",0)
            finalSummaryTable = arcpy.CreateUniqueName("FinalSummaryTable", outWorkspace)
            arcpy.Statistics_analysis(outWorkTable, finalSummaryTable, "NEW_POP SUM; NEWDENSITY MEAN; NEWDENSITY MIN; NEWDENSITY MAX; NEWDENSITY STD", ancCatName)
           
        # Geoprocessing Errors will be caught here
        except Exception as e:
            print (e.message)
            messages.AddErrorMessage(e.message)
        
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
        

class CreateFinalRaster(object):
    """
    # ---------------------------------------------------------------------------
    # CreateFinalRaster.py
    # Part 5 of the Intelligent Areal Weighting Dasymetric Mapping Toolset
    # Usage: CreateFinalRaster <dasyRaster> <dasyWorkTable> <outputRaster> 
    # ---------------------------------------------------------------------------
    """
    def __init__(self):
        self.label = u'Step 5 - Create Final Dasymetric Raster'
        self.description = "This tool creates a floating-point population density raster by joining a table with dasymetrically calculated population density with the combined population and ancillary raster created in step 2."
        self.canRunInBackground = False
    def getParameterInfo(self):
        # Dasymetric_Raster
        param_1 = arcpy.Parameter()
        param_1.name = u'Dasymetric_Raster'
        param_1.displayName = u'Dasymetric Raster'
        param_1.parameterType = 'Required'
        param_1.direction = 'Input'
        param_1.datatype = u'Raster Dataset'

        # Dasymetric_Working_Table
        param_2 = arcpy.Parameter()
        param_2.name = u'Dasymetric_Working_Table'
        param_2.displayName = u'Dasymetric Working Table'
        param_2.parameterType = 'Required'
        param_2.direction = 'Input'
        param_2.datatype = u'Table'

        # Density_Raster
        param_3 = arcpy.Parameter()
        param_3.name = u'Density_Raster'
        param_3.displayName = u'Density Raster'
        param_3.parameterType = 'Required'
        param_3.direction = 'Output'
        param_3.datatype = u'Raster Dataset'

        return [param_1, param_2, param_3]
    def isLicensed(self):
        """Allow the tool to execute, only if the Spatial Analyst extension 
        is available."""
        try:
            if arcpy.CheckExtension("spatial") != "Available":
                raise Exception
        except Exception:
            return False  # tool cannot be executed
        return True  # tool can be executed
    def updateParameters(self, parameters):
        validator = getattr(self, 'ToolValidator', None)
        if validator:
             return validator(parameters).updateParameters()
    def updateMessages(self, parameters):
        validator = getattr(self, 'ToolValidator', None)
        if validator:
             return validator(parameters).updateMessages()
    def execute(self, parameters, messages):
        try:
            # Check out any necessary licenses
            if arcpy.CheckExtension("spatial") == "Available":
                arcpy.CheckOutExtension("spatial")
            else:
                AddPrintMessage("Spatial Analyst license is unavailable", 2)
            
            # Enable Overwriting
            arcpy.env.overwriteOutput = True
            
            # Script arguments...
            dasyRaster = parameters[0].valueAsText # The combined population and ancillary raster created as the output from step 2.
            dasyWorkTable = parameters[1].valueAsText # The dasymetric working table created in step 2 and populated in step 4. This script will use the final column from that table for the output density values. 
            outputRaster = parameters[2].valueAsText # Please enter the desired output raster with the full path. When you're not saving to a geodatabase, specify .tif for a TIFF file format, .img for an ERDAS IMAGINE file format, or no extension for an ESRI GRID file format.
            
            outWorkspace = os.path.dirname(str(outputRaster))
            arcpy.env.workspace = outWorkspace
            
            # Make the raster layer and add the join
            arcpy.MakeRasterLayer_management(dasyRaster, "DRL")
            arcpy.AddJoin_management("DRL", "Value", dasyWorkTable, "Value", "KEEP_COMMON")    
            
            # Due to bug NIM066814 we can't use the lookup tool on the joined table, so we have to copy the joined raster.
            dasyoutrast = arcpy.CreateUniqueName("dasyoutrast", outWorkspace)
            joinedRaster = arcpy.CopyRaster_management("DRL", dasyoutrast)
            
            lookupRaster = arcpy.sa.Lookup(joinedRaster, "NEWDENSITY") 
            
            lookupRaster.save(outputRaster)
            
            # Clean up the in-memory raster layer and the intermediate joined raster
            arcpy.Delete_management("DRL")
            arcpy.Delete_management(dasyoutrast)
            
        # Geoprocessing Errors will be caught here
        except Exception as e:
            print (e.message)
            messages.AddErrorMessage(e.message)
        
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
        

class CombinedSteps123(object):
    def __init__(self):
        self.label = u'Combined Steps 1-3 - Prepare for Dasymetric Calc'
        self.canRunInBackground = False
    def getParameterInfo(self):
        # Population_Features
        param_1 = arcpy.Parameter()
        param_1.name = u'Population_Features'
        param_1.displayName = u'Population Features'
        param_1.parameterType = 'Required'
        param_1.direction = 'Input'
        param_1.datatype = u'Feature Class'

        # Population_Count_Field
        param_2 = arcpy.Parameter()
        param_2.name = u'Population_Count_Field'
        param_2.displayName = u'Population Count Field'
        param_2.parameterType = 'Required'
        param_2.direction = 'Input'
        param_2.datatype = u'Field'

        # Population_Key_Field
        param_3 = arcpy.Parameter()
        param_3.name = u'Population_Key_Field'
        param_3.displayName = u'Population Key Field'
        param_3.parameterType = 'Optional'
        param_3.direction = 'Input'
        param_3.datatype = u'Field'

        # Population_Raster
        param_4 = arcpy.Parameter()
        param_4.name = u'Population_Raster'
        param_4.displayName = u'Population Raster'
        param_4.parameterType = 'Required'
        param_4.direction = 'Output'
        param_4.datatype = u'Raster Dataset'

        # Population_Working_Table
        param_5 = arcpy.Parameter()
        param_5.name = u'Population_Working_Table'
        param_5.displayName = u'Population Working Table'
        param_5.parameterType = 'Required'
        param_5.direction = 'Output'
        param_5.datatype = u'Table'

        # Cell_Assignment_Type
        param_6 = arcpy.Parameter()
        param_6.name = u'Cell_Assignment_Type'
        param_6.displayName = u'Cell Assignment Type'
        param_6.parameterType = 'Optional'
        param_6.direction = 'Input'
        param_6.datatype = u'String'
        param_6.value = u'CELL_CENTER'
        param_6.filter.list = [u'CELL_CENTER', u'MAXIMUM_AREA', u'MAXIMUM_COMBINED_AREA']

        # Ancillary_Raster
        param_7 = arcpy.Parameter()
        param_7.name = u'Ancillary_Raster'
        param_7.displayName = u'Ancillary Raster'
        param_7.parameterType = 'Required'
        param_7.direction = 'Input'
        param_7.datatype = u'Raster Dataset'

        # Ancillary_Preset_Table
        param_8 = arcpy.Parameter()
        param_8.name = u'Ancillary_Preset_Table'
        param_8.displayName = u'Ancillary Preset Table'
        param_8.parameterType = 'Required'
        param_8.direction = 'Output'
        param_8.datatype = u'Table'

        # Dasymetric_Raster
        param_9 = arcpy.Parameter()
        param_9.name = u'Dasymetric_Raster'
        param_9.displayName = u'Dasymetric Raster'
        param_9.parameterType = 'Required'
        param_9.direction = 'Output'
        param_9.datatype = u'Raster Dataset'

        # Dasymetric_Working_Table
        param_10 = arcpy.Parameter()
        param_10.name = u'Dasymetric_Working_Table'
        param_10.displayName = u'Dasymetric Working Table'
        param_10.parameterType = 'Required'
        param_10.direction = 'Output'
        param_10.datatype = u'Table'

        return [param_1, param_2, param_3, param_4, param_5, param_6, param_7, param_8, param_9, param_10]
    def isLicensed(self):
        return True
    def updateParameters(self, parameters):
        validator = getattr(self, 'ToolValidator', None)
        if validator:
             return validator(parameters).updateParameters()
    def updateMessages(self, parameters):
        validator = getattr(self, 'ToolValidator', None)
        if validator:
             return validator(parameters).updateMessages()
    def execute(self, parameters, messages):
        pass

            