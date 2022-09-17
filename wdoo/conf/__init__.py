# -*- coding: utf-8 -*-
# Part of wdoo. See LICENSE file for full copyright and licensing details.

""" Library-wide configuration variables.
For now, configuration code is in wdoo.tools.config. It is in mainly
unprocessed form, e.g. addons_path is a string with commas-separated
paths. The aim is to have code related to configuration (command line
parsing, configuration file loading and saving, ...) in this module
and provide real Python variables, e.g. addons_paths is really a list
of paths.
To initialize properly this module, wdoo.tools.config.parse_config()
must be used.
"""

# Paths to search for wdoo addons.
addons_paths = []

# List of server-wide modules to load. Those modules are supposed to provide
# features not necessarily tied to a particular database. This is in contrast
# to modules that are always bound to a specific database when they are
# installed (i.e. the majority of wdoo addons). This is set with the --load
# command-line option.
server_wide_modules = []