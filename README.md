# SignalFX Vsphere integration
SignalFx Integration for VMware vSphere

## Installation

### Using code directly - On Linux(16.*)
* Checkout this repository somewhere on your system accessible. Copy all the files to `/usr/share/vsphere`
* Install the Python requirements with sudo ```pip install -r requirements.txt```
* Configure the application (see below)
* Place the config.yaml in ```/etc/vsphere```
* Start the application with following command ```$ ./vsphere-monitor start```

### Using OVF
* Download the SignalFx-Vsphere monitoring application <a target="_blank" href="https://github.com/signalfx/signalfx-vsphere/releases/tag/v1.0.0/"> ovf template</a>.
* Deploy the ovf template at place where VCenter(to be monitored) is accessible.
* Login to the virtual machine . User : ```signalfx``` Password : ```signalfx```
* Modify the sample configuration file located at ```/etc/vsphere/config.yaml``` as described in [Configuration](#configuration), below.
* Restart the service by  ```$ service vsphere-monitor restart```


## Requirements

* Python 3.6 or later
* VSphere 6.5 or later


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


Note that multiple vCenter servers can be configured in the same file.

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