# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
from pyramid import testing

import mock
import unittest2 as unittest


class DefaultSendMailTest(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def test_setup_delivery__settings(self):
        from nuorisovaalitadmin.sendmail import _setup_delivery

        mailer = _setup_delivery().mailer
        self.assertEquals('localhost', mailer.hostname)
        self.assertEquals(25, mailer.port)
        self.assertEquals(False, mailer.debug_smtp)


class ConfiguredSendMailTest(unittest.TestCase):

    def setUp(self):
        settings = {
            'nuorisovaalitadmin.smtp_host': 'my-host',
            'nuorisovaalitadmin.smtp_port': '1025',
            'nuorisovaalitadmin.smtp_debug': 'true',
        }
        self.config = testing.setUp(settings=settings)

    def tearDown(self):
        testing.tearDown()

    def test_setup_delivery__settings(self):
        from nuorisovaalitadmin.sendmail import _setup_delivery

        mailer = _setup_delivery().mailer
        self.assertEquals('my-host', mailer.hostname)
        self.assertEquals(1025, mailer.port)
        self.assertEquals(True, mailer.debug_smtp)


class BadConfigurationSendMailTest(unittest.TestCase):

    def setUp(self):
        settings = {
            'nuorisovaalitadmin.smtp_port': 'bad',
        }
        self.config = testing.setUp(settings=settings)

    def tearDown(self):
        testing.tearDown()

    def test_setup_delivery__settings(self):
        from nuorisovaalitadmin.sendmail import _setup_delivery

        mailer = _setup_delivery().mailer
        self.assertEquals(25, mailer.port)


class FunctionEntrypointTest(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def test_send_mail__call_delegates_with_params(self):
        from nuorisovaalitadmin import sendmail

        self.failUnless(sendmail._delivery is None)
        sendmail._delivery = sendmail._setup_delivery()
        self.failIf(sendmail._delivery is None)

        # Assert that calls to function delegate get passed to the delivery object.
        sendmail._delivery.send = mock.Mock()
        sendmail.send_mail(u'foo', u'bar', foo=1, bar=2)
        sendmail._delivery.send.assert_called_once_with(u'foo', u'bar', foo=1, bar=2)

    @mock.patch('nuorisovaalitadmin.sendmail.DirectMailDelivery', mock.Mock())
    def test_send_mail__create_delivery_on_demand(self):
        from nuorisovaalitadmin import sendmail

        sendmail._delivery = None
        self.failUnless(sendmail._delivery is None)
        # Call the method to force the delivery to be instansiated.
        sendmail.send_mail()
        self.failIf(sendmail._delivery is None)
