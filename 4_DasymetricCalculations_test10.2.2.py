# ---------------------------------------------------------------------------
# DasymetricCalculations.py
# Part 4 of the Intelligent Areal Weighting Dasymetric Mapping Toolset
# By Torrin Hultgren and Jeremy Mennis
# For Tim Wade, U.S. EPA
# For use with ArcGIS 10 - 2010
# Usage: VectDasy <PopFeatureClass> <popCountField> <areaField>
# <popIDField> <AncFeatureClass> <ancCatName> <presetTable> <presetField>
# <OutFeatureClass> <percent> <sampleMin>
# ---------------------------------------------------------------------------

# Import system modules
import sys, string, os, arcpy, traceback

arcpy.env.overwriteOutput = True

# Helper function for displaying messages
def AddPrintMessage(msg, severity):
    print msg
    if severity == 0: arcpy.AddMessage(msg)
    elif severity == 1: arcpy.AddWarning(msg)
    elif severity == 2: arcpy.AddError(msg)

# Strips path from dataset
def GetName(datasetName):
    return os.path.basename(datasetName)

# Strips extension from filename
def GetFileName(datasetName):
    return os.path.splitext(datasetName)[0]

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

# Pulls all the values from a field in a table into a python list object
def GetValues(table, field, float="n"):
    inList = []
    if table and table <> "#":
        fieldObj = arcpy.ListFields(table, field)[0]
        rows = arcpy.SearchCursor(table)
        row = rows.next()
        while row:
            inList.append(row.getValue(field))
            row = rows.next()
        if fieldObj.type <> "String" and float <> "y":  #Convert numeric class values to strings
            inList = [str(int(val)) for val in inList]
        rows, row, fieldList, fieldObj = None, None, None, None
    return inList

 # Because NULL values can be problematic in queries and field calculations, replaces all NULLS with zeroess.
def RemoveNulls(tableView,field):
    arcpy.SelectLayerByAttribute_management(tableView, "NEW_SELECTION", arcpy.AddFieldDelimiters(tableView,field) + " IS NULL")
    if arcpy.GetCount_management(tableView):
        arcpy.CalculateField_management(tableView, field, "0", 'PYTHON')

# The working tables are frequently reused, so it's necessary to reset fields to zeroes
def ClearField(tableName,fieldName):
    fields = arcpy.ListFields(tableName, fieldName)
    if (len(fields) > 0):
        field = fields[0]
        if field.type == 'String':
            arcpy.CalculateField_management(tableName,fieldName, "''", 'PYTHON')
        else:
            arcpy.CalculateField_management(tableName,fieldName, "0", 'PYTHON')

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
    ##    # TEST Script arguments...
##    popWorkingTable = "D:\\dasy\\tim\\popworktbl.dbf"
##    popCountField = "POP2000"
##    popAreaField = "COUNT"
##    outWorkTable = "D:\\dasy\\tim\\DasyWorkTbl.dbf"
##    popIDField = "BLKRAST"
##    ancCatName = "LC01R"
##    dasyAreaField = "COUNT"
##    sampleMin = "3"
##    popAreaMin = 1
##    percent = "0.95"
##    presetTable = "#"
##    presetField = "#"

    #Script arguments...
    popWorkingTable = arcpy.GetParameterAsText(0) # the name of the population working table from step 2
    popCountField = arcpy.GetParameterAsText(1) # the field containing population counts
    popAreaField = arcpy.GetParameterAsText(2) # the area or cell count field in the population working table
    outWorkTable = arcpy.GetParameterAsText(3) # Dasymetric output working table from step 2
    popIDField = arcpy.GetParameterAsText(4) # the field in the output working table that uniquely identifies population source units.
    ancCatName = arcpy.GetParameterAsText(5) # the name of the field in the output working layer containing category information
    dasyAreaField = arcpy.GetParameterAsText(6) # the name of the field in the output working layer containing area (or raster cell count)
    sampleMin = arcpy.GetParameterAsText(7) # Minimum number of source units to ensure a representative sample - default = 3
    popAreaMin = arcpy.GetParameterAsText(8) # Minimum number of raster cells required for a source unit to be considered representative - default = 1
    percent = arcpy.GetParameterAsText(9) # Optional parameter - percent value for percent area method - default = 0.95
    presetTable = arcpy.GetParameterAsText(10) # Optional parameter - Table with ancillary categorys and preset values from step 5
    presetField = arcpy.GetParameterAsText(11) # Optional parameter - Field in preset table with preset values - field with class values assumed to be the same as ancCatName



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
    ancCategoryTable, ancCategoryTableName = NameCheck("AncCategoryTable",tableSuffix)
    arcpy.Frequency_analysis(outWorkTable, ancCategoryTable, ancCatName)
    # Gather the IDs from the table to a python list object
    inAncCatList = GetValues(ancCategoryTable, ancCatName)
    outAncCatList = inAncCatList
    ancCatFieldProps = FieldProps(outWorkTable,ancCatName)
    if ancCatFieldProps[0] == "TEXT": #Strings require special treatment in where clauses, integers are fine as is.
        inAncCatList = ["'" + ancCat + "'" for ancCat in inAncCatList]
        outAncCatList = ['"' + ancCat + '"' for ancCat in outAncCatList]
    arcpy.Delete_management(ancCategoryTable)

    # Create dictionary object of ancillary classes and their preset densities, as well as list of classes preset to zero
    unInhabList, unSampledList = [], []
    inPresetCatList = GetValues(presetTable, "Value") #Assumes that the ancillary dataset is raster - might need to be more flexible here.
    outPresetCatList = inPresetCatList
    if ancCatFieldProps[0] == "TEXT":
        inPresetCatList = ["'" + AncCat + "'" for AncCat in inPresetCatList]
        outPresetCatList = ['"' + AncCat + '"' for AncCat in outPresetCatList]
    presetValList = GetValues(presetTable, presetField, "y")
    i = 0
    for presetCat in inPresetCatList:
        if float(presetValList[i]) == 0:
            unInhabList.append(presetCat)
        i = i + 1
    i = None

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
    if unInhabList:
        arcpy.SelectLayerByAttribute_management(outWorkTableView, "NEW_SELECTION", arcpy.AddFieldDelimiters(outWorkTableView,ancCatName) + " NOT IN (" + ", ".join(unInhabList) + ")")
    else:
        arcpy.SelectLayerByAttribute_management(outWorkTableView, "CLEAR_SELECTION")
    inhabAreaTable, inhabAreaTableName = NameCheck("InhabAreaTable", tableSuffix)
    arcpy.Frequency_analysis(outWorkTableView, inhabAreaTable, popIDField, dasyAreaField)
    arcpy.AddJoin_management(outWorkTableView, popIDField, inhabAreaTable, popIDField, "KEEP_COMMON")
    arcpy.CalculateField_management(outWorkTableView, joinedFieldName(outWorkTableView,outWorkTableName,"POP_AREA"), "!" + joinedFieldName(dasyWorkTableView,inhabAreaTableName,dasyAreaField) + "!", 'PYTHON')
    arcpy.RemoveJoin_management(outWorkTableView, inhabAreaTableName)
    arcpy.AddJoin_management(popWorkTableView, "Value", inhabAreaTable, popIDField, "KEEP_COMMON")
    arcpy.CalculateField_management(popWorkTableView, joinedFieldName(popWorkTableView,popWorkTableName,"POP_AREA"), "!" + joinedFieldName(popWorkTableView,inhabAreaTableName,dasyAreaField) + "!", 'PYTHON')
    arcpy.RemoveJoin_management(popWorkTableView, inhabAreaTableName)
    arcpy.Delete_management(inhabAreaTable)

    # Make sure output working table has population counts
    arcpy.SelectLayerByAttribute_management(outWorkTableView, "CLEAR_SELECTION")
    arcpy.AddJoin_management(outWorkTableView, popIDField, popWorkTableView, "Value", "KEEP_COMMON")
    arcpy.CalculateField_management(outWorkTableView, joinedFieldName(outWorkTableView,outWorkTableName,"POP_COUNT"), "!" + joinedFieldName(dasyWorkTableView,popWorkTableName,popCountField) + "!", 'PYTHON')
    arcpy.RemoveJoin_management(outWorkTableView, popWorkTableName)

    # The default value for a number field is zero in a shapefile, but is null in a geodatabase
    # These nulls cause problems in summary operations, so define a function to set them to zero.
    RemoveNulls(outWorkTableView,"POP_AREA")
    RemoveNulls(popWorkTableView,"POP_AREA")

    # Select all non-zero population units (dividing by zero to get density is bad)
    popAreawhereClause = arcpy.AddFieldDelimiters(popWorkTableView,"POP_AREA") + " > 0"
    arcpy.SelectLayerByAttribute_management(popWorkTableView, "NEW_SELECTION", popAreawhereClause)
    arcpy.CalculateField_management(popWorkTableView, "POP_DENS", "!" + popCountField + "! / !POP_AREA!", 'PYTHON')

    # Begin selection process...
    AddPrintMessage("Selecting representative source units...",0)
    # The goal is to calculate "representative" population density values for each ancillary class
    # - by selecting all population units that "represent" that ancillary class and summing population and area.
    # percent area method
    # Slightly different selection set here - only inhabited classes above the minimum threshold specified by the user.
    popAreawhereClause = arcpy.AddFieldDelimiters(popWorkTableView,"POP_AREA") + " > " + str(popAreaMin)
    percentAreaTable, percentAreaTableName = NameCheck("percentAreaTable",tableSuffix)
    arcpy.SelectLayerByAttribute_management(outWorkTableView, "NEW_SELECTION", popAreawhereClause)
    arcpy.Frequency_analysis(outWorkTableView, percentAreaTable, popIDField + ";" + ancCatName + ";POP_AREA", dasyAreaField)
    arcpy.AddField_management(percentAreaTable, "percent", "DOUBLE")
    arcpy.CalculateField_management(percentAreaTable, "percent", "!" + dasyAreaField + "! / !POP_AREA!", 'PYTHON')
    for inAncCat, OutAncCat in zip(inAncCatList, outAncCatList):
        whereClause = arcpy.AddFieldDelimiters(percentAreaTable,"percent") + " >= " + percent
        whereClause = whereClause + " AND " + arcpy.AddFieldDelimiters(percentAreaTable,ancCatName) + " = " + inAncCat
        popSelSetTable, popSelSetTableName = NameCheck("PopSelSet",tableSuffix)
        arcpy.TableSelect_analysis(percentAreaTable, popSelSetTable, whereClause)
        count = int(arcpy.GetCount_management(popSelSetTable).getOutput(0))
        # If the selection set is not empty...
        if count >= long(sampleMin):
            arcpy.AddJoin_management(popWorkTableView, "Value", popSelSetTable, popIDField, "KEEP_COMMON")
            # Designate these source units as representative of the current ancillary category by putting the category value in the REP_CAT field
            arcpy.CalculateField_management(popWorkTableView, joinedFieldName(popWorkTableView,popWorkTableName,"REP_CAT"), OutAncCat, 'PYTHON')
            arcpy.RemoveJoin_management(popWorkTableView, popSelSetTableName)
            AddPrintMessage("Class " + inAncCat + " was sufficiently sampled with " + str(count) + " representative source units.",0)
        # Flag this class if it was insufficiently sampled and not preset
        elif inAncCat not in inPresetCatList:
            unSampledList.append(inAncCat)
            AddPrintMessage("Class " + inAncCat + " was not sufficiently sampled with only " + str(count) + " representative source units.",0)
        # End loop for this ancillary class...
        #Funkiness because of lock error
        import time
        breaktime = time.time() + 30 #wait up to 30 seconds to see if lock can be released.
        while breaktime > time.time():
            if arcpy.TestSchemaLock(popSelSetTable):
                arcpy.Delete_management(popSelSetTable)
                break
    arcpy.Delete_management(percentAreaTable)

    # For each ancillary class (listed in the REP_CAT field) calculate sum of population and area and statistics
    # - (count, mean, min, max, stddev) of densities further analysis
    AddPrintMessage("Calculating statistics for selected classes...",0)
    # Make sure there are representative classes.
    whereClause = arcpy.AddFieldDelimiters(popWorkingTable,"REP_CAT") + " IS NOT NULL"
    if ancCatFieldProps[0] == "TEXT":
        whereClause = whereClause + " AND " + arcpy.AddFieldDelimiters(popWorkingTable,"REP_CAT") + " <> ''"
    aPopWorkTableView = "aPopWorkTableView"
    arcpy.MakeTableView_management(popWorkingTable, aPopWorkTableView, whereClause)
    ancDensTable, ancDensTableName = NameCheck("SamplingSummaryTable",tableSuffix)
    if arcpy.GetCount_management(aPopWorkTableView):
        arcpy.Statistics_analysis(aPopWorkTableView, ancDensTable, popCountField + " SUM; " + popAreaField + " SUM; CELL_DENS MEAN; CELL_DENS MIN; CELL_DENS MAX; CELL_DENS STD; POP_AREA SUM; POP_DENS MEAN; POP_DENS MIN; POP_DENS MAX; POP_DENS STD;" , "REP_CAT")
        arcpy.AddField_management(ancDensTable, "SAMPLDENS", "DOUBLE")
        # Calculate an initial population estimate for each polygon in this class by multiplying the representative class densities by the polygon areas
        calcExpression = "!" + "SUM_" + popCountField + "! / !SUM_POP_AREA!"
        arcpy.CalculateField_management(ancDensTable, "SAMPLDENS", calcExpression, 'PYTHON')
        # Add a field that designates these classes as "Sampled"
        arcpy.AddField_management(ancDensTable, "METHOD", "TEXT", "", "", "7")
        arcpy.CalculateField_management(ancDensTable, "METHOD", '"Sampled"', 'PYTHON')
        arcpy.AddField_management(ancDensTable, "CLASSDENS", "DOUBLE")
        arcpy.CalculateField_management(ancDensTable, "CLASSDENS", "!SAMPLDENS!", 'PYTHON')
        # For all sampled classes that are not preset, calculate a population estimate for every intersected polygon by joining the ancDensTable and multiplying the class density by the polygon area.
        AddPrintMessage("Calculating first population estimate for sampled and preset classes...",0)
        arcpy.AddJoin_management(outWorkTableView, ancCatName, ancDensTable, "REP_CAT", "KEEP_COMMON")
        if presetTable and presetTable <> "#":
            whereClause = arcpy.AddFieldDelimiters(outWorkTableView,joinedFieldName(outWorkTableView,outWorkTableName,ancCatName)) + " NOT IN (" + ", ".join(inPresetCatList) + ")"
            arcpy.SelectLayerByAttribute_management(outWorkTableView, "NEW_SELECTION", whereClause)
        else:
            arcpy.SelectLayerByAttribute_management(outWorkTableView, "CLEAR_SELECTION")
        arcpy.CalculateField_management(outWorkTableView, joinedFieldName(outWorkTableView,outWorkTableName,"POP_EST"), "!" + joinedFieldName(dasyWorkTableView,dasyWorkTableName,dasyAreaField) + "! * !" + joinedFieldName(dasyWorkTableView,ancDensTableName,"CLASSDENS") + "!", 'PYTHON')
        arcpy.RemoveJoin_management(outWorkTableView, ancDensTableName)
    else:
        # CreateTable_management (out_path, out_name, template, config_keyword)
        ancDensTable = CreateTable_management(outWorkspace, ancDensTable)
        arcpy.AddField_management(ancDensTable, "REP_CAT", ancCatFieldProps[0], "", "", ancCatFieldProps[1])
        arcpy.AddField_management(ancDensTable, "SAMPLDENS", "DOUBLE")
        arcpy.AddField_management(ancDensTable, "METHOD", "TEXT", "", "", "7")
        arcpy.AddField_management(ancDensTable, "CLASSDENS", "DOUBLE")

    if presetTable and presetTable <> "#":
        AddPrintMessage("Adding preset values to the summary table...",0)
        # Now, for the preset classes, calculate a population estimate for every intersected polygon by joining the Preset Table and multiplying the preset density by the polygon area
        arcpy.SelectLayerByAttribute_management(outWorkTableView, "CLEAR_SELECTION")
        arcpy.AddJoin_management(outWorkTableView, ancCatName, presetTable, "Value", "KEEP_COMMON")
        presetTableName = GetName(GetFileName(presetTable))
        arcpy.CalculateField_management(outWorkTableView, joinedFieldName(outWorkTableView,outWorkTableName,"POP_EST"), "!" + joinedFieldName(dasyWorkTableView,dasyWorkTableName,dasyAreaField) + "! * !" + joinedFieldName(dasyWorkTableView,ancPresetTableName,presetField) + "!", 'PYTHON')
        arcpy.RemoveJoin_management(outWorkTableView,presetTableName)
        # Add these preset values to the ancDensTable for comparison purposes, altering the official CLASSDENS field, but not the SAMPLDENS field.
        i = 0
        for inPresetCat in inPresetCatList:
            ancDensTableView = "AncDensTableView_" + str(inPresetCat)
            arcpy.MakeTableView_management(ancDensTable, ancDensTableView, arcpy.AddFieldDelimiters(ancDensTable,"REP_CAT") + " = " + inPresetCat)
            count = int(arcpy.GetCount_management(ancDensTableView).getOutput(0))
            if count > 0:
                arcpy.CalculateField_management(ancDensTableView, "CLASSDENS", presetValList[i], 'PYTHON')
                arcpy.CalculateField_management(ancDensTableView, "METHOD", '"Preset"', 'PYTHON')
            else:
                rows = arcpy.InsertCursor(ancDensTable)
                row = rows.newRow()
                row.CLASSDENS = presetValList[i]
                row.METHOD = "Preset"
                row.REP_CAT = outPresetCatList[i]
                rows.insertRow(row)
                row, rows = None, None
            i = i + 1
        outPresetCatList, inPresetCatList, i = None, None, None
    RemoveNulls(outWorkTableView,"POP_EST")

    # Intelligent areal weighting for unsampled classes
    # - for every source population unit sum the initial population estimates and compare
    # - the result to the actual count for the unit. Distribute any residual population
    # - among the remaining unsampled inhabited dasymetric polygons
    AddPrintMessage("Performing intelligent areal weighting for unsampled classes...",0)
    if unSampledList:
        arcpy.SelectLayerByAttribute_management(outWorkTableView, "NEW_SELECTION", arcpy.AddFieldDelimiters(outWorkTableView,ancCatName) + " IN (" + ", ".join(unSampledList) + ")")
        arcpy.CalculateField_management(outWorkTableView, "REM_AREA", "!" + dasyAreaField + "!", 'PYTHON')
        RemoveNulls(outWorkTableView,"REM_AREA")
        remainderTable, remainderTableName = NameCheck("remainderTable", tableSuffix)
        arcpy.SelectLayerByAttribute_management(outWorkTableView, "CLEAR_SELECTION") # To clear previous selection set
        arcpy.Frequency_analysis(outWorkTableView, remainderTable, popIDField + ";POP_COUNT", "POP_EST;REM_AREA")
        arcpy.AddField_management(remainderTable, "POP_DIFF", "DOUBLE")
        arcpy.CalculateField_management(remainderTable, "POP_DIFF", "!POP_COUNT! - !POP_EST!", 'PYTHON')
        arcpy.AddJoin_management(outWorkTableView, popIDField, remainderTable, popIDField, "KEEP_COMMON")
        whereClause = arcpy.AddFieldDelimiters(outWorkTableView,joinedFieldName(outWorkTableView,remainderTableName,"POP_DIFF")) + " > 0"
        whereClause = whereClause + " AND " + arcpy.AddFieldDelimiters(outWorkTableView,joinedFieldName(outWorkTableView,remainderTableName,"REM_AREA")) + " <> 0"
        arcpy.SelectLayerByAttribute_management(outWorkTableView, "NEW_SELECTION", whereClause)
        arcpy.CalculateField_management(outWorkTableView, joinedFieldName(outWorkTableView,outWorkTableName,"POP_EST"), "!" + joinedFieldName(dasyWorkTableView,remainderTableName,"POP_DIFF") + "! * !" + joinedFieldName(dasyWorkTableView,dasyWorkTableName,"REM_AREA") + "! / !" + joinedFieldName(dasyWorkTableView,remainderTableName,"REM_AREA") + "!", 'PYTHON')
        arcpy.RemoveJoin_management(outWorkTableView, remainderTableName)
        arcpy.Delete_management(remainderTable)

        # Calculate population density values for these unsampled classes
        # - for every unsampled ancillary class, sum total area and total population estimated using intelligent areal weighting.
        # Calculate class representative density.
        whereClause = arcpy.AddFieldDelimiters(outWorkTableView,ancCatName) + " IN (" + ", ".join(unSampledList) + ")"
        whereClause = whereClause + " AND " + arcpy.AddFieldDelimiters(outWorkTableView,"POP_COUNT") + " <> 0"
        arcpy.SelectLayerByAttribute_management(outWorkTableView, "NEW_SELECTION", whereClause)
        ancDensTable2, ancDensTable2Name = NameCheck("ancDensTable2",tableSuffix)
        arcpy.Frequency_analysis(outWorkTableView, ancDensTable2, ancCatName, "POP_EST;POP_AREA")
        arcpy.AddField_management(ancDensTable2, "CLASSDENS", "DOUBLE")
        whereClause = arcpy.AddFieldDelimiters(ancDensTable2,"POP_AREA") + " > 0"
        ancDensTable2View = "ancDensTable2View"
        arcpy.MakeTableView_management(ancDensTable2, ancDensTable2View, whereClause)
        arcpy.CalculateField_management(ancDensTable2View, "CLASSDENS", "!POP_EST! / !POP_AREA!", 'PYTHON')
        arcpy.AddJoin_management(outWorkTableView, ancCatName, ancDensTable2, ancCatName, "KEEP_COMMON")
        # - Again recalculate population estimate field (POP_EST) using new representative density for final stats analysis
        arcpy.CalculateField_management(outWorkTableView, joinedFieldName(outWorkTableView,outWorkTableName,"POP_EST"), "!" + joinedFieldName(dasyWorkTableView,dasyWorkTableName,dasyAreaField) + "! * !" + joinedFieldName(dasyWorkTableView,ancDensTable2Name,"CLASSDENS") + "!", 'PYTHON')
        arcpy.RemoveJoin_management(outWorkTableView, ancDensTable2Name)

        # - Lastly, add these IAW values to the ancDensTable
        iawValList = GetValues(ancDensTable2, "CLASSDENS", "y")
        unSampledList = GetValues(ancDensTable2, ancCatName)
        rows = arcpy.InsertCursor(ancDensTable)
        for i in range(0, len(iawValList)):
            row = rows.newRow()
            row.CLASSDENS = iawValList[i]
            row.METHOD = "IAW"
            row.REP_CAT = int(unSampledList[i])
            rows.insertRow(row)
        del rows, row
        arcpy.Delete_management(ancDensTable2)
    # End of intelligent areal weighting

    # Perform final calculations to ensure pycnophylactic integrity
    AddPrintMessage("Performing final calculations to ensure pycnophylactic integrity...",0)
    # For each population source unit, sum the population estimates,
    # - which do not necessarily sum to the actual population of the source,
    # - and use the ratio of the estimates to the estimated total to distribute the actual total.
    popEstSumTable, popEstSumTableName = NameCheck("popEstSumTable", tableSuffix)
    arcpy.SelectLayerByAttribute_management(outWorkTableView, "CLEAR_SELECTION") # To clear previous selection set
    arcpy.Frequency_analysis(outWorkTableView, popEstSumTable, popIDField, "POP_EST")
    arcpy.AddJoin_management(outWorkTableView, popIDField, popEstSumTable, popIDField, "KEEP_COMMON")
    # The ratio of each dasymetric unit's population estimate to this sum is called the total fraction
    whereClause = arcpy.AddFieldDelimiters(outWorkTableView, joinedFieldName(outWorkTableView,popEstSumTableName,"POP_EST")) + " <> 0"
    arcpy.SelectLayerByAttribute_management(outWorkTableView, "NEW_SELECTION", whereClause)
    # [TOTALFRACT] = [POP_EST] / POP_ESTSum
    arcpy.CalculateField_management(outWorkTableView, joinedFieldName(outWorkTableView,outWorkTableName,"TOTALFRACT"), "!" + joinedFieldName(dasyWorkTableView,dasyWorkTableName,"POP_EST") + "! / !" + joinedFieldName(dasyWorkTableView,popEstSumTableName,"POP_EST") + "!", 'PYTHON')
    arcpy.RemoveJoin_management(outWorkTableView, popEstSumTableName)
    arcpy.Delete_management(popEstSumTable)
    # The total fraction times the actual population is the true dasymetric estimate
    # [NEW_POP] = [TOTALFRACT] * [source unit pop] = [source unit pop] * [POP_EST] / POP_ESTSum
    arcpy.CalculateField_management(outWorkTableView, "NEW_POP", "!POP_COUNT! * !TOTALFRACT!", 'PYTHON')
    # Calculate a final density value for statistical purposes
    whereClause = arcpy.AddFieldDelimiters(outWorkTableView,dasyAreaField) + " <> 0"
    arcpy.SelectLayerByAttribute_management(outWorkTableView, "NEW_SELECTION", whereClause)
    # [NEWDENSITY] = [NEW_POP] / dasyAreaField
    arcpy.CalculateField_management(outWorkTableView, "NEWDENSITY", "!NEW_POP! / !" + dasyAreaField + "!", 'PYTHON')

    # Lastly create an official output statistics table
    AddPrintMessage("Creating a final summary table",0)
    finalSummaryTable, finalSummaryTableName = NameCheck("FinalSummaryTable",tableSuffix)
    arcpy.Statistics_analysis(outWorkTable, finalSummaryTable, "NEW_POP SUM; NEWDENSITY MEAN; NEWDENSITY MIN; NEWDENSITY MAX; NEWDENSITY STD", ancCatName)

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
