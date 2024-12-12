#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2020, Ahmed Zaki <azaki00.dev@gmail.com> ; adjustment 2020, un_pogaz <un.pogaz@gmail.com>'


try:
    load_translations()
except NameError:
    pass # load_translations() added in calibre 1.9

from typing import List, Tuple

try:
    from qt.core import QPushButton
except ImportError:
    from PyQt5.Qt import QPushButton

from calibre.db.lazy import Metadata
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.book.formatter import SafeFormat
from calibre.gui2 import error_dialog
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.gui2.widgets2 import Dialog

from . import GUI, current_db, get_icon

TEMPLATE_PREFIX = 'TEMPLATE: '
TEMPLATE_ERROR = 'TEMPLATE_ERROR: '
TEMPLATE_FIELD = '{template}'

def check_template(template, show_error=False) -> bool:
    db = current_db()
    error_msgs = [
        TEMPLATE_ERROR,
        'unknown function',
        'unknown identifier',
        'unknown field',
        'assign requires the first parameter be an id',
        'missing closing parenthesis',
        'incorrect number of arguments for function',
        'expression is not function or constant'
    ]
    try:
        book_id = list(db.all_ids())[0]
        mi = db.get_metadata(book_id, index_is_id=True, get_user_categories=True)
    except:
        mi = MetaInformation(_('Unknown'))
    
    output = SafeFormat().safe_format(template, mi, TEMPLATE_ERROR, mi)
    for msg in error_msgs:
        if output.lower().find(msg.lower()) != -1:
            error = output.lstrip(TEMPLATE_ERROR)
            if show_error:
                error_dialog(GUI, _('Template Error'),
                        _('Running the template returned an error:') +'\n'+ str(error),
                        show=True)
            return error
    return True

class TemplateEditorDialog(TemplateDialog):
    def __init__(self, parent=None, mi=None, fm=None, template_text=''):
        self.db = current_db()
        self.template = template_text
        parent = parent or GUI
        
        if not template_text:
            text = _('Enter a template to test using data from the selected book')
            text_is_placeholder = True
        else:
            text = None
            text_is_placeholder = False
         
        TemplateDialog.__init__(self, parent, text, mi=mi, fm=fm, text_is_placeholder=text_is_placeholder)
        self.setWindowTitle(_('Template editor'))
        self.setWindowIcon(get_icon('template_funcs.png'))
        if template_text:
            self.textbox.insertPlainText(template_text)
    
    def template_is_valide(self):
        return check_template(self.template) is True
    
    def accept(self):
        self.template = self.textbox.toPlainText().rstrip()
        TemplateDialog.accept(self)

def open_template_dialog(
    mi: List[Metadata]=None,
    template_text: str=None,
    parent=None,
) -> Tuple[Dialog.DialogCode, str]:
    d = TemplateEditorDialog(parent=parent, mi=mi or [], template_text=template_text or '')
    rslt = d.exec()
    return rslt, d.template

class TemplateEditorDialogButton(QPushButton):
    def __init__(self, show_icon=True, show_text=True, parent=None):
        if not show_icon and not show_text:
            raise ValueError('Need at least the icon or text')
        QPushButton.__init__(self,
            get_icon('template_funcs.png' if show_icon else None),
            (_('Open the template editor') if show_text else ''),
            parent=parent,
        )
        self.setToolTip(_('Open the template editor'))
