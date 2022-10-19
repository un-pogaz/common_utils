#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Grant Drake <grant.drake@gmail.com> ; 2020, un_pogaz <un.pogaz@gmail.com>'
__docformat__ = 'restructuredtext en'

import os, sys, copy, time
# python3 compatibility
from six.moves import range
from six import text_type as unicode

try:
    load_translations()
except NameError:
    pass # load_translations() added in calibre 1.9

from datetime import datetime
from collections import defaultdict, OrderedDict
from functools import partial

try: #polyglot added in calibre 4.0
    from polyglot.builtins import iteritems, itervalues
except ImportError:
    def iteritems(d):
        return d.iteritems()
    def itervalues(d):
        return d.itervalues()

from calibre import prints
from calibre.constants import DEBUG, numeric_version as calibre_version
from calibre.gui2.ui import get_gui

GUI = get_gui()


# ----------------------------------------------
#               Controls
# ----------------------------------------------
def __Controls__(): pass

class ReadOnlyLineEdit(QLineEdit):
    def __init__(self, text, parent):
        text = text or ''
        QLineEdit.__init__(self, text, parent)
        self.setEnabled(False)

class NoWheelComboBox(QComboBox):
    """
    For combobox displayed in a table cell using the mouse wheel has nasty interactions
    due to the conflict between scrolling the table vs scrolling the combobox item.
    Inherit from this class to disable the combobox changing value with mouse wheel.
    """
    def wheelEvent(self, event):
        event.ignore()

class ImageComboBox(NoWheelComboBox):
    def __init__(self, parent, image_map, selected_text):
        NoWheelComboBox.__init__(self, parent)
        self.populate_combo(image_map, selected_text)
    
    def populate_combo(self, image_map, selected_text):
        self.clear()
        for i, image in enumerate(get_image_names(image_map), 0):
            self.insertItem(i, image_map.get(image, image), image)
        idx = self.findText(selected_text)
        self.setCurrentIndex(idx)
        self.setItemData(0, idx)

class ListComboBox(QComboBox):
    def __init__(self, parent, values, selected_value=None):
        QComboBox.__init__(self, parent)
        self.values = values
        if selected_value is not None:
            self.populate_combo(selected_value)
    
    def populate_combo(self, selected_value):
        self.clear()
        selected_idx = idx = -1
        for value in self.values:
            idx = idx + 1
            self.addItem(value)
            if value == selected_value:
                selected_idx = idx
        self.setCurrentIndex(selected_idx)
    
    def selected_value(self):
        return unicode(self.currentText())

class KeyValueComboBox(QComboBox):
    def __init__(self, parent, values, selected_key=None, values_ToolTip={}):
        QComboBox.__init__(self, parent)
        self.populate_combo(values, selected_key, values_ToolTip)
        self.refresh_ToolTip()
        self.currentIndexChanged.connect(self.key_value_changed)
    
    def populate_combo(self, values, selected_key=None, values_ToolTip={}):
        self.clear()
        self.values_ToolTip = values_ToolTip
        self.values = values
        
        selected_idx = start = 0
        for idx, (key, value) in enumerate(iteritems(self.values), start):
            self.addItem(value)
            if key == selected_key:
                selected_idx = idx
        
        self.setCurrentIndex(selected_idx)
    
    def selected_key(self):
        currentText = unicode(self.currentText()).strip()
        for key, value in iteritems(self.values):
            if value == currentText:
                return key
    
    def key_value_changed(self, val):
        self.refresh_ToolTip()
    
    def refresh_ToolTip(self):
        if self.values_ToolTip:
            self.setToolTip(self.values_ToolTip.get(self.selected_key(), ''))

class CustomColumnComboBox(QComboBox):
    def __init__(self, parent, custom_columns, selected_column='', initial_items=['']):
        QComboBox.__init__(self, parent)
        self.populate_combo(custom_columns, selected_column, initial_items)
        self.refresh_ToolTip()
        self.currentTextChanged.connect(self.current_text_changed)
    
    def populate_combo(self, custom_columns, selected_column='', initial_items=['']):
        self.clear()
        self.custom_columns = custom_columns
        self.column_names = []
        initial_items = initial_items or []
        
        selected_idx = start = 0
        for start, init in enumerate(initial_items, 1):
            self.column_names.append(init)
            self.addItem(init)
        
        for idx, (key, value) in enumerate(iteritems(self.custom_columns), start):
            self.column_names.append(key)
            self.addItem('{:s} ({:s})'.format(key, value.display_name))
            if key == selected_column:
                selected_idx = idx
        
        self.setCurrentIndex(selected_idx)
    
    def refresh_ToolTip(self):
        cc = self.custom_columns.get(self.get_selected_column(), None)
        if cc:
            self.setToolTip(cc.description)
        else:
            self.setToolTip('')
    
    def get_selected_column(self):
        return self.column_names[self.currentIndex()]
    
    def current_text_changed(self, new_text):
        self.refresh_ToolTip()
        self.current_index = self.currentIndex()

class ReorderedComboBox(QComboBox):
    def __init__(self, parent, strip_items=True):
        QComboBox.__init__(self, parent)
        self.strip_items = strip_items
        self.setEditable(True)
        self.setMaxCount(10)
        self.setInsertPolicy(QComboBox.InsertAtTop)
    
    def populate_items(self, items, sel_item):
        self.blockSignals(True)
        self.clear()
        self.clearEditText()
        for text in items:
            if text != sel_item:
                self.addItem(text)
        if sel_item:
            self.insertItem(0, sel_item)
            self.setCurrentIndex(0)
        else:
            self.setEditText('')
        self.blockSignals(False)
    
    def reorder_items(self):
        self.blockSignals(True)
        text = unicode(self.currentText())
        if self.strip_items:
            text = text.strip()
        if not text.strip():
            return
        existing_index = self.findText(text, Qt.MatchExactly)
        if existing_index:
            self.removeItem(existing_index)
            self.insertItem(0, text)
            self.setCurrentIndex(0)
        self.blockSignals(False)
    
    def get_items_list(self):
        if self.strip_items:
            return [unicode(self.itemText(i)).strip() for i in range(0, self.count())]
        else:
            return [unicode(self.itemText(i)) for i in range(0, self.count())]

class DragDropLineEdit(QLineEdit):
    """
    Unfortunately there is a flaw in the Qt implementation which means that
    when the QComboBox is in editable mode that dropEvent is not fired
    if you drag into the editable text area. Working around this by having
    a custom LineEdit() set for the parent combobox.
    """
    def __init__(self, parent, drop_mode):
        QLineEdit.__init__(self, parent)
        self.drop_mode = drop_mode
        self.setAcceptDrops(True)
    
    def dragMoveEvent(self, event):
        event.acceptProposedAction()
    
    def dragEnterEvent(self, event):
        if int(event.possibleActions() & Qt.CopyAction) + \
           int(event.possibleActions() & Qt.MoveAction) == 0:
            return
        data = self._get_data_from_event(event)
        if data:
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        data = self._get_data_from_event(event)
        event.setDropAction(Qt.CopyAction)
        self.setText(data[0])
    
    def _get_data_from_event(self, event):
        md = event.mimeData()
        if self.drop_mode == 'file':
            urls, filenames = dnd_get_files(md, ['csv', 'txt'])
            if not urls:
                # Nothing found
                return
            if not filenames:
                # Local files
                return urls
            else:
                # Remote files
                return filenames
        if event.mimeData().hasFormat('text/uri-list'):
            urls = [unicode(u.toString()).strip() for u in md.urls()]
            return urls

class DragDropComboBox(ReorderedComboBox):
    """
    Unfortunately there is a flaw in the Qt implementation which means that
    when the QComboBox is in editable mode that dropEvent is not fired
    if you drag into the editable text area. Working around this by having
    a custom LineEdit() set for the parent combobox.
    """
    def __init__(self, parent, drop_mode='url'):
        ReorderedComboBox.__init__(self, parent)
        self.drop_line_edit = DragDropLineEdit(parent, drop_mode)
        self.setLineEdit(self.drop_line_edit)
        self.setAcceptDrops(True)
        self.setEditable(True)
        self.setMaxCount(10)
        self.setInsertPolicy(QComboBox.InsertAtTop)
    
    def dragMoveEvent(self, event):
        self.lineEdit().dragMoveEvent(event)
    
    def dragEnterEvent(self, event):
        self.lineEdit().dragEnterEvent(event)
    
    def dropEvent(self, event):
        self.lineEdit().dropEvent(event)
