#!/usr/bin/env python3

#******************************************************************************
# treeview.py, provides a class for the indented tree view
#
# TreeLine, an information storage program
# Copyright (C) 2017, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
#******************************************************************************

from PyQt5.QtCore import QPoint, Qt, pyqtSignal
from PyQt5.QtWidgets import (QAbstractItemView, QHeaderView, QTreeView)
import treeselection
import treenode
import globalref


class TreeView(QTreeView):
    """Class override for the indented tree view.

    Sets view defaults and links with document for content.
    """
    skippedMouseSelect = pyqtSignal(treenode.TreeNode)
    def __init__(self, model, allActions, parent=None):
        """Initialize the tree view.

        Arguments:
            model -- the initial model for view data
            allActions -- a dictionary of control actions for popup menus
            parent -- the parent main window
        """
        super().__init__(parent)
        self.resetModel(model)
        self.allActions = allActions
        self.noMouseSelectMode = False
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.header().setStretchLastSection(False)
        self.setHeaderHidden(True)
        self.updateTreeGenOptions()
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDropIndicatorShown(True)
        self.setUniformRowHeights(True)

    def resetModel(self, model):
        """Change the model assigned to this view.

        Also assigns a new selection model.
        Arguments:
            model -- the new model to assign
        """
        self.setModel(model)
        self.setSelectionModel(treeselection.TreeSelection(model, self))

    def updateTreeGenOptions(self):
        """Set the tree to match the current general options.
        """
        if globalref.genOptions['ClickRename']:
            self.setEditTriggers(QAbstractItemView.SelectedClicked)
        else:
            self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        dragAvail = globalref.genOptions['DragTree']
        self.setDragEnabled(dragAvail)
        self.setAcceptDrops(dragAvail)
        self.setIndentation(globalref.genOptions['IndentOffset'] *
                            self.fontInfo().pixelSize())

    def expandSpot(self, spot):
        """Expand a spot in this view.
        """
        self.expand(spot.index(self.model()))

    def collapseSpot(self, spot):
        """Collapse a spot in this view.
        """
        self.collapse(spot.index(self.model()))

    def expandBranch(self, parentSpot):
        """Expand all spots in the given branch.

        Arguments:
            parentSpot -- the top spot in the branch
        """
        for spot in parentSpot.spotDescendantGen():
            if spot.nodeRef.childList:
                self.expand(spot.index(self.model()))

    def collapseBranch(self, parentSpot):
        """Collapse all spots in the given branch.

        Arguments:
            parentSpot -- the top spot in the branch
        """
        for spot in parentSpot.spotDescendantGen():
            if spot.nodeRef.childList:
                self.collapse(spot.index(self.model()))

    def endEditing(self):
        """Stop the editing of any item being renamed.
        """
        self.closePersistentEditor(self.selectionModel().currentIndex())

    def toggleNoMouseSelectMode(self, active=True):
        """Set noMouseSelectMode to active or inactive.

        noMouseSelectMode will not change selection on mouse click,
        it will just signal the clicked node for use in links, etc.
        Arguments:
            active -- if True, activate noMouseSelectMode
        """
        self.noMouseSelectMode = active

    def mousePressEvent(self, event):
        """Skip unselecting click on blank spaces and if in noMouseSelectMode.

        If in noMouseSelectMode, signal which node is under the mouse.
        Arguments:
            event -- the mouse click event
        """
        clickedSpot = self.indexAt(event.pos()).internalPointer()
        if self.noMouseSelectMode and clickedSpot:
            self.skippedMouseSelect.emit(clickedSpot.nodeRef)
            event.ignore()
            return
        super().mousePressEvent(event)

    def dropEvent(self, event):
        """Event handler for view drop actions.

        Selects parent node at destination.
        Arguments:
            event -- the drop event
        """
        clickedSpot = self.indexAt(event.pos()).internalPointer()
        if clickedSpot:
            # clear selection to avoid invalid select bug
            self.selectionModel().selectSpots([], False)
            super().dropEvent(event)
            self.selectionModel().selectSpots([clickedSpot], False)
            self.scheduleDelayedItemsLayout()  # reqd before expand
            self.expandSpot(clickedSpot)
        else:
            super().dropEvent(event)
            self.selectionModel().selectSpots([])
            self.scheduleDelayedItemsLayout()
        self.model().treeModified.emit(True)
