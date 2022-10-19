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

from . import get_pixmap


try:
    from qt.core import (Qt, QTableWidgetItem, QComboBox, QHBoxLayout, QLabel, QFont, 
                        QDateTime, QStyledItemDelegate, QLineEdit)
except ImportError:
    from PyQt5.Qt import (Qt, QTableWidgetItem, QComboBox, QHBoxLayout, QLabel, QFont, 
                        QDateTime, QStyledItemDelegate, QLineEdit)

from calibre.gui2 import error_dialog, UNDEFINED_QDATETIME
from calibre.utils.date import now, format_date, UNDEFINED_DATE
from calibre.gui2.library.delegates import DateDelegate as _DateDelegate

from . import get_date_format


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
        print('DateDelegate fmt:',fmt)

    def createEditor(self, parent, option, index):
        qde = QStyledItemDelegate.createEditor(self, parent, option, index)
        qde.setDisplayFormat(self.format)
        qde.setMinimumDateTime(UNDEFINED_QDATETIME)
        qde.setSpecialValueText(_('Undefined'))
        qde.setCalendarPopup(True)
        return qde

    def setEditorData(self, editor, index):
        val = index.model().data(index, Qt.DisplayRole)
        print('setEditorData val:',val)
        if val is None or val == UNDEFINED_QDATETIME:
            if self.default_to_today:
                val = self.default_date
            else:
                val = UNDEFINED_QDATETIME
        editor.setDateTime(val)

    def setModelData(self, editor, model, index):
        val = editor.dateTime()
        print('setModelData: ',val)
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
        ReadOnlyCheckableTableWidgetItem.__init__(self, text)
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
