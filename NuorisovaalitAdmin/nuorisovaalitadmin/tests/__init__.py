# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from nuorisovaalit.models import School
from nuorisovaalit.tests import populate_testing_db as populate_db
from nuorisovaalitadmin.models import DBSession
from nuorisovaalitadmin.models import User

import datetime
import unittest2
import xlrd


class XlsTestCase(unittest2.TestCase):

    maxDiff = None

    def assertXlsEquals(self, name, structure, xls_contents, adapters=None, skip_header=True, sheet=0, col_widths=None):
        """Assert the given list of tuples against the Xls file
        contents. Each list item represents a row in the Xls file and
        each tuple item represents a cell value in the corresponding
        row.

        :param structure: List of tuples representing the Xls file as
                          a matrix.
        :type structure: list

        :param xls_contents: The Xls file contents.
        :type xls_contents: str

        :param sheet: Index number of the sheet that is asserted (default 0).
        :type sheet: int

        :param adapters: Optional tuple of functions to convert the
                         xls cell values in the corresponding column
                         into the required type.
        :type adapters: tuple
        """
        wb = xlrd.open_workbook(file_contents=xls_contents, formatting_info=True)
        ws = wb.sheet_by_index(sheet)

        self.assertEquals(name, ws.name)

        if adapters is None:
            adapters = [None] * ws.ncols

        offset = 1 if skip_header else 0

        self.assertEquals(len(structure) + offset, ws.nrows)
        self.assertEquals(len(structure[0]), ws.ncols)
        self.assertEquals(len(adapters), ws.ncols)

        # Assert column widths if they were given.
        if len(structure) > 0 and col_widths is not None:
            self.assertEquals(ws.ncols, len(col_widths))
            for i in xrange(ws.ncols):
                self.assertEquals(col_widths[i], ws.computed_column_width(i))

        xls = []
        for i in xrange(offset, ws.nrows):
            row = []
            for j in xrange(ws.ncols):
                if callable(adapters[j]):
                    try:
                        row.append(adapters[j](ws.cell_value(i, j)))
                    except:
                        row.append(ws.cell_value(i, j))
                else:
                    row.append(ws.cell_value(i, j))
            xls.append(tuple(row))
        self.assertEquals(structure, xls)


def init_testing_db():
    from sqlalchemy import create_engine
    from nuorisovaalitadmin.models import initialize_sql
    initialize_sql(create_engine('sqlite://'))


def populate_testing_db():
    session = DBSession()
    populate_db()
    school = session.query(School).first()
    session.add(User(u'keijo',
                     u'passwd',
                     u'Keijo Käyttäjä',
                     'keijo.kayttaja@example.org',
                     True,
                     school))
    session.flush()


def static_datetime(date):
    """Returns a modified ``datetime.datetime`` class with a static .now()
    method which returns the given ``date`` which must be an instance of
    ``datetime.datetime``."""
    if not isinstance(date, datetime.datetime):
        raise TypeError('The static datetime must be an instance of datetime.datetime.')

    class StaticNow(datetime.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return date

    return StaticNow


# These settings can be used with Configuration().add_settings()
# in unit / integration tests.
DUMMY_SETTINGS = {
    u'nuorisovaalitadmin_user_attributes': u'''\
        http://axschema.org/namePerson Fullname
        http://axschema.org/namePerson/first First näme
        http://axschema.org/namePerson/last Last name
        http://axschema.org/company/name Company
        http://axschema.org/contact/city City
        http://axschema.org/contact/email Email''',
    u'nuorisovaalitadmin.from_address': u'xxxx@xxxx.xxx',
    u'nuorisovaalitadmin.date_format': u'%d.%m.%Y %H:%M',
    u'nuorisovaalitadmin.smtp_port': u'1025',
    u'nuorisovaalitadmin.smtp_host': u'stmp.provider.com',
    u'nuorisovaalitadmin.smtp_debug': u'true',
    u'session.key': 'nuorisovaalit',
    u'session.cookie_expires': 'true',
    u'session.type': 'cookie',
    u'session.auto': 'true',
}
