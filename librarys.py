#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2011, Grant Drake <grant.drake@gmail.com> ; 2020, un_pogaz <un.pogaz@gmail.com>'


try:
    load_translations()
except NameError:
    pass # load_translations() added in calibre 1.9

from typing import List

from calibre.gui2 import error_dialog

from . import GUI, PLUGIN_NAME, current_db
from .columns import get_categories
from .compatibility import category_display_order

try:
    import re
    
    from calibre.utils.config import tweaks
    authors_split_regex = tweaks['authors_split_regex']
    re.compile(authors_split_regex)
    del re, tweaks
except Exception:
    authors_split_regex = r'(?i),?\s+(and|with)\s+'
    """tweaks split regex for authors"""

def string_to_authors(raw_string: str) -> List[str]:
    'Split a string into a list of authors'
    from calibre.ebooks.metadata import string_to_authors
    return string_to_authors(raw_string)

def no_launch_error(title, name: str=None, msg: str=None):
    'Show a error dialog  for an operation that cannot be launched'
    
    if msg and len(msg) > 0:
        msg = '\n'+msg
    else:
        msg = ''
    
    error_dialog(GUI, title, (title +'.\n'+ _('Could not to launch {:s}').format(PLUGIN_NAME or name) + msg), show=True, show_copy_button=False)

def _BookIds_error(book_ids: List[int], show_error: bool, title: str, name: str=None):
    if not book_ids and show_error:
        no_launch_error(title, name=name)
    return book_ids

def get_BookIds_selected(show_error=False):
    """return the books id selected in the gui"""
    try:
        ids = GUI.library_view.get_selected_ids()
    except:
        ids = []
   
    return _BookIds_error(ids, show_error, _('No book selected'))

def get_BookIds_all(show_error=False):
    """return all books id in the library"""
    ids = current_db().all_ids()
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
    data = current_db().data
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
    data = current_db().data
    return data.get_base_restriction_name(), data.get_base_restriction()

def get_curent_restriction_search():
    """The search restriction is a top level filtre, based on the saved searches"""
    data = current_db().data
    name = data.get_search_restriction_name()
    return name, get_saved_searches().get(name, data.search_restriction)

def get_virtual_libraries():
    """Get all virtual library set in the database"""
    return current_db().prefs.get('virtual_libraries', {})

def get_saved_searches():
    """Get all saved searches set in the database"""
    return current_db().prefs.get('saved_searches', {})


def get_marked(label: str=None):
    """
    Get the marked books
    
    label:
        Filtre to only label. No case sensitive
    
    return: { label : [id,] }
    """
    
    rslt = {}
    for k,v in current_db().data.marked_ids.items():
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

def set_marked(label: str, book_ids: List[int], append=False, reset=False):
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
    marked = {} if reset else current_db().data.marked_ids.copy()
    
    if not append:
        del_id = []
        for k,v in marked.items():
            if v == label: del_id.append(k)
        
        for k in del_id:
            del marked[k]
    
    marked.update( {idx:label for idx in book_ids} )
    current_db().data.set_marked_ids(marked)

def get_category_icons_map():
    return GUI.tags_view.model().category_custom_icons

def get_tags_browsable_fields(use_defaults=False, order_override: List[str]=None, include_composite=True):
    if use_defaults:
        tbo = []
    elif order_override:
        tbo = order_override
    else:
        tbo = current_db().new_api.pref('tag_browser_category_order', [])
    
    return category_display_order(tbo, get_categories(include_composite=include_composite).keys())
