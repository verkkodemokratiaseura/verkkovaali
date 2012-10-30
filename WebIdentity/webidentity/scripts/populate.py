# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
from paste.deploy import appconfig
from sqlalchemy import engine_from_config
from webidentity.models import DBSession
from webidentity.models import User
from webidentity.models import initialize_sql

import os
import sys
import transaction


def get_config():
    if len(sys.argv) < 2:
        print("Usage: {0} <config>".format(sys.argv[0]))
        sys.exit(1)

    config_uri = 'config:{0}#webidentity'.format(
        os.path.join(os.getcwd(), sys.argv[1].strip()))

    return appconfig(config_uri)


def populate_demo():
    """Populates the database with 50 demo users."""
    engine = engine_from_config(get_config(), 'sqlalchemy.')
    initialize_sql(engine, False)

    session = DBSession()

    for count in range(1, 51):
        session.add(User('test.user{0:02}'.format(count), 'testi', 'xxxx@xxxx.xx'))

    session.add(User('test.pref01', 'testi', u'xxxx@xxxx.xx'))
    session.add(User('test.pref02', 'testi', None))
    session.add(User('test.pref03', 'testi', u'xxxx@xxxx.xx'))
    session.add(User('test.pref04', 'testi', u'xxxx@xxxx.xx'))
    session.add(User('test.pref05', 'testi', None))

    session.flush()
    transaction.commit()
    print("Generated 50 demo users.")


def populate_accounts():
    """Populates the database with production data."""
    engine = engine_from_config(get_config(), 'sqlalchemy.')
    initialize_sql(engine, False)
    session = DBSession()

    if len(sys.argv) < 3:
        print "Usage: {0} <config> <data>".format(sys.argv[0])
        sys.exit(1)

    for line in open(sys.argv[2]).readlines():
        username, password = line.strip().split('|', 1)
        session.add(User(username.strip(), password.strip(), 'xxxx@xxxx.xx'))
        print username

    session.flush()
    transaction.commit()


def verify_accounts():
    """Verifies the create accounts against the password file."""
    engine = engine_from_config(get_config(), 'sqlalchemy.')
    initialize_sql(engine, False)
    session = DBSession()

    if len(sys.argv) < 3:
        print "Usage: {0} <config> <data>".format(sys.argv[0])
        sys.exit(1)

    users = dict((user.username, user) for user in session.query(User).all())
    failed = 0

    print "Checking.."
    passwords = open(sys.argv[2]).readlines()
    for line in passwords:
        username, password = line.strip().split('|', 1)
        if username not in users:
            print "Unknown user:", username
            failed += 1
        elif not users[username].check_password(password):
            print "Invalid password for user", username
            failed += 1

    print "Checked", len(passwords), "passwords against", len(users), "users."
    print "Failures", failed
    if failed == 0:
        print "All OK"
    else:
        print "Data inconsistency, please investigate!"
