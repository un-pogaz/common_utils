#!/usr/bin/python

__license__   = 'GPL v3'
__copyright__ = '2022, Grant Drake'

'''
Creates a GitHub release for a plugin, including uploading the zip file.

Invocation should be via each plugin release.cmd, which will ensure that:
- Working directory is set to the <plugin> subfolder
- Zip file for plugin is rebuilt for latest local code/translations
- Pass through the CALIBRE_GITHUB_TOKEN environment variable value
'''

import sys, os, re, json, configparser
from urllib import request, parse, error
from glob import glob

def read_repos_detail():
    config = configparser.ConfigParser()
    config.read(os.path.join(os.getcwd(), '.git','config'))
    origin = None
    for section in ['remote "origin"', "remote 'origin'"]:
        if section in config:
            origin = config.get(section, 'url')
    if not origin:
        RuntimeError('Could not find the git repository')
    
    return origin[len('https://github.com/'):-len('.git')]

def read_plugin_details():
    short_name = os.path.split(os.getcwd())[1]
    initFile = os.path.join(os.getcwd(), '__init__.py')
    if not os.path.exists(initFile):
        print('ERROR: No __init__.py file found for this plugin')
        raise FileNotFoundError(initFile)
    
    plugin_name = None
    with open(initFile, 'r') as file:
        content = file.read()
        nameMatches = re.findall("\s+name\s*=\s*\'([^\']*)\'", content)
        if nameMatches: 
            plugin_name = nameMatches[0]
        else:
            raise RuntimeError('Could not find plugin name in __init__.py')
        versionMatches = re.findall("\s+version\s*=\s*\(([^\)]*)\)", content)
        if versionMatches: 
            version = versionMatches[0].replace(',','.').replace(' ','')

    print("Plugin to be released for: '{}' v{}".format(plugin_name, version))
    return short_name, plugin_name, version

def get_plugin_zip_path(plugin_name):
    zip_file = os.path.join(os.getcwd(), '-- versioning', plugin_name+'.zip')
    if not os.path.exists(zip_file):
        print('ERROR: No zip file found for this plugin at: {}'.format(zip_file))
        raise FileNotFoundError(zip_file)
    return zip_file

def read_change_log_for_version(version):
    changeLogFile = os.path.join(os.getcwd(), 'CHANGELOG.md')
    if not os.path.exists(changeLogFile):
        print('ERROR: No change log found for this plugin at: {}'.format(changeLogFile))
        raise FileNotFoundError(changeLogFile)
    
    with open(changeLogFile, 'r') as file:
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
        print('ERROR: No change log details found for this version: {}'.format(version))
        raise RuntimeError('Missing details in changelog')

    # Trim trailing blank lines (start/end)
    for idx in [0, -1]:
        while changeLines and len(changeLines[idx].strip()) == 0:
            changeLines.pop(idx)

    print('ChangeLog details found: {0} lines'.format(len(changeLines)))
    return '\n'.join(changeLines)

def check_if_release_exists(api_repo_url, api_token, tag_name):
    # If we have already released this plugin version then we have a problem
    # Most likely have forgotten to bump the version number?
    endpoint = api_repo_url + '/releases/tags/' + tag_name
    req = request.Request(url=endpoint, method='GET')
    req.add_header('accept', 'application/vnd.github+json')
    req.add_header('Authorization', 'BEARER {}'.format(api_token))
    try:
        print('Checking if GitHub tag exists: {}'.format(endpoint))
        with request.urlopen(req) as response:
            response = response.read().decode('utf-8')
            raise RuntimeError('Release for this version already exists. Do you need to bump version?')
    except error.HTTPError as e:
        if e.code == 404:
            print('Existing release for this version not found, OK to proceed')
        else:
            raise RuntimeError('Failed to check release existing API due to:',e)

def create_GitHub_release(api_repo_url ,api_token, plugin_name, tag_name, changeBody):
    endpoint = api_repo_url + '/releases'
    data = {
        'tag_name': tag_name,
        'target_commitish': 'main',
        'name': '{} {}'.format(plugin_name, tag_name),
        'body': changeBody,
        'draft': False,
        'prerelease': False,
        'generate_release_notes': False
    }
    data = json.dumps(data)
    data = data.encode()
    req = request.Request(url=endpoint, data=data, method='POST')
    req.add_header('accept', 'application/vnd.github+json')
    req.add_header('Authorization', 'BEARER {}'.format(api_token))
    req.add_header('Content-Type', 'application/json')
    try:
        print('Creating release: {}'.format(endpoint))
        with request.urlopen(req) as response:
            response = response.read().decode('utf-8')
            content = json.loads(response)
            htmlUrl = content['html_url']
            upload_url = content['upload_url']
            return (htmlUrl, upload_url)
    except error.HTTPError as e:
        raise RuntimeError('Failed to create release due to:',e)

def upload_zip_to_release(api_token, upload_url, zip_file, tag_name):
    dst = os.path.splitext(zip_file)[0] +'-'+tag_name+'.zip'
    os.rename(zip_file, dst)
    zip_file = dst
    zip_file_up = parse.quote(os.path.basename(zip_file))
    
    endpoint = upload_url.replace('{?name,label}','?name={}&label={}'.format(zip_file_up, zip_file_up))
    with open(zip_file, 'rb') as file:
        content = file.read()
    
    req = request.Request(url=endpoint, data=content, method='POST')
    req.add_header('accept', 'application/vnd.github+json')
    req.add_header('Authorization', 'BEARER {}'.format(api_token))
    req.add_header('Content-Type', 'application/octet-stream')
    try:
        print('Uploading zip for release: {}'.format(endpoint))
        with request.urlopen(req) as response:
            response = response.read().decode('utf-8')
            content = json.loads(response)
            downloadUrl = content['browser_download_url']
            print('Zip uploaded successfully: {}'.format(downloadUrl))
    except error.HTTPError as e:
        raise RuntimeError('Failed to upload zip due to:',e)


if __name__=="__main__":
    api_token = sys.argv[1]
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
    print('Github release completed: {}'.format(html_url))