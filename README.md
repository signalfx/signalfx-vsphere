# SignalFx vSphere integration
SignalFx Integration for VMware vSphere

## Installation

### Using code directly - On Linux(16.*)
* Checkout this repository somewhere on your system accessible. Copy all the files to `/usr/share/vsphere`
* Install the Python requirements with sudo ```pip install -r requirements.txt```
* Configure the application (see below)
* Place the config.yaml in ```/etc/vsphere```
* Start the application with following command ```$ ./vsphere-monitor start```

### Using SignalFx's OVF
* Download the latest SignalFx-vSphere monitoring application <a target="_blank" href="https://github.com/signalfx/signalfx-vsphere/releases"> OVF Template</a> zip file.
* Unzip the OVF Template zip file
* Deploy the OVF Template to a host that can access the vCenter Server that you want to monitor.
* Login to the virtual machine . User : ```signalfx``` Password : ```signalfx```
* Modify the sample configuration file located at ```/etc/vsphere/config.yaml``` as described in [Configuration](#configuration), below.
* Restart the service by  ```$ service vsphere-monitor restart```


## Requirements

* Python 3.6 or later
* vSphere 6.5 or later


## Configuration
The following are required configuration keys:

* host - Required. Hostname or IP address of the vCenter Server.
* username - Required. Username required to login to vCenter Server.
* password - Required. Password required to login to vCenter Server.
* Name - Required. Name of the vCenter Server.
* IngestToken -  Required. SignalFx Ingest Token required to send metrics to ingest server.

Optional configurations keys include:

* MORSyncInterval - Time interval at which the vCenter inventory should be synced.
* MetricSyncInterval - Time interval at which the available metrics should be synced.
* IngestEndpoint - The url of ingest endpoint to send to metrics.
* IncludeMetric - Metrics required for different inventory objects can be included individually. Currently metrics can be added for datacenter, cluster, host and vm.
* ExcludeMetric - Metrics emitted from different inventory objects can be excluded individually.
* Dimensions - Additional dimensions specific to environment.

NOTE: Multiple vCenter servers can be configured for monitoring within the same file.

```
config:
  - host: 192.168.1.60
    username: administrator@vsphere.local
    password: Abcd123$
    Name: VCenter4
    IngestToken: **************
    IngestEndpoint: 'https://ingest.signalfx.com'
    MORSyncInterval: 300
    MetricSyncInterval: 300
    IncludeMetrics:
      host:
        - random.test.metric
      cluster:
        - mem.usage.average
    Dimensions:
      test_name: "Test name"
      test_dim: "Test Dim"

  - host: 192.168.1.20
    username: administrator@vsphere.local
    password: Abcd123$
    Name: 192.168.1.20
    IngestToken: **************
    IngestEndpoint: 'https://ingest.signalfx.com'
    MORSyncInterval: 20
    MetricSyncInterval: 60
    EncludeMetrics:
      host:
        - disk.usage.average
```
