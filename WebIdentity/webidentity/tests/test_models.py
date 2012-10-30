# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from webidentity.models import DBSession
from webidentity.tests import _initTestingDB
from webidentity.tests import DUMMY_USER_ATTRIBUTES

import unittest


class TestCascade(unittest.TestCase):

    def setUp(self):
        _initTestingDB(echo=True)

    def tearDown(self):
        DBSession.remove()

    def DISABLED__test_cascading_delete(self):
        from webidentity.models import Persona
        from webidentity.models import User
        from webidentity.models import UserAttribute
        from webidentity.models import VisitedSite

        user = User(u'john.doe', u'secret', u'john@doe.com')
        user.personas.append(
            Persona(u'Test persönä', attributes=[
                UserAttribute(type_uri, value)
                for type_uri, value
                in DUMMY_USER_ATTRIBUTES.iteritems()]))
        user.personas.append(
            Persona(u'Reversed persönä', attributes=[
                UserAttribute(type_uri, ''.join(reversed(value)))
                for type_uri, value
                in DUMMY_USER_ATTRIBUTES.iteritems()]))

        site1 = VisitedSite('http://www.rp.com', remember=False)
        site2 = VisitedSite('http://www.plone.org', remember=True)
        site2.persona = user.personas[0]

        user.visited_sites.append(site1)
        user.visited_sites.append(site2)

        session = DBSession()
        session.add(user)
        session.flush()

        self.assertEquals(2, len(session.query(User).get(1).personas))
        self.assertEquals(2, len(session.query(User).get(1).visited_sites))
        self.assertEquals(6, len(session.query(User).get(1).personas[0].attributes))

        session.query(User).filter_by(username=u'john.doe').delete()
        session.flush()

        self.assertEquals(0, session.query(User).count())
        self.assertEquals(0, session.query(Persona).count())
        self.assertEquals(0, session.query(UserAttribute).count())
        self.assertEquals(0, session.query(VisitedSite).count())


class TestUser(unittest.TestCase):

    def _makeUser(self, *args, **kwargs):
        from webidentity.models import User
        return User(*args, **kwargs)

    def test_check_password(self):
        user = self._makeUser(username=u'dokai', password=u'secret', email=u'dokai@iki.fi')
        # The password is not stored in plain text
        self.failIfEqual(user.password, u'secret')
        # Verification against a plain text candidate works
        self.failUnless(user.check_password(u'secret'))
        # Invalid passwords are rejected
        self.failIf(user.check_password(u'invalid'))
