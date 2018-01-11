metrics = {
    'host': [
        'sys.uptime.latest',

        'cpu.utilization.average',
        'cpu.usagemhz.average',
        'cpu.ready.summation',
        'cpu.swapwait.summation',
        'cpu.idle.summation',
        'cpu.latency.average',

        'mem.usage.average',
        'mem.granted.average',
        'mem.consumed.average',
        'mem.active.average',
        'mem.shared.average',
        'mem.sharedcommon.average',
        'mem.swapin.average',
        'mem.swapout.average',

        'disk.usage.average',
        'disk.read.average',
        'disk.write.average',
        'disk.totalLatency.average',

        'datastore.read.average',
        'datastore.write.average',
        'datastore.totalReadLatency.average',
        'datastore.totalWriteLatency.average',

        'net.usage.average',
        'net.received.average',
        'net.transmitted.average',
        'net.errorsRx.summation',
        'net.errorsTx.summation',
    ],
    'vm': [
        'sys.uptime.latest',

        'cpu.usage.average',
        'cpu.usagemhz.average',
        'cpu.ready.summation',
        'cpu.swapwait.summation',
        'cpu.idle.summation',
        'cpu.latency.average',

        'mem.usage.average',
        'mem.granted.average',
        'mem.consumed.average',
        'mem.active.average',
        'mem.shared.average',
        'mem.swapin.average',
        'mem.swapout.average',

        'disk.usage.average',
        'disk.read.average',
        'disk.write.average',

        'virtualDisk.totalReadLatency.average',
        'virtualDisk.totalWriteLatency.average',

        'datastore.read.average',
        'datastore.write.average',
        'datastore.totalReadLatency.average',
        'datastore.totalWriteLatency.average',

        'net.usage.average',
        'net.received.average',
        'net.transmitted.average',
        'net.errorsRx.summation',
        'net.errorsTx.summation',
    ],
    'cluster': [],
    'datacenter': []
}


def get_metrics(conf):
    vsphere_metrics = metrics.copy()
    if 'include_metrics' in conf:
        for mor in conf['include_metrics'].keys():
            vsphere_metrics[mor].extend(conf['include_metrics'][mor])
    if 'exclude_metrics' in conf:
        for mor in conf['exclude_metrics'].keys():
            if mor in vsphere_metrics.keys():
                for metric in conf['exclude_metrics'][mor]:
                    vsphere_metrics[mor].remove(metric)
    return vsphere_metrics
