#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2023, un_pogaz <un.pogaz@gmail.com>'
__doc__       = 'various backward compatibility implementation'


try:
    from calibre.db.categories import category_display_order
except:
    def category_display_order(ordered_cats, all_cats):
        def is_standard_category(key):
            return not (key.startswith('@') or key == 'search')
        
        # ordered_cats is the desired order. all_cats is the list of keys returned
        # by get_categories, which is in the default order
        cat_ord = []
        all_cat_set = frozenset(all_cats)
        # Do the standard categories first
        # Verify all the columns in ordered_cats are actually in all_cats
        for key in ordered_cats:
            if is_standard_category(key) and key in all_cat_set:
                cat_ord.append(key)
        # Add any new standard cats at the end of the list
        for key in all_cats:
            if key not in cat_ord and is_standard_category(key):
                cat_ord.append(key)
        # Now add the non-standard cats (user cats and search)
        for key in all_cats:
            if not is_standard_category(key):
                cat_ord.append(key)
        return cat_ord

try:
    from calibre.utils.date import qt_from_dt
except:
    try:
        from qt.core import QDateTime
    except ImportError:
        from PyQt5.Qt import QDateTime
    
    def qt_from_dt(d, as_utc: bool = False, assume_utc: bool = False):
        return QDateTime(d)
