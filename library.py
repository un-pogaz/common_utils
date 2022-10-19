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

from . import GUI, PLUGIN_NAME


try:
    authors_split_regex = tweaks['authors_split_regex']
    re.compile(authors_split_regex)
except Exception:
    authors_split_regex = r'(?i),?\s+(and|with)\s+'
    """tweaks split regex for authors"""

def string_to_authors(raw_string):
    """
    Split a string into a list of authors
    
    return: list(str)
    """
    from calibre.ebooks.metadata import string_to_authors
    return string_to_authors(raw_string)

def no_launch_error(title, name=None, msg=None):
    """Show a error dialog  for an operation that cannot be launched"""
    
    if msg and len(msg) > 0:
        msg = '\n'+msg
    else:
        msg = ''
    
    error_dialog(GUI, title, (title +'.\n'+ _('Could not to launch {:s}').format(PLUGIN_NAME or name) + msg), show=True, show_copy_button=False)

def _BookIds_error(book_ids, show_error, title, name=None):
    if not book_ids and show_error:
        no_launch_error(title, name=name)
    return book_ids

def get_BookIds_selected(show_error=False):
    """return the books id selected in the gui"""
    rows = GUI.library_view.selectionModel().selectedRows()
    if not rows or len(rows) == 0:
        ids = []
    else:
        ids = GUI.library_view.get_selected_ids()
   
    return _BookIds_error(ids, show_error, _('No book selected'))

def get_BookIds_all(show_error=False):
    """return all books id in the library"""
    ids = GUI.current_db.all_ids()
    return _BookIds_error(ids, show_error, _('No book in the library'))

def get_BookIds_virtual(show_error=False):
    """return the books id of the virtual library (without search restriction)"""
    ids = get_BookIds('', use_search_restriction=False, use_virtual_library=True)
    return _BookIds_error(ids, show_error, _('No book in the virtual library'))

def get_BookIds_filtered(show_error=False):
    """return the books id of the virtual library AND search restriction applied.
    This is the strictest result"""
    ids = get_BookIds('', use_search_restriction=True, use_virtual_library=True)
    return _BookIds_error(ids, show_error, _('No book in the virtual library'))

def get_BookIds_search(show_error=False):
    """return the books id of the current search"""
    ids = get_BookIds(get_curent_search(), use_search_restriction=True, use_virtual_library=True)
    return _BookIds_error(ids, show_error, _('No book in the current search'))

def get_BookIds(query, use_search_restriction=True, use_virtual_library=True):
    """
    return the books id corresponding to the query
    
    query:
        Search query of wanted books
    
    use_search_restriction:
        Limit the search to the actual search restriction
    
    use_virtual_library:
        Limit the search to the actual virtual library
    """
    data = GUI.current_db.data
    query = query or ''
    search_restriction = data.search_restriction if use_search_restriction else ''
    return data.search_getting_ids(query, search_restriction,
                                    set_restriction_count=False, use_virtual_library=use_virtual_library, sort_results=True)


def get_curent_search():
    """Get the current search string. Can be invalid"""
    return GUI.search.current_text

def get_last_search():
    """Get last search string performed with succes"""
    return GUI.library_view.model().last_search

def get_curent_virtual():
    """The virtual library, can't be a temporary VL"""
    data = GUI.current_db.data
    return data.get_base_restriction_name(), data.get_base_restriction()

def get_curent_restriction_search():
    """The search restriction is a top level filtre, based on the saved searches"""
    data = GUI.current_db.data
    name = data.get_search_restriction_name()
    return name, get_saved_searches().get(name, data.search_restriction)

def get_virtual_libraries():
    """Get all virtual library set in the database"""
    return GUI.current_db.prefs.get('virtual_libraries', {})

def get_saved_searches():
    """Get all saved searches set in the database"""
    return GUI.current_db.prefs.get('saved_searches', {})


def get_marked(label=None):
    """
    Get the marked books
    
    label:
        Filtre to only label. No case sensitive
    
    return: { label : [id,] }
    """
    
    rslt = {}
    for k,v in iteritems(GUI.current_db.data.marked_ids):
        v = str(v).lower()
        if v not in rslt:
            rslt[v] = [k]
        else:
            rslt[v].append(k)
    
    if label == None:
        return rslt
    else:
        label = str(label).lower()
        return { label:rslt[label] }

def set_marked(label, book_ids, append=False, reset=False):
    """
    Set the marked books
    
    label:
        String label. No case sensitive
    
    book_ids:
        Book id to affect the label
    
    append:
        Append the book id to the books that already this label.
        By default clear the previous book with this lable.
    
    book_ids:
        Book id to affect the label
    """
    label = str(label).lower()
    marked = {} if reset else GUI.current_db.data.marked_ids.copy()
    
    if not append:
        del_id = []
        for k,v in iteritems(marked):
            if v == label: del_id.append(k)
        
        for k in del_id:
            del marked[k]
    
    marked.update( {idx:label for idx in book_ids} )
    GUI.current_db.data.set_marked_ids(marked)

