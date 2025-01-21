#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2021, un_pogaz <un.pogaz@gmail.com>'


try:
    load_translations()
except NameError:
    pass  # load_translations() added in calibre 1.9

import copy
import os
import sys
from typing import Callable, Dict, List, Optional, Tuple

from calibre import prints
from calibre.constants import numeric_version as CALIBRE_VERSION
from calibre.db.legacy import LibraryDatabase
from calibre.library.field_metadata import FieldMetadata


def current_db() -> LibraryDatabase:
    from calibre.gui2.ui import get_gui
    return getattr(get_gui(),'current_db', None)


class typeproperty(property):
    registry = []
    
    def __init__(self, func):
        property.__init__(self, fget=func)
        typeproperty.registry.append(func)


def get_all_identifiers() -> List[str]:
    'Get the identifiers in the library'
    return current_db().get_all_identifier_types()


def is_enum_value(name, value) -> bool:
    '''
    Test if the value is valide in the column enumeration
    
    name:
        Column name to test
    
    value:
        Value to test
    
    return: True / raise Error
    '''
    
    col_metadata = get_column_from_name(name)
    if not col_metadata._is_enumeration:
        raise ValueError(f'The column "{name}" is not a enumeration')
    col_vals = col_metadata.enum_values
    if value not in col_vals:
        raise ValueError(f'\'{value}\' is not a valide value on the enumeration "{name}".')
    else:
        return True


def is_bool_value(value: str) -> bool:
    '''
    Test if the value is considered as a boulean by Calibre
    
    value:
        Value to test
    
    return: True / False / raise Error
    '''
    
    if str(value).lower() in ['yes','y','true','1']:
        return True
    elif str(value).lower() in ['no','n','false','0']:
        return False
    else:
        raise ValueError(f"'{value}' is not considered as a boulean by Calibre")


class ColumnTypes:
    bool           = 'bool'
    datetime       = 'datetime'
    enumeration    = 'enumeration'
    identifiers    = 'identifiers'
    float          = 'float'
    integer        = 'integer'
    names          = 'names'
    rating         = 'rating'
    series         = 'series'
    series_index   = 'series_index'
    tags           = 'tags'
    text           = 'text'
    html           = 'html'
    long_text      = 'long_text'
    markdown       = 'markdown'
    title          = 'title'
    composite_tag  = 'composite_tag'
    composite_text = 'composite_text'
    
    cover          = 'cover'
    news           = 'news'


class MutipleValue(dict):
    def __init__(self, data: dict):
        self.update(data)
    
    def __repr__(self):
        return self.__class__.__name__ +'('+ repr(self._data)[1:-1]+')'
    
    @property
    def ui_to_list(self) -> str:
        return self._data.get('ui_to_list', None)
    
    @property
    def list_to_ui(self) -> str:
        return self._data.get('list_to_ui', None)
    
    @property
    def cache_to_list(self) -> str:
        return self._data.get('cache_to_list', None)


class ColumnMetadata:
    '''
    You should only need the following @property of the ColumnMetadata:
    
    @property string (read-only) to identify the ColumnMetadata instance
        name
        display_name
        description
        type
        is_custom
        is_composite
    
    @property (read-only) of ColumnMetadata instance
    return is None if the column does not support this element
        allow_half_stars = bool
        category_sort = string > one of then [None, 'value', 'name']
        colnum = int
        column = string > one of then [None, 'value', 'name']
        composite_contains_html = bool
        composite_make_category = bool
        composite_sort = string > one of then ['text', 'number', 'date', 'bool']
        composite_template = string
        datatype = string
        display = {} // contains an arbitrary data set. reanalys in other property
        enum_colors = string[]
        enum_values = string[]
        heading_position = string > one of then ['text', 'number', 'date', 'bool']
        is_category = bool
        is_csp = bool
        is_editable = bool
        is_multiple = {} // contains an arbitrary data set. reanalys in other property
        kind = > one of then ['field', 'category', 'user', 'search']
        label = string
        link_column = string
        rec_index = int
        search_terms = string[]
        table = string
        use_decorations = bool
    
    @property bool (read-only) of ColumnMetadata instance
    that which identifies the type of the ColumnMetadata
        
        _is_bool
        _is_composite_tag
        _is_composite_text
        _is_datetime
        _is_enumeration
        _is_float
        _is_integer
        _is_identifiers
        _is_names
        _is_rating
        _is_series
        _is_tags
        _is_text
        _is_html
        _is_long_text
        _is_markdown
        _is_title
        
        _is_comments
        _is_news
    '''
    
    def __init__(self, metadata, is_custom=True):
        self.metadata = copy.deepcopy(metadata)
        self._custom = is_custom
        
        self._multiple = self.metadata['is_multiple']
        if self.is_csp:
            self._multiple = MutipleValue({'ui_to_list': ',', 'list_to_ui': ', ', 'cache_to_list': ','})
        if self._multiple:
            self._multiple = MutipleValue(self._multiple)
        else:
            self._multiple = None
        
        self._type = None
        for func in typeproperty.registry:
            if func.__call__(self):
                self._type = func.__name__.split('_is_', 1)[-1]
        
        if not self._type:
            prints('common_utils.columns.py', self.name)
            prints('common_utils.columns.py', 'metadata', self.metadata)
            raise TypeError('Invalide Column metadata.')
    
    def __repr__(self):
        # <calibre_plugins. __module__ .common_utils.ColumnMetadata instance at 0x1148C4B8>
        # ''.join(['<', str(self.__class__), ' instance at ', hex(id(self)),'>'])
        return ''.join(['<',repr(self.name),' {type=', self.type,'}>'])
    
    '''
        name: the key to the dictionary is:
        - for standard fields, the metadata field name.
        - for custom fields, the metadata field name prefixed by '#'
        This is done to create two 'namespaces' so the names don't clash
        
        label: the actual column label. No prefixing.
        
        datatype: the type of information in the field. Valid values are listed in
        VALID_DATA_TYPES below.
        is_multiple: valid for the text datatype. If {}, the field is to be
        treated as a single term. If not None, it contains a dict of the form
                {'cache_to_list': ',',
                'ui_to_list': ',',
                'list_to_ui': ', '}
        where the cache_to_list contains the character used to split the value in
        the meta2 table, ui_to_list contains the character used to create a list
        from a value shown in the ui (each resulting value must be strip()ed and
        empty values removed), and list_to_ui contains the string used in join()
        to create a displayable string from the list.
        
        kind == field: is a db field.
        kind == category: standard tag category that isn't a field. see news.
        kind == user: user-defined tag category.
        kind == search: saved-searches category.
        
        is_category: is a tag browser category. If true, then:
        table: name of the db table used to construct item list
        column: name of the column in the normalized table to join on
        link_column: name of the column in the connection table to join on. This
                        key should not be present if there is no link table
        category_sort: the field in the normalized table to sort on. This
                        key must be present if is_category is True
        If these are None, then the category constructor must know how
        to build the item list (e.g., formats, news).
        The order below is the order that the categories will
        appear in the tags pane.
        
        display_name: the text that is to be used when displaying the field. Column headings
        in the GUI, etc.
        
        search_terms: the terms that can be used to identify the field when
        searching. They can be thought of as aliases for metadata keys, but are only
        valid when passed to search().
        
        is_custom: the field has been added by the user.
        
        rec_index: the index of the field in the db metadata record.
        
        is_csp: field contains colon-separated pairs. Must also be text, is_multiple
        
        '''
    
    # type property
    @property
    def name(self) -> str:
        if self._custom:
            return '#' + self.label
        else:
            if self.label == 'sort':
                return 'title_sort'
            return self.label
    
    @property
    def display_name(self) -> str:
        return self.metadata.get('name', None)
    
    @property
    def description(self) -> str:
        return self.display.get('description', None)
    
    @property
    def type(self) -> str:
        return self._type
    
    @typeproperty
    def _is_names(self) -> bool:
        return bool(self.label == 'authors' or (self.datatype == 'text' and self.is_multiple and self.display.get('is_names', False)))
    
    @typeproperty
    def _is_tags(self) -> bool:
        return bool(self.label == 'tags' or (self.datatype == 'text' and self.is_multiple and not (self.label == 'authors' or self.display.get('is_names', False) or self.is_csp)))
    
    @typeproperty
    def _is_title(self) -> bool:
        return bool(self.label == 'title' or (self.datatype == 'comments' and self.display.get('interpret_as', None) == 'short-text'))
    
    @typeproperty
    def _is_text(self) -> bool:
        return bool(self.label not in ['comments', 'title'] and self.datatype == 'text' and not self.is_multiple)
    
    @typeproperty
    def _is_series(self) -> bool:
        return bool(self.datatype == 'series')
    
    @typeproperty
    def _is_float(self) -> bool:
        return bool(self.label == 'size' or (self.datatype == 'float' and self._src_is_custom and self.label != 'series_index'))
    
    @typeproperty
    def _is_series_index(self) -> bool:
        return bool(self.label == 'series_index' or (self.datatype == 'float' and not self._src_is_custom and self.label != 'size'))
    
    @typeproperty
    def _is_integer(self) -> bool:
        return bool(self.datatype == 'int' and self.label != 'cover')
    
    @typeproperty
    def _is_cover(self) -> bool:
        return bool(self.label == 'cover')
    
    @typeproperty
    def _is_datetime(self) -> bool:
        return bool(self.datatype == 'datetime')
    
    @typeproperty
    def _is_rating(self) -> bool:
        return bool(self.datatype == 'rating')
    
    @typeproperty
    def _is_bool(self) -> bool:
        return bool(self.datatype == 'bool')
    
    @typeproperty
    def _is_enumeration(self) -> bool:
        return bool(self.datatype == 'enumeration')
    
    @property
    def enum_values(self) -> List[str]:
        if self._is_enumeration:
            rslt = self.display.get('enum_values', [])
            rslt.insert(0, '')
            return rslt
        else:
            return None
    
    @property
    def enum_colors(self) -> List[str]:
        if self._is_enumeration:
            return self.display.get('enum_colors', None)
        else:
            return None
    
    @property
    def _is_comments(self) -> bool:
        return bool(self.label == 'comments' or (self.datatype == 'comments' and self.display.get('interpret_as', None) != 'short-text'))
    
    @typeproperty
    def _is_html(self) -> bool:
        return bool(self.label == 'comments' or (self._is_comments and self.display.get('interpret_as', None) == 'html'))
    
    @typeproperty
    def _is_markdown(self) -> bool:
        return bool(self._is_comments and self.display.get('interpret_as', None) == 'markdown')

    @typeproperty
    def _is_long_text(self) -> bool:
        return bool(self._is_comments and self.display.get('interpret_as', None)== 'long-text')
    
    @property
    def is_composite(self) -> bool:
        return bool(self.datatype == 'composite')
    
    @typeproperty
    def _is_composite_text(self) -> bool:
        return bool(self.is_composite and self.is_multiple)
    
    @typeproperty
    def _is_composite_tag(self) -> bool:
        return bool(self.is_composite and not self.is_multiple)
    
    @typeproperty
    def _is_identifiers(self) -> bool:
        return bool(self.is_csp)
    
    @typeproperty
    def _is_news(self) -> bool:
        return bool(self.label == 'news')
    
    # others
    @property
    def heading_position(self) -> str:
        # 'hide', 'above', 'side'
        if self._is_comments:
            return self.display.get('heading_position', None)
        else:
            return None
    
    @property
    def use_decorations(self) -> str:
        # 'hide', 'above', 'side'
        if self._is_text or self._is_enumeration or self._is_composite_text:
            return self.display.get('use_decorations', None)
        else:
            return None
    
    @property
    def allow_half_stars(self) -> bool:
        if self._is_rating:
            return bool(self.display.get('allow_half_stars', False))
        else:
            return None
    
    @property
    def composite_sort(self) -> str:
        if self.is_composite:
            return self.display.get('composite_sort', None)
        else:
            return None
    
    @property
    def composite_make_category(self) -> bool:
        if self.is_composite:
            return self.display.get('make_category', None)
        else:
            return None
    
    @property
    def composite_contains_html(self) -> bool:
        if self.is_composite:
            return self.display.get('contains_html', None)
        else:
            return None
    
    @property
    def composite_template(self) -> str:
        if self.is_composite:
            return self.display.get('composite_template', None)
        else:
            return None
    
    @property
    def number_format(self) -> str:
        if self._is_float:
            return self.display.get('number_format', None)
        else:
            return None
    
    @property
    def table(self) -> str:
        return self.metadata.get('table', None)
    
    @property
    def column(self) -> str:
        return self.metadata.get('column', None)
    
    @property
    def datatype(self) -> str:
        return self.metadata.get('datatype', None)
    
    @property
    def kind(self) -> str:
        return self.metadata.get('kind', None)
    
    @property
    def search_terms(self) -> str:
        return self.metadata.get('search_terms', None)
    
    @property
    def label(self) -> str:
        return self.metadata.get('label', None)
    
    @property
    def colnum(self) -> int:
        return self.metadata.get('colnum', None)
    
    @property
    def display(self) -> str:
        return self.metadata.get('display', None)
    
    @property
    def is_custom(self) -> bool:
        return self._custom
    
    @property
    def _src_is_custom(self) -> str:
        return self.metadata.get('is_custom', None)
        # the custom series index are not marked as custom a internal bool is nesecary
    
    @property
    def is_category(self) -> bool:
        return self.metadata.get('is_category', False)
    
    @property
    def is_multiple(self) -> bool:
        return self._multiple is not None
    
    @property
    def multiple(self) -> bool:
        return self._multiple
    
    @property
    def link_column(self) -> str:
        return self.metadata.get('link_column', None)
    
    @property
    def category_sort(self)-> str:
        return self.metadata.get('category_sort', None)
    
    @property
    def rec_index(self)-> int:
        return self.metadata.get('rec_index', None)
    
    @property
    def is_editable(self) -> bool:
        return self.metadata.get('is_editable', False)
    
    @property
    def is_csp(self) -> bool:
        '''Colon-Separated Pairs, field identifiers'''
        return self.metadata.get('is_csp', False)


def _test_is_custom(column: ColumnMetadata, only_custom: Optional[bool]) -> bool:
    '''
    only_custom:
        True= Only custom
        False= Only default
        None= Both
    '''
    
    if only_custom is True:
        return column.is_custom
    elif only_custom is False:
        return not column.is_custom
    else:
        return True


def _test_include_composite(column: ColumnMetadata, only_custom: Optional[bool]=None, include_composite: Optional[bool]=False) -> bool:
    if not include_composite and column.is_composite:
        return False
    elif include_composite and only_custom is None:
        return True
    else:
        return _test_is_custom(column, only_custom)


def get_all_columns(only_custom: Optional[bool]=None, include_composite: Optional[bool]=False) -> Dict[str, ColumnMetadata]:
    '''
    only_custom:
        True= Only custom
        False= Only default
        None= Both
    '''
    def predicate(column):
        return _test_include_composite(column, only_custom=only_custom, include_composite=include_composite)
    return get_columns_where(predicate)


def get_column_from_name(name: str) -> ColumnMetadata:
    'Get the column with the specified name, else None'
    def predicate(column: ColumnMetadata):
        return column.name == name
    for v in get_columns_where(predicate).values():
        return v
    return None


def _get_columns_type(type, only_custom: Optional[bool]=None) -> Dict[str, ColumnMetadata]:
    def predicate(column: ColumnMetadata):
        if type == column.type:
            return _test_is_custom(column, only_custom)
        else:
            return False
    
    return get_columns_where(predicate)


def get_categories(only_custom: Optional[bool]=None, include_composite: Optional[bool]=None) -> Dict[str, ColumnMetadata]:
    def predicate(column: ColumnMetadata):
        if column.is_category:
            return _test_include_composite(column, only_custom=only_custom, include_composite=include_composite)
    return get_columns_where(predicate)


# get type
def get_names(only_custom: Optional[bool]=None) -> Dict[str, ColumnMetadata]:
    '''
    only_custom:
        True= Only custom
        False= Only default
        None= Both
    '''
    return _get_columns_type(ColumnTypes.names, only_custom)


def get_tags(only_custom: Optional[bool]=None) -> Dict[str, ColumnMetadata]:
    '''
    only_custom:
        True= Only custom
        False= Only default
        None= Both
    '''
    return _get_columns_type(ColumnTypes.tags, only_custom)


def get_enumeration(only_custom: Optional[bool]=None) -> Dict[str, ColumnMetadata]:
    '''
    only_custom:
        True= Only custom
        False= Only default
        None= Both
    '''
    return _get_columns_type(ColumnTypes.enumeration, only_custom)


def get_float(only_custom: Optional[bool]=None) -> Dict[str, ColumnMetadata]:
    '''
    only_custom:
        True= Only custom
        False= Only default
        None= Both
    '''
    return _get_columns_type(ColumnTypes.float, only_custom)


def get_datetime(only_custom: Optional[bool]=None) -> Dict[str, ColumnMetadata]:
    '''
    only_custom:
        True= Only custom
        False= Only default
        None= Both
    '''
    return _get_columns_type(ColumnTypes.datetime, only_custom)


def get_rating(only_custom: Optional[bool]=None) -> Dict[str, ColumnMetadata]:
    '''
    only_custom:
        True= Only custom
        False= Only default
        None= Both
    '''
    return _get_columns_type(ColumnTypes.rating, only_custom)


def get_series(only_custom: Optional[bool]=None) -> Dict[str, ColumnMetadata]:
    '''
    only_custom:
        True= Only custom
        False= Only default
        None= Both
    '''
    return _get_columns_type(ColumnTypes.series, only_custom)


def get_series_index(only_custom: Optional[bool]=None) -> Dict[str, ColumnMetadata]:
    '''
    only_custom:
        True= Only custom
        False= Only default
        None= Both
    '''
    return _get_columns_type(ColumnTypes.series_index, only_custom)


def get_text(only_custom: Optional[bool]=None) -> Dict[str, ColumnMetadata]:
    '''
    only_custom:
        True= Only custom
        False= Only default
        None= Both
    '''
    return _get_columns_type(ColumnTypes.text, only_custom)


def get_bool(only_custom: Optional[bool]=None) -> Dict[str, ColumnMetadata]:
    '''
    only_custom:
        True= Only custom
        False= Only default
        None= Both
    '''
    return _get_columns_type(ColumnTypes.bool, only_custom)


def get_html(only_custom: Optional[bool]=None) -> Dict[str, ColumnMetadata]:
    '''
    only_custom:
        True= Only custom
        False= Only default
        None= Both
    '''
    return _get_columns_type(ColumnTypes.html, only_custom)


def get_markdown(only_custom: Optional[bool]=None) -> Dict[str, ColumnMetadata]:
    '''
    only_custom:
        True= Only custom
        False= Only default
        None= Both
    '''
    return _get_columns_type(ColumnTypes.markdown, only_custom)


def get_long_text(only_custom: Optional[bool]=None) -> Dict[str, ColumnMetadata]:
    '''
    only_custom:
        True= Only custom
        False= Only default
        None= Both
    '''
    return _get_columns_type(ColumnTypes.long_text, only_custom)


def get_title(only_custom: Optional[bool]=None) -> Dict[str, ColumnMetadata]:
    '''
    only_custom:
        True= Only custom
        False= Only default
        None= Both
    '''
    return _get_columns_type(ColumnTypes.title, only_custom)


def get_composite_text(only_custom: Optional[bool]=None) -> Dict[str, ColumnMetadata]:
    '''
    only_custom:
        True= Only custom
        False= Only default
        None= Both
    '''
    return _get_columns_type(ColumnTypes.composite_text, only_custom)


def get_composite_tag(only_custom: Optional[bool]=None) -> Dict[str, ColumnMetadata]:
    '''
    only_custom:
        True= Only custom
        False= Only default
        None= Both
    '''
    return _get_columns_type(ColumnTypes.composite_tag, only_custom)


def get_possible_fields() -> Tuple[List[str], List[str]]:
    '''
    Get the fields of the current library
    
    return: all_fields, writable_fields
    '''
    def predicate(column):
        if column.name not in ['id' , 'au_map', 'timestamp', 'formats', 'ondevice', 'news', 'series_sort', 'path', 'in_tag_browser'] and column.type:
            return True
        else:
            return False
    
    columns = get_columns_where(predicate)
    
    all_fields = [cc.name for cc in columns.values()]
    all_fields.sort()
    all_fields.insert(0, '{template}')
    writable_fields = [cc.name for cc in columns.values() if not cc.is_composite]
    writable_fields.sort()
    return all_fields, writable_fields


def get_possible_columns() -> List[str]:
    '''
    Get the name of the columns in the library
    
    return: list(str)
    '''
    standard = ['title', 'authors', 'tags', 'series', 'publisher', 'pubdate', 'rating', 'languages', 'last_modified', 'timestamp', 'comments', 'author_sort', 'title_sort', 'marked']
    if CALIBRE_VERSION >= (6,17,0):
        standard += ['id', 'path']
    
    def predicate(column):
        if column.is_custom and not (column.is_composite or column._is_series_index):
            return True
        else:
            return False
    
    return standard + sorted(get_columns_where(predicate).keys())


def get_columns_from_dict(src_dict: FieldMetadata, predicate=None) -> Dict[str, ColumnMetadata]:
    'Convert a FieldMetadata dict to a ColumnMetadata dict'
    def _predicate(column: ColumnMetadata):
        return True
    predicate = predicate or _predicate
    return {cm.name:cm for cm in [ColumnMetadata(fm, k.startswith('#')) for k,fm in src_dict.items() if fm.get('label', None)] if predicate(cm)}


def get_columns_where(predicate: Callable[[ColumnMetadata], bool]=None) -> Dict[str, ColumnMetadata]:
    'Get ColumnMetadata of the currend library'
    if current_db():
        return get_columns_from_dict(current_db().field_metadata, predicate)
    else:
        return {}


if __name__ == '__main__':
    def wait_exit():
        input('Press any key to exit…')
        exit()
    
    if len(sys.argv) <= 1:
        prints('Need to parse a library path as arguments')
        wait_exit()
    
    path = os.path.abspath(sys.argv[1])
    if not os.path.exists(path):
        prints('The path "'+path+'" don\'t exists')
        exit()
    
    prints('Loading library:', path)
    def current_db():
        return current_db.db
    current_db.db = LibraryDatabase(library_path=path, read_only=True)
    prints()
    
    prints('All columns:')
    for k,c in get_all_columns().items():
        prints(k,c)
    prints()
    
    prints('All functions:')
    for f in [get_all_columns,
              get_names, get_tags, get_enumeration, get_float, get_datetime, get_rating, get_title,
              get_series, get_series_index, get_text, get_bool, get_html, get_markdown, get_long_text,
              get_composite_text, get_composite_tag, get_categories]:
        prints(f.__name__, list(f().keys()))
        prints()
    
    for f in [get_possible_fields, get_possible_columns]:
        prints(f.__name__, f())
        prints()
    
    current_db().close()
    wait_exit()
