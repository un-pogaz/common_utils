#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Grant Drake <grant.drake@gmail.com> ; 2022, un_pogaz <un.pogaz@gmail.com>'
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
from calibre.constants import DEBUG, numeric_version as calibre_version
from calibre.gui2.ui import get_gui

GUI = get_gui()


_PLUGIN = None
def get_plugin_attribut(name, default=None):
    """Retrieve a attribut on the main plugin class"""
    global _PLUGIN
    if not _PLUGIN:
        import importlib
        from calibre.customize import Plugin
        #Yes, it's very long for a one line. It's seems crazy, but it's fun and it works
        plugin_classes = [ obj for obj in itervalues(importlib.import_module('.'.join(__name__.split('.')[:-1])).__dict__) if isinstance(obj, type) and issubclass(obj, Plugin) and obj.name != 'Trivial Plugin' ]
        
        plugin_classes.sort(key=lambda c:(getattr(c, '__module__', None) or '').count('.'))
        _PLUGIN = plugin_classes[0]
    
    return getattr(_PLUGIN, name, default)

ROOT = __name__.split('.')[-2]

# Global definition of our plugin name. Used for common functions that require this.
PLUGIN_NAME = get_plugin_attribut('name', ROOT)
PREFS_NAMESPACE = get_plugin_attribut('PREFS_NAMESPACE', ROOT)
DEBUG_PRE = get_plugin_attribut('DEBUG_PRE', PLUGIN_NAME)

BASE_TIME = time.time()
def debug_print(*args):
    if DEBUG:
        prints('DEBUG', DEBUG_PRE+':', *args)
        #prints('DEBUG', DEBUG_PRE,'({:.3f})'.format(time.time()-BASE_TIME),':', *args)


# ----------------------------------------------
#          Icon Management functions
# ----------------------------------------------

try:
    from qt.core import QIcon, QPixmap, QApplication
except ImportError:
    from PyQt5.Qt import QIcon, QPixmap, QApplication

from calibre.constants import iswindows
from calibre.utils.config import config_dir

# Global definition of our plugin resources. Used to share between the xxxAction and xxxBase
# classes if you need any zip images to be displayed on the configuration dialog.
PLUGIN_RESOURCES = {}

THEME_COLOR = ['', 'dark', 'light']

def get_theme_color():
    """Get the theme color of Calibre"""
    if calibre_version > (5, 90):
        return THEME_COLOR[1] if QApplication.instance().is_dark_theme else THEME_COLOR[2]
    return THEME_COLOR[0]

def get_icon_themed(icon_name, theme_color=None):
    """Apply the theme color to a path"""
    theme_color = get_theme_color() if theme_color is None else theme_color
    return icon_name.replace('/', '/'+theme_color+'/', 1).replace('//', '/')

def load_plugin_resources(plugin_path, names=[]):
    """
    Load all images in the plugin and the additional specified name.
    Set our global store of plugin name and icon resources for sharing between
    the InterfaceAction class which reads them and the ConfigWidget
    if needed for use on the customization dialog for this plugin.
    """
    from calibre.utils.zipfile import ZipFile
    
    global PLUGIN_RESOURCES
    
    if plugin_path is None:
        raise ValueError('This plugin was not loaded from a ZIP file')
    
    names = names or []
    ans = {}
    with ZipFile(plugin_path, 'r') as zf:
        for entry in zf.namelist():
            if entry in names or (entry.startswith('images/') and os.path.splitext(entry)[1].lower() == '.png' and entry not in PLUGIN_RESOURCES):
                ans[entry] = zf.read(entry)
    
    PLUGIN_RESOURCES.update(ans)

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
def __Functions__(): pass

def get_date_format(tweak_name='gui_timestamp_display_format', default_fmt='dd MMM yyyy'):
    from calibre.utils.config import tweaks
    format = tweaks[tweak_name]
    if format is None:
        format = default_fmt
    return format


# ----------------------------------------------
#               Ohters
# ----------------------------------------------
def __Ohters__(): pass

from calibre.gui2 import error_dialog, show_restart_warning
from calibre.utils.config import JSONConfig, DynamicConfig

def current_db():
    """Safely provides the current_db or None"""
    return getattr(GUI,'current_db', None)
    # db.library_id

def has_restart_pending(show_warning=True, msg_warning=None):
    restart_pending = GUI.must_restart_before_config
    if restart_pending and show_warning:
        msg = msg_warning if msg_warning else _('You cannot configure this plugin before calibre is restarted.')
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
            if sys.version_info < (2,):
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
        if self.search(pattern, string, flag):
            return regex._re.finditer(pattern, string, flag)
        else:
            return None
    
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


class PREFS_json(JSONConfig):
    """
    Use plugin name to create a JSONConfig file
    to store the preferences for plugin
    """
    def __init__(self):
        JSONConfig.__init__(self, 'plugins/'+PLUGIN_NAME)
    
    def update(self, other, **kvargs):
        JSONConfig.update(self, other, **kvargs)
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
