# Changelog - common_utils

## 2023/09/30
- Drop Python 2 / Calibre 4 comatibility, only 5 and above

## 2023/09/29
- Add SelectFieldValuesWidget and SelectNotesWidget

## 2023/09/28
- Add PLUGIN_CLASSE
- remove load_plugin_resources(), Add ZipResources and PluginResources
    - PLUGIN_RESOURCES will now auto load any requested items
- Drop Calibre 2 and 3 comatibility, only 4 and above
    - !! Remove SizePersistedDialog !!
- Add ImageDialog, rework ImageComboBox

## 2023/09/26
- rework custom_exception_dialog()

## 2023/09/24
- little improvement of debug_print
- Add LibraryPrefsViewerDialogButton, improve LibraryPrefsViewerDialog (with result code)

## 2023/09/23
- Add PLUGIN_INSTANCE
- Add KeyboardConfigDialogButton

## 2023/09/13
- Don't update the file of PREFS_json at the initialization

## 2023/09/08
- Don't update common_utils when release

## 2023/08/27
- Add sub LICENSE and CREDITS to PluginZip

## 2023/08/08
- Add ProgressDialog

## 2023/08/07
- Add build_MobileRead_post() to release.py
- Add truncate_title()

## 2023/08/06
- Edit Changelog to [Common Changelog](https://common-changelog.org)
- Update release.py to the new Changelog format

## 2023/04/29
- update build

## 2023/04/28
- add 'id', 'path' to possible_columns ; self test/debug
- fix `possible_fields()`

## 2023/04/12
- standalone columns.py

## 2023/04/10
- `ColumnTypes.comments` don't exist

## 2022/10/29
- fix `error_dialog`

## 2022/10/20
- add release scripts
- improve dialog.py

## 2022/10/20
- It's Work!

## 2022/10/19
- init()
- Start build this thing and migrate the elements in the convenient place.
- Don't use it. Won't work for a while.
