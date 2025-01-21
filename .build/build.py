#!/usr/bin/python

__license__   = 'GPL v3'
__copyright__ = '2022, un_pogaz based on code from JimmXinu and Grant Drake'

'''
Creates an uncompressed zip file for the plugin.
Plugin zips are uncompressed so to not negatively impact calibre load times.

1. Derive the plugin zip filename by reading __init__.py in plugin folder
2. Also derive the version (for printing)

All subfolders of the plugin folder will be included, unless prefixed with '.'
i.e. .build and .tx will not be included in the zip.
'''

import os
import re
import zipfile
from glob import glob
from subprocess import PIPE, Popen
from typing import Tuple, Union

CALIBRE_CONFIG_DIRECTORY = os.environ.get(
    'CALIBRE_CONFIG_DIRECTORY',
    os.path.join(os.environ.get('appdata'), 'calibre'),
)
PLUGINS_DIRECTORY = os.path.join(CALIBRE_CONFIG_DIRECTORY, 'plugins')


def get_calibre_bin(calibre_bin: str) -> str:
    return os.path.join(os.environ.get('CALIBRE_DIRECTORY', ''), calibre_bin)


def run_command(command_line: Union[list, str], wait=False) -> Popen:
    '''
    Lauch a command line and return the subprocess
    
    :param command_line:    command line to execute
    :param wait:            Wait for the file to be closed
    :return:                The subprocess returned by the Popen call
    '''
    
    if not isinstance(command_line, str):
        for idx in range(len(command_line)):
            if ' ' in command_line[idx]:
                command_line[idx] = '"'+command_line[idx]+'"'
        command_line = ' '.join(command_line)
    
    subproc = Popen(command_line, stdout=PIPE, stderr=PIPE, shell=True)
    if wait:
        subproc.wait()
    return subproc


def read_plugin_name() -> Tuple[str, str]:
    init_file = os.path.join(os.getcwd(), '__init__.py')
    if not os.path.exists(init_file):
        print('ERROR: No __init__.py file found for this plugin')
        raise FileNotFoundError(init_file)
    
    zip_file_name = None
    with open(init_file) as file:
        content = file.read()
        name_matches = re.findall(r"\s+name\s*=\s*\'([^\']*)\'", content)
        if name_matches:
            name = name_matches[0]
            zip_file_name = name+'.zip'
        else:
            raise RuntimeError('Could not find plugin name in __init__.py')
        version_matches = re.findall(r'\s+version\s*=\s*\(([^\)]*)\)', content)
        if version_matches:
            version = '.'.join(re.findall(r'\d+', version_matches[0]))
    
    print(f'Plugin {name!r} v{version} will be zipped to: "{zip_file_name}"')
    return zip_file_name, version


def update_translations():
    for po in glob('translations/**/*.po', recursive=True):
        run_command([
            get_calibre_bin('calibre-debug'),
            '-c',
            'from calibre.translations.msgfmt import main; main()',
            os.path.abspath(po),
        ], wait=True)


def create_zip_file(filename, mode, files):
    with zipfile.ZipFile(filename, mode, zipfile.ZIP_STORED) as zip:
        for file in files:
            if os.path.isfile(file):
                zip.write(file, file)


def build_plugin():
    
    PLUGIN, version = read_plugin_name()
    
    update_translations()
    
    files = []
    files.extend(glob('plugin-import-name-*.txt'))
    files.extend(glob('**/*.py', recursive=True))
    files.extend(glob('**/*.ui', recursive=True))
    files.extend(glob('images/**/*.png', recursive=True))
    files.extend(glob('translations/*.pot'))
    files.extend(glob('translations/*.mo'))
    files.extend(glob('translations/*.po'))
    files.extend(glob('**/*.md', recursive=True))
    files.extend(glob('**/*.html', recursive=True))
    files.extend(glob('**/*.cmd', recursive=True))
    files.extend(glob('**/LICENSE', recursive=True))
    files.extend(glob('**/CREDITS', recursive=True))
    
    create_zip_file(PLUGIN, 'w', files)
    
    run_command([get_calibre_bin('calibre-customize'), '-a', PLUGIN], wait=True)
    
    versioning = os.path.join(os.getcwd(), '-- versioning')
    os.makedirs(versioning, exist_ok=True)
    out = os.path.join(versioning, PLUGIN)
    if os.path.exists(out):
        os.remove(out)
    os.rename(PLUGIN, out)
    
    print(f'Plugin {PLUGIN!r} build with succes.')


if __name__=='__main__':
    build_plugin()
