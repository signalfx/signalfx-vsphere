"""
Module containing classes for getting the inventory for a vCenter Server,
caching relevant information, and periodically updating it.
"""

import logging
import threading
import time
from pyVmomi import vim


class InventoryManager(threading.Thread):
    def __init__(self, si, refresh_interval, vc_name, instance_id, *args, **kwargs):
        self._si = si
        self._refresh_interval = refresh_interval
        self.vc_name = vc_name
        self._logger = logging.getLogger("{0}-IM".format(instance_id))
        self._perf_manager = self._si.RetrieveServiceContent().perfManager
        threading.Thread.__init__(self, *args, **kwargs)
        self.daemon = True
        self.update_lock = threading.Lock()
        self._stop_signal = threading.Event()
        self._has_inventory = threading.Event()
        self._cache = self._new_cache()

    def _new_cache(self):
        """
        Creates a new, empty cache that will be used to store inventory objects.
        :return: dict

        """
        cache = {
            'datacenter': [],
            'cluster': [],
            'host': [],
            'vm': []
        }
        return cache

    def _sync(self, mor, cache, meta_dims=None):
        """
        Recursively walk the tree of inventory objects and update the cache
        as we find elements we're interested in monitoring.

        :param mor: Managed Object Reference
        :param cache:
        :param meta_dims: Meta dimensions of mor
        :return: null
        """
        if isinstance(mor, vim.Folder):
            for item in mor.childEntity:
                self._sync(item, cache, meta_dims)

        elif isinstance(mor, vim.Datacenter):
            datacenter = Datacenter(mor, self._perf_manager, self.vc_name)
            cache['datacenter'].append(datacenter)
            for item in mor.hostFolder.childEntity:
                self._sync(item, cache, datacenter.mor_dimensions)

        elif isinstance(mor, vim.ClusterComputeResource):
            cluster = Cluster(mor, self._perf_manager, self.vc_name, meta_dims)
            cache['cluster'].append(cluster)
            for host in mor.host:
                if hasattr(host, 'vm'):
                    self._sync(host, cache, cluster.mor_dimensions)

        elif isinstance(mor, vim.ComputeResource):
            for host in mor.host:
                if hasattr(host, 'vm'):
                    self._sync(host, cache, meta_dims)

        elif isinstance(mor, vim.HostSystem):
            host = Host(mor, self._perf_manager, self.vc_name, meta_dims)
            cache['host'].append(host)
            for vm in mor.vm:
                if vm.runtime.powerState == 'poweredOn':
                    self._sync(vm, cache, host.mor_dimensions)

        elif isinstance(mor, vim.VirtualMachine):
            cache['vm'].append(VirtualMachine(mor, self._perf_manager, self.vc_name, meta_dims))

        else:
            self._logger.error("Unhandled managed object: {0}".format(mor))

    def sync_inventory(self):
        cache = self._new_cache()
        self._sync(self._si.RetrieveServiceContent().rootFolder, cache)
        with self.update_lock:
            self._cache = cache
        self._has_inventory.set()

    def block_until_inventory(self, timeout=None):
        """
        Wait until the inventory cache is populated. Useful for right after the thread starts.
        :param timeout: Maximum time to wait before raising an exception
        :return: Boolean
        """
        return self._has_inventory.wait(timeout=timeout)

    def current_inventory(self):
        """
        Thread-safe way to get the current inventory cache.
        Return a map of {str: list of InventoryObject}
                The mapping of inventory type (datacenter, host, cluster, vm) to inventory objects of that type.
        :return: dict
        """
        with self.update_lock:
            return self._cache

    def run(self):
        while not self._stop_signal.is_set():
            next_interval = time.time() + self._refresh_interval
            try:
                self.sync_inventory()
            except Exception as e:
                self._logger.warning("Exception when syncing vCenter inventory, "
                                     "continuing anyway: {0}".format(e))
            except KeyboardInterrupt:
                break
            sleep_time = next_interval - time.time()
            self._logger.info("vCenter inventory sync complete. Next sync in {0} seconds".format(sleep_time))
            if sleep_time < 0:
                self._logger.warning("vCenter inventory time exceeded the refresh interval")

            while (not self._stop_signal.is_set() and time.time() < next_interval):
                time.sleep(1)

    def stop(self):
        self._stop_signal.set()


class InventoryObject(object):
    INSTANT_INTERVAL = 20

    def __init__(self, mor, perf_mgr, vc_name, meta_dims=None):
        self.mor = mor
        self._perf_mgr = perf_mgr
        self.vc_name = vc_name
        # Mapping of integer counter key to its corresponding MetricId object
        self.metric_id_map = self._mor_metrics()
        self.dimensions = self._get_dimensions()
        self.properties = self._get_properties()
        self.sf_metadata_dims = self._get_sf_metadata_dims()
        if meta_dims is not None:
            self.sf_metadata_dims.update(meta_dims)
        self.mor_dimensions = self._get_mor_dimensions()

    def _mor_metrics(self):
        """
        Determines the metrics being published by a given managed object.

        :return: dict

        """
        metrics = self._perf_mgr.QueryAvailablePerfMetric(self.mor, None, None, self.INSTANT_INTERVAL)
        metric_map = {}
        for metric_id_obj in metrics:
            metric_map[metric_id_obj.counterId] = metric_id_obj
        return metric_map

    def _get_dimensions(self):
        dimensions = {
            'vc_name': self.vc_name
        }
        return dimensions

    def _get_mor_dimensions(self):
        dimensions = self.sf_metadata_dims.copy()
        if 'object_type' in dimensions:
            dimensions.pop('object_type')
        return dimensions

    def _get_properties(self):
        return []

    def _get_sf_metadata_dims(self):
        metadata_dims = self.dimensions.copy()
        return metadata_dims


class Datacenter(InventoryObject):
    INSTANT_INTERVAL = 300

    def _get_dimensions(self):
        dimensions = InventoryObject._get_dimensions(self).copy()
        additional_dims = {
            'datacenter': self.mor.name,
            'object_type': 'datacenter',
        }
        dimensions.update(additional_dims)
        return dimensions


class Cluster(InventoryObject):
    INSTANT_INTERVAL = 300

    def _get_dimensions(self):
        dimensions = InventoryObject._get_dimensions(self).copy()
        additional_dims = {
            'cluster': self.mor.name,
            'object_type': 'cluster',
        }
        dimensions.update(additional_dims)
        return dimensions


class Host(InventoryObject):
    def _get_dimensions(self):
        dimensions = InventoryObject._get_dimensions(self).copy()
        additional_dims = {
            'esx_host': self.mor.name,
            'host': self.mor.name,
            'object_type': 'host',
        }
        dimensions.update(additional_dims)
        return dimensions


class VirtualMachine(InventoryObject):
    def _get_dimensions(self):
        dimensions = InventoryObject._get_dimensions(self).copy()
        additional_dims = {
            'vm': self.mor.name,
            'object_type': 'vm',
        }
        dimensions.update(additional_dims)
        return dimensions

    def _get_sf_metadata_dims(self):
        dimensions = self._get_dimensions().copy()
        metadata_dims = {
            'guest_os': self.mor.config.guestFullName,
        }
        dimensions.update(metadata_dims)
        return dimensions
