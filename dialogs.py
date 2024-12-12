#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2011, Grant Drake <grant.drake@gmail.com> ; 2020, un_pogaz <un.pogaz@gmail.com>'


try:
    load_translations()
except NameError:
    pass # load_translations() added in calibre 1.9

import os
import shutil
import sys
import time
from locale import Error
from typing import Any, List

try:
    from qt.core import (
        QAbstractItemView,
        QApplication,
        QDialogButtonBox,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QProgressDialog,
        QPushButton,
        QRadioButton,
        QSize,
        Qt,
        QTextBrowser,
        QTextEdit,
        QTimer,
        QVBoxLayout,
        pyqtSignal,
    )
except ImportError:
    from PyQt5.Qt import (
        QAbstractItemView,
        QApplication,
        QDialogButtonBox,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QProgressDialog,
        QPushButton,
        QRadioButton,
        QSize,
        Qt,
        QTextBrowser,
        QTextEdit,
        QTimer,
        QVBoxLayout,
        pyqtSignal,
    )

from calibre.gui2 import choose_files, error_dialog, question_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.keyboard import ShortcutConfig
from calibre.gui2.widgets2 import Dialog

from . import GUI, PLUGIN_NAME, PREFS_NAMESPACE, current_db, debug_print, get_icon, local_resource


class KeyboardConfigDialog(Dialog):
    """
    This dialog is used to allow editing of keyboard shortcuts.
    """
    def __init__(self, group_name: str, parent=None):
        self.group_name = group_name
        Dialog.__init__(self,
            title=_('Keyboard shortcuts'),
            name='plugin.common_utils:keyboard_shortcut_dialog',
            parent=parent or GUI,
        )
    
    def setup_ui(self):
        self.setWindowIcon(get_icon('keyboard-prefs.png'))
        layout = QVBoxLayout(self)
        self.setLayout(layout)
        
        self.keyboard_widget = ShortcutConfig(self)
        layout.addWidget(self.keyboard_widget)
        
        self.keyboard_widget.initialize(GUI.keyboard)
        self.keyboard_widget.highlight_group(self.group_name)
        
        layout.addWidget(self.bb)
    
    def accept(self):
        self.keyboard_widget.commit()
        Dialog.accept(self)

def edit_keyboard_shortcuts_dialog(plugin_action: InterfaceAction, parent=None):
    getattr(plugin_action, 'rebuild_menus', ())()
    d = KeyboardConfigDialog(plugin_action.action_spec[0], parent=parent)
    if d.exec():
        GUI.keyboard.finalize()

class KeyboardConfigDialogButton(QPushButton):
    def __init__(self, show_icon=True, parent=None):
        QPushButton.__init__(self, get_icon('keyboard-prefs.png' if show_icon else None), _('Keyboard shortcuts')+'…', parent)
        self.setToolTip(_('Edit the keyboard shortcuts associated with this plugin'))
        self.clicked.connect(self.edit_shortcuts)

    def edit_shortcuts(self):
        from . import PLUGIN_INSTANCE
        plugin_action = PLUGIN_INSTANCE.load_actual_plugin(GUI)
        edit_keyboard_shortcuts_dialog(plugin_action)


class LibraryPrefsViewerDialog(Dialog):
    def __init__(self, namespace: str, parent=None):
        self.db = current_db()
        self.namespace = namespace
        self.prefs = {}
        self.current_key = None
        Dialog.__init__(self,
            title=_('Preferences for:')+' '+namespace,
            name='plugin.common_utils:library_prefs_viewer_dialog',
            parent=parent or GUI,
            default_buttons=QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Reset,
        )
    
    def setup_ui(self):
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
        
        reset_button = self.bb.button(QDialogButtonBox.Reset)
        reset_button.setToolTip(_('Clear all settings for this plugin'))
        reset_button.clicked.connect(self._reset_settings)
        layout.addWidget(self.bb)
        
        self._populate_settings()
        
        if self.keys_list.count():
            self.keys_list.setCurrentRow(0)
    
    def _populate_settings(self):
        self.prefs.clear()
        self.keys_list.clear()
        ns_prefix = 'namespaced:'+self.namespace+':'
        ns_len = len(ns_prefix)
        for key in sorted([k[ns_len:] for k in self.db.prefs.keys() if k.startswith(ns_prefix)]):
            self.keys_list.addItem(key)
            val = self.db.prefs.get_namespaced(self.namespace, key, None)
            self.prefs[key] = self.db.prefs.to_raw(val) if val != None else None
        self.keys_list.setMinimumWidth(self.keys_list.sizeHintForColumn(0))
        self.keys_list.currentRowChanged[int].connect(self._current_row_changed)
    
    def _save_current_row(self):
        if self.current_key != None:
            self.prefs[self.current_key] = self.value_text.toPlainText()
    
    def _current_row_changed(self, new_row):
        self._save_current_row()
        
        if new_row < 0:
            self.value_text.clear()
            self.current_key = None
            return
        
        self.current_key = self.keys_list.currentItem().text()
        self.value_text.setPlainText(self.prefs[self.current_key])
    
    def accept(self):
        self._save_current_row()
        for k,v in self.prefs.items():
            try:
                self.db.prefs.raw_to_object(v)
            except Exception as ex:
                custom_exception_dialog(ex, additional_msg=_('The changes cannot be applied.'), show_detail=False)
                return
        
        from calibre.gui2.dialogs.confirm_delete import confirm
        message = '<p>'+_('Are you sure you want to change your settings in this library for this plugin?')+'</p>' \
                  '<p>'+_('Any settings in other libraries or stored in a JSON file in your calibre plugins ' \
                  'folder will not be touched.')+'</p>'
        if not confirm(message, 'library_prefs_viewer_dialog_apply_settings:'+self.namespace, self):
            return
        
        for k,v in self.prefs.items():
            self.db.prefs.set_namespaced(self.namespace, k, self.db.prefs.raw_to_object(v))
        Dialog.accept(self)
    
    def _reset_settings(self):
        from calibre.gui2.dialogs.confirm_delete import confirm
        message = '<p>'+_('Are you sure you want to clear your settings in this library for this plugin?')+'</p>' \
                  '<p>'+_('Any settings in other libraries or stored in a JSON file in your calibre plugins ' \
                  'folder will not be touched.')+'</p>'
        if not confirm(message, 'library_prefs_viewer_dialog_reset_settings:'+self.namespace, self):
            return
        
        for k in self.prefs.keys():
            self.prefs[k] = '{}'
            self.db.prefs.set_namespaced(self.namespace, k, self.db.prefs.raw_to_object('{}'))
        self._populate_settings()
        Dialog.accept(self)

def library_prefs_dialog(prefs_namespace: str=PREFS_NAMESPACE, parent=None) -> Dialog.DialogCode:
    d = LibraryPrefsViewerDialog(prefs_namespace, parent)
    return d.exec()

class LibraryPrefsViewerDialogButton(QPushButton):
    
    library_prefs_changed = pyqtSignal()
    
    def __init__(self, prefs_namespace: str=PREFS_NAMESPACE, show_icon=False, parent=None):
        QPushButton.__init__(self, get_icon('lt.png' if show_icon else None), _('View library preferences')+'…', parent)
        self.setToolTip(_('View data stored in the library database for this plugin'))
        self.clicked.connect(self.library_prefs_dialog)
        self.prefs_namespace = prefs_namespace
        self.parent = parent

    def library_prefs_dialog(self):
        if library_prefs_dialog(self.prefs_namespace, self.parent):
            self.library_prefs_changed.emit()


class ProgressDialog(QProgressDialog):
    
    icon=None
    title=None
    cancel_text=None
    
    def __init__(self, book_ids: Any, parent=None, **kvargs):
        
        # DB
        self.db = current_db()
        # DB API
        self.dbAPI = self.db.new_api
        
        # list of book id
        self.book_ids = book_ids
        # Count book
        self.book_count = len(self.book_ids)
        
        value_max = self.setup_progress(**kvargs) or self.book_count
        
        cancel_text = kvargs.get('cancel_text', None) or self.cancel_text or _('Cancel')
        QProgressDialog.__init__(self, '', cancel_text, 0, value_max, parent or GUI)
        
        self.setMinimumWidth(500)
        self.setMinimumHeight(100)
        self.setMinimumDuration(100)
        
        self.setAutoClose(True)
        self.setAutoReset(False)
        
        title = kvargs.get('title', None) or self.title or _('{PLUGIN_NAME} progress').format(PLUGIN_NAME=PLUGIN_NAME)
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
            self.exec()
            
            self.db.clean()
            
            self.time_execut = round(time.time() - self.start, 3)
            
            self.end_progress()
        
        self.close()
    
    def set_value(self, value: int, text: str=None):
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
    
    def increment(self, value: int=1, text: str=None) -> int:
        rslt = self.value() + value
        if rslt > self.maximum():
            rslt = self.maximum()
        self.set_value(rslt, text=text)
        return rslt
    
    def _job_progress(self):
        self.set_value(0)
        self.job_progress()
        self.hide()
    
    def progress_text(self) -> str:
        return _('Book {:d} of {:d}').format(self.value(), self.book_count)
    
    def setup_progress(self, **kvargs):
        raise NotImplementedError()
    
    def end_progress(self):
        raise NotImplementedError()
    
    def job_progress(self):
        raise NotImplementedError()

class ViewLogDialog(Dialog):
    def __init__(self, title: str, html: str, parent=None):
        self.src_html = html or ''
        Dialog.__init__(self,
            title=title,
            name='plugin.common_utils:log_viewer_dialog',
            parent=parent or GUI,
        )
    
    def setup_ui(self):
        self.setWindowIcon(get_icon('debug.png'))
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        
        self.tb = QTextBrowser(self)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        # Rather than formatting the text in <pre> blocks like the calibre
        # ViewLog does, instead just format it inside divs to keep style formatting
        html = self.src_html.replace('\t','&nbsp;&nbsp;&nbsp;&nbsp;').replace('\n', '<br/>')
        html = html.replace('> ','>&nbsp;')
        self.tb.setHtml('<div>'+html+'</div>')
        QApplication.restoreOverrideCursor()
        l.addWidget(self.tb)
        
        self.copy_button = self.bb.addButton(_('Copy to clipboard'), self.bb.ActionRole)
        self.copy_button.setIcon(get_icon('edit-copy.png'))
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        l.addWidget(self.bb)
        
        self.setModal(False)
        self.resize(QSize(700, 500))
        self.show()
    
    def copy_to_clipboard(self):
        txt = self.tb.toPlainText()
        QApplication.clipboard().setText(txt)


class ImageDialog(Dialog):
    def __init__(self, existing_images: List[str]=None, resources_dir: str=None, parent=None):
        self.resources_dir = resources_dir or local_resource.IMAGES
        self.existing_images = existing_images or []
        Dialog.__init__(self,
            title=_('Add New Image'),
            name='plugin.common_utils:add_new_image',
            parent=parent or GUI,
        )
    
    def setup_ui(self):
        v = QVBoxLayout(self)
        
        group_box = QGroupBox(_('&Select image source'), self)
        v.addWidget(group_box)
        grid = QGridLayout()
        self._radio_web = QRadioButton(_('From &web domain favicon'), self)
        self._radio_web.setChecked(True)
        self._web_domain_edit = QLineEdit(self)
        self._radio_web.setFocusProxy(self._web_domain_edit)
        grid.addWidget(self._radio_web, 0, 0)
        grid.addWidget(self._web_domain_edit, 0, 1)
        grid.addWidget(QLabel('e.g. www.amazon.com'), 0, 2)
        self._radio_file = QRadioButton(_('From .png &file'), self)
        self._input_file_edit = QLineEdit(self)
        self._input_file_edit.setMinimumSize(200, 0)
        self._radio_file.setFocusProxy(self._input_file_edit)
        pick_button = QPushButton(get_icon('document_open.png'),'', self)
        pick_button.setMaximumSize(24, 20)
        pick_button.clicked.connect(self.pick_file_to_import)
        grid.addWidget(self._radio_file, 1, 0)
        grid.addWidget(self._input_file_edit, 1, 1)
        grid.addWidget(pick_button, 1, 2)
        group_box.setLayout(grid)
        
        save_layout = QHBoxLayout()
        lbl_filename = QLabel(_('&Save as filename:'), self)
        lbl_filename.setMinimumSize(155, 0)
        self._save_as_edit = QLineEdit('', self)
        self._save_as_edit.setMinimumSize(200, 0)
        lbl_filename.setBuddy(self._save_as_edit)
        lbl_ext = QLabel('.png', self)
        save_layout.addWidget(lbl_filename, 0, Qt.AlignLeft)
        save_layout.addWidget(self._save_as_edit, 0, Qt.AlignLeft)
        save_layout.addWidget(lbl_ext, 1, Qt.AlignLeft)
        v.addLayout(save_layout)
        
        v.addWidget(self.bb)
        self.resize(self.sizeHint())
        self._web_domain_edit.setFocus()
        self.new_image_name = None
    
    @property
    def image_name(self) -> str:
        return self.new_image_name
    
    def pick_file_to_import(self):
        images = choose_files(None, 'menu_icon_dialog', _('Select a .png file for the menu icon'),
                             filters=[('PNG Image Files', ['png'])], all_files=False, select_only_single_file=True)
        if not images:
            return
        f = images[0]
        if not f.lower().endswith('.png'):
            return error_dialog(self, _('Cannot import image'), _('Source image must be a .png file.'), show=True)
        self._input_file_edit.setText(f)
        self._save_as_edit.setText(os.path.splitext(os.path.basename(f))[0])
        self._radio_file.click()
    
    def accept(self):
        # Validate all the inputs
        save_name = self._save_as_edit.text().strip()
        if not save_name:
            return error_dialog(self, _('Cannot import image'), _('You must specify a filename to save as.'), show=True)
        self.new_image_name = os.path.splitext(save_name)[0] + '.png'
        if save_name.find('\\') > -1 or save_name.find('/') > -1:
            return error_dialog(self, _('Cannot import image'), _('The save as filename should consist of a filename only.'), show=True)
        if not os.path.exists(self.resources_dir):
            os.makedirs(self.resources_dir)
        dest_path = os.path.join(self.resources_dir, self.new_image_name)
        if save_name in self.existing_images or os.path.exists(dest_path):
            if not question_dialog(self, _('Are you sure?'), _('An image with this name already exists - overwrite it?'), show_copy_button=False):
                return
        
        if self._radio_web.isChecked():
            try:
                from urllib.request import urlretrieve
            except ImportError:
                from urllib import urlretrieve
            domain = self._web_domain_edit.text().strip()
            if not domain:
                return error_dialog(self, _('Cannot import image'), _('You must specify a web domain url'), show=True)
            url = 'http://www.google.com/s2/favicons?domain=' + domain
            urlretrieve(url, dest_path)
        else:
            source_file_path = self._input_file_edit.text().strip()
            if not source_file_path:
                return error_dialog(self, _('Cannot import image'), _('You must specify a source file.'), show=True)
            if not source_file_path.lower().endswith('.png'):
                return error_dialog(self, _('Cannot import image'), _('Source image must be a .png file.'), show=True)
            if not os.path.exists(source_file_path):
                return error_dialog(self, _('Cannot import image'), _('Source image does not exist!'), show=True)
            shutil.copyfile(source_file_path, dest_path)
        Dialog.accept(self)


def custom_exception_dialog(exception: Error, additional_msg: str=None, title: str=None, show_detail=True, parent=None):
    
    import traceback

    from calibre import force_unicode, prepare_string_for_xml, prints
    from polyglot.io import PolyglotStringIO
    
    sio = PolyglotStringIO(errors='replace')
    try:
        from calibre.debug import print_basic_debug_info
        print_basic_debug_info(out=sio)
    except:
        pass
    traceback.print_exception(exception.__class__, exception, exception.__traceback__, file=sio)
    if getattr(exception, 'locking_debug_msg', None):
        prints(exception.locking_debug_msg, file=sio)
    fe = sio.getvalue()
    prints(fe, file=sys.stderr)
    fe = force_unicode(fe)
    try:
        if getattr(GUI, 'show_possible_sharing_violation', lambda *a: None)(exception, det_msg=fe):
            return
    except Exception:
        traceback.print_exc()
    
    msg = []
    msg.append('<span>' + prepare_string_for_xml(_('The {PLUGIN_NAME} plugin has encounter a unhandled exception.').format(PLUGIN_NAME=PLUGIN_NAME)))
    if additional_msg: msg.append(additional_msg)
    if exception: msg.append(f'<b>{exception.__class__.__name__:s}</b>: ' + prepare_string_for_xml(str(exception)))
    
    if show_detail:
        det_msg=fe
    else:
        det_msg=None
    
    error_dialog(parent or GUI, title or _('Unhandled exception'), '\n'.join(msg).replace('\n', '<br>'), det_msg=det_msg, show=True, show_copy_button=bool(det_msg))
