import constants
from pyVim.connect import SmartConnect
from pkg_resources import parse_version
import socket
import ssl
import yaml

DEFAULT_VERSION = '6.5.0'
REMOTE_SERVER = "www.signalfx.com"
REFERENCE_ARTICLE = "https://kb.vmware.com/s/article/2107096"


class BColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[0;32m'
    WARNING = '\033[1;33m'
    FAIL = '\033[0;31m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    TICK = u'\u2714'
    CROSS = u'\u2718'


def is_connected(hostname):
    try:
        host = socket.gethostbyname(hostname)
        socket.create_connection((host, 80), 2)
        print("VM is able to connect to {0}{1}{2}\t{3}{4}".format(BColors.OKGREEN, BColors.BOLD, hostname, BColors.TICK,
                                                                  BColors.ENDC))
        return True
    except Exception:
        print("VM is unable to connect to {0}{1}{2}\t{3}{4}".format(BColors.FAIL, BColors.BOLD, hostname, BColors.CROSS,
                                                                    BColors.ENDC))
        print("{0}Please check the network connectivity of the VM{1}".format(BColors.WARNING, BColors.ENDC))
        return False


def connect_to_vcenter(host, username, password):
    context = None
    si = None
    if hasattr(ssl, 'SSLContext'):
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
        context.verify_mode = ssl.CERT_NONE
    try:
        si = SmartConnect(host=host, user=username,
                          pwd=password, sslContext=context)
        print("The application is able to connect to vCenter host : {0}{1}{2}\t{3}{4}".format(BColors.OKGREEN,
                                                                                              BColors.BOLD, host,
                                                                                              BColors.TICK,
                                                                                              BColors.ENDC))
    except Exception:
        print("The application is unable to connect to vCenter host : {0}{1}{2}\t{3}{4}".format(BColors.FAIL,
                                                                                                BColors.BOLD, host,
                                                                                                BColors.CROSS,
                                                                                                BColors.ENDC))
        print("{0}Please check the credentials provided{1}".format(BColors.WARNING, BColors.ENDC))
        si = None
    return si


def check_version(si):
    if si is not None:
        version = si.content.about.version
        if parse_version(version) >= parse_version(DEFAULT_VERSION):
            print("vCenter version : {0}{1}{2}{3}\t{4}{5}{6}{7}".format(BColors.OKBLUE, BColors.BOLD,
                                                                        version, BColors.ENDC, BColors.OKGREEN,
                                                                        BColors.BOLD, BColors.TICK, BColors.ENDC))
        else:
            print("vCenter version : {0}{1}{2}{3}\t{4}{5}{6}{7}".format(BColors.OKBLUE, BColors.BOLD,
                                                                        version, BColors.ENDC, BColors.FAIL,
                                                                        BColors.BOLD, BColors.CROSS, BColors.ENDC))
            print("{0}Please check the following article before starting the application to avoid any issues : "
                  "{1}{2}{3}{4}".format(BColors.WARNING, BColors.BOLD, BColors.UNDERLINE,
                                        REFERENCE_ARTICLE, BColors.ENDC))


def check(host, username, password):
    if is_connected(REMOTE_SERVER):
        si = connect_to_vcenter(host, username, password)
        check_version(si)


def perform_basic_checks():
    f = open(constants.CONFIG_FILE)
    config = (yaml.load(f))['config']
    for conf in config:
        host = conf['host']
        username = conf['username']
        password = conf['password']
        check(host, username, password)


perform_basic_checks()
