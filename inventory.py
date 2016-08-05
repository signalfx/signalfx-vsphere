"""
Module containing classes for getting the inventory for a vCenter Server,
caching relevant information, and periodically updating it.
"""
from pyVmomi import vim
import threading
import time

# Load the dummy collectd module if running this module outside of collectd
try:
    import collectd
except ImportError:
    import dummy_collectd as collectd


class InventoryManager(threading.Thread):
    def __init__(self, si, refresh_interval, vc_name,  *args, **kwargs):
        self._si = si
        self._refresh_interval = refresh_interval
        self._vc_name = vc_name
        self._perf_manager = self._si.RetrieveServiceContent().perfManager
        threading.Thread.__init__(self, *args, **kwargs)
        self.daemon = True
        self.update_lock = threading.Lock()
        self._stop_signal = threading.Event()
        self._has_inventory = threading.Event()
        self._cache = self._new_cache()

    def _new_cache(self):
        """
        Creates a new, empty cache that will be used to store inventory objects
        """
        cache = {
            'datacenters': [],
            'clusters': [],
            'hosts': [],
            'vms': [],
        }
        return cache

    def _sync(self, mor, cache):
        """
        Recursively walk the tree of inventory objects and update the cache
        as we find elements we're interested in monitoring.
        """
        if isinstance(mor, vim.Folder):
            # We're not interested in monitoring folders directly, so walk
            # their contents instead
            for item in mor.childEntity:
                self._sync(item, cache)

        elif isinstance(mor, vim.Datacenter):
            # TODO: Figure out why maxSample doesn't work for querying
            # datacenter metrics
            # cache['datacenters'].append(
            #    Datacenter(mor, self._perf_manager, self._vc_name))
            for item in mor.hostFolder.childEntity:
                self._sync(item, cache)

        # Standalone hosts not in a cluster
        elif isinstance(mor, vim.ComputeResource):
            for host in mor.host:
                if hasattr(host, 'vm'):
                    self._sync(host, cache)

        elif isinstance(mor, vim.ClusterComputeResource):
            cache['clusters'].append(
                Cluster(mor, self._perf_manager, self._vc_name))
            for host in mor.host:
                if hasattr(host, 'vm'):
                    self._sync(host, cache)

        elif isinstance(mor, vim.HostSystem):
            cache['hosts'].append(
                Host(mor, self._perf_manager, self._vc_name))
            for vm in mor.vm:
                if vm.runtime.powerState == 'poweredOn':
                    self._sync(vm, cache)

        elif isinstance(mor, vim.VirtualMachine):
            cache['vms'].append(
                VirtualMachine(mor, self._perf_manager, self._vc_name))

        else:
            collectd.warning("Unhandled managed object: %s" % mor)

    def sync_inventory(self):
        cache = self._new_cache()
        self._sync(self._si.RetrieveServiceContent().rootFolder, cache)
        with self.update_lock:
            self._cache = cache
        self._has_inventory.set()

    def block_until_inventory(self, timeout=None):
        """
        Wait until the inventory cache is populated. Useful for right after
        the thread starts.

        Args:
            timeout (int): The maximum time to wait before raising
                an exception

        Returns:
            True if metric metadata was retrieved within the timeout.
            False if the timeout was exceeded.
        """
        return self._has_inventory.wait(timeout=timeout)

    def current_inventory(self):
        """
        Thread-safe way to get the current inventory cache.

        Returns:
            dict: map of {str: list of InventoryObject}
                The mapping of inventory type (datacenter, host, cluster,
                vm) to inventory objects of that type
        """
        with self.update_lock:
            return self._cache

    def run(self):
        while not self._stop_signal.is_set():
            next_interval = time.time() + self._refresh_interval
            try:
                self.sync_inventory()
            except Exception as e:
                collectd.error("Exception when syncing vCenter inventory, "
                               "continuing anyway: %s" % e)
                raise  # *************TEMPORARY FOR TESTING************
            except KeyboardInterrupt:
                break
            # Wait until next time
            sleep_time = next_interval - time.time()
            collectd.info("vCenter inventory sync complete. Next sync in "
                          "%d seconds" % sleep_time)
            if sleep_time < 0:
                collectd.warning("vCenter inventory time exceeded the refresh "
                                 "interval")
            while (not self._stop_signal.is_set() and
                   time.time() < next_interval):
                time.sleep(1)

    def stop(self):
        self._stop_signal.set()


class InventoryObject(object):
    # Time in seconds representing vCenter's "instantaneous" interval
    INSTANT_INTERVAL = 20  # seconds

    def __init__(self, mor, perf_mgr, vc_name):
        self.mor = mor
        self._perf_mgr = perf_mgr
        self._vc_name = vc_name
        # Mapping of integer counter key to its corresponding MetricId object
        self.metric_id_map = self._mor_metrics()
        self.dimensions = self._get_dimensions()
        self.properties = self._get_properties()
        self.sf_metadata_dims = self._get_sf_metadata_dims()

    def _mor_metrics(self):
        """
        Determines the metrics being published by a given managed object

        Args:
            mor (ManagedObject): Managed object to get metrics from
        """
        metrics = self._perf_mgr.QueryAvailablePerfMetric(
            self.mor, None, None, self.INSTANT_INTERVAL)
        metric_map = {}
        for metric_id_obj in metrics:
            metric_map[metric_id_obj.counterId] = metric_id_obj
        return metric_map

    def _get_dimensions(self):
        return {}

    def _get_properties(self):
        return []

    def _get_sf_metadata_dims(self):
        return {}


class Datacenter(InventoryObject):
    INSTANT_INTERVAL = 300
    pass


class Cluster(InventoryObject):
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
            'esx_host': self.mor.runtime.host.name,
        }
        dimensions.update(metadata_dims)
        return dimensions
