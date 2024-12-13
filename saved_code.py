#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2024, un_pogaz <un.pogaz@gmail.com>'

# not "implemented" code, need to be copy/past into the actual plugin
# this functions cannot be imported and called directly from the plugin
# <Exception: circular import>


from calibre.customize import Plugin


class MainPlugin(Plugin):
    
    def initialize_embedded_plugin(self, plugin, name: str=None, description: str=None):
        """
        A Calibre plugin can normally only contain one Plugin class.
        In our case, this would be the file type class.
        However, we want to load the GUI plugin, too, so we have to trick
        Calibre into believing that there's actually a 2nd plugin.
        """
        
        from calibre.customize.ui import _initialized_plugins, initialize_plugin
        
        for p in _initialized_plugins:
            if isinstance(p, plugin):
                return p
        
        plugin.name = name or str(plugin.__name__)
        plugin.description = description or self.description
        
        plugin.version = self.version
        plugin.minimum_calibre_version = self.minimum_calibre_version
        plugin.supported_platforms = self.supported_platforms
        plugin.author = self.author
        
        plugin.file_types = getattr(self, 'file_types', None)
        
        installation_type = getattr(self, 'installation_type', None)
        
        try:
            if installation_type is not None:
                p = initialize_plugin(plugin, self.plugin_path, installation_type)
            else:
                p = initialize_plugin(plugin, self.plugin_path)
            _initialized_plugins.append(p)
            return p
        except Exception as err:
            print(f'{self.name}: Error during the initialize of the embedded plugin "{plugin.name}":\n{err}\n')
            return None
