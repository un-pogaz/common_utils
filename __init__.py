#!/usr/bin/env python
# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2011, Grant Drake <grant.drake@gmail.com> ; 2022, un_pogaz <un.pogaz@gmail.com>'
__docformat__ = 'restructuredtext en'


try:
    load_translations()
except NameError:
    pass # load_translations() added in calibre 1.9

from collections import defaultdict, OrderedDict
from functools import partial
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import os
import copy

try:
    from qt.core import (
        QApplication, QIcon, QPixmap,
    )
except ImportError:
    from PyQt5.Qt import (
        QApplication, QIcon, QPixmap,
    )

from calibre import prints
from calibre.constants import DEBUG, iswindows, numeric_version as CALIBRE_VERSION
from calibre.customize.ui import find_plugin
from calibre.gui2 import show_restart_warning
from calibre.db.legacy import LibraryDatabase
from calibre.gui2.ui import Main
from calibre.utils.monotonic import monotonic

from calibre.utils.config import config_dir, JSONConfig, DynamicConfig

def get_gui() -> Main:
    from calibre.gui2.ui import get_gui
    return get_gui()

GUI = get_gui()

def current_db() -> LibraryDatabase:
    return getattr(GUI,'current_db', None)


PLUGIN_CLASSE = None
def get_plugin_attribut(name: str, default: Optional[Any]=None) -> Any:
    """Retrieve a attribut on the main plugin class"""
    global PLUGIN_CLASSE
    if not PLUGIN_CLASSE:
        import importlib
        from calibre.customize import Plugin
        #Yes, it's very long for a one line. It's seems crazy, but it's fun and it works
        plugin_classes = [ obj for obj in importlib.import_module('.'.join(__name__.split('.')[:-1])).__dict__.values() if isinstance(obj, type) and issubclass(obj, Plugin) and obj.name != 'Trivial Plugin' ]
        
        plugin_classes.sort(key=lambda c:(getattr(c, '__module__', None) or '').count('.'))
        PLUGIN_CLASSE = plugin_classes[0]
    
    return getattr(PLUGIN_CLASSE, name, default)

ROOT = __name__.split('.')[1]

# Global definition of our plugin name. Used for common functions that require this.
PLUGIN_NAME = get_plugin_attribut('name', ROOT)
PREFS_NAMESPACE = get_plugin_attribut('PREFS_NAMESPACE', ROOT)
DEBUG_PRE = get_plugin_attribut('DEBUG_PRE', PLUGIN_NAME)

# Plugin instance.
PLUGIN_INSTANCE = find_plugin(PLUGIN_NAME)

BASE_TIME = monotonic()
def debug_print(*args, **kw):
    '''
    Print a output assigned to the plugin
    
    **kw
    sep: separator between each *args
    end: end of line character
    
    pre: prefix to the printed line
         else use DEBUG_PRE or the plugin name
    
    file: output file, else stdout
    flush: flush buffer
    '''
    if DEBUG:
        pre = kw.get('pre', DEBUG_PRE)
        time_format = kw.get('time', None)
        if time_format:
            if not isinstance(time_format, str):
                time_format = '.2f'
            try:
                time_format = (monotonic()-BASE_TIME).__format__(time_format)
            except:
                time_format = (monotonic()-BASE_TIME).__format__('.2f')
            time_format =  f'[{time_format}]'
        
        if pre or time_format:
            if pre and time_format:
                pre = f'{time_format} {pre}'
            
            if pre:
                if not pre.endswith(':'):
                    pre = pre+':'
            else:
                pre = time_format+' '
            
            prints(pre, *args, **kw)
        else:
            prints(*args, **kw)
        #prints(DEBUG_PRE,'[{:.2f}]'.format(monotonic()-BASE_TIME),':', *args, **kw)


# ----------------------------------------------
#          Icon Management functions
# ----------------------------------------------

THEME_COLOR = ['', 'dark', 'light']

def get_theme_name() -> str:
    """Get the theme color of Calibre"""
    if CALIBRE_VERSION >= (6,0,0):
        return THEME_COLOR[1] if QApplication.instance().is_dark_theme else THEME_COLOR[2]
    return THEME_COLOR[0]

def linux(path: str) -> str:
    return path.replace('\\', '/')

def get_icon_themed_names(icon_name) -> List[str]:
    # images/<icon_name>-for-dark-theme.png
    # images/dark/<icon_name>.png
    # images/<icon_name>.png
    rslt = []
    theme_name = get_theme_name()
    if theme_name:
        path, ext = os.path.splitext(linux(icon_name).strip('/'))
        name = os.path.basename(path)
        dir = os.path.dirname(path).strip('/')
        rslt.append(f'{dir}/{name}-for-{theme_name}-theme{ext}')
        rslt.append(f'{dir}/{theme_name}/{name}{ext}')
    
    rslt.append(icon_name)
    return rslt

if not hasattr(QIcon, 'ic'):
    QIcon.ic = lambda x: QIcon(I(x))

def get_icon(icon_name: str) -> QIcon:
    """
    Retrieve a QIcon for the named image from the zip file if it exists,
    or if not then from Calibre's image cache.
    """
    if isinstance(icon_name, QIcon):
        return icon_name
    
    if icon_name:
        icon_name = linux(icon_name).strip('/')
        if not icon_name.startswith('images/'):
            # We know this is definitely not an icon belonging to this plugin
            return QIcon.ic(icon_name)
        
        rslt = PLUGIN_RESOURCES.ICONS.get(icon_name, None)
        if not rslt:
            pixmap = get_pixmap(icon_name)
            if pixmap:
                rslt = QIcon(pixmap)
                PLUGIN_RESOURCES.ICONS[icon_name] = rslt
        
        if rslt:
            return rslt
    
    return QIcon()

def get_pixmap(icon_name: str) -> QPixmap:
    """
    Retrieve a QPixmap for the named image
    Any icons belonging to the plugin must be prefixed with 'images/'
    """
    
    if icon_name:
        icon_name = linux(icon_name).strip('/')
        
        def from_resources(search_name):
            raw = None
            for name in get_icon_themed_names(search_name):
                try:
                    raw = I(name, data=True, allow_user_override=True)
                except:
                    pass
                
                if raw:
                    rslt = QPixmap()
                    rslt.loadFromData(raw)
                    return rslt
            return None
        
        if not icon_name.startswith('images/'):
            # We know this is definitely not an icon belonging to this plugin
            return from_resources(icon_name)
        
        rslt = PLUGIN_RESOURCES.PIXMAP.get(icon_name, None)
        if not rslt:
            # test user overide
            rslt = from_resources(os.path.join(PLUGIN_NAME, icon_name.split('/', 1)[-1]))
            if not rslt:
                # inside plugin ZIP
                for name in get_icon_themed_names(icon_name):
                    if name in PLUGIN_RESOURCES:
                        rslt = QPixmap()
                        rslt.loadFromData(PLUGIN_RESOURCES[name])
                        break
            
            if rslt:
                PLUGIN_RESOURCES.PIXMAP[icon_name] = rslt
        
        if rslt:
            return rslt

def local_resource(*subfolders: Optional[List[str]]) -> str:
    """
    Returns a path to the user's local resources folder
    If a subfolder name parameter is specified, appends this to the path
    """
    rslt = os.path.join(config_dir, 'resources', *[f.replace('/','-').replace('\\','-') for f in subfolders])
    
    if iswindows:
        rslt = os.path.normpath(rslt)
    return linux(rslt)
local_resource.IMAGES = local_resource('images')+'/'

def _class_name(obj, inside) -> str:
    if not isinstance(obj, type):
        obj.__class__
    return obj.__name__+'('+inside+')'

class PathDict(dict):
    'dict than contain only path string as keys'
    
    def _k(self, __key):
        if not isinstance(__key, str):
            raise KeyError("Key can only can only be str. Type pased: "+ type(__key).__name__)
        if not __key:
            raise KeyError("Key can't be a empty string")
        return linux(__key)
    
    def __contains__(self, __key: str) -> bool:
        return dict.__contains__(self, self._k(__key))
    
    def __setitem__(self, __key: str, __value):
        return dict.__setitem__(self, self._k(__key), __value)
    
    def __getitem__(self, __key: str) -> Any:
        return dict.__getitem__(self, self._k(__key))
    
    def __delitem__(self, __key):
        return dict.__delitem__(self, self._k(__key))
    
    def get(self, __key, __default) -> Any:
        return dict.get(self, self._k(__key), __default)
    
    def pop(self, __key, __default: Any=Any) -> Any:
        if __key in self:
            return dict.pop(__key)
        if __default == Any:
            raise KeyError(__key)
        else:
            return __default

class ZipResources(PathDict):
    def __init__(self, zip_path: str, preload_keys: List[str]=None):
        PathDict.__init__(self)
        self.zip_path = linux(zip_path)
        self.load_many(preload_keys)
    
    def __getitem__(self, __key: str) -> Union[bytes, Any]:
        if __key in self:
            return PathDict.__getitem__(self, __key)
        else:
            data = self.load(__key)
            if data is None:
                raise KeyError(__key)
            return data
    
    def __str__(self):
        return _class_name(self, repr(self.zip_path)+', '+str(list(self.keys())))
    
    def __repr__(self):
        return _class_name(self,'zip_path='+ repr(self.zip_path)+', '+repr(list(self.keys())))
    
    def load(self, key: str) -> Union[bytes, Any]:
        return self.load_many([key]).get(key, None)
    
    def load_many(self, keys: Optional[List[str]]) -> Dict[str, Union[bytes, str]]:
        names = set(linux(n) for n in (keys or []) if n)
        rslt = {}
        from calibre.utils.zipfile import ZipFile
        with ZipFile(self.zip_path, 'r') as zf:
            for entry in zf.namelist():
                if entry in names:
                    data = zf.read(entry)
                    self[entry] = data
                    rslt[entry] = data
        return rslt

class PluginResources(ZipResources):
    def __init__(self, preload_keys: List[str]=None):
        from calibre.utils.zipfile import ZipFile
        ZipResources.__init__(self, PLUGIN_INSTANCE.plugin_path)
        preload_keys = [linux(k) for k in preload_keys or []]
        
        self.ICONS = PathDict()
        self.PIXMAP = PathDict()
        
        with ZipFile(self.zip_path, 'r') as zf:
            for entry in zf.namelist():
                if entry.startswith('images/') and os.path.splitext(entry)[1].lower() == '.png' or entry in preload_keys:
                    self.__setitem__(entry, zf.read(entry))
    
    def __str__(self):
        return _class_name(self, str(list(self.keys())))
    
    def __repr__(self):
        return _class_name(self, repr(list(self.keys())))

# Global definition of our plugin resources. Used to share between the xxxAction and xxxBase
# classes if you need any zip images to be displayed on the configuration dialog.
PLUGIN_RESOURCES = PluginResources()


# ----------------------------------------------
#               Functions
# ----------------------------------------------

def get_date_format(tweak_name: str='gui_timestamp_display_format', default_fmt: Optional[str]='dd MMM yyyy') -> str:
    from calibre.utils.config import tweaks
    format = tweaks[tweak_name]
    if format is None:
        format = default_fmt
    return format

def truncate_title(title: str, max_length: int=75) -> str:
    return (title[:max_length] + '…') if len(title) > max_length else title

def get_image_map(subdir: str=None) -> Dict[str, QIcon]:
    rslt = {}
    resources_dir = os.path.join(config_dir, 'resources', 'images', subdir or '')
    if os.path.exists(resources_dir):
        # Get the names of any .png images in this directory
        for f in sorted(os.listdir(resources_dir)):
            if f.lower().endswith('.png'):
                name = os.path.basename(f)
                rslt[linux(name)] = get_icon(name)
    
    return rslt

def split_long_text(text: str, max_length: int=70) -> List[str]:
    'Split a long text to various lines with a max lenght for each one'
    text_lenght = len(text)
    if text_lenght < max_length+10:
        return [text]
    
    def split_to_space(src_text: str, lentgh: int) -> Tuple[str, str]:
        if len(src_text) < lentgh:
            return src_text, None
        
        end = src_text[lentgh:]
        if ' ' not in end:
            return src_text, None
        
        split_lentgh = lentgh + end.index(' ')
        return src_text[:split_lentgh], src_text[split_lentgh+1:]
    
    for spliting in range(2, 11):
        length_attempt = text_lenght // spliting
        rslt = []
        
        adding_line, next_line = None, text
        while next_line:
            adding_line, next_line = split_to_space(next_line, length_attempt)
            rslt.append(adding_line)
        
        to_long = False
        for l in rslt:
            if len(l) > max_length:
                to_long = True
                break
        
        if not to_long:
            break
    
    return rslt

def return_line_long_text(text: str, max_length: int=70) -> str:
    return '\n'.join(split_long_text(text=text, max_length=max_length))

# ----------------------------------------------
#               Ohters
# ----------------------------------------------

def has_restart_pending(show_warning=True, msg_warning=None) -> bool:
    restart_pending = GUI.must_restart_before_config
    if restart_pending and show_warning:
        msg = msg_warning or _('You cannot configure this plugin before calibre is restarted.')
        if show_restart_warning(msg):
            GUI.quit(restart=True)
    return restart_pending


def duplicate_entry(lst: Iterable) -> List:
    'retrive the entry in double inside a iterable'
    return list(set([x for x in lst if lst.count(x) > 1]))

# Simple Regex
class regex():
    
    import re as _re
    def __init__(self, flag=None):
        
        #set the default flag
        self.flag = flag
        if not self.flag:
            self.flag = regex._re.ASCII + regex._re.MULTILINE + regex._re.DOTALL
            # calibre 5 // re.ASCII for Python3 only
    
    def __call__(self, flag=None):
        return self.__class__(flag)
    
    def match(self, pattern, string, flag=None):
        flag = flag or self.flag
        return regex._re.fullmatch(pattern, string, flag)
    
    def search(self, pattern, string, flag=None):
        flag = flag or self.flag
        return regex._re.search(pattern, string, flag)
    
    def searchall(self, pattern, string, flag=None):
        flag = flag or self.flag
        return regex._re.finditer(pattern, string, flag)
    
    def split(self, pattern, string, maxsplit=0, flag=None):
        flag = flag or self.flag
        return regex._re.split(pattern, string, maxsplit, flag)
    
    def simple(self, pattern, repl, string, flag=None):
        flag = flag or self.flag
        return regex._re.sub(pattern, repl, string, 0, flag)
    
    def loop(self, pattern, repl, string, flag=None):
        flag = flag or self.flag
        i = 0
        while self.search(pattern, string, flag):
            if i > 1000:
                raise regex.Exception('the pattern and substitution string caused an infinite loop', pattern, repl)
            string = self.simple(pattern, repl, string, flag)
            i+=1
            
        return string
    
    class Exception(BaseException):
        def __init__(self, msg, pattern=None, repl=None):
            self.pattern = pattern
            self.repl = repl
            self.msg = msg
        
        def __str__(self):
            return self.msg
regex = regex()
"""Easy Regex"""

class PREFS_json(JSONConfig):
    """
    Use plugin name to create a JSONConfig file
    to store the preferences for plugin
    """
    def __init__(self):
        self._is_init = True
        JSONConfig.__init__(self, 'plugins/'+PLUGIN_NAME)
        self._is_init = False
    
    def __getitem__(self, key):
        d = self.defaults.get(key, None)
        if isinstance(d, dict):
            d = d.copy()
            d.update(JSONConfig.get(self, key, {}))
            return d
        else:
            return JSONConfig.__getitem__(self, key)
    
    def update(self, other, **kvargs):
        JSONConfig.update(self, other, **kvargs)
        if not self._is_init:
            self.commit()
    
    def __call__(self):
        self.refresh()
        return self
    
    def copy(self):
        """
        get a copy dict of this instance
        """
        rslt = {copy.deepcopy(k):copy.deepcopy(v) for k,v in self.items()}
        rslt.update({copy.deepcopy(k):copy.deepcopy(v) for k,v in self.defaults.items() if k not in rslt})
        return rslt

class PREFS_dynamic(DynamicConfig):
    """
    Use plugin name to create a DynamicConfig file
    to store the preferences for plugin
    """
    def __init__(self):
        self._no_commit = False
        DynamicConfig.__init__(self, 'plugins/'+PLUGIN_NAME)
    
    def commit(self):
        if self._no_commit:
            return
        DynamicConfig.commit(self)
    
    def __enter__(self):
        self._no_commit = True

    def __exit__(self, *args):
        self._no_commit = False
        self.commit()
    
    def __call__(self):
        self.refresh()
        return self
    
    def update(self, other, **kvargs):
        DynamicConfig.update(self, other, **kvargs)
        self.commit()
    
    def copy(self):
        """
        get a copy dict of this instance
        """
        rslt = {}
        for k,v in self.items():
            rslt[copy.deepcopy(k)] = copy.deepcopy(v)
        
        for k, v in self.defaults.items():
            if k not in rslt:
                rslt[k] = copy.deepcopy(v)
        return rslt

class PREFS_library(dict):
    """
    Create a dictionary of preference stored in the library
    
    Defined a custom namespaced at the root of __init__.py // __init__.PREFS_NAMESPACE
    """
    def __init__(self, key='settings', defaults={}):
        dict.__init__(self)
        self._no_commit = False
        self._db = None
        self.key = key if key else ''
        self.defaults = defaults if defaults else {}
        
        if not isinstance(key, str):
            raise TypeError("The 'key' for the namespaced preference is not a string")
            
        if not isinstance(defaults, dict):
            raise TypeError("The 'defaults' for the namespaced preference is not a dict")
        
        self._namespace = PREFS_NAMESPACE
        
        self.refresh()
    
    @property
    def namespace(self):
        return self._namespace
    
    def __getitem__(self, key):
        self.refresh()
        try:
            d = self.defaults.get(key, None)
            if isinstance(d, dict):
                d = d.copy()
                d.update(dict.get(self, key, {}))
                return d
            else:
                return dict.__getitem__(self, key)
        except KeyError:
            return self.defaults[key]
    
    def get(self, key, default=None):
        self.refresh()
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return self.defaults.get(key, default)
    
    def __setitem__(self, key, val):
        self.refresh()
        dict.__setitem__(self, key, val)
        self.commit()
    
    def set(self, key, val):
        self.__setitem__(key, val)
    
    def __delitem__(self, key):
        self.refresh()
        try:
            dict.__delitem__(self, key)
        except KeyError:
            pass  # ignore missing keys
        self.commit()
    
    def __str__(self):
        self.refresh()
        return dict.__str__(self.copy())
    
    def _check_db(self):
        if current_db() and self._db != current_db():
            self._db = current_db()
        return self._db != None
    
    def refresh(self):
        if self._check_db():
            rslt = self._db.prefs.get_namespaced(self.namespace, self.key, {})
            self._no_commit = True
            self.clear()
            self.update(rslt)
            self._no_commit = False
    
    def commit(self):
        if self._no_commit:
            return
        
        if self._check_db():
            self._db.prefs.set_namespaced(self.namespace, self.key, self.copy())
            self.refresh()
    
    def __enter__(self):
        self.refresh()
        self._no_commit = True
    
    def __exit__(self, *args):
        self._no_commit = False
        self.commit()
    
    def __call__(self):
        self.refresh()
        return self
    
    def update(self, other, **kvargs):
        dict.update(self, other, **kvargs)
        self.commit()
    
    def copy(self):
        """
        get a copy dict of this instance
        """
        rslt = {copy.deepcopy(k):copy.deepcopy(v) for k,v in self.items()}
        rslt.update({copy.deepcopy(k):copy.deepcopy(v) for k,v in self.defaults.items() if k not in rslt})
        return rslt
