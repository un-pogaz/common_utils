@echo off
call common_utils\.build\update_common_utils.cmd

python common_utils\.build\build.py
