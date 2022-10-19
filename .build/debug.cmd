@echo off
call common_utils\.build\build.cmd

echo Starting calibre in debug mode
calibre-debug.exe -g
