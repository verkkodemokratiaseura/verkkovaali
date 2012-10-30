# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from sqlalchemy import create_engine

# These settings can be used with Configuration().add_settings()
# in unit / integration tests.
DUMMY_SETTINGS = {
    u'webidentity_user_attributes': u'''\
        http://axschema.org/namePerson Fullname
        http://axschema.org/namePerson/first First näme
        http://axschema.org/namePerson/last Last name
        http://axschema.org/company/name Company
        http://axschema.org/contact/city City
        http://axschema.org/contact/email Email''',
    u'webidentity_from_address': u'webidentity@provider.com',
    u'webidentity_date_format': u'%d.%m.%Y %H:%M',
    u'webidentity_smtp_port': u'1025',
    u'webidentity_smtp_host': u'stmp.provider.com',
    u'webidentity_smtp_debug': u'true',
    u'session.key': 'nuorisovaalit',
    u'session.cookie_expires': 'true',
    u'session.type': 'cookie',
    u'session.auto': 'true',
}

DUMMY_USER_ATTRIBUTES = {
    u'http://axschema.org/namePerson': u'Jöhn Döe',
    u'http://axschema.org/namePerson/first': u'Jöhn',
    u'http://axschema.org/namePerson/last': u'Döe',
    u'http://axschema.org/company/name': u'Äcme Inc',
    u'http://axschema.org/contact/city': u'Röswell',
    u'http://axschema.org/contact/email': u'john@doe.com',
}


class DummyOpenIdRequest(object):
    """Dummy OpenID request."""

    def __init__(self, message, trust_root=''):
        self.message = message
        self.trust_root = trust_root


def _initTestingDB(echo=False):
    from webidentity.models import initialize_sql
    engine = create_engine('sqlite:///', echo=echo)
    session = initialize_sql(engine, populate_db=False)
    return session
