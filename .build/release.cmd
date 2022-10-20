@echo off
call common_utils\.build\update_common_utils.cmd

python common_utils\.build\build.py

python common_utils\.build\release.py "%CALIBRE_GITHUB_TOKEN%"
