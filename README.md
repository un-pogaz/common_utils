# common_utils

This repository contains the `common_utils` module used for my Calibre plugins.

All this work is is highly based on the [work of kiwidude](https://github.com/kiwidude68/calibre_plugins/tree/main/common).

This module repository was created for my personal comfort and rearranged in a format I like.

## Installation

```
git submodule add --name common_utils https://github.com/un-pogaz/common_utils.git
git submodule init
git submodule update --remote --merge
```

1) Install this repository as a submodule
2) Initialize the submodule
3) Update the submodule

## Content

| Filename | Purpose |
| -------- | ------- |
| \_\_init\_\_.py | Root element, `get_icon()` and various self-suffisant functions |
| columns.py | Get colums information, based on their type |
| dialogs.py | Pre-build useful dialogs |
| librarys.py | Functions to retrive Book IDs for various case |
| menus.py | Helper functions for building menus for `action.py` |
| widgets.py | Additional Qt widgets for use in dialogs or grid tables |

The folder `/translations/` contains the base PO file to translate the various string of the `common_utils`. This entrys need to be manualy merged to your real translation files.

The folder `/.build/` contains tricky thing to help on the developement. Certainly the most personal part of this repository. Need a tutorial, but no idea how to start explaining this exotic thing.

# DISCLAIMER

This module is provided "as is", without warranty of any kind.

Modifications are made at my discretion and may cause incompatibility without notice.

Help, suggestions and feedbacks are welcome, but remember that this module repository was first created for my personal use, so if you decide to use it, well Thank you very much to use my work, but be warn to don't be surprised if bad surprises happen.
