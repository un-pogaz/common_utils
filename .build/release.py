#!/usr/bin/python

__license__   = 'GPL v3'
__copyright__ = '2022, un_pogaz based on code from Grant Drake'

'''
Creates a GitHub release for a plugin, including uploading the zip file.

Invocation should be via each plugin release.cmd, which will ensure that:
- Working directory is set to the <plugin> subfolder
- Zip file for plugin is rebuilt for latest local code/translations
- Pass through the CALIBRE_GITHUB_TOKEN environment variable value
'''

import os
import re
import json
import configparser
from urllib import request, parse, error
from subprocess import Popen, PIPE
from typing import Tuple, Union

def read_repos_detail() -> str:
    config = configparser.ConfigParser()
    config.read(os.path.join(os.getcwd(), '.git','config'))
    origin = None
    for section in ['remote "origin"', "remote 'origin'"]:
        if section in config:
            origin = config.get(section, 'url')
    if not origin:
        RuntimeError('Could not find the git repository')
    
    return origin[len('https://github.com/'):-len('.git')]

def read_plugin_details() -> Tuple[str, str, str]:
    short_name = os.path.split(os.getcwd())[1]
    initFile = os.path.join(os.getcwd(), '__init__.py')
    if not os.path.exists(initFile):
        print('ERROR: No __init__.py file found for this plugin')
        raise FileNotFoundError(initFile)
    
    plugin_name = None
    with open(initFile) as file:
        content = file.read()
        nameMatches = re.findall(r"\s+name\s*=\s*\'([^\']*)\'", content)
        if nameMatches: 
            plugin_name = nameMatches[0]
        else:
            raise RuntimeError('Could not find plugin name in __init__.py')
        versionMatches = re.findall(r"\s+version\s*=\s*\(([^\)]*)\)", content)
        if versionMatches: 
            version = versionMatches[0].replace(',','.').replace(' ','')

    print(f"Plugin to be released for: '{plugin_name}' v{version}")
    return short_name, plugin_name, version

def get_plugin_zip_path(plugin_name: str) -> str:
    zip_file = os.path.join(os.getcwd(), '-- versioning', plugin_name+'.zip')
    if not os.path.exists(zip_file):
        print(f'ERROR: No zip file found for this plugin at: {zip_file}')
        raise FileNotFoundError(zip_file)
    return zip_file

def read_change_log_for_version(version: str) -> str:
    changeLogFile = os.path.join(os.getcwd(), 'changelog.md')
    if not os.path.exists(changeLogFile):
        print(f'ERROR: No change log found for this plugin at: {changeLogFile}')
        raise FileNotFoundError(changeLogFile)
    
    with open(changeLogFile) as file:
        content = file.readlines()
    
    foundVersion = False
    changeLines = []
    for line in content:
        if not foundVersion:
            if line.startswith(f'## [{version}]'):
                foundVersion = True
            continue
        # We are within the current version - include content unless we hit the previous version
        if line.startswith('## ['):
            break
        changeLines.append(line.rstrip())

    if len(changeLines) == 0:
        print(f'ERROR: No change log details found for this version: {version}')
        raise RuntimeError('Missing details in changelog')

    # Trim trailing blank lines (start/end)
    for idx in [0, -1]:
        while changeLines and len(changeLines[idx].strip()) == 0:
            changeLines.pop(idx)

    print(f'ChangeLog details found: {len(changeLines):d} lines')
    return '\n'.join(changeLines)

def check_if_release_exists(api_repo_url: str, api_token: str, tag_name: str):
    # If we have already released this plugin version then we have a problem
    # Most likely have forgotten to bump the version number?
    endpoint = api_repo_url + '/releases/tags/' + tag_name
    req = request.Request(url=endpoint, method='GET')
    req.add_header('accept', 'application/vnd.github+json')
    req.add_header('Authorization', f'BEARER {api_token}')
    try:
        print(f'Checking if GitHub tag exists: {endpoint}')
        with request.urlopen(req) as response:
            response = response.read().decode('utf-8')
            raise RuntimeError('Release for this version already exists. Do you need to bump version?')
    except error.HTTPError as e:
        if e.code == 404:
            print('Existing release for this version not found, OK to proceed')
        else:
            raise RuntimeError('Failed to check release existing API due to:',e)

def create_GitHub_release(api_repo_url: str, api_token: str, plugin_name: str, tag_name: str, changeBody: str):
    endpoint = api_repo_url + '/releases'
    data = {
        'tag_name': tag_name,
        'target_commitish': 'main',
        'name': f'{plugin_name} {tag_name}',
        'body': changeBody,
        'draft': False,
        'prerelease': False,
        'generate_release_notes': False,
    }
    data = json.dumps(data)
    data = data.encode()
    req = request.Request(url=endpoint, data=data, method='POST')
    req.add_header('accept', 'application/vnd.github+json')
    req.add_header(f'Authorization', f'BEARER {api_token}')
    req.add_header('Content-Type', 'application/json')
    try:
        print(f'Creating release: {endpoint}')
        with request.urlopen(req) as response:
            response = response.read().decode('utf-8')
            content = json.loads(response)
            htmlUrl = content['html_url']
            upload_url = content['upload_url']
            return (htmlUrl, upload_url)
    except error.HTTPError as e:
        raise RuntimeError('Failed to create release due to:',e)

def upload_zip_to_release(api_token: str, upload_url: str, zip_file: str, tag_name: str):
    dst = os.path.splitext(zip_file)[0] +'-'+tag_name+'.zip'
    os.rename(zip_file, dst)
    zip_file = dst
    zip_file_up = parse.quote(os.path.basename(zip_file))
    
    endpoint = upload_url.replace('{?name,label}', f'?name={zip_file_up}&label={zip_file_up}')
    with open(zip_file, 'rb') as file:
        content = file.read()
    
    req = request.Request(url=endpoint, data=content, method='POST')
    req.add_header('accept', 'application/vnd.github+json')
    req.add_header(f'Authorization', f'BEARER {api_token}')
    req.add_header('Content-Type', 'application/octet-stream')
    try:
        print(f'Uploading zip for release: {endpoint}')
        with request.urlopen(req) as response:
            response = response.read().decode('utf-8')
            content = json.loads(response)
            downloadUrl = content['browser_download_url']
            print(f'Zip uploaded successfully: {downloadUrl}')
    except error.HTTPError as e:
        raise RuntimeError('Failed to upload zip due to:',e)

def run_command(command_line: Union[list, str], wait=False) -> Popen:
    """
    Lauch a command line and return the subprocess
    
    :param command_line:    command line to execute
    :param wait:            Wait for the file to be closed
    :return:                The subprocess returned by the Popen call
    """
    
    if not isinstance(command_line, str):
        for idx in range(len(command_line)):
            if ' ' in command_line[idx]: command_line[idx] = '"'+command_line[idx]+'"'
        command_line = ' '.join(command_line)
    
    subproc = Popen(command_line, stdout=PIPE, stderr=PIPE, shell=True)
    if wait:
        subproc.wait()
    return subproc


def build_MobileRead_post():
    output_file = 'MobileRead_post.bbcode'
    MobileRead_body = os.path.join(os.getcwd(), 'readme.bbcode')
    if not os.path.exists(MobileRead_body):
        print(f'Creating {output_file} aborted: no body found')
        return
    
    with open(MobileRead_body) as f:
        MobileRead_body = f.read().strip()
    
    with open(os.path.join(os.getcwd(), 'changelog.md')) as f:
        changelog_src = f.read().strip().splitlines()
    
    changelog = []
    global bb_list_level, list_prefix_last
    bb_list_level = 0
    list_prefix_last = None
    
    def md2bb(line):
        line = line.replace('`', '')
        line = line.replace('<br>', '\n')
        line = re.sub(r'\*\*\*(.+?)\*\*\*', r'[B][I]\1[/I][/B]', line)
        line = re.sub(r'\*\*(.+?)\*\*', r'[B]\1[/B]', line)
        line = re.sub(r'\*(.+?)\*', r'[I]\1[/I]', line)
        
        return line
    
    def bb_list_close():
        global bb_list_level, list_prefix_last
        for idx in range(bb_list_level):
            changelog.append('[/LIST]')
        bb_list_level = 0
        list_prefix_last = None
    
    for line in changelog_src:
        
        if line.startswith('# '):
            pass
        
        if line.startswith('## '):
            bb_list_close()
            line = line.replace('#', '').replace('[', '').replace(']', '').strip()
            changelog.append('\n[B]version '+line+'[/B]')
        
        if line.startswith('### '):
            bb_list_close()
            changelog.append(line.replace('#', '').strip())
        
        if re.match(r'\s*- ', line):
            list_prefix = line.split('-', maxsplit=1)[0]
            if list_prefix != list_prefix_last:
                if list_prefix_last is None or len(list_prefix_last) < len(list_prefix):
                    bb_list_level += 1
                    changelog.append('[LIST]')
                elif len(list_prefix_last) == len(list_prefix):
                    pass
                elif len(list_prefix_last) > len(list_prefix):
                    bb_list_level -= 1
                    changelog.append('[/LIST]')
                
                list_prefix_last = list_prefix
            
            line = line.strip().removeprefix('- ')
            changelog.append('[*]'+md2bb(line))
    
    bb_list_close()
    
    
    with open(output_file, 'w', newline='\n') as f:
        f.write(MobileRead_body)
        f.write('\n\n[B]Version History:[/B]\n')
        f.write('[SPOILER]'+'\n'.join(changelog).strip()+'[/SPOILER]')
    
    print(f'{output_file} builded')


if __name__=="__main__":
    api_token = os.environ.get('CALIBRE_GITHUB_TOKEN')
    if not api_token:
        raise RuntimeError('No GitHub API token found. Please set it in CALIBRE_GITHUB_TOKEN variable.')
    
    repos_name = read_repos_detail()
    
    api_repo_url = 'https://api.github.com/repos/'+repos_name
    
    short_name, plugin_name, version = read_plugin_details()
    if version.count('.') >= 3:
        raise RuntimeError('This is a test/experimental version. Aborted.')
    tag_name = version
    
    check_if_release_exists(api_repo_url, api_token, tag_name)
    
    zip_file = get_plugin_zip_path(plugin_name)
    
    changeBody = read_change_log_for_version(version)
    
    html_url, upload_url = create_GitHub_release(api_repo_url, api_token, plugin_name, tag_name, changeBody)
    upload_zip_to_release(api_token, upload_url, zip_file, tag_name)
    print('Github release completed:', html_url)
    run_command('git pull --tags')
    
    build_MobileRead_post()
