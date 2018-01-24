import logging
import os
import socket
import unittest

import vcr
from vcr import config
from vcr.stubs import VCRHTTPSConnection

from pyVmomi import SoapAdapter


def tests_resource_path(local_path=''):
    this_file = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(this_file, local_path)


fixtures_path = tests_resource_path('fixtures')


def monkey_patch_vcrpy():
    vcr.stubs.VCRHTTPSConnection.is_verified = True
    vcr.stubs.VCRFakeSocket = socket.socket


class VCRTestBase(unittest.TestCase):
    my_vcr = config.VCR(
        custom_patches=((SoapAdapter, '_HTTPSConnection', VCRHTTPSConnection),))

    def setUp(self):
        monkey_patch_vcrpy()
        logging.basicConfig()
