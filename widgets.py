#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Grant Drake <grant.drake@gmail.com> ; 2020, un_pogaz <un.pogaz@gmail.com>'
__docformat__ = 'restructuredtext en'


# python3 compatibility
from six.moves import range
from six import text_type as unicode
from polyglot.builtins import iteritems, itervalues

try:
    load_translations()
except NameError:
    pass # load_translations() added in calibre 1.9

from collections import defaultdict, OrderedDict
from functools import partial

try:
    from qt.core import (
        Qt, QComboBox, QDateTime, QDialog, QFont, QFont, QHBoxLayout, QLabel, QLineEdit,
        QStyledItemDelegate, QTableWidgetItem, pyqtSignal,
    )
except ImportError:
    from PyQt5.Qt import (
        Qt, QComboBox, QDateTime, QDialog, QFont, QFont, QHBoxLayout, QLabel, QLineEdit,
        QStyledItemDelegate, QTableWidgetItem, pyqtSignal,
    )

from calibre.gui2 import error_dialog, UNDEFINED_QDATETIME
from calibre.utils.date import now, format_date, UNDEFINED_DATE
from calibre.gui2.library.delegates import DateDelegate as _DateDelegate

from . import debug_print, get_icon, get_pixmap, get_date_format


# ----------------------------------------------
#               Widgets
# ----------------------------------------------

class ImageTitleLayout(QHBoxLayout):
    """
    A reusable layout widget displaying an image followed by a title
    """
    def __init__(self, parent, icon_name, title):
        QHBoxLayout.__init__(self)
        self.title_image_label = QLabel(parent)
        self.update_title_icon(icon_name)
        self.addWidget(self.title_image_label)
        
        title_font = QFont()
        title_font.setPointSize(16)
        shelf_label = QLabel(title, parent)
        shelf_label.setFont(title_font)
        self.addWidget(shelf_label)
        self.insertStretch(-1)
    
    def update_title_icon(self, icon_name):
        pixmap = get_pixmap(icon_name)
        if pixmap is None:
            error_dialog(self.parent(), _('Restart required'),
                         _('Title image not found - you must restart Calibre before using this plugin!'), show=True)
        else:
            self.title_image_label.setPixmap(pixmap)
        self.title_image_label.setMaximumSize(32, 32)
        self.title_image_label.setScaledContents(True)

class CheckableTableWidgetItem(QTableWidgetItem):
    """
    For use in a table cell, displays a checkbox that can potentially be tristate
    """
    def __init__(self, checked=False, is_tristate=False):
        QTableWidgetItem.__init__(self, '')
        self.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled )
        if is_tristate:
            self.setFlags(self.flags() | Qt.ItemFlag.ItemIsUserTristate)
        if checked:
            self.setCheckState(Qt.Checked)
        else:
            if is_tristate and checked is None:
                self.setCheckState(Qt.CheckState.PartiallyChecked)
            else:
                self.setCheckState(Qt.CheckState.Unchecked)
    
    def get_boolean_value(self):
        """
        Return a boolean value indicating whether checkbox is checked
        If this is a tristate checkbox, a partially checked value is returned as None
        """
        if self.checkState() == Qt.PartiallyChecked:
            return None
        else:
            return self.checkState() == Qt.Checked

class DateDelegate(_DateDelegate):
    """
    Delegate for dates. Because this delegate stores the
    format as an instance variable, a new instance must be created for each
    column. This differs from all the other delegates.
    """
    def __init__(self, parent, fmt='dd MMM yyyy', default_to_today=True):
        DateDelegate.__init__(self, parent)
        self.format = get_date_format(default_fmt=fmt)
        self.default_to_today = default_to_today
        debug_print('DateDelegate fmt:',fmt)

    def createEditor(self, parent, option, index):
        qde = QStyledItemDelegate.createEditor(self, parent, option, index)
        qde.setDisplayFormat(self.format)
        qde.setMinimumDateTime(UNDEFINED_QDATETIME)
        qde.setSpecialValueText(_('Undefined'))
        qde.setCalendarPopup(True)
        return qde

    def setEditorData(self, editor, index):
        val = index.model().data(index, Qt.DisplayRole)
        debug_print('setEditorData val:',val)
        if val is None or val == UNDEFINED_QDATETIME:
            if self.default_to_today:
                val = self.default_date
            else:
                val = UNDEFINED_QDATETIME
        editor.setDateTime(val)

    def setModelData(self, editor, model, index):
        val = editor.dateTime()
        debug_print('setModelData: ',val)
        if val <= UNDEFINED_QDATETIME:
            model.setData(index, UNDEFINED_QDATETIME, Qt.EditRole)
        else:
            model.setData(index, QDateTime(val), Qt.EditRole)

class DateTableWidgetItem(QTableWidgetItem):
    def __init__(self, date_read, is_read_only=False, default_to_today=False, fmt=None):
        if date_read is None or date_read == UNDEFINED_DATE and default_to_today:
            date_read = now()
        if is_read_only:
            QTableWidgetItem.__init__(self, format_date(date_read, fmt))
            self.setFlags(Qt.ItemIsSelectable|Qt.ItemIsEnabled)
            self.setData(Qt.DisplayRole, QDateTime(date_read))
        else:
            QTableWidgetItem.__init__(self, '')
            self.setData(Qt.DisplayRole, QDateTime(date_read))

class RatingTableWidgetItem(QTableWidgetItem):
    def __init__(self, rating, is_read_only=False):
        QTableWidgetItem.__init__(self, '')
        self.setData(Qt.DisplayRole, rating)
        if is_read_only:
            self.setFlags(Qt.ItemIsSelectable|Qt.ItemIsEnabled)

class TextIconWidgetItem(QTableWidgetItem):
    def __init__(self, text, icon, tooltip=None, is_read_only=False):
        QTableWidgetItem.__init__(self, text)
        if icon: self.setIcon(icon)
        if tooltip: self.setToolTip(tooltip)
        if is_read_only: self.setFlags(Qt.ItemIsSelectable|Qt.ItemIsEnabled)

class ReadOnlyTableWidgetItem(QTableWidgetItem):
    """
    For use in a table cell, displays text the user cannot select or modify.
    """
    def __init__(self, text):
        text = text or ''
        QTableWidgetItem.__init__(self, text)
        self.setFlags(Qt.ItemIsSelectable|Qt.ItemIsEnabled)

class ReadOnlyCheckableTableWidgetItem(ReadOnlyTableWidgetItem):
    '''
    For use in a table cell, displays a checkbox next to some text the user cannot select or modify.
    '''
    def __init__(self, text, checked=False, is_tristate=False):
        ReadOnlyTableWidgetItem.__init__(self, text)
        try: # For Qt Backwards compatibility.
            self.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled )
        except:
            self.setFlags(Qt.ItemFlags(Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled ))
        if is_tristate:
            self.setFlags(self.flags() | Qt.ItemIsTristate)
        if checked:
            self.setCheckState(Qt.Checked)
        else:
            if is_tristate and checked is None:
                self.setCheckState(Qt.PartiallyChecked)
            else:
                self.setCheckState(Qt.Unchecked)

    def get_boolean_value(self):
        '''
        Return a boolean value indicating whether checkbox is checked
        If this is a tristate checkbox, a partially checked value is returned as None
        '''
        if self.checkState() == Qt.PartiallyChecked:
            return None
        else:
            return self.checkState() == Qt.Checked

class ReadOnlyTextIconWidgetItem(ReadOnlyTableWidgetItem):
    """
    For use in a table cell, displays an icon the user cannot select or modify.
    """
    def __init__(self, text, icon):
        ReadOnlyTableWidgetItem.__init__(self, text)
        if icon: self.setIcon(icon)


# ----------------------------------------------
#               Controls
# ----------------------------------------------

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
    
    COMBO_IMAGE_ADD = _('Add New Image...')
    
    new_image_added = pyqtSignal(str)
    
    def __init__(self, image_map, selected_image_name=None):
        NoWheelComboBox.__init__(self)
        self.populate_combo(image_map, selected_image_name=selected_image_name)
        self.currentIndexChanged.connect(self.index_changed)
    
    def populate_combo(self, image_map, selected_image_name=None):
        self.clear()
        self.image_map = image_map or {}
        
        image_names = sorted(image_map.keys())
        # Add a blank item at the beginning of the list, and a blank then special 'Add" item at end
        image_names.insert(0, '')
        image_names.append('')
        image_names.append(ImageComboBox.COMBO_IMAGE_ADD)
        
        for i, image in enumerate(image_names, 0):
            self.insertItem(i, image_map.get(image, image), image)
        idx = self.findText(selected_image_name or '')
        self.setCurrentIndex(idx)
        self.setItemData(0, idx)
    
    def index_changed(self, idx):
        if self.currentText() == ImageComboBox.COMBO_IMAGE_ADD:
            self.blockSignals(True)
            # Special item in the combo for choosing a new image to add to Calibre
            from .dialogs import ImageDialog
            d = ImageDialog(existing_images=self.image_map.keys())
            
            if d.exec():
                self.image_map[d.image_name] = get_icon(d.image_name)
                self.populate_combo(self.image_map, self.currentText())
                # Select the newly added item
                idx = self.findText(d.image_name)
            else:
                # User cancelled the add operation or an error - set to previous idx value
                idx = self.itemData(0)
            self.setCurrentIndex(idx)
            self.blockSignals(False)
            
            if d.result():
                # Now, emit the event than user has added a new image so we need to repopulate every combo with new sorted list
                self.new_image_added.emit(d.image_name)
            
        # Store the current index as item data in index 0 in case user cancels dialog in future
        self.setItemData(0, self.currentIndex())


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
