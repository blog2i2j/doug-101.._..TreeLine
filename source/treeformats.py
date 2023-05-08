#!/usr/bin/env python3

#******************************************************************************
# treeformats.py, provides a class to store node format types and info
#
# TreeLine, an information storage program
# Copyright (C) 2023, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY.  See the included LICENSE file for details.
#******************************************************************************

import operator
import copy
import xml.sax.saxutils
import nodeformat
import matheval
import conditional
import treenode
import treestructure


defaultTypeName = _('DEFAULT')
_showConfRootTypeName = _('FILE')
_showConfTypeTypeName = _('TYPE')
_showConfTypeTitleFieldName = _('TitleFormat')
_showConfTypeOutputFieldName = _('OutputFormat')
_showConfTypeSpaceFieldName = _('SpaceBetween')
_showConfTypeHtmlFieldName = _('FormatHtml')
_showConfTypeBulletsFieldName = _('Bullets')
_showConfTypeTableFieldName = _('Table')
_showConfTypeChildFieldName = _('ChildType')
_showConfTypeIconFieldName = _('Icon')
_showConfTypeGenericFieldName = _('GenericType')
_showConfTypeConditionFieldName = _('ConditionalRule')
_showConfTypeSeparatorFieldName = _('ListSeparator')
_showConfTypeChildLimitFieldName = _('ChildTypeLimit')
_showConfFieldTypeName = _('FIELD')
_showConfFieldTypeFieldName = _('FieldType')
_showConfFieldFormatFieldName = _('Format')
_showConfFieldPrefixFieldName = _('Prefix')
_showConfFieldSuffixFieldName = _('Suffix')
_showConfFieldInitFieldName = _('InitialValue')
_showConfFieldLinesFieldName = _('NumLines')
_showConfFieldSortKeyFieldName = _('SortKeyNum')
_showConfFieldSortDirFieldName = _('SortForward')
_showConfFieldEvalHtmlFieldName = _('EvalHtml')

class TreeFormats(dict):
    """Class to store node format types and info.

    Stores node formats by format name in a dictionary.
    Provides methods to change and update format data.
    """
    def __init__(self, formatList=None, setDefault=False):
        """Initialize the format storage.

        Arguments:
            formatList -- the list of formats' file info
            setDefault - if true, initializes with a default format
        """
        super().__init__()
        # new names for types renamed in the config dialog (orig names as keys)
        self.typeRenameDict = {}
        # nested dict for fields renamed, keys are type name then orig field
        self.fieldRenameDict = {}
        self.conditionalTypes = set()
        # set of math field names with deleted equations, keys are type names
        self.emptiedMathDict = {}
        self.mathFieldRefDict = {}
        # list of math eval levels, each is a dict by type name with lists of
        # equation fields
        self.mathLevelList = []
        # for saving all-type find/filter conditionals
        self.savedConditionText = {}
        # used by copied configs in config dialog
        self.configModified = False
        self.fileInfoFormat = nodeformat.FileInfoFormat(self)
        if formatList:
            for formatData in formatList:
                name = formatData['formatname']
                self[name] = nodeformat.NodeFormat(name, self, formatData)
            self.updateDerivedRefs()
            try:
                self.updateMathFieldRefs()
            except matheval.CircularMathError:
                # can see if types with math fields were copied from a 2nd file
                # handle the exception to avoid failure at file open
                print('Warning - Circular math fields detected')
        if nodeformat.FileInfoFormat.typeName in self:
            self.fileInfoFormat.duplicateFileInfo(self[nodeformat.
                                                       FileInfoFormat.
                                                       typeName])
            del self[nodeformat.FileInfoFormat.typeName]
        if setDefault:
            self[defaultTypeName] = nodeformat.NodeFormat(defaultTypeName,
                                                          self,
                                                          addDefaultField=True)

    def storeFormats(self):
        """Return a list of formats stored in JSON data.
        """
        formats = list(self.values())
        if self.fileInfoFormat.fieldFormatModified:
            formats.append(self.fileInfoFormat)
        return sorted([nodeFormat.storeFormat() for nodeFormat in formats],
                      key=operator.itemgetter('formatname'))

    def loadGlobalSavedConditions(self, propertyDict):
        """Load all-type saved conditionals from property dict.

        Arguments:
            propertyDict -- a JSON property dict
        """
        for key in propertyDict.keys():
            if key.startswith('glob-cond-'):
                self.savedConditionText[key[10:]] = propertyDict[key]

    def storeGlobalSavedConditions(self, propertyDict):
        """Save all-type saved conditionals to property dict.

        Arguments:
            propertyDict -- a JSON property dict
        """
        for key, text in self.savedConditionText.items():
            propertyDict['glob-cond-' + key] = text
        return propertyDict

    def copySettings(self, sourceFormats):
        """Copy all settings from other type formats to these formats.

        Copy any new formats and delete any missing formats.
        Arguments:
            sourceFormats -- the type formats to copy
        """
        if sourceFormats.typeRenameDict:
            for oldName, newName in sourceFormats.typeRenameDict.items():
                try:
                    self[oldName].name = newName
                except KeyError:
                    pass    # skip if new type is renamed
            formats = list(self.values())
            self.clear()
            for nodeFormat in formats:
                self[nodeFormat.name] = nodeFormat
            sourceFormats.typeRenameDict = {}
        for name in list(self.keys()):
            if name in sourceFormats:
                self[name].copySettings(sourceFormats[name])
            else:
                del self[name]
        for name in sourceFormats.keys():
            if name not in self:
                self[name] = copy.deepcopy(sourceFormats[name])
        if (sourceFormats.fileInfoFormat.fieldFormatModified or
            self.fileInfoFormat.fieldFormatModified):
            self.fileInfoFormat.duplicateFileInfo(sourceFormats.fileInfoFormat)

    def typeNames(self):
        """Return a sorted list of type names.
        """
        return sorted(list(self.keys()))

    def updateLineParsing(self):
        """Update the fields parsed in the output lines for each format type.
        """
        for typeFormat in self.values():
            typeFormat.updateLineParsing()

    def addTypeIfMissing(self, typeFormat):
        """Add format to available types if not a duplicate.

        Arguments:
            typeFormat -- the node format to add
        """
        self.setdefault(typeFormat.name, typeFormat)

    def fieldNameDict(self):
        """Return a dictionary of field name sets using type names as keys.
        """
        result = {}
        for typeFormat in self.values():
            result[typeFormat.name] = set(typeFormat.fieldNames())
        return result

    def updateDerivedRefs(self):
        """Update derived type lists (in generics) & the conditional type set.
        """
        self.conditionalTypes = set()
        for typeFormat in self.values():
            typeFormat.derivedTypes = []
            if typeFormat.conditional:
                self.conditionalTypes.add(typeFormat)
                if typeFormat.genericType:
                    self.conditionalTypes.add(self[typeFormat.genericType])
        for typeFormat in self.values():
            if typeFormat.genericType:
                genericType = self[typeFormat.genericType]
                genericType.derivedTypes.append(typeFormat)
                if genericType in self.conditionalTypes:
                    self.conditionalTypes.add(typeFormat)
        for typeFormat in self.values():
            if not typeFormat.genericType and not typeFormat.derivedTypes:
                typeFormat.conditional = None
                self.conditionalTypes.discard(typeFormat)

    def updateMathFieldRefs(self):
        """Update refs used to cycle thru math field evaluations.
        """
        self.mathFieldRefDict = {}
        allRecursiveRefs = []
        recursiveRefDict = {}
        matheval.RecursiveEqnRef.recursiveRefDict = recursiveRefDict
        for typeFormat in self.values():
            for field in typeFormat.fields():
                if field.typeName == 'Math' and field.equation:
                    recursiveRef = matheval.RecursiveEqnRef(typeFormat.name,
                                                            field)
                    allRecursiveRefs.append(recursiveRef)
                    recursiveRefDict.setdefault(field.name,
                                                []).append(recursiveRef)
                    for fieldRef in field.equation.fieldRefs:
                        fieldRef.eqnNodeTypeName = typeFormat.name
                        fieldRef.eqnFieldName = field.name
                        self.mathFieldRefDict.setdefault(fieldRef.fieldName,
                                                         []).append(fieldRef)
        if not allRecursiveRefs:
            return
        for ref in allRecursiveRefs:
            ref.setPriorities()
        allRecursiveRefs.sort()
        self.mathLevelList = [{allRecursiveRefs[0].eqnTypeName:
                               [allRecursiveRefs[0]]}]
        for prevRef, currRef in zip(allRecursiveRefs, allRecursiveRefs[1:]):
            if currRef.evalSequence == prevRef.evalSequence:
                if prevRef.evalDirection == matheval.EvalDir.optional:
                    prevRef.evalDirection = currRef.evalDirection
                elif currRef.evalDirection == matheval.EvalDir.optional:
                    currRef.evalDirection = prevRef.evalDirection
                if currRef.evalDirection != prevRef.evalDirection:
                    self.mathLevelList.append({})
            else:
                self.mathLevelList.append({})
            self.mathLevelList[-1].setdefault(currRef.eqnTypeName,
                                              []).append(currRef)

    def numberingFieldDict(self):
        """Return a dict of numbering field names by node format name.
        """
        result = {}
        for typeFormat in self.values():
            numberingFields = typeFormat.numberingFieldList()
            if numberingFields:
                result[typeFormat.name] = numberingFields
        return result

    def commonFields(self, nodes):
        """Return a list of field names common to all given node formats.

        Retains the field sequence from one of the types.
        Arguments:
            nodes -- the nodes to check for common fields
        """
        formats = set()
        for node in nodes:
            formats.add(node.formatRef.name)
        firstFields = self[formats.pop()].fieldNames()
        commonFields = set(firstFields)
        for formatName in formats:
            commonFields.intersection_update(self[formatName].fieldNames())
        return [field for field in firstFields if field in commonFields]

    def savedConditions(self):
        """Return a dictionary with saved Conditonals from all type formats.
        """
        savedConditions = {}
        # all-type conditions
        for name, text in self.savedConditionText.items():
            cond = conditional.Conditional(text)
            savedConditions[name] = cond
        # specific type conditions
        for typeFormat in self.values():
            for name, text in typeFormat.savedConditionText.items():
                cond = conditional.Conditional(text, typeFormat.name)
                savedConditions[name] = cond
        return savedConditions

    def visualConfigStructure(self, fileName):
        """Export a TreeLine structure containing the config types and fields.

        Returns the structure.
        Arguments:
            fileName -- the name for the root node
        """
        structure = treestructure.TreeStructure()
        structure.treeFormats = TreeFormats()
        rootFormat = nodeformat.NodeFormat(_showConfRootTypeName,
                                           structure.treeFormats,
                                           addDefaultField=True)
        structure.treeFormats[rootFormat.name] = rootFormat
        typeFormat = nodeformat.NodeFormat(_showConfTypeTypeName,
                                           structure.treeFormats,
                                           addDefaultField=True)
        typeFormat.addField(_showConfTypeTitleFieldName)
        typeFormat.addField(_showConfTypeOutputFieldName)
        typeFormat.addField(_showConfTypeSpaceFieldName,
                            {'fieldtype': 'Boolean'})
        typeFormat.addField(_showConfTypeHtmlFieldName,
                            {'fieldtype': 'Boolean'})
        typeFormat.addField(_showConfTypeBulletsFieldName,
                            {'fieldtype': 'Boolean'})
        typeFormat.addField(_showConfTypeTableFieldName,
                            {'fieldtype': 'Boolean'})
        typeFormat.addField(_showConfTypeChildFieldName)
        typeFormat.addField(_showConfTypeIconFieldName)
        typeFormat.addField(_showConfTypeGenericFieldName)
        typeFormat.addField(_showConfTypeConditionFieldName)
        typeFormat.addField(_showConfTypeSeparatorFieldName)
        typeFormat.addField(_showConfTypeChildLimitFieldName)
        structure.treeFormats[typeFormat.name] = typeFormat
        fieldFormat = nodeformat.NodeFormat(_showConfFieldTypeName,
                                            structure.treeFormats,
                                            addDefaultField=True)
        fieldFormat.addField(_showConfFieldTypeFieldName)
        fieldFormat.addField(_showConfFieldFormatFieldName)
        fieldFormat.addField(_showConfFieldPrefixFieldName)
        fieldFormat.addField(_showConfFieldSuffixFieldName)
        fieldFormat.addField(_showConfFieldInitFieldName)
        fieldFormat.addField(_showConfFieldLinesFieldName,
                             {'fieldtype': 'Number'})
        fieldFormat.addField(_showConfFieldSortKeyFieldName,
                             {'fieldtype': 'Number'})
        fieldFormat.addField(_showConfFieldSortDirFieldName,
                             {'fieldtype': 'Boolean'})
        fieldFormat.addField(_showConfFieldEvalHtmlFieldName,
                             {'fieldtype': 'Boolean'})
        line = '{{*{0}*}} ({{*{1}*}})'.format(nodeformat.defaultFieldName,
                                              _showConfFieldTypeFieldName)
        fieldFormat.changeTitleLine(line)
        fieldFormat.changeOutputLines([line])
        structure.treeFormats[fieldFormat.name] = fieldFormat
        rootNode = treenode.TreeNode(rootFormat)
        structure.childList.append(rootNode)
        structure.addNodeDictRef(rootNode)
        rootNode.data[nodeformat.defaultFieldName] = fileName
        for typeName in self.typeNames():
            typeNode = treenode.TreeNode(typeFormat)
            rootNode.childList.append(typeNode)
            structure.addNodeDictRef(typeNode)
            typeNode.data[nodeformat.defaultFieldName] = typeName
            titleLine = self[typeName].getTitleLine()
            outputList = self[typeName].getOutputLines()
            if self[typeName].formatHtml:
                titleLine = xml.sax.saxutils.escape(titleLine)
                outputList = [xml.sax.saxutils.escape(line) for line in
                              outputList]
            outputLines = '<br>\n'.join(outputList)
            typeNode.data[_showConfTypeTitleFieldName] = titleLine
            typeNode.data[_showConfTypeOutputFieldName] = outputLines
            spaceBetween = repr(self[typeName].spaceBetween)
            typeNode.data[_showConfTypeSpaceFieldName] = spaceBetween
            formatHtml = repr(self[typeName].formatHtml)
            typeNode.data[_showConfTypeHtmlFieldName] = formatHtml
            useBullets = repr(self[typeName].useBullets)
            typeNode.data[_showConfTypeBulletsFieldName] = useBullets
            useTables = repr(self[typeName].useTables)
            typeNode.data[_showConfTypeTableFieldName] = useTables
            typeNode.data[_showConfTypeChildFieldName] = (self[typeName].
                                                          childType)
            typeNode.data[_showConfTypeIconFieldName] = (self[typeName].
                                                         iconName)
            typeNode.data[_showConfTypeGenericFieldName] = (self[typeName].
                                                            genericType)
            if self[typeName].conditional:
                condition = self[typeName].conditional.conditionStr()
                typeNode.data[_showConfTypeConditionFieldName] = condition
            separator = self[typeName].outputSeparator
            typeNode.data[_showConfTypeSeparatorFieldName] = separator
            childLimit = ','.join(sorted(list(self[typeName].childTypeLimit)))
            typeNode.data[_showConfTypeChildLimitFieldName] = childLimit
            fieldSortKeyDict = {}
            fieldSortSet = False
            for field in self[typeName].fields():
                fieldSortKeyDict[field.name] = repr(field.sortKeyNum)
                if field.sortKeyNum != 0:
                    fieldSortSet = True
            if not fieldSortSet:
                sortField = list(self[typeName].fields())[0]
                fieldSortKeyDict[sortField.name] = repr(1)
            for field in self[typeName].fields():
                fieldNode = treenode.TreeNode(fieldFormat)
                typeNode.childList.append(fieldNode)
                structure.addNodeDictRef(fieldNode)
                fieldNode.data[nodeformat.defaultFieldName] = field.name
                fieldNode.data[_showConfFieldTypeFieldName] = field.typeName
                fieldNode.data[_showConfFieldFormatFieldName] = field.format
                fieldNode.data[_showConfFieldPrefixFieldName] = field.prefix
                fieldNode.data[_showConfFieldSuffixFieldName] = field.suffix
                fieldNode.data[_showConfFieldInitFieldName] = field.initDefault
                numLines = repr(field.numLines)
                fieldNode.data[_showConfFieldLinesFieldName] = numLines
                sortKeyNum = fieldSortKeyDict[field.name]
                fieldNode.data[_showConfFieldSortKeyFieldName] = sortKeyNum
                sortKeyFwd = repr(field.sortKeyForward)
                fieldNode.data[_showConfFieldSortDirFieldName] = sortKeyFwd
                evalHtml = repr(field.evalHtml)
                fieldNode.data[_showConfFieldEvalHtmlFieldName] = evalHtml
        structure.generateSpots(None)
        return structure
