#!/usr/bin/env python
# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2011, Grant Drake <grant.drake@gmail.com> ; 2020, un_pogaz <un.pogaz@gmail.com>'
__docformat__ = 'restructuredtext en'


try:
    load_translations()
except NameError:
    pass # load_translations() added in calibre 1.9

from collections import defaultdict, OrderedDict
from functools import partial
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from qt.core import (
        Qt, QAbstractItemView, QComboBox, QDateTime, QFont, QFont, QHBoxLayout, QIcon, QLabel,
        QLineEdit, QStyledItemDelegate, QSize, QTableWidgetItem, QTreeWidget, QTreeWidgetItem,
        pyqtSignal,
    )
except ImportError:
    from PyQt5.Qt import (
        Qt, QAbstractItemView, QComboBox, QDateTime, QFont, QFont, QHBoxLayout, QIcon, QLabel,
        QLineEdit, QStyledItemDelegate, QSize, QTableWidgetItem, QTreeWidget, QTreeWidgetItem,
        pyqtSignal,
    )

from calibre.gui2 import error_dialog, UNDEFINED_QDATETIME
from calibre.gui2.dnd import dnd_get_files
from calibre.utils.date import now, datetime, format_date, UNDEFINED_DATE
from calibre.gui2.library.delegates import DateDelegate as _DateDelegate
from calibre.ebooks.metadata import rating_to_stars

from . import debug_print, get_icon, get_pixmap, get_date_format, return_line_long_text, current_db, GUI
from .librarys import get_category_icons_map, get_tags_browsable_fields
from .columns import get_all_identifiers, ColumnMetadata


# ----------------------------------------------
#               Widgets
# ----------------------------------------------

class ImageTitleLayout(QHBoxLayout):
    """
    A reusable layout widget displaying an image followed by a title
    """
    def __init__(self, icon_name: str, title: str, parent=None):
        QHBoxLayout.__init__(self, parent)
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
    def __init__(self, checked: bool=False, text: str='', is_tristate=False, is_read_only=False):
        QTableWidgetItem.__init__(self, text)
        self.is_read_only = is_read_only
        if is_read_only:
            self.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        else:
            self.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        
        if is_tristate:
            self.setFlags(self.flags() | Qt.ItemFlag.ItemIsUserTristate)
        if checked:
            self.setCheckState(Qt.Checked)
        else:
            if is_tristate and checked is None:
                self.setCheckState(Qt.CheckState.PartiallyChecked)
            else:
                self.setCheckState(Qt.CheckState.Unchecked)
    
    def get_boolean_value(self) -> bool:
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
    def __init__(self, fmt='dd MMM yyyy', default_to_today=True, parent=None):
        DateDelegate.__init__(self, parent)
        self.format = get_date_format(default_fmt=fmt)
        self.default_to_today = default_to_today
        self.parent = parent

    def createEditor(self, option, index, parent=None):
        parent = parent or self.parent or GUI
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
    def __init__(self, date_read: datetime, default_to_today=False, fmt=None, is_read_only=False):
        if date_read is None or date_read == UNDEFINED_DATE and default_to_today:
            date_read = now()
        self.is_read_only = is_read_only
        if is_read_only:
            QTableWidgetItem.__init__(self, format_date(date_read, fmt))
            self.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.setData(Qt.DisplayRole, QDateTime(date_read))
        else:
            QTableWidgetItem.__init__(self, '')
            self.setData(Qt.DisplayRole, QDateTime(date_read))

class RatingTableWidgetItem(QTableWidgetItem):
    def __init__(self, rating: int, is_read_only=False):
        QTableWidgetItem.__init__(self, '')
        self.setData(Qt.DisplayRole, rating)
        self.is_read_only = is_read_only
        if is_read_only: self.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

class TextIconWidgetItem(QTableWidgetItem):
    def __init__(self, text: str, icon_name: str, tooltip=None, is_read_only=False):
        QTableWidgetItem.__init__(self, text)
        self.setIcon(get_icon(icon_name))
        self.setToolTip(tooltip)
        self.is_read_only = is_read_only
        if is_read_only: self.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

class ReadOnlyTableWidgetItem(QTableWidgetItem):
    """
    For use in a table cell, displays text the user cannot select or modify.
    """
    def __init__(self, text: str):
        text = text or ''
        QTableWidgetItem.__init__(self, text)
        self.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)


class FieldsValueTreeWidget(QTreeWidget):
    def __init__(self, book_ids: List[int]=None, parent=None):
        'If book_ids is not None, display a entry that contain a subset of Notes for listed books'
        QTreeWidget.__init__(self, parent)
        
        self.setIconSize(QSize(20, 20))
        self.header().hide()
        self.setSelectionMode(QAbstractItemView.MultiSelection)
        self.itemChanged.connect(self.item_changed)
        
        self._dbAPI = current_db().new_api
        self._book_item = None
        self._separator_item = None
        
        self.populate_tree(book_ids=book_ids)
    
    def _build_content_map(self, book_ids: Union[List[int], None]):
        raise NotImplementedError()
    
    def populate_tree(self, book_ids: List[int]=None):
        
        self.content_map = content_map = self._build_content_map(None)
        self.book_ids = book_ids
        
        self._book_item = book_item = None
        self._separator_item = separator = None
        self.takeTopLevelItem(-1)
        
        fields_order = get_tags_browsable_fields()
        
        category_icons = get_category_icons_map()
        
        def create_tree_item(parent, text, data, icon):
            rslt = QTreeWidgetItem(parent)
            rslt.setText(0, text)
            rslt.setData(0, Qt.UserRole, data)
            rslt.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            rslt.setCheckState(0, Qt.Unchecked)
            rslt.setIcon(0, icon)
            return rslt
        
        def create_root_item(parent, field, items):
            icon = category_icons[field]
            name = self._dbAPI.field_metadata[field]['name']
            root = create_tree_item(parent, f'{name} ({field})', field, icon)
            
            for data in items:
                if self._dbAPI.field_metadata[field]['datatype'] == 'rating':
                    text = rating_to_stars(data[0], allow_half_stars=True)
                else:
                    text = data[0]
                
                ch = create_tree_item(root, text, data, icon)
                root.addChild(ch)
            
            root.sortChildren(0, Qt.AscendingOrder)
            return root
        
        if not content_map:
            self._separator_item = separator = QTreeWidgetItem(self)
            separator.setFlags(Qt.NoItemFlags)
            self.addTopLevelItem(separator)
        
        elif book_ids is not None:
            self._book_item = book_item = QTreeWidgetItem(self)
            book_item.setFlags(Qt.ItemIsEnabled)
            book_item.setIcon(0, get_icon('book.png'))
            self.addTopLevelItem(book_item)
            
            book_fields_ids = self._build_content_map(book_ids)
            
            for field in fields_order:
                items = book_fields_ids.get(field, None)
                if items:
                    book_item.addChild(create_root_item(book_item, field, items))
            
            self._separator_item = separator = QTreeWidgetItem(self)
            separator.setFlags(Qt.NoItemFlags)
            self.addTopLevelItem(separator)
        
        for field in fields_order:
            items = content_map.get(field, None)
            if items:
                self.addTopLevelItem(create_root_item(self, field, items))
        
        self.update_texts(
            empty='',
            separator='--------------',
            tooltip=_('Subset of values associate to the books'),
            zero_book=_('No books'),
            zero_values=_('{:d} books (no values)'),
            has_book_values=_('{:d} books'),
        )
    
    def update_texts(self,
            empty: str=None,
            separator: str=None,
            tooltip: str=None,
            zero_book: str=None,
            zero_values: str=None,
            has_book_values: str=None,
        ):
        if not self.content_map:
            if empty is not None:
                self._separator_item.setText(0, empty)
        
        elif self.book_ids is not None:
            if tooltip is not None:
                self._book_item.setToolTip(0, tooltip)
            
            if not self.book_ids:
                msg = zero_book
            elif not self._book_item.childCount():
                msg = zero_values
            else:
                msg = has_book_values
            
            if msg is not None:
                self._book_item.setText(0, msg.format(len(self.book_ids)))
            
            if separator is not None:
                self._separator_item.setText(0, separator)
    
    def item_changed(self, item: QTreeWidgetItem, column: int):
        self.blockSignals(True)
        
        parent = item.parent()
        if isinstance(parent, QTreeWidgetItem) and parent.data(column, Qt.UserRole):
            state = False
            for idx in range(parent.childCount()):
                if parent.child(idx).checkState(column) == Qt.CheckState.Checked:
                    state = True
                    break
            parent.setCheckState(column, Qt.CheckState.PartiallyChecked if state else Qt.CheckState.Unchecked)
        else:
            if item.checkState(column) == Qt.CheckState.Checked:
                state = Qt.ItemIsUserCheckable
            else:
                state = Qt.ItemIsEnabled | Qt.ItemIsUserCheckable
            for idx in range(item.childCount()):
                item.child(idx).setFlags(state)
        
        self.blockSignals(False)
    
    def get_selected(self) -> Dict[str, List[tuple]]:
        rslt = defaultdict(list)
        
        def parse_tree_item(item):
            field = item.data(0, Qt.UserRole)
            all_field = False
            if item.checkState(0) == Qt.CheckState.Checked:
                all_field = True
            
            for idx in range(item.childCount()):
                child = item.child(idx)
                if all_field or child.checkState(0) == Qt.CheckState.Checked:
                    rslt[field].append(child.data(0, Qt.UserRole))
        
        for idx in range(self.topLevelItemCount()):
            item = self.topLevelItem(idx)
            
            if item.data(0, Qt.UserRole):
                parse_tree_item(item)
            else:
                for idx in range(item.childCount()):
                    ch = item.child(idx)
                    parse_tree_item(ch)
        
        return rslt

class SelectFieldValuesWidget(FieldsValueTreeWidget):
    def __init__(self, book_ids: List[int]=None, parent=None):
        'If book_ids is not None, display a entry that contain a subset of Notes for listed books'
        FieldsValueTreeWidget.__init__(self, book_ids=book_ids, parent=parent)
    
    def _build_content_map(self, book_ids: Union[List[int], None]):
        
        list_field = get_tags_browsable_fields(include_composite=False)
        for f in ['news', 'formats']:
            if f in list_field:
                list_field.remove(f)
        
        rslt = defaultdict(list)
        if book_ids is None:
            for field in list_field:
                for (id, value) in self._dbAPI.get_id_map(field).items():
                    rslt[field].append((value, id))
            
            identifiers = list(get_all_identifiers().keys())
            
            for id in identifiers:
                rslt['identifiers'].append((id, id))
        else:
            for field in list_field:
                for book_id in book_ids:
                    rslt[field].extend(self._dbAPI.field_ids_for(field, book_id))
                
                rslt[field] = list(set(rslt[field]))
                for idx,id_field in enumerate(rslt[field]):
                    if field == 'identifiers':
                        value = id_field
                    else:
                        value = self._dbAPI.get_item_name(field, id_field)
                    rslt[field][idx] = (value, id_field)
                
                if not len(rslt[field]):
                    del rslt[field]
        
        return rslt

class SelectNotesWidget(FieldsValueTreeWidget):
    def __init__(self, book_ids: List[int]=None, parent=None):
        'If book_ids is not None, display a entry that contain a subset of Notes for listed books'
        FieldsValueTreeWidget.__init__(self, book_ids=book_ids, parent=parent)
        self.update_texts(empty=_('No notes'))
    
    def _build_content_map(self, book_ids: Union[List[int], None]):
        '''
        Return item_ids for items that have notes in the specified field or all fields if field_name is None.
        If book_ids if passed, return for entry only relative to this book list.
        '''
        items_map = self._dbAPI.get_all_items_that_have_notes()
        
        rslt = defaultdict(list)
        if book_ids is None:
            for field,items in items_map.items():
                id_map = self._dbAPI.get_id_map(field)
                for id in items:
                    rslt[field].append((id_map[id], id))
        else:
            for book_id in book_ids:
                for field,items in items_map.items():
                    for id_field in self._dbAPI.field_ids_for(field, book_id):
                        if id_field in items:
                            rslt[field].append((self._dbAPI.get_item_name(field, id_field), id_field))
        
        return rslt


# ----------------------------------------------
#               Controls
# ----------------------------------------------

class ReadOnlyLineEdit(QLineEdit):
    def __init__(self, text: str, parent=None):
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
    
    COMBO_IMAGE_ADD = _('Add New Image…')
    
    new_image_added = pyqtSignal(str)
    
    def __init__(self, image_map, selected_image_name=None):
        NoWheelComboBox.__init__(self)
        self.populate_combo(image_map, selected_image_name=selected_image_name)
        self.currentIndexChanged.connect(self.index_changed)
    
    def populate_combo(self, image_map: Dict[str, QIcon], selected_image_name: str=None):
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
    
    def index_changed(self, idx: int):
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
    def __init__(self, values: List[str], selected_value: str=None, parent=None):
        QComboBox.__init__(self, parent)
        self.populate_combo(values=values, selected_value=selected_value)
    
    def populate_combo(self, values: List[str], selected_value: str=None):
        self.clear()
        selected_idx = 0
        for value in values:
            self.addItem(value)
            if value == selected_value:
                selected_idx = self.count()-1
        self.setCurrentIndex(selected_idx)
    
    def selected_value(self) -> str:
        return self.currentText()

class KeyValueComboBox(QComboBox):
    def __init__(self, key_text_map: Dict[str, str], selected_key: str=None, tooltip_map: Dict[str, str]=None, parent=None):
        QComboBox.__init__(self, parent)
        self.populate_combo(key_text_map, selected_key, tooltip_map)
        self.currentIndexChanged.connect(self.key_value_changed)
        self.key_value_changed(-1)
    
    def populate_combo(self, key_text_map: Dict[str, str], selected_key: str=None, tooltip_map: Dict[str, str]=None):
        self.clear()
        self.key_text_map = key_text_map
        self.tooltip_map = tooltip_map or {}
        
        selected_idx = 0
        for key, value in self.key_text_map.items():
            self.addItem(value, key)
            if key == selected_key:
                selected_idx = self.count()-1
        self.setCurrentIndex(selected_idx)
    
    def selected_entry(self) -> Tuple[str, str]:
        key = self.selected_key()
        if key:
            return key, self.key_text_map[key]
    
    def selected_key(self) -> str:
        key = self.currentData()
        if key:
            return key
    
    def selected_text(self) -> str:
        return self.key_text_map.get(self.selected_key(), None)
    
    def key_value_changed(self, idx: int):
        self.setToolTip(return_line_long_text(self.tooltip_map.get(self.selected_key(), '')))

class CustomColumnComboBox(QComboBox):
    def __init__(self, custom_columns: Dict[str ,ColumnMetadata], selected_column: str='', parent=None):
        QComboBox.__init__(self, parent)
        self.populate_combo(custom_columns=custom_columns, selected_column=selected_column)
        self.currentIndexChanged.connect(self.column_changed)
        self.column_changed(-1)
    
    def populate_combo(self, custom_columns: Dict[str ,ColumnMetadata], selected_column: str=''):
        self.clear()
        self.custom_columns = cc = OrderedDict()
        self.custom_columns['']=''
        self.description_map = tt = OrderedDict()
        self.description_map['']=''
        for entry in custom_columns.values():
            if entry:
                cc[entry.name] = f'{entry.display_name} ({entry.name})'
                tt[entry.name] = entry.description
        
        selected_idx = 0
        for key, value in cc.items():
            self.addItem(value, key)
            if key == selected_column:
                selected_idx = self.count()-1
        self.setCurrentIndex(selected_idx)
    
    def selected_name(self) -> str:
        name = self.currentData()
        if name:
            return name
    
    def selected_entry(self) -> Tuple[str ,ColumnMetadata]:
        name = self.selected_name()
        if name:
            return name, self.custom_columns.get(name, None)
    
    def selected_column(self) -> ColumnMetadata:
        kv = self.selected_entry()
        if kv:
            return kv[1]
    
    def column_changed(self, idx: int):
        self.setToolTip(return_line_long_text(self.description_map.get(self.selected_name(), '')))

class ReorderedComboBox(QComboBox):
    def __init__(self, strip_items=True, parent=None):
        QComboBox.__init__(self, parent)
        self.strip_items = strip_items
        self.setEditable(True)
        self.setMaxCount(10)
        self.setInsertPolicy(QComboBox.InsertAtTop)
    
    def populate_items(self, items: List[str], sel_item: str):
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
        text = self.currentText()
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
            return [self.itemText(i).strip() for i in range(0, self.count())]
        else:
            return [self.itemText(i) for i in range(0, self.count())]

class DragDropLineEdit(QLineEdit):
    """
    Unfortunately there is a flaw in the Qt implementation which means that
    when the QComboBox is in editable mode that dropEvent is not fired
    if you drag into the editable text area. Working around this by having
    a custom LineEdit() set for the parent combobox.
    """
    def __init__(self, drop_mode: str, parent=None):
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
            urls = [u.toString().strip() for u in md.urls()]
            return urls

class DragDropComboBox(ReorderedComboBox):
    """
    Unfortunately there is a flaw in the Qt implementation which means that
    when the QComboBox is in editable mode that dropEvent is not fired
    if you drag into the editable text area. Working around this by having
    a custom LineEdit() set for the parent combobox.
    """
    def __init__(self, drop_mode='url', parent=None):
        ReorderedComboBox.__init__(self, parent)
        self.drop_line_edit = DragDropLineEdit(drop_mode, parent)
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
