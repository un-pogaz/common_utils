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

from collections import OrderedDict
from functools import partial

try:
    load_translations()
except NameError:
    pass # load_translations() added in calibre 1.9

try: #polyglot added in calibre 4.0
    from polyglot.builtins import iteritems, itervalues
except ImportError:
    def iteritems(d):
        return d.iteritems()
    def itervalues(d):
        return d.itervalues()

import sys, time

try:
    from qt.core import (
        Qt, QAbstractItemView, QApplication, QDialog, QDialogButtonBox, QHBoxLayout,
        QLabel, QListWidget, QProgressBar, QProgressDialog, QPushButton, QSize,
        QTextBrowser, QTextEdit, QTimer, QVBoxLayout, pyqtSignal,
    )
except ImportError:
    from PyQt5.Qt import (
        Qt, QAbstractItemView, QApplication, QDialog, QDialogButtonBox, QHBoxLayout,
        QLabel, QListWidget, QProgressBar, QProgressDialog, QPushButton, QSize,
        QTextBrowser, QTextEdit, QTimer, QVBoxLayout, pyqtSignal,
    )

from calibre.gui2 import error_dialog, gprefs, Application
from calibre.gui2.keyboard import ShortcutConfig

from . import GUI, PLUGIN_NAME, PREFS_NAMESPACE, debug_print, get_icon


class SizePersistedDialog(QDialog):
    """
    This dialog is a base class for any dialogs that want their size/position
    restored when they are next opened.
    """
    def __init__(self, parent, unique_pref_name):
        QDialog.__init__(self, parent)
        self.unique_pref_name = PLUGIN_NAME+':'+ unique_pref_name
        self.geom = gprefs.get(unique_pref_name, None)
        self.finished.connect(self.dialog_closing)
    
    def resize_dialog(self):
        if self.geom is None:
            self.resize(self.sizeHint())
        else:
            self.restoreGeometry(self.geom)
    
    def dialog_closing(self, result):
        geom = bytearray(self.saveGeometry())
        gprefs[self.unique_pref_name] = geom
        self.persist_custom_prefs()
    
    def persist_custom_prefs(self):
        """
        Invoked when the dialog is closing. Override this function to call
        save_custom_pref() if you have a setting you want persisted that you can
        retrieve in your __init__() using load_custom_pref() when next opened
        """
        pass
    
    def load_custom_pref(self, name, default=None):
        return gprefs.get(self.unique_pref_name+':'+name, default)
    
    def save_custom_pref(self, name, value):
        gprefs[self.unique_pref_name+':'+name] = value
    
    def help_link_activated(self, url):
        if self.plugin_action is not None:
            self.plugin_action.show_help(anchor=self.help_anchor)

class KeyboardConfigDialog(SizePersistedDialog):
    """
    This dialog is used to allow editing of keyboard shortcuts.
    """
    def __init__(self, gui, group_name):
        SizePersistedDialog.__init__(self, gui, 'Keyboard shortcut dialog')
        self.gui = gui
        self.setWindowTitle(_('Keyboard shortcuts'))
        layout = QVBoxLayout(self)
        self.setLayout(layout)
        
        self.keyboard_widget = ShortcutConfig(self)
        layout.addWidget(self.keyboard_widget)
        self.group_name = group_name
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.commit)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Cause our dialog size to be restored from prefs or created on first usage
        self.resize_dialog()
        self.initialize()
    
    def initialize(self):
        self.keyboard_widget.initialize(self.gui.keyboard)
        self.keyboard_widget.highlight_group(self.group_name)
    
    def commit(self):
        self.keyboard_widget.commit()
        self.accept()

def edit_keyboard_shortcuts(plugin_action):
    getattr(plugin_action, 'rebuild_menus', ())()
    d = KeyboardConfigDialog(GUI, plugin_action.action_spec[0])
    if d.exec_() == d.Accepted:
        GUI.keyboard.finalize()

class KeyboardConfigDialogButton(QPushButton):
    def __init__(self, parent=None):
        QPushButton.__init__(self, _('Keyboard shortcuts')+'...', parent)
        self.setToolTip(_('Edit the keyboard shortcuts associated with this plugin'))
        self.clicked.connect(self.edit_shortcuts)

    def edit_shortcuts(self):
        from . import PLUGIN_INSTANCE
        plugin_action = PLUGIN_INSTANCE.load_actual_plugin(GUI)
        edit_keyboard_shortcuts(plugin_action)


class LibraryPrefsViewerDialog(SizePersistedDialog):
    def __init__(self, gui, namespace):
        SizePersistedDialog.__init__(self, gui, 'Prefs Viewer dialog')
        self.setWindowTitle(_('Preferences for:')+' '+namespace)
        
        self.gui = gui
        self.db = GUI.current_db
        self.namespace = namespace
        self.prefs = {}
        self.current_key = None
        self._init_controls()
        self.resize_dialog()
        
        self._populate_settings()
        
        if self.keys_list.count():
            self.keys_list.setCurrentRow(0)
    
    def _init_controls(self):
        layout = QVBoxLayout(self)
        self.setLayout(layout)
        
        ml = QHBoxLayout()
        layout.addLayout(ml, 1)
        
        self.keys_list = QListWidget(self)
        self.keys_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.keys_list.setFixedWidth(150)
        self.keys_list.setAlternatingRowColors(True)
        ml.addWidget(self.keys_list)
        self.value_text = QTextEdit(self)
        self.value_text.setReadOnly(False)
        ml.addWidget(self.value_text, 1)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._apply_changes)
        button_box.rejected.connect(self.reject)
        self.clear_button = button_box.addButton(_('Clear'), QDialogButtonBox.ResetRole)
        self.clear_button.setIcon(get_icon('trash.png'))
        self.clear_button.setToolTip(_('Clear all settings for this plugin'))
        self.clear_button.clicked.connect(self._clear_settings)
        layout.addWidget(button_box)
    
    def _populate_settings(self):
        self.prefs.clear()
        self.keys_list.clear()
        ns_prefix = 'namespaced:{:s}:'.format(self.namespace)
        ns_len = len(ns_prefix)
        for key in sorted([k[ns_len:] for k in self.db.prefs.keys() if k.startswith(ns_prefix)]):
            self.keys_list.addItem(key)
            val = self.db.prefs.get_namespaced(self.namespace, key, None)
            self.prefs[key] = self.db.prefs.to_raw(val) if val != None else None
        self.keys_list.setMinimumWidth(self.keys_list.sizeHintForColumn(0))
        self.keys_list.currentRowChanged[int].connect(self._current_row_changed)
    
    def _save_current_row(self):
        if self.current_key != None:
            self.prefs[self.current_key] = unicode(self.value_text.toPlainText())
    
    def _current_row_changed(self, new_row):
        self._save_current_row()
        
        if new_row < 0:
            self.value_text.clear()
            self.current_key = None
            return
        
        self.current_key = unicode(self.keys_list.currentItem().text())
        self.value_text.setPlainText(self.prefs[self.current_key])
    
    def _apply_changes(self):
        self._save_current_row()
        for k,v in iteritems(self.prefs):
            try:
                self.db.prefs.raw_to_object(v)
            except Exception as ex:
                CustomExceptionErrorDialog(ex, custome_msg=_('The changes cannot be applied.'))
                return
        
        from calibre.gui2.dialogs.confirm_delete import confirm
        message = '<p>'+_('Are you sure you want to change your settings in this library for this plugin?')+'</p>' \
                  '<p>'+_('Any settings in other libraries or stored in a JSON file in your calibre plugins ' \
                  'folder will not be touched.')+'</p>'
        if not confirm(message, self.namespace+'_apply_settings', self):
            return
        
        for k,v in iteritems(self.prefs):
            self.db.prefs.set_namespaced(self.namespace, k, self.db.prefs.raw_to_object(v))
        self.accept()
    
    def _clear_settings(self):
        from calibre.gui2.dialogs.confirm_delete import confirm
        message = '<p>'+_('Are you sure you want to clear your settings in this library for this plugin?')+'</p>' \
                  '<p>'+_('Any settings in other libraries or stored in a JSON file in your calibre plugins ' \
                  'folder will not be touched.')+'</p>'
        if not confirm(message, self.namespace+'_clear_settings', self):
            return
        
        for k in self.prefs.keys():
            self.prefs[k] = '{}'
            self.db.prefs.set_namespaced(self.namespace, k, self.db.prefs.raw_to_object('{}'))
        self._populate_settings()
        self.accept()

def view_library_prefs(prefs_namespace=PREFS_NAMESPACE):
    d = LibraryPrefsViewerDialog(GUI, prefs_namespace)
    return d.exec_()

class LibraryPrefsViewerDialogButton(QPushButton):
    
    library_prefs_changed = pyqtSignal()
    
    def __init__(self, parent=None, prefs_namespace=PREFS_NAMESPACE):
        QPushButton.__init__(self, _('View library preferences')+'...', parent)
        self.setToolTip(_('View data stored in the library database for this plugin'))
        self.clicked.connect(self.view_library_prefs)
        self.prefs_namespace = prefs_namespace

    def view_library_prefs(self):
        if view_library_prefs(self.prefs_namespace) == QDialog.Accepted:
            self.library_prefs_changed.emit()


class ProgressBarDialog(QDialog):
    def __init__(self, parent=None, max_items=100, window_title='Progress Bar',
                 label='Label goes here', on_top=False):
        if on_top:
            ProgressBarDialog.__init__(self, parent=parent, flags=Qt.WindowStaysOnTopHint)
        else:
            ProgressBarDialog.__init__(self, parent=parent)
        self.application = Application
        self.setWindowTitle(window_title)
        self.l = QVBoxLayout(self)
        self.setLayout(self.l)
        
        self.label = QLabel(label)
        #self.label.setAlignment(Qt.AlignHCenter)
        self.l.addWidget(self.label)
        
        self.progressBar = QProgressBar(self)
        self.progressBar.setRange(0, max_items)
        self.progressBar.setValue(0)
        self.l.addWidget(self.progressBar)
    
    def increment(self):
        self.progressBar.setValue(self.progressBar.value() + 1)
        self.refresh()
    
    def refresh(self):
        self.application.processEvents()
    
    def set_label(self, value):
        self.label.setText(value)
        self.refresh()
    
    def left_align_label(self):
        self.label.setAlignment(Qt.AlignLeft )
    
    def set_maximum(self, value):
        self.progressBar.setMaximum(value)
        self.refresh()
    
    def set_value(self, value):
        self.progressBar.setValue(value)
        self.refresh()
    
    def set_progress_format(self, progress_format=None):
        pass

class ProgressDialog(QProgressDialog):
    
    icon=None
    title=None
    cancel_text=None
    
    def __init__(self, book_ids=[], **kvargs):
        
        # DB
        self.db = GUI.current_db
        # DB API
        self.dbAPI = self.db.new_api
        
        # list of book id
        self.book_ids = book_ids
        # Count book
        self.book_count = len(self.book_ids)
        
        value_max = self.setup_progress(**kvargs) or self.book_count
        
        cancel_text = kvargs.get('cancel_text', None) or self.cancel_text or _('Cancel')
        QProgressDialog.__init__(self, '', cancel_text, 0, value_max, GUI)
        
        self.setMinimumWidth(500)
        self.setMinimumHeight(100)
        self.setMinimumDuration(100)
        
        self.setAutoClose(True)
        self.setAutoReset(False)
        
        title = kvargs.get('title', None) or self.title or _('{} progress').format(PLUGIN_NAME)
        self.setWindowTitle(title)
        
        for icon in [kvargs.get('icon', None), self.icon, 'images/plugin.png', 'lt.png']:
            icon = get_icon(icon)
            if not icon.isNull():
                break
        self.setWindowIcon(icon)
        
        self.start = time.time()
        self.time_execut = 0
        
        if not book_ids:
            debug_print('No book_ids passed to '+ str(self.__class__.__name__) +'. Skiped.')
        else:
            QTimer.singleShot(0, self._job_progress)
            self.exec_()
            
            self.db.clean()
            
            self.time_execut = round(time.time() - self.start, 3)
            
            self.end_progress()
        
        self.close()
    
    def set_value(self, value, text=None):
        if value < 0:
            value = self.maximum()
        self.setValue(value)
        
        if not text:
            if callable(self.progress_text):
                text = self.progress_text()
            else:
                text = self.progress_text
        
        self.setLabelText(text)
        if self.maximum() < 100:
            self.hide()
        else:
            self.show()
    
    def increment(self, value=1, text=None):
        rslt = self.value() + value
        if rslt > self.maximum():
            rslt = self.maximum()
        self.set_value(rslt, text=text)
        return rslt
    
    def _job_progress(self):
        self.set_value(0)
        self.job_progress()
        self.hide()
    
    def progress_text(self):
        return _('Book {:d} of {:d}').format(self.value(), self.book_count)
    
    def setup_progress(self, **kvargs):
        raise NotImplementedError()
    
    def end_progress(self):
        raise NotImplementedError()
    
    def job_progress(self):
        raise NotImplementedError()

class ViewLogDialog(QDialog):
    def __init__(self, title, html, parent=None):
        QDialog.__init__(self, parent)
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        
        self.tb = QTextBrowser(self)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        # Rather than formatting the text in <pre> blocks like the calibre
        # ViewLog does, instead just format it inside divs to keep style formatting
        html = html.replace('\t','&nbsp;&nbsp;&nbsp;&nbsp;').replace('\n', '<br/>')
        html = html.replace('> ','>&nbsp;')
        self.tb.setHtml('<div>{:s}</div>'.format(html))
        QApplication.restoreOverrideCursor()
        l.addWidget(self.tb)
        
        self.bb = QDialogButtonBox(QDialogButtonBox.Ok)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        self.copy_button = self.bb.addButton(_('Copy to clipboard'),
                self.bb.ActionRole)
        self.copy_button.setIcon(get_icon('edit-copy.png'))
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        l.addWidget(self.bb)
        self.setModal(False)
        self.resize(QSize(700, 500))
        self.setWindowTitle(title)
        self.setWindowIcon(get_icon('debug.png'))
        self.show()
    
    def copy_to_clipboard(self):
        txt = self.tb.toPlainText()
        QApplication.clipboard().setText(txt)

def CustomExceptionErrorDialog(exception, custome_title=None, custome_msg=None, show=True):
    
    from polyglot.io import PolyglotStringIO
    import traceback
    from calibre import as_unicode, prepare_string_for_xml
    
    sio = PolyglotStringIO(errors='replace')
    try:
        from calibre.debug import print_basic_debug_info
        print_basic_debug_info(out=sio)
    except:
        pass
    
    try:
        traceback.print_exception(type(exception), exception, exception.__traceback__, file=sio)
    except:
        traceback.print_exception(type(exception), exception, sys.exc_traceback, file=sio)
        pass
    
    fe = sio.getvalue()
    
    if not custome_title:
        custome_title = _('Unhandled exception')
    
    msg = []
    msg.append('<span>' + prepare_string_for_xml(as_unicode(_('The {:s} plugin has encounter a unhandled exception.').format(PLUGIN_NAME))))
    if custome_msg: msg.append(custome_msg)
    msg.append('<b>{:s}</b>: '.format(exception.__class__.__name__) + prepare_string_for_xml(as_unicode(str(exception))))
    
    return error_dialog(GUI, custome_title, '\n'.join(msg).replace('\n', '<br>'), det_msg=fe, show=show, show_copy_button=True)
