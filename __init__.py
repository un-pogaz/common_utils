#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Grant Drake <grant.drake@gmail.com> ; 2022, un_pogaz <un.pogaz@gmail.com>'
__docformat__ = 'restructuredtext en'


# python3 compatibility
from six.moves import range
from six import text_type as unicode
from polyglot.builtins import iteritems, itervalues

try:
    load_translations()
except NameError:
    pass # load_translations() added in calibre 1.9

from collections import defaultdict, OrderedDict
from functools import partial

import os, sys, copy, time

from calibre import prints
from calibre.constants import DEBUG, iswindows, numeric_version as calibre_version
from calibre.customize.ui import find_plugin
from calibre.gui2 import show_restart_warning
from calibre.gui2.ui import get_gui
from calibre.gui2.widgets2 import Dialog
from calibre.utils.config import config_dir, JSONConfig, DynamicConfig

GUI = get_gui()


PLUGIN_CLASSE = None
def get_plugin_attribut(name, default=None):
    """Retrieve a attribut on the main plugin class"""
    global PLUGIN_CLASSE
    if not PLUGIN_CLASSE:
        import importlib
        from calibre.customize import Plugin
        #Yes, it's very long for a one line. It's seems crazy, but it's fun and it works
        plugin_classes = [ obj for obj in itervalues(importlib.import_module('.'.join(__name__.split('.')[:-1])).__dict__) if isinstance(obj, type) and issubclass(obj, Plugin) and obj.name != 'Trivial Plugin' ]
        
        plugin_classes.sort(key=lambda c:(getattr(c, '__module__', None) or '').count('.'))
        PLUGIN_CLASSE = plugin_classes[0]
    
    return getattr(PLUGIN_CLASSE, name, default)

ROOT = __name__.split('.')[-2]

# Global definition of our plugin name. Used for common functions that require this.
PLUGIN_NAME = get_plugin_attribut('name', ROOT)
PREFS_NAMESPACE = get_plugin_attribut('PREFS_NAMESPACE', ROOT)
DEBUG_PRE = get_plugin_attribut('DEBUG_PRE', PLUGIN_NAME)

# Plugin instance.
PLUGIN_INSTANCE = find_plugin(PLUGIN_NAME)

BASE_TIME = time.time()
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
        if not pre:
            prints(*args, **kw)
        else:
            if not pre.endswith(':'):
                pre = pre+':'
            prints(pre, *args, **kw)
        #prints('DEBUG', DEBUG_PRE,'({:.3f})'.format(time.time()-BASE_TIME),':', *args)


# ----------------------------------------------
#          Icon Management functions
# ----------------------------------------------

try:
    from qt.core import (
        QApplication, QIcon, QPixmap,
    )
except ImportError:
    from PyQt5.Qt import (
        QApplication, QIcon, QPixmap,
    )

class ZipResources(dict):
    def __init__(self, zip_path, preload_keys=[]):
        dict.__init__(self)
        self.zip_path = zip_path
        self.load_many(preload_keys)
    
    def __getitem__(self, __key):
        if __key in self:
            return dict.__getitem__(self, __key)
        else:
            return self.load_many([__key])[__key]
    
    def __str__(self):
        return self.__class__.__name__+'('+ repr(self.zip_path)+', '+str(list(self.keys()))+')'
    
    def __repr__(self):
        return self.__class__.__name__+'(zip_path='+ repr(self.zip_path)+', '+repr(list(self.keys()))+')'
    
    def load(self, name):
        return self.load_many([name]).get(name, None)
    def load_many(self, names):
        names = names or []
        rslt = {}
        from calibre.utils.zipfile import ZipFile
        with ZipFile(self.zip_path, 'r') as zf:
            for entry in zf.namelist():
                if entry in names:
                    data = zf.read(entry)
                    self.__setitem__(entry, data)
                    rslt[entry] = data
        return rslt

class PluginResources(ZipResources):
    def __init__(self, preload_keys=[]):
        from calibre.utils.zipfile import ZipFile
        ZipResources.__init__(self, PLUGIN_INSTANCE.plugin_path)
        
        with ZipFile(self.zip_path, 'r') as zf:
            for entry in zf.namelist():
                if entry.startswith('images/') and os.path.splitext(entry)[1].lower() == '.png' or entry in preload_keys:
                    data = zf.read(entry)
                    self.__setitem__(entry, data)
    
    def __str__(self):
        return self.__class__.__name__+'('+str(list(self.keys()))+')'
    
    def __repr__(self):
        return self.__class__.__name__+'('+repr(list(self.keys()))+')'

# Global definition of our plugin resources. Used to share between the xxxAction and xxxBase
# classes if you need any zip images to be displayed on the configuration dialog.
PLUGIN_RESOURCES = PluginResources()


THEME_COLOR = ['', 'dark', 'light']

def get_theme_color():
    """Get the theme color of Calibre"""
    if calibre_version > (5, 90):
        return THEME_COLOR[1] if QApplication.instance().is_dark_theme else THEME_COLOR[2]
    return THEME_COLOR[0]

def get_icon_themed(icon_name, theme_color=None):
    """Apply the theme color to a path"""
    theme_color = get_theme_color() if theme_color is None else theme_color
    path, ext = os.path.splitext(icon_name)
    return (path+('' if not theme_color else '-'+ theme_color)+ext).replace('//', '/')


def get_icon(icon_name):
    """
    Retrieve a QIcon for the named image from the zip file if it exists,
    or if not then from Calibre's image cache.
    """
    def themed_icon(icon_name):
        if calibre_version < (6,0,0):
            return QIcon(I(icon_name))
        else:
            return QIcon.ic(icon_name)
    
    if icon_name:
        pixmap = get_pixmap(icon_name)
        if pixmap is None:
            # Look in Calibre's cache for the icon
            return themed_icon(icon_name)
        else:
            return QIcon(pixmap)
    return QIcon()

def get_pixmap(icon_name):
    """
    Retrieve a QPixmap for the named image
    Any icons belonging to the plugin must be prefixed with 'images/'
    """
    
    if not icon_name.startswith('images/'):
        # We know this is definitely not an icon belonging to this plugin
        pixmap = QPixmap()
        pixmap.load(I(icon_name))
        return pixmap
    
    # Build the icon_name according to the theme of the OS or Qt
    icon_themed = get_icon_themed(icon_name)
    
    if PLUGIN_NAME:
        # Check to see whether the icon exists as a Calibre resource
        # This will enable skinning if the user stores icons within a folder like:
        # ...\AppData\Roaming\calibre\resources\images\Plugin_Name\
        def get_from_local(name):
            local_images_dir = get_local_resource('images', PLUGIN_NAME)
            local_image_path = os.path.join(local_images_dir, name.replace('images/', ''))
            if os.path.exists(local_image_path):
                pxm = QPixmap()
                pxm.load(local_image_path)
                return pxm
            return None
        
        pixmap = get_from_local(icon_themed)
        if not pixmap:
            pixmap = get_from_local(icon_name)
        if pixmap:
            return pixmap
    
    ##
    # As we did not find an icon elsewhere, look within our zip resources
    global PLUGIN_RESOURCES
    def get_from_resources(name):
        if name in PLUGIN_RESOURCES:
            pxm = QPixmap()
            pxm.loadFromData(PLUGIN_RESOURCES[name])
            return pxm
        return None
    
    pixmap = get_from_resources(icon_themed)
    if not pixmap:
        pixmap = get_from_resources(icon_name)
    
    return pixmap

def get_local_resource(*subfolder):
    """
    Returns a path to the user's local resources folder
    If a subfolder name parameter is specified, appends this to the path
    """
    rslt = os.path.join(config_dir, 'resources', *[f.replace('/','-').replace('\\','-') for f in subfolder])
    
    if iswindows:
        rslt = os.path.normpath(rslt)
    return rslt

# ----------------------------------------------
#               Functions
# ----------------------------------------------

def get_date_format(tweak_name='gui_timestamp_display_format', default_fmt='dd MMM yyyy'):
    from calibre.utils.config import tweaks
    format = tweaks[tweak_name]
    if format is None:
        format = default_fmt
    return format

def truncate_title(title, length=75):
    return (title[:length] + '…') if len(title) > length else title

# ----------------------------------------------
#               Ohters
# ----------------------------------------------

def current_db():
    """Safely provides the current_db or None"""
    return getattr(GUI,'current_db', None)
    # db.library_id

def has_restart_pending(show_warning=True, msg_warning=None):
    restart_pending = GUI.must_restart_before_config
    if restart_pending and show_warning:
        msg = msg_warning or _('You cannot configure this plugin before calibre is restarted.')
        if show_restart_warning(msg):
            GUI.quit(restart=True)
    return restart_pending


def duplicate_entry(lst):
    return list(set([x for x in lst if lst.count(x) > 1]))

# Simple Regex
class regex():
    
    import re as _re
    def __init__(self, flag=None):
        
        #set the default flag
        self.flag = flag
        if not self.flag:
            if sys.version_info < (3,):
                self.flag = regex._re.MULTILINE + regex._re.DOTALL
            else:
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
    
    def update(self, other, **kvargs):
        JSONConfig.update(self, other, **kvargs)
        if not self._is_init:
            self.commit()
    
    def __call__(self):
        self.refresh()
        return self
    
    def deepcopy_dict(self):
        """
        get a deepcopy dict of this instance
        """
        rslt = {}
        for k,v in iteritems(self):
            rslt[copy.deepcopy(k)] = copy.deepcopy(v)
        
        for k, v in iteritems(self.defaults):
            if k not in rslt:
                rslt[k] = copy.deepcopy(v)
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
    
    def deepcopy_dict(self):
        """
        get a deepcopy dict of this instance
        """
        rslt = {}
        for k,v in iteritems(self):
            rslt[copy.deepcopy(k)] = copy.deepcopy(v)
        
        for k, v in iteritems(self.defaults):
            if k not in rslt:
                rslt[k] = copy.deepcopy(v)
        return rslt

class PREFS_library(dict):
    """
    Create a dictionary of preference stored in the library
    
    Defined a custom namespaced at the root of __init__.py // __init__.PREFS_NAMESPACE
    """
    def __init__(self, key='settings', defaults={}):
        self._no_commit = False
        self._db = None
        self.key = key if key else ''
        self.defaults = defaults if defaults else {}
        
        if not isinstance(key, unicode) and not isinstance(key, str):
            raise TypeError("The 'key' for the namespaced preference is not a string")
            
        if not isinstance(defaults, dict):
            raise TypeError("The 'defaults' for the namespaced preference is not a dict")
        
        self._namespace = PREFS_NAMESPACE
        
        self.refresh()
        dict.__init__(self)
    
    @property
    def namespace(self):
        return self._namespace
    
    def __getitem__(self, key):
        self.refresh()
        try:
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
        return dict.__str__(self.deepcopy_dict())
    
    def _check_db(self):
        new_db = current_db()
        if new_db and self._db != new_db:
            self._db = new_db
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
            self._db.prefs.set_namespaced(self.namespace, self.key, self.deepcopy_dict())
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
    
    def deepcopy_dict(self):
        """
        get a deepcopy dict of this instance
        """
        rslt = {}
        for k,v in iteritems(self):
            rslt[copy.deepcopy(k)] = copy.deepcopy(v)
        
        for k, v in iteritems(self.defaults):
            if k not in rslt:
                rslt[k] = copy.deepcopy(v)
        return rslt
