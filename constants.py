#!/usr/bin/env python
# Copyright (C) 2016 SignalFx, Inc.
"""
Constants for the SignalFx collectd plugin for vSphere
"""
# The maximum field size for collectd
COLLECTD_FIELD_LENGTH = 1024

# How often to sync local cache of metric metadata from vCenter's perf counters
DEFAULT_METRIC_SYNC_INTERVAL = 5 * 60  # 5 minutes

# How often to sync local cache of managed object references to
# vCenter's inventory
DEFAULT_MOR_SYNC_INTERVAL = 5 * 60  # 5 minutes

# Maximum number of seconds to wait for API calls to vCenter to complete
DEFAULT_TIMEOUT = 60

# Determines which metrics are collected and sent to SignalFx.
DEFAULT_VERBOSITY_LEVEL = 1

# The longest time to wait for vCenter inventory sync to complete
INVENTORY_SYNC_TIMEOUT = 60  # 1 minute

# Name for the 1-per-entity metadata metric
METADATA_METRIC_NAME = "signalfx_vsphere_metadata"

# The name of the plugin, reported as a dimension with every metric
PLUGIN_NAME = "vsphere"

# The list of allowed verbosity levels
VERBOSITY_LEVELS = (1, 2, 3, 4)
