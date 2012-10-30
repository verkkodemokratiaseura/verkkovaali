# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from openidalchemy.models import bind_engine
from openidalchemy.store import AlchemyStore
from openidalchemy.storetest import testStore
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker

import time
import unittest

DBSession = scoped_session(sessionmaker())


def initialize_sql(db_string='sqlite://', echo=False):
    engine = create_engine(db_string, echo=echo)
    DBSession.configure(bind=engine)
    bind_engine(engine)


class TestOpenIDStore(unittest.TestCase):

    def setUp(self):
        initialize_sql()

    def tearDown(self):
        DBSession.remove()

    def test_AlchemyStore(self):
        """Run the OpenIDStore API tests from python-openid."""
        testStore(AlchemyStore(DBSession()))


class TestAssociation(unittest.TestCase):

    def test_fromOpenIdAssociation(self):
        from openidalchemy.models import Association
        from openid import association

        openid_assoc = association.Association('<handle>', 's3kr3t', 12345678, 7200, 'HMAC-SHA256')
        assoc = Association.fromOpenIdAssociation('http://example.com', openid_assoc)

        self.assertEquals(assoc.server_url, 'http://example.com')
        self.assertEquals(assoc.handle, '<handle>')
        self.assertEquals(assoc.secret, 's3kr3t')
        self.assertEquals(assoc.issued, 12345678)
        self.assertEquals(assoc.lifetime, 7200)
        self.assertEquals(assoc.assoc_type, 'HMAC-SHA256')

    def test_update__handle_mismatch(self):
        from openidalchemy.models import Association
        from openid import association

        assoc = Association('http://example.com', '<handle>', 'secret', int(time.time()), 3600, 'HMAC-SHA1')
        openid_assoc = association.Association('<otherhandle>', 'secret', int(time.time()), 7200, 'HMAC-SHA1')
        self.assertRaises(ValueError, lambda: assoc.update(openid_assoc))

    def test_update(self):
        from openidalchemy.models import Association
        from openid import association

        assoc = Association('http://example.com', '<handle>', 'secret', 1234567, 3600, 'HMAC-SHA1')
        openid_assoc = association.Association('<handle>', 's3kr3t', 12345678, 7200, 'HMAC-SHA256')
        assoc.update(openid_assoc)

        self.assertEquals(assoc.handle, '<handle>')
        self.assertEquals(assoc.secret, 's3kr3t')
        self.assertEquals(assoc.issued, 12345678)
        self.assertEquals(assoc.lifetime, 7200)
        self.assertEquals(assoc.assoc_type, 'HMAC-SHA256')
