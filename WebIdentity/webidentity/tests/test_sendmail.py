# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from pyramid import testing
from webidentity.tests import DUMMY_SETTINGS

import mock
import unittest


class TestSendmail(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    @mock.patch('webidentity.sendmail.SMTPMailer')
    def test__setup_delivery__with_settings(self, SMTPMailer):
        from webidentity.sendmail import _setup_delivery

        self.config.add_settings(DUMMY_SETTINGS)
        _setup_delivery()
        self.assertEquals(SMTPMailer.call_args, ((), {
            'debug_smtp': True,
            'hostname': u'stmp.provider.com',
            'port': 1025}))

    @mock.patch('webidentity.sendmail.SMTPMailer')
    def test__setup_delivery__missing_settings(self, SMTPMailer):
        from webidentity.sendmail import _setup_delivery

        self.config.add_settings({})
        _setup_delivery()
        self.assertEquals(SMTPMailer.call_args, ((), {
            'debug_smtp': False,
            'hostname': u'localhost',
            'port': 25}))

    @mock.patch('webidentity.sendmail.SMTPMailer')
    def test__setup_delivery__invalid_settings(self, SMTPMailer):
        from webidentity.sendmail import _setup_delivery

        self.config.add_settings({
            'webidentity_smtp_port': 'foobar',
        })
        _setup_delivery()
        self.assertEquals(SMTPMailer.call_args, ((), {
            'debug_smtp': False,
            'hostname': u'localhost',
            'port': 25}))

    @mock.patch('webidentity.sendmail.DirectMailDelivery')
    def test_send_mail(self, DirectMailDelivery):
        from webidentity.sendmail import send_mail

        self.config.add_settings({})
        # Check that we propagate parameters correctly to the delivery system
        send_mail(u'My message', to='john@doe.com')
        self.assertEquals(DirectMailDelivery().send.call_args_list, [
            ((u'My message', ), {'to': 'john@doe.com'})])
