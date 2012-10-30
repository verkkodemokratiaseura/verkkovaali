# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from cStringIO import StringIO
from datetime import date
from nuorisovaalitadmin.models import DBSession
from nuorisovaalitadmin.tests import XlsTestCase
from nuorisovaalitadmin.tests import init_testing_db
from nuorisovaalitadmin.tests import populate_testing_db
from pyramid import testing
from pyramid.exceptions import Forbidden
from pyramid.session import UnencryptedCookieSessionFactoryConfig
from pyramid.testing import DummyRequest
from pyramid.url import route_url
from webob import Response
from webob.exc import HTTPFound

import csv
import mock
import os
import time
import unittest2 as unittest
import xlrd
import xlwt


def make_csv_dict(rows):
    """Returns a list of dictionaries containing the data in the given
    rows.
    """
    from nuorisovaalitadmin.views.school import SubmitVoters
    return [dict((key, value)
                 for key, value
                 in zip(SubmitVoters.CSV_FIELDS, row))
            for row in rows]


def make_csv_file(rows, encoding='latin-1', delimiter=','):
    """Returns a file-like object containing the rows.

    :param rows: iterable of tuples containing the data for each row.
    :type rows: iterable
    """
    from nuorisovaalitadmin.views.school import SubmitVoters

    headers = SubmitVoters.CSV_HEADER

    csvfile = StringIO()
    writer = csv.writer(csvfile, delimiter=delimiter)

    writer.writerow([v.encode(encoding) for v in headers])
    for row in rows:
        writer.writerow([v.encode(encoding) for v in row])

    csvfile.seek(0)
    return csvfile


def make_xls_file(rows, headers, formats):
    """Returns a file-like object containing the rows.

    :param rows: iterable of tuples containing the data for each row.
    :type rows: iterable
    """
    xlsfile = StringIO()
    wb = xlwt.Workbook()
    ws = wb.add_sheet('Nuorisovaalit 2011')

    # Compile the style objects
    styles = []
    for fmt in formats:
        if fmt is None:
            styles.append(None)
        else:
            styles.append(xlwt.easyxf(num_format_str=fmt))

    for c, header in enumerate(headers):
        ws.write(0, c, header)

    for r, row in enumerate(rows, start=1):
        for c, item in enumerate(row):
            if len(styles) == len(row) and styles[c] is not None:
                ws.write(r, c, item, styles[c])
            else:
                ws.write(r, c, item)

    wb.save(xlsfile)
    xlsfile.seek(0)

    return xlsfile


def open_test_file(filename):
    """Opens a test file and returns the file handle."""
    return open(os.path.join(os.path.dirname(__file__), 'data', filename), 'rb')


class SubmitVoterTest(unittest.TestCase):
    """Tests for the voter info submission functionality."""

    def setUp(self):
        self.config = testing.setUp()
        init_testing_db()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_CSVSubmission__with_invalid_kind(self):
        from nuorisovaalit.models import School
        from nuorisovaalitadmin.models import CSVSubmission

        populate_testing_db()
        session = DBSession()
        school = session.query(School).first()
        self.assertTrue(school is not None)

        self.assertRaises(ValueError, lambda: CSVSubmission(None, school, u'invalid kind'))

    def test_submit_voters__unauthenticated(self):
        from nuorisovaalitadmin.views.school import SubmitVoters

        self.assertRaises(Forbidden, lambda: SubmitVoters(DummyRequest()).submit_voters())

    def test_submit_voters__empty_no_post(self):
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import SubmitVoters

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()

        self.config.testing_securitypolicy(userid=user.username)
        self.config.add_route('voters_template_xls', '/voters-template.xls')
        self.config.add_route('submit_voters', '/submit-voters')
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()
        options = SubmitVoters(request).submit_voters()

        self.assertEquals(options, {
            'csrf_token': csrf_token,
            'errors': None,
            'errors_left': 0,
            'file_type_error': None,
            'template_url': 'http://example.com/voters-template.xls',
            'action_url': 'http://example.com/submit-voters',
            'data_length_text': u'0 henkilöä',
            'submission': None})

    @mock.patch('nuorisovaalitadmin.models.datetime')
    def test_submit_voters__with_existing_submission_no_post(self, mock_datetime):
        from datetime import datetime
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.models import CSVSubmission
        from nuorisovaalitadmin.views.school import SubmitVoters

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()
        # Set a static datetime value for the the submission entry.
        mock_datetime.now.return_value = datetime(2011, 1, 28, 9, 27)

        # Initialize the previously stored submission data.
        submission = (
            {'address': u'Väinötie 5, 00200 Laukaa',
             'dob': u'15.11.1990',
             'email': u'matti@maikalainen.fi',
             'firstname': u'Mätti',
             'gsm': u'040 123 456',
             'lastname': u'Meikäläinen'},
            {'address': u'Jössäin kaukana',
             'dob': u'1.3.1982',
             'email': u'maija@maikalainen.com',
             'firstname': u'Mäijä',
             'gsm': u'0500 987 6543',
             'lastname': u'Meikäläinen'})
        session.add(CSVSubmission(submission, user.school, CSVSubmission.VOTER))
        session.flush()

        self.config.testing_securitypolicy(userid=user.username)
        self.config.add_route('voters_template_xls', '/voters-template.xls')
        self.config.add_route('submit_voters', '/submit-voters')
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()
        options = SubmitVoters(request).submit_voters()

        self.assertEquals(options, {
            'csrf_token': csrf_token,
            'errors': None,
            'errors_left': 0,
            'file_type_error': None,
            'template_url': 'http://example.com/voters-template.xls',
            'action_url': 'http://example.com/submit-voters',
            'data_length_text': u'2 henkilöä',
            'submission': {
                'timestamp': '28.01.2011 09:27',
                'data': (
                    {'firstname': u'Mätti', 'dob': u'15.11.1990', 'lastname': u'Meikäläinen', 'address': u'Väinötie 5, 00200 Laukaa', 'gsm': u'040 123 456', 'email': u'matti@maikalainen.fi'},
                    {'firstname': u'Mäijä', 'dob': u'1.3.1982', 'lastname': u'Meikäläinen', 'address': u'Jössäin kaukana', 'gsm': u'0500 987 6543', 'email': u'maija@maikalainen.com'})}})

    def test_submit_voters__with_post_validation_failure(self):
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import SubmitVoters

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()

        self.config.testing_securitypolicy(userid=user.username)
        self.config.add_route('voters_template_xls', '/voters-template.xls')
        self.config.add_route('submit_voters', '/submit-voters')
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)

        # Create a CSV file containing errors to upload.
        rows = [
            (u'Mätti', u'Meikäläinen', u'31.2.1992', u'040 123 456', u'matti@meikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            (u'Mätti', u'', u'15.11.1989', u'040 123 456', u'matti@meikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            (u'Mätti', u'Meikäläinen', u'1.2.1994', u'040 123 456', u'matti@meikalainen', u'Väinötie 5, 00200 Laukaa'),
            ]
        csvfile = mock.Mock()
        csvfile.file = make_csv_file(rows)
        csvfile.type = 'text/csv'

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()
        request.POST = {
            'csrf_token': csrf_token,
            'csvfile': csvfile,
        }
        options = SubmitVoters(request).submit_voters()

        self.assertEquals(options, {
            'action_url': 'http://example.com/submit-voters',
            'csrf_token': csrf_token,
            'errors': [{'lineno': 2, 'msg': u'Syntymäaika "31.2.1992" on väärän muotoinen.'},
                       {'lineno': 3, 'msg': u'Sukunimi puuttuu.'},
                       {'lineno': 4, 'msg': u'Sähköpostiosoite "matti@meikalainen" on väärän muotoinen.'}],
            'errors_left': 0,
            'file_type_error': None,
            'submission': None,
            'data_length_text': u'0 henkilöä',
            'template_url': 'http://example.com/voters-template.xls'})

    def test_submit_voters__with_post_validation_failure_with_more_than_limit_errors(self):
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import SubmitVoters

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()

        self.config.testing_securitypolicy(userid=user.username)
        self.config.add_route('voters_template_xls', '/voters-template.xls')
        self.config.add_route('submit_voters', '/submit-voters')
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)

        # Create a CSV file containing errors to upload.
        rows = [
            (u'Mätti', u'Meikäläinen', u'31.2.1992', u'040 123 456', u'matti@meikalainen.fi', u'Väinötie 5, 00200 Laukaa')
            for i in range(20)
            ]
        csvfile = mock.Mock()
        csvfile.file = make_csv_file(rows)
        csvfile.type = 'text/csv'

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()
        request.POST = {
            'csrf_token': csrf_token,
            'csvfile': csvfile,
        }
        options = SubmitVoters(request).submit_voters()

        self.assertEquals(options, {
            'action_url': 'http://example.com/submit-voters',
            'csrf_token': csrf_token,
            'errors': [{'lineno': i + 2, 'msg': u'Syntymäaika "31.2.1992" on väärän muotoinen.'}
                       for i in range(15)],
            'errors_left': 5,
            'file_type_error': None,
            'submission': None,
            'data_length_text': u'0 henkilöä',
            'template_url': 'http://example.com/voters-template.xls'})

    def test_submit_voters__with_post_validation_failure_due_to_invalid_file(self):
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import SubmitVoters

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()

        self.config.testing_securitypolicy(userid=user.username)
        self.config.add_route('voters_template_xls', '/voters-template.xls')
        self.config.add_route('submit_voters', '/submit-voters')
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)

        # Create an invalid file
        csvfile = mock.Mock()
        csvfile.file = StringIO('\0\0\0\0')
        csvfile.type = 'application/octet-stream'

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()
        request.POST = {
            'csrf_token': csrf_token,
            'csvfile': csvfile,
        }
        options = SubmitVoters(request).submit_voters()

        self.assertEquals(options, {
            'action_url': 'http://example.com/submit-voters',
            'csrf_token': csrf_token,
            'errors': [],
            'errors_left': 0,
            'file_type_error': True,
            'submission': None,
            'data_length_text': u'0 henkilöä',
            'template_url': 'http://example.com/voters-template.xls'})

    def test_submit_voters__with_post_csrf_mismatch(self):
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import SubmitVoters

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()

        self.config.testing_securitypolicy(userid=user.username)
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)

        # Create a dummy CSV file to upload.
        rows = [(u'', u'', u'', u'', u'', u'')]
        csvfile = mock.Mock()
        csvfile.file = make_csv_file(rows)

        request = DummyRequest()
        request.session.new_csrf_token()
        request.POST = {
            'csrf_token': 'invalid token',
            'csvfile': csvfile,
        }
        self.assertRaises(Forbidden, lambda: SubmitVoters(request).submit_voters())

    def test_submit_voters__with_csv_post_success(self):
        from nuorisovaalit.models import School
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.models import CSVSubmission
        from nuorisovaalitadmin.views.school import SubmitVoters

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()

        self.config.testing_securitypolicy(userid=user.username)
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        self.config.add_route('submit_voters', '/submit-voters')

        # Create a CSV file to upload.
        rows = [
            (u'Mätti', u'Meikäläinen', u'15.11.1990', u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            # Empty rows will be ignored.
            (u'', u'', u'', u'', u'', u''),
            (u'Mäijä', u'Meikäläinen', u'1.3.1987', u'0500 987 6543', u'maija@maikalainen.com', u'Jössäin kaukana'),
            ]
        csvfile = mock.Mock()
        csvfile.file = make_csv_file(rows)
        csvfile.type = 'text/csv'

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()
        request.POST = {
            'csrf_token': csrf_token,
            'csvfile': csvfile,
        }
        # Assert we get redirected to avoid resubmission on reload.
        redirect = SubmitVoters(request).submit_voters()
        self.assertEquals(redirect.location, 'http://example.com/submit-voters')

        # Assert the submission was persisted.
        session.flush()
        submission = session.query(CSVSubmission)\
                     .filter(CSVSubmission.kind == CSVSubmission.VOTER)\
                     .filter(School.id == user.school.id).first()
        self.assertEquals(submission.csv, (
            {'address': u'Väinötie 5, 00200 Laukaa',
             'dob': u'15.11.1990',
             'email': u'matti@maikalainen.fi',
             'firstname': u'Mätti',
             'gsm': u'040 123 456',
             'lastname': u'Meikäläinen'},
            {'address': u'Jössäin kaukana',
             'dob': u'1.3.1987',
             'email': u'maija@maikalainen.com',
             'firstname': u'Mäijä',
             'gsm': u'0500 987 6543',
             'lastname': u'Meikäläinen'}))

    def test_submit_voters__with_xls_post_success(self):
        from nuorisovaalit.models import School
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.models import CSVSubmission
        from nuorisovaalitadmin.views.school import SubmitVoters

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()

        self.config.testing_securitypolicy(userid=user.username)
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        self.config.add_route('submit_voters', '/submit-voters')

        # Create an xls file to upload.
        xlsfile = mock.Mock()
        xlsfile.file = open_test_file('SubmitVoters_ooo_3.2.1-excel_97_2000_xp.xls')
        xlsfile.type = 'application/vnd.ms-excel'

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()
        request.POST = {
            'csrf_token': csrf_token,
            'csvfile': xlsfile,
        }
        # Assert we get redirected to avoid resubmission on reload.
        redirect = SubmitVoters(request).submit_voters()
        self.assertEquals(redirect.location, 'http://example.com/submit-voters')

        # Assert the submission was persisted.
        session.flush()
        submission = session.query(CSVSubmission)\
                     .filter(CSVSubmission.kind == CSVSubmission.VOTER)\
                     .filter(School.id == user.school.id).first()
        self.assertEquals(submission.csv, (
            {'address': u'xxxx x, xxxxx xxxx',
             'dob': u'15.11.1992',
             'email': u'matti@meikalainen.fi',
             'firstname': u'Mätti Petteri',
             'gsm': u'040123456',
             'lastname': u'Meikäläinen'},
            {'address': u'xxxx x x, xxxxx xxxx',
             'dob': u'30.04.1990',
             'email': u'maija@meikalainen.fi',
             'firstname': u'Mäijä Mirjami',
             'gsm': u'05007654321',
             'lastname': u'Meikäläinen'}))

    def test_parse_xls__ooo_321_excel_5(self):
        """Parses an Excel 5 formatted file generated with OpenOffice.org 3.2.1."""
        from nuorisovaalitadmin.views.school import SubmitVoters

        parsed = SubmitVoters(None).parse_xls(open_test_file('SubmitVoters_ooo_3.2.1-excel_5.xls'))
        self.assertEquals(parsed, (
            {'address': u'xxxx x, xxxx xxxx',
             'dob': u'15.11.1992',
             'email': u'matti@meikalainen.fi',
             'firstname': u'Mätti Petteri',
             'gsm': u'040123456',
             'lastname': u'Meikäläinen'},
            {'address': u'xxxx x x, xxxxx xxxx',
             'dob': u'30.04.1990',
             'email': u'maija@meikalainen.fi',
             'firstname': u'Mäijä Mirjami',
             'gsm': u'05007654321',
             'lastname': u'Meikäläinen'}))

    def test_parse_xls__ooo_321_excel_95(self):
        """Parses an Excel 95 formatted file generated with OpenOffice.org 3.2.1."""
        from nuorisovaalitadmin.views.school import SubmitVoters

        parsed = SubmitVoters(None).parse_xls(open_test_file('SubmitVoters_ooo_3.2.1-excel_95.xls'))
        self.assertEquals(parsed, (
            {'address': u'Väinämöisenkatu 3, 00400 Espoo',
             'dob': u'15.11.1992',
             'email': u'matti@meikalainen.fi',
             'firstname': u'Mätti Petteri',
             'gsm': u'040123456',
             'lastname': u'Meikäläinen'},
            {'address': u'Työpajankatu 6 A, 00580 Helsinki',
             'dob': u'30.04.1990',
             'email': u'maija@meikalainen.fi',
             'firstname': u'Mäijä Mirjami',
             'gsm': u'05007654321',
             'lastname': u'Meikäläinen'}))

    def test_parse_xls__ooo_321_excel_97(self):
        """Parses an Excel 97/2000/XP formatted file generated
        with OpenOffice.org 3.2.1.
        """
        from nuorisovaalitadmin.views.school import SubmitVoters

        parsed = SubmitVoters(None).parse_xls(open_test_file('SubmitVoters_ooo_3.2.1-excel_97_2000_xp.xls'))
        self.assertEquals(parsed, (
            {'address': u'Väinämöisenkatu 3, 00400 Espoo',
             'dob': u'15.11.1992',
             'email': u'matti@meikalainen.fi',
             'firstname': u'Mätti Petteri',
             'gsm': u'040123456',
             'lastname': u'Meikäläinen'},
            {'address': u'Työpajankatu 6 A, 00580 Helsinki',
             'dob': u'30.04.1990',
             'email': u'maija@meikalainen.fi',
             'firstname': u'Mäijä Mirjami',
             'gsm': u'05007654321',
             'lastname': u'Meikäläinen'}))

    def test_parse_xls__office_2007_excel_97(self):
        """Parses an Excel 97/2000/XP formatted file generated
        with Office 2007.
        """
        from nuorisovaalitadmin.views.school import SubmitVoters

        parsed = SubmitVoters(None).parse_xls(open_test_file('SubmitVoters_win_office_2007-excel_97_2000.xls'))
        self.assertEquals(parsed, (
            {'address': u'Väinämöisenkatu 3, 00400 Espoo',
             'dob': u'15.11.1992',
             'email': u'matti@meikalainen.fi',
             'firstname': u'Mätti Petteri',
             'gsm': u'040123456',
             'lastname': u'Meikäläinen'},
            {'address': u'Työpajankatu 6 A, 00580 Helsinki',
             'dob': u'30.04.1990',
             'email': u'maija@meikalainen.fi',
             'firstname': u'Mäijä Mirjami',
             'gsm': u'05007654321',
             'lastname': u'Meikäläinen'}))

    def test_parse_xls__office_2010_excel_95(self):
        """Parses an Excel 95 formatted file generated with Office 2010.
        """
        from nuorisovaalitadmin.views.school import SubmitVoters

        parsed = SubmitVoters(None).parse_xls(open_test_file('SubmitVoters_win_office_2010-excel_95.xls'))
        self.assertEquals(parsed, (
            {'address': u'Väinämöisenkatu 3, 00400 Espoo',
             'dob': u'15.11.1992',
             'email': u'matti@meikalainen.fi',
             'firstname': u'Mätti Petteri',
             'gsm': u'040123456',
             'lastname': u'Meikäläinen'},
            {'address': u'Työpajankatu 6 A, 00580 Helsinki',
             'dob': u'30.04.1990',
             'email': u'maija@meikalainen.fi',
             'firstname': u'Mäijä Mirjami',
             'gsm': u'05007654321',
             'lastname': u'Meikäläinen'}))

    def test_parse_xls__office_2010_excel_97_2003(self):
        """Parses an Excel 97/2003 formatted file generated with Office 2010.
        """
        from nuorisovaalitadmin.views.school import SubmitVoters

        parsed = SubmitVoters(None).parse_xls(open_test_file('SubmitVoters_win_office_2010-excel_97_2003.xls'))
        self.assertEquals(parsed, (
            {'address': u'Väinämöisenkatu 3, 00400 Espoo',
             'dob': u'15.11.1992',
             'email': u'matti@meikalainen.fi',
             'firstname': u'Mätti Petteri',
             'gsm': u'040123456',
             'lastname': u'Meikäläinen'},
            {'address': u'Työpajankatu 6 A, 00580 Helsinki',
             'dob': u'30.04.1990',
             'email': u'maija@meikalainen.fi',
             'firstname': u'Mäijä Mirjami',
             'gsm': u'05007654321',
             'lastname': u'Meikäläinen'}))

    def test_parse_xlsx__office_2010_excel_current(self):
        """Parses a file formatted by the default version generated with
        Office 2010.

        This is currently unsupported :(
        """
        from nuorisovaalitadmin.views.school import SubmitVoters

        self.assertRaises(xlrd.XLRDError, lambda: SubmitVoters(None).parse_xls(open_test_file('SubmitVoters_win_office_2010-excel_latest.xlsx')))

    def test_parse_xls__text_column_not_text_value(self):
        """Parses an XLS file which contains a numeric value in a column we
        expect to be text formatted.
        """
        from nuorisovaalitadmin.views.school import SubmitVoters

        parsed = SubmitVoters(None).parse_xls(open_test_file('SubmitVoters_text_column_wrong_type.xls'))
        self.assertEquals(parsed, (
            {'firstname': u'xxxx xxxx',
             'dob': u'xx.xx.xxxx',
             'lastname': u'12345',
             'address': u'xxxx x x xx, xxxxx xxxx',
             'gsm': u'xxxxxxx',
             'email': u'xxxx.xxxx@xxxx.xx'},))

    def test_parse_xls__missing_column(self):
        """Parses an XLS file which is missing a column."""
        from nuorisovaalitadmin.views.school import SubmitVoters
        self.assertRaises(IndexError, lambda: SubmitVoters(None).parse_xls(open_test_file('SubmitVoters_missing_column.xls')))

    def test_parse_xls__date_column_not_date_value(self):
        """Parses an XLS file which contains a non-date value in a date column.
        """
        from nuorisovaalitadmin.views.school import SubmitVoters

        parsed = SubmitVoters(None).parse_xls(open_test_file('SubmitVoters_date_column_wrong_type.xls'))
        self.assertEquals(parsed, (
            {'firstname': u'xxxx xxxx',
             'dob': u'xx.xx.xxxx',
             'lastname': u'xxxx',
             'address': u'xxxx x x xx, xxxxx xxxx',
             'gsm': u'xxxxxxx',
             'email': u'xxxx.xxxx@xxxx.xx'},))

    def test_parse_csv(self):
        from nuorisovaalitadmin.views.school import SubmitVoters

        rows = [
            (u'Mätti', u'Meikäläinen', u'15.11.1990', u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            (u'Mäijä', u'Meikäläinen', u'1.3.1982', u'0500 987 6543', u'maija@maikalainen.com', u'Jössäin kaukana'),
            ]

        parsed = SubmitVoters(None).parse_csv(make_csv_file(rows))
        self.assertEquals(parsed, (
            {'address': u'Väinötie 5, 00200 Laukaa',
             'dob': u'15.11.1990',
             'email': u'matti@maikalainen.fi',
             'firstname': u'Mätti',
             'gsm': u'040 123 456',
             'lastname': u'Meikäläinen'},
            {'address': u'Jössäin kaukana',
             'dob': u'1.3.1982',
             'email': u'maija@maikalainen.com',
             'firstname': u'Mäijä',
             'gsm': u'0500 987 6543',
             'lastname': u'Meikäläinen'}))

    def test_parse_csv__alternate_delimiter(self):
        from nuorisovaalitadmin.views.school import SubmitVoters

        rows = [
            (u'Mätti', u'Meikäläinen', u'15.11.1990', u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            (u'Mäijä', u'Meikäläinen', u'1.3.1982', u'0500 987 6543', u'maija@maikalainen.com', u'Jössäin kaukana'),
            ]

        parsed = SubmitVoters(None).parse_csv(make_csv_file(rows, delimiter=';'))
        self.assertEquals(parsed, (
            {'address': u'Väinötie 5, 00200 Laukaa',
             'dob': u'15.11.1990',
             'email': u'matti@maikalainen.fi',
             'firstname': u'Mätti',
             'gsm': u'040 123 456',
             'lastname': u'Meikäläinen'},
            {'address': u'Jössäin kaukana',
             'dob': u'1.3.1982',
             'email': u'maija@maikalainen.com',
             'firstname': u'Mäijä',
             'gsm': u'0500 987 6543',
             'lastname': u'Meikäläinen'}))

    def test_parse_csv__unknown_delimiter(self):
        from nuorisovaalitadmin.views.school import SubmitVoters

        rows = [
            (u'Mätti', u'Meikäläinen', u'15.11.1990', u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            (u'Mäijä', u'Meikäläinen', u'1.3.1982', u'0500 987 6543', u'maija@maikalainen.com', u'Jössäin kaukana'),
            ]

        self.assertRaises(ValueError,
            lambda: SubmitVoters(None).parse_csv(make_csv_file(rows, delimiter='#')))

    def test_parse_csv__with_encoding(self):
        from nuorisovaalitadmin.views.school import SubmitVoters

        rows = [
            (u'Mätti', u'Meikäläinen', u'15.11.1990', u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            (u'Mäijä', u'Meikäläinen', u'1.3.1982', u'0500 987 6543', u'maija@maikalainen.com', u'Jössäin kaukana'),
            ]

        parsed = SubmitVoters(None).parse_csv(make_csv_file(rows, 'utf-8'), encoding='utf-8')
        self.assertEquals(parsed, (
            {'address': u'Väinötie 5, 00200 Laukaa',
             'dob': u'15.11.1990',
             'email': u'matti@maikalainen.fi',
             'firstname': u'Mätti',
             'gsm': u'040 123 456',
             'lastname': u'Meikäläinen'},
            {'address': u'Jössäin kaukana',
             'dob': u'1.3.1982',
             'email': u'maija@maikalainen.com',
             'firstname': u'Mäijä',
             'gsm': u'0500 987 6543',
             'lastname': u'Meikäläinen'}))

    def test_parse_csv__trailing_fields(self):
        from nuorisovaalitadmin.views.school import SubmitVoters

        rows = [
            (u'Mätti', u'Meikäläinen', u'15.11.1990', u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa', u'', u''),
            (u'Mäijä', u'Meikäläinen', u'1.3.1982', u'0500 987 6543', u'maija@maikalainen.com', u'Jössäin kaukana', u'', u'', u'', u''),
            (u'Mäijä', u'Meikäläinen', u'020382', u'0500 987 6543', u'maija@maikalainen.com', u'Jössäin kaukana', u'', u'', u'', u''),
            (u'Mäijä', u'Meikäläinen', u'3.3.82', u'0500 987 6543', u'maija@maikalainen.com', u'Jössäin kaukana', u'', u'', u'', u''),
            ]

        parsed = SubmitVoters(None).parse_csv(make_csv_file(rows))
        self.assertEquals(parsed, (
            {'address': u'Väinötie 5, 00200 Laukaa',
             'dob': u'15.11.1990',
             'email': u'matti@maikalainen.fi',
             'firstname': u'Mätti',
             'gsm': u'040 123 456',
             'lastname': u'Meikäläinen'},
            {'address': u'Jössäin kaukana',
             'dob': u'1.3.1982',
             'email': u'maija@maikalainen.com',
             'firstname': u'Mäijä',
             'gsm': u'0500 987 6543',
             'lastname': u'Meikäläinen'},
            {'address': u'Jössäin kaukana',
             'dob': u'020382',
             'email': u'maija@maikalainen.com',
             'firstname': u'Mäijä',
             'gsm': u'0500 987 6543',
             'lastname': u'Meikäläinen'},
            {'address': u'Jössäin kaukana',
             'dob': u'3.3.82',
             'email': u'maija@maikalainen.com',
             'firstname': u'Mäijä',
             'gsm': u'0500 987 6543',
             'lastname': u'Meikäläinen'},
             ))

    def test_parse_csv__empty_rows(self):
        from nuorisovaalitadmin.views.school import SubmitVoters

        rows = [
            (u'Mätti', u'Meikäläinen', u'15.11.1990', u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            (u'', u'', u'', u'', u'', u''),
            (u'Mäijä', u'Meikäläinen', u'1.3.1982', u'0500 987 6543', u'maija@maikalainen.com', u'Jössäin kaukana'),
            (u'', u'', u'', u'', u'', u''),
            (u'', u'', u'', u'', u'', u''),
            ]

        parsed = SubmitVoters(None).parse_csv(make_csv_file(rows))
        self.assertEquals(parsed, (
            {'address': u'Väinötie 5, 00200 Laukaa',
             'dob': u'15.11.1990',
             'email': u'matti@maikalainen.fi',
             'firstname': u'Mätti',
             'gsm': u'040 123 456',
             'lastname': u'Meikäläinen'},
            {'address': u'',
             'dob': u'',
             'email': u'',
             'firstname': u'',
             'gsm': u'',
             'lastname': u''},
            {'address': u'Jössäin kaukana',
             'dob': u'1.3.1982',
             'email': u'maija@maikalainen.com',
             'firstname': u'Mäijä',
             'gsm': u'0500 987 6543',
             'lastname': u'Meikäläinen'},
            {'address': u'',
             'dob': u'',
             'email': u'',
             'firstname': u'',
             'gsm': u'',
             'lastname': u''},
            {'address': u'',
             'dob': u'',
             'email': u'',
             'firstname': u'',
             'gsm': u'',
             'lastname': u''},
            ))

    def test_validate__valid_submission(self):
        from nuorisovaalitadmin.views.school import SubmitVoters

        rows = [
            # Full date format
            (u'Mätti', u'Meikäläinen', u'15.11.1990', u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            # Short date format
            (u'Mäijä', u'Meikäläinen', u'010387', u'0500 987 6543', u'maija@maikalainen.com', u'Jössäin kaukana'),
            # Short date format (alternate)
            (u'Mäijä', u'Meikäläinen', u'01.03.87', u'0500 987 6543', u'maija@maikalainen.com', u'Jössäin kaukana'),
            # Short date format (alternate)
            (u'Mäijä', u'Meikäläinen', u'010387-123X', u'0500 987 6543', u'maija@maikalainen.com', u'Jössäin kaukana'),
            # Short date format (alternate)
            (u'Mäijä', u'Meikäläinen', u'010387123X', u'0500 987 6543', u'maija@maikalainen.com', u'Jössäin kaukana'),
            # Short date format (alternate)
            (u'Mäijä', u'Meikäläinen', u'010387-1234', u'0500 987 6543', u'maija@maikalainen.com', u'Jössäin kaukana'),
            # Short date format (alternate)
            (u'Mäijä', u'Meikäläinen', u'0103871234', u'0500 987 6543', u'maija@maikalainen.com', u'Jössäin kaukana'),
            ]

        errors = SubmitVoters(None).validate(make_csv_dict(rows))
        self.assertEquals(0, len(errors))

    def test_validate__missing_fields(self):
        from nuorisovaalitadmin.views.school import SubmitVoters

        row = [
            (u'Mätti', u'', u'', u'', u'', u''),
            (u'', u'', u'', u'', u'', u''),  # Empty rows should not produce error.
            (u'', u'Meikäläinen', u'', u'', u'', u''),
        ]
        errors = SubmitVoters(None).validate(make_csv_dict(row))
        self.assertEquals(errors, [
            {'lineno': 2, 'msg': u'Sukunimi puuttuu.'},
            {'lineno': 2, 'msg': u'Syntymäaika puuttuu.'},
            {'lineno': 2, 'msg': u'Ainakin yksi yhteystieto (GSM-numero, email, osoite) on pakollinen.'},
            {'lineno': 4, 'msg': u'Etunimi puuttuu.'},
            {'lineno': 4, 'msg': u'Syntymäaika puuttuu.'},
            {'lineno': 4, 'msg': u'Ainakin yksi yhteystieto (GSM-numero, email, osoite) on pakollinen.'},
        ])

    def test_validate__invalid_dob(self):
        from nuorisovaalitadmin.views.school import SubmitVoters

        rows = [
            (u'Mätti', u'Meikäläinen', u'invalid', u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            (u'Mätti', u'Meikäläinen', u'31.2.1992', u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            (u'Mätti', u'Meikäläinen', u'22.222.1992', u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            (u'Mätti', u'Meikäläinen', u'310292', u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            (u'Mätti', u'Meikäläinen', u'31.02.92', u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            (u'Mätti', u'Meikäläinen', u'222221992', u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            (u'Mätti', u'Meikäläinen', u'310292-123X', u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            (u'Mätti', u'Meikäläinen', u'310292123X', u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            (u'Mätti', u'Meikäläinen', u'3102921234', u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            ]

        errors = SubmitVoters(None).validate(make_csv_dict(rows))
        self.assertEquals(errors, [
            {'lineno': 2, 'msg': u'Syntymäaika "invalid" on väärän muotoinen.'},
            {'lineno': 3, 'msg': u'Syntymäaika "31.2.1992" on väärän muotoinen.'},
            {'lineno': 4, 'msg': u'Syntymäaika "22.222.1992" on väärän muotoinen.'},
            {'lineno': 5, 'msg': u'Syntymäaika "310292" on väärän muotoinen.'},
            {'lineno': 6, 'msg': u'Syntymäaika "31.02.92" on väärän muotoinen.'},
            {'lineno': 7, 'msg': u'Syntymäaika "222221992" on väärän muotoinen.'},
            {'lineno': 8, 'msg': u'Syntymäaika "310292-123X" on väärän muotoinen.'},
            {'lineno': 9, 'msg': u'Syntymäaika "310292123X" on väärän muotoinen.'},
            {'lineno': 10, 'msg': u'Syntymäaika "3102921234" on väärän muotoinen.'},
            ])

    def test_validate__invalid_age(self):
        from nuorisovaalitadmin.views.school import SubmitVoters
        too_young = date.today().strftime('%d.%m.%Y')
        too_young_short1 = date.today().strftime('%d%m%y')
        too_young_short2 = date.today().strftime('%d.%m.%y')
        too_young_short3 = date.today().strftime('%d%m%y-666X')
        too_young_short4 = date.today().strftime('%d%m%y-6667')
        too_young_short5 = date.today().strftime('%d%m%y666X')
        too_young_short6 = date.today().strftime('%d%m%y6667')
        too_old = '1.1.1900'

        rows = [
            (u'Mätti', u'Meikäläinen', too_young, u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            (u'Mätti', u'Meikäläinen', too_young_short1, u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            (u'Mätti', u'Meikäläinen', too_young_short2, u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            (u'Mätti', u'Meikäläinen', too_young_short3, u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            (u'Mätti', u'Meikäläinen', too_young_short4, u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            (u'Mätti', u'Meikäläinen', too_young_short5, u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            (u'Mätti', u'Meikäläinen', too_young_short6, u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            (u'Mätti', u'Meikäläinen', too_old, u'040 123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            ]

        errors = SubmitVoters(None).validate(make_csv_dict(rows))
        self.assertEquals(errors, [
            {'lineno': 2, 'msg': u'Äänestäjän ikä pitää olla välillä 12-25.'},
            {'lineno': 3, 'msg': u'Äänestäjän ikä pitää olla välillä 12-25.'},
            {'lineno': 4, 'msg': u'Äänestäjän ikä pitää olla välillä 12-25.'},
            {'lineno': 5, 'msg': u'Äänestäjän ikä pitää olla välillä 12-25.'},
            {'lineno': 6, 'msg': u'Äänestäjän ikä pitää olla välillä 12-25.'},
            {'lineno': 7, 'msg': u'Äänestäjän ikä pitää olla välillä 12-25.'},
            {'lineno': 8, 'msg': u'Äänestäjän ikä pitää olla välillä 12-25.'},
            {'lineno': 9, 'msg': u'Äänestäjän ikä pitää olla välillä 12-25.'},
            ])

    def test_validate__invalid_email(self):
        from nuorisovaalitadmin.views.school import SubmitVoters

        rows = [
            (u'Mätti', u'Meikäläinen', u'15.11.1990', u'040 123 456', u'matti@meikalainen.invalid', u'Väinötie 5, 00200 Laukaa'),
            (u'Mäijä', u'Meikäläinen', u'1.3.1987', u'0500 987 6543', u'maijameikalainen', u'Jössäin kaukana'),
            ]

        errors = SubmitVoters(None).validate(make_csv_dict(rows))
        self.assertEquals(errors, [
            {'lineno': 2, 'msg': u'Sähköpostiosoite "matti@meikalainen.invalid" on väärän muotoinen.'},
            {'lineno': 3, 'msg': u'Sähköpostiosoite "maijameikalainen" on väärän muotoinen.'}])

    def test_validate__invalid_gsm(self):
        from nuorisovaalitadmin.views.school import SubmitVoters

        rows = [
            (u'Mätti', u'Meikäläinen', u'15.11.1990', u'123 456', u'matti@maikalainen.fi', u'Väinötie 5, 00200 Laukaa'),
            (u'Mäijä', u'Meikäläinen', u'1.3.1987', u'050987', u'maija@maikalainen.com', u'Jössäin kaukana'),
            ]

        errors = SubmitVoters(None).validate(make_csv_dict(rows))
        self.assertEquals(errors, [
            {'lineno': 2, 'msg': u'GSM-numero "123 456" on väärän muotoinen.'},
            {'lineno': 3, 'msg': u'GSM-numero "050987" on väärän muotoinen.'}])

    def test_normalize(self):
        from nuorisovaalitadmin.views.school import SubmitVoters

        submission = (
            {'address': u'Väinötie 5, 00200 Laukaa',
             'dob': u'15.11.1990',
             'email': u'matti@maikalainen.fi',
             'firstname': u'Mätti',
             'gsm': u'040 123 456',
             'lastname': u'Meikäläinen'},
            {'address': u'Jössäin kaukana',
             'dob': u'1.3.1982',
             'email': u'maija@maikalainen.com',
             'firstname': u'Mäijä',
             'gsm': u'0500 987 6543',
             'lastname': u'Meikäläinen'},
            {'address': u'Jössäin kaukana',
             'dob': u'020382',
             'email': u'maija@maikalainen.com',
             'firstname': u'Mäijä',
             'gsm': u'0500 987 6543',
             'lastname': u'Meikäläinen'},
             # Empty rows should be filtered out.
            {'address': u'',
             'dob': u'',
             'email': u'',
             'firstname': u'',
             'gsm': u'',
             'lastname': u''},
            {'address': u'Jössäin kaukana',
             'dob': u'3.3.82',
             'email': u'maija@maikalainen.com',
             'firstname': u'Mäijä',
             'gsm': u'0500 987 6543',
             'lastname': u'Meikäläinen'},
            {'address': u'Jössäin kaukana',
             'dob': u'030382-123X',
             'email': u'maija@maikalainen.com',
             'firstname': u'Mäijä',
             'gsm': u'0500 987 6543',
             'lastname': u'Meikäläinen'},
            {'address': u'Jössäin kaukana',
             'dob': u'030382-123A',
             'email': u'maija@maikalainen.com',
             'firstname': u'Mäijä',
             'gsm': u'0500 987 6543',
             'lastname': u'Meikäläinen'},
            {'address': u'Jössäin kaukana',
             'dob': u'030382123X',
             'email': u'maija@maikalainen.com',
             'firstname': u'Mäijä',
             'gsm': u'0500 987 6543',
             'lastname': u'Meikäläinen'},
            {'address': u'Jössäin kaukana',
             'dob': u'030382123A',
             'email': u'maija@maikalainen.com',
             'firstname': u'Mäijä',
             'gsm': u'0500 987 6543',
             'lastname': u'Meikäläinen'},
             )

        self.assertEquals(SubmitVoters(None).normalize(submission), (
            {'firstname': u'Mätti', 'dob': u'15.11.1990', 'lastname': u'Meikäläinen', 'address': u'Väinötie 5, 00200 Laukaa', 'gsm': u'040 123 456', 'email': u'matti@maikalainen.fi'},
            {'firstname': u'Mäijä', 'dob': u'1.3.1982', 'lastname': u'Meikäläinen', 'address': u'Jössäin kaukana', 'gsm': u'0500 987 6543', 'email': u'maija@maikalainen.com'},
            {'firstname': u'Mäijä', 'dob': u'02.03.1982', 'lastname': u'Meikäläinen', 'address': u'Jössäin kaukana', 'gsm': u'0500 987 6543', 'email': u'maija@maikalainen.com'},
            {'firstname': u'Mäijä', 'dob': u'03.03.1982', 'lastname': u'Meikäläinen', 'address': u'Jössäin kaukana', 'gsm': u'0500 987 6543', 'email': u'maija@maikalainen.com'},
            {'firstname': u'Mäijä', 'dob': u'03.03.1982', 'lastname': u'Meikäläinen', 'address': u'Jössäin kaukana', 'gsm': u'0500 987 6543', 'email': u'maija@maikalainen.com'},
            {'firstname': u'Mäijä', 'dob': u'03.03.1982', 'lastname': u'Meikäläinen', 'address': u'Jössäin kaukana', 'gsm': u'0500 987 6543', 'email': u'maija@maikalainen.com'},
            {'firstname': u'Mäijä', 'dob': u'03.03.1982', 'lastname': u'Meikäläinen', 'address': u'Jössäin kaukana', 'gsm': u'0500 987 6543', 'email': u'maija@maikalainen.com'},
            {'firstname': u'Mäijä', 'dob': u'03.03.1982', 'lastname': u'Meikäläinen', 'address': u'Jössäin kaukana', 'gsm': u'0500 987 6543', 'email': u'maija@maikalainen.com'},
            ))


class SubmitResultsTest(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.maxDiff = None
        init_testing_db()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_parse_xls__ooo_321_excel_5(self):
        from nuorisovaalitadmin.views.school import SubmitResults

        parsed = SubmitResults(None).parse_xls(open_test_file('SubmitResults_ooo_3.2.1-excel_5.xls'))
        self.assertEquals(parsed, (
            {'name': u'Akü Änkkä', 'number': u'2', 'votes': u'100'},
            {'name': u'Rööpe Änkkä', 'number': u'3', 'votes': u'50'},
            {'name': u'Kröisös Pennönen', 'number': u'4', 'votes': u'25'}))

    def test_parse_xls__ooo_321_excel_95(self):
        from nuorisovaalitadmin.views.school import SubmitResults

        parsed = SubmitResults(None).parse_xls(open_test_file('SubmitResults_ooo_3.2.1-excel_95.xls'))
        self.assertEquals(parsed, (
            {'name': u'Akü Änkkä', 'number': u'2', 'votes': u'100'},
            {'name': u'Rööpe Änkkä', 'number': u'3', 'votes': u'50'},
            {'name': u'Kröisös Pennönen', 'number': u'4', 'votes': u'25'}))

    def test_parse_xls__ooo_321_excel_97(self):
        from nuorisovaalitadmin.views.school import SubmitResults

        parsed = SubmitResults(None).parse_xls(open_test_file('SubmitResults_ooo_3.2.1-excel_97_2000_xp.xls'))
        self.assertEquals(parsed, (
            {'name': u'Akü Änkkä', 'number': u'2', 'votes': u'100'},
            {'name': u'Rööpe Änkkä', 'number': u'3', 'votes': u'50'},
            {'name': u'Kröisös Pennönen', 'number': u'4', 'votes': u'25'}))

    def test_parse_xls__office_2007_excel_97_2003(self):
        """Tests parsing of a sheet saved using Office 2007 in Excel 97-2003
        compatible format.
        """
        from nuorisovaalitadmin.views.school import SubmitResults

        parsed = SubmitResults(None).parse_xls(open_test_file('SubmitResults_win_office_2007-excel_97_2003.xls'))
        self.assertEquals(parsed, (
            {'name': u'Akü Änkkä', 'number': u'2', 'votes': u'100'},
            {'name': u'Rööpe Änkkä', 'number': u'3', 'votes': u'50'},
            {'name': u'Kröisös Pennönen', 'number': u'4', 'votes': u'25'}))

    def test_parse_xls__office_2007_excel_95(self):
        """Tests parsing of a sheet saved using Office 2007 in Excel 5.0/95
        compatible format.
        """
        from nuorisovaalitadmin.views.school import SubmitResults

        parsed = SubmitResults(None).parse_xls(open_test_file('SubmitResults_win_office_2007-excel_5_95.xls'))
        self.assertEquals(parsed, (
            {'name': u'Akü Änkkä', 'number': u'2', 'votes': u'100'},
            {'name': u'Rööpe Änkkä', 'number': u'3', 'votes': u'50'},
            {'name': u'Kröisös Pennönen', 'number': u'4', 'votes': u'25'}))

    def test_parse_xls__office_2010_excel_95(self):
        """Tests parsing of a sheet saved using Office 2010 in Excel 5.0/95
        compatible format.
        """
        from nuorisovaalitadmin.views.school import SubmitResults

        parsed = SubmitResults(None).parse_xls(open_test_file('SubmitResults_win_office_2010-excel_5_95.xls'))
        self.assertEquals(parsed, (
            {'name': u'Akü Änkkä', 'number': u'2', 'votes': u'100'},
            {'name': u'Rööpe Änkkä', 'number': u'3', 'votes': u'50'},
            {'name': u'Kröisös Pennönen', 'number': u'4', 'votes': u'25'}))

    def test_parse_xlsx__office_2007_excel_xlsx(self):
        from nuorisovaalitadmin.views.school import SubmitResults

        parsed = SubmitResults(None).parse_xlsx(open_test_file('SubmitResults_win_office_2007-excel_default.xlsx'))
        self.assertEquals(parsed, (
            {'name': u'Akü Änkkä', 'number': u'2', 'votes': u'100'},
            {'name': u'Rööpe Änkkä', 'number': u'3', 'votes': u'50'},
            {'name': u'Kröisös Pennönen', 'number': u'4', 'votes': u'25'}))

    def test_parse_xlsx__office_2010_excel_xlsx(self):
        from nuorisovaalitadmin.views.school import SubmitResults

        parsed = SubmitResults(None).parse_xlsx(open_test_file('SubmitResults_win_office_2010-excel_default.xlsx'))
        self.assertEquals(parsed, (
            {'name': u'Akü Änkkä', 'number': u'2', 'votes': u'100'},
            {'name': u'Rööpe Änkkä', 'number': u'3', 'votes': u'50'},
            {'name': u'Kröisös Pennönen', 'number': u'4', 'votes': u'25'}))

    def test_parse_xlsx__missing_column(self):
        """Parses an XLSX file which is missing a column."""
        from nuorisovaalitadmin.views.school import SubmitResults
        self.assertRaises(IndexError, lambda: SubmitResults(None).parse_xlsx(open_test_file('SubmitResults_missing_columns.xlsx')))

    def test_parse_xls__missing_column(self):
        """Parses an XLS file which is missing a column."""
        from nuorisovaalitadmin.views.school import SubmitResults
        self.assertRaises(IndexError, lambda: SubmitResults(None).parse_xls(open_test_file('SubmitResults_missing_columns.xls')))

    def test_parse_xls__office_2010_excel_97_2003(self):
        from nuorisovaalitadmin.views.school import SubmitResults

        parsed = SubmitResults(None).parse_xls(open_test_file('SubmitResults_win_office_2010-excel_97_2003.xls'))
        self.assertEquals(parsed, (
            {'name': u'Akü Änkkä', 'number': u'2', 'votes': u'100'},
            {'name': u'Rööpe Änkkä', 'number': u'3', 'votes': u'50'},
            {'name': u'Kröisös Pennönen', 'number': u'4', 'votes': u'25'}))

    def test_submit_results__unauthenticated(self):
        from nuorisovaalitadmin.views.school import SubmitResults

        self.assertRaises(Forbidden, lambda: SubmitResults(DummyRequest()).submit_results())

    def test_submit_results__non_compliant_file(self):
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import SubmitResults

        self.config.add_route('results_template_xls', '/results-template.xls')
        self.config.add_route('submit_results', '/submit-results')

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()
        self.config.testing_securitypolicy(userid=user.username)

        xlsfile = mock.Mock()
        xlsfile.file = open_test_file('SubmitResults_win_office_2007-excel_2003_xml.xml')
        xlsfile.type = 'application/vnd.ms-excel'

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()
        request.POST = {
            'xlsfile': xlsfile,
            'csrf_token': csrf_token,
        }
        self.assertEquals({
            'title': u'Tulostietojen lähetys',
            'errors': [],
            'errors_left': 0,
            'file_type_error': True,
            'csrf_token': csrf_token,
            'submission': None,
            'template_url': route_url('results_template_xls', request),
            'action_url': route_url('submit_results', request),
        }, SubmitResults(request).submit_results())

    def test_submit_results__validation_errors(self):
        from nuorisovaalit.models import Candidate
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import SubmitResults

        self.config.add_route('results_template_xls', '/results-template.xls')
        self.config.add_route('submit_results', '/submit-results')

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()
        self.config.testing_securitypolicy(userid=user.username)

        # Select one candidate form user's district and one from another.
        candidate = session.query(Candidate)\
                    .filter(Candidate.district == user.school.district)\
                    .first()
        self.assertTrue(candidate is not None)
        candidate_bad = session.query(Candidate)\
                    .filter(Candidate.district != user.school.district)\
                    .first()
        self.assertTrue(candidate_bad is not None)

        submission = [
            (u'', u'Näme', u''),
            (u'', u'', u'1'),
            (u'', u'', u''),
            (u'invalid', u'valid name', u'invalid'),
            (candidate.number, candidate.fullname(), u'100'),
            (u'9999', candidate_bad.fullname(), u'bad'),
            (u'', u'Foo', u'1'),
            (u'', u'Foo', u'1'),
            (u'', u'Foo', u'1'),
            (u'', u'Foo', u'1'),
            (u'', u'Foo', u'1'),
            (u'', u'Foo', u'1'),
            (u'', u'Foo', u'1'),
            (u'', u'Foo', u'1'),
            (u'', u'Foo', u'1'),
            (u'', u'Foo', u'1'),
            ]
        xlsfile = mock.Mock()
        xlsfile.file = make_xls_file(submission, headers=SubmitResults.XLS_HEADER, formats=SubmitResults.XLS_FORMATS)
        xlsfile.type = 'application/vnd.ms-excel'

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()
        request.POST = {
            'xlsfile': xlsfile,
            'csrf_token': csrf_token,
        }

        self.assertEquals({
            'title': u'Tulostietojen lähetys',
            'errors': [
                {'lineno': 2, 'msg': u'Ehdokkaan äänimäärä puuttuu.'},
                {'lineno': 2, 'msg': u'Ehdokasnumero puuttuu.'},
                {'lineno': 3, 'msg': u'Ehdokkaan nimi puuttuu.'},
                {'lineno': 3, 'msg': u'Ehdokasnumero puuttuu.'},
                {'lineno': 5, 'msg': u'Äänimäärä on väärää muotoa. Tarkista, että äänimäärä on positiivinen kokonaisluku.'},
                {'lineno': 5, 'msg': u'Ehdokasnumero on väärää muotoa. Tarkista, että ehdokasnumero on positiivinen kokonaisluku.'},
                {'lineno': 7, 'msg': u'Äänimäärä on väärää muotoa. Tarkista, että äänimäärä on positiivinen kokonaisluku.'},
                {'lineno': 7, 'msg': u'Ehdokasnumero 9999 ei vastaa yhtään vaalipiirin ehdokasta.'},
                {'lineno': 8, 'msg': u'Ehdokasnumero puuttuu.'},
                {'lineno': 9, 'msg': u'Ehdokasnumero puuttuu.'},
                {'lineno': 10, 'msg': u'Ehdokasnumero puuttuu.'},
                {'lineno': 11, 'msg': u'Ehdokasnumero puuttuu.'},
                {'lineno': 12, 'msg': u'Ehdokasnumero puuttuu.'},
                {'lineno': 13, 'msg': u'Ehdokasnumero puuttuu.'},
                {'lineno': 14, 'msg': u'Ehdokasnumero puuttuu.'}],
            'errors_left': 3,
            'file_type_error': None,
            'csrf_token': csrf_token,
            'submission': None,
            'template_url': route_url('results_template_xls', request),
            'action_url': route_url('submit_results', request),
        }, SubmitResults(request).submit_results())

    def test_submit_results__no_xls_file(self):
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import SubmitResults

        self.config.add_route('results_template_xls', '/results-template.xls')
        self.config.add_route('submit_results', '/submit-results')

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()
        self.config.testing_securitypolicy(userid=user.username)

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()

        self.assertEquals({
            'title': u'Tulostietojen lähetys',
            'errors': None,
            'errors_left': 0,
            'file_type_error': None,
            'csrf_token': csrf_token,
            'submission': None,
            'template_url': route_url('results_template_xls', request),
            'action_url': route_url('submit_results', request),
        }, SubmitResults(request).submit_results())

    def test_submit_results__empty_xls_file(self):
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import SubmitResults

        self.config.add_route('results_template_xls', '/results-template.xls')
        self.config.add_route('submit_results', '/submit-results')

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()
        self.config.testing_securitypolicy(userid=user.username)

        request = DummyRequest()
        request.POST['xlsfile'] = u''
        csrf_token = request.session.new_csrf_token()

        self.assertEquals({
            'title': u'Tulostietojen lähetys',
            'errors': None,
            'errors_left': 0,
            'file_type_error': None,
            'csrf_token': csrf_token,
            'submission': None,
            'template_url': route_url('results_template_xls', request),
            'action_url': route_url('submit_results', request),
        }, SubmitResults(request).submit_results())

    def test_submit_results__invalid_csrf_token(self):
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import SubmitResults

        self.config.add_route('results_template_xls', '/results-template.xls')
        self.config.add_route('submit_results', '/submit-results')

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()
        self.config.testing_securitypolicy(userid=user.username)

        request = DummyRequest()
        xlsfile = mock.Mock()
        xlsfile.file = StringIO()
        request.POST['xlsfile'] = xlsfile
        csrf_token = request.session.new_csrf_token()
        request.POST['csrf_token'] = 'invalid' + csrf_token

        self.assertRaises(Forbidden, lambda: SubmitResults(request).submit_results())

    def test_submit_results__xls_97_2003_submission(self):
        from nuorisovaalit.models import School
        from nuorisovaalitadmin.models import CSVSubmission
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import SubmitResults

        self.config.add_route('results_template_xls', '/results-template.xls')
        self.config.add_route('submit_results', '/submit-results')

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()
        self.config.testing_securitypolicy(userid=user.username)

        xlsfile = mock.Mock()
        xlsfile.file = open_test_file('SubmitResults_win_office_2010-submit_results.xls')
        xlsfile.type = 'application/vnd.ms-excel'

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()
        request.POST = {
            'xlsfile': xlsfile,
            'csrf_token': csrf_token,
        }
        # Assert we get redirected to avoid resubmission on reload.
        redirect = SubmitResults(request).submit_results()
        self.assertEquals(redirect.location, 'http://example.com/submit-results')

        # Assert the submission was persisted.
        session.flush()
        submission = session.query(CSVSubmission)\
                     .filter(CSVSubmission.kind == CSVSubmission.RESULT)\
                     .filter(School.id == user.school.id).first()
        self.assertEquals(submission.csv, (
            {'name': u'Akü Änkkä', 'number': 1, 'votes': 100},
            {'name': u'Rööpe Änkkä', 'number': 2, 'votes': 50},
            {'name': u'Kröisös Pennönen', 'number': 3, 'votes': 25}))

    def test_submit_results__xlsx_submission(self):
        from nuorisovaalit.models import School
        from nuorisovaalitadmin.models import CSVSubmission
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import SubmitResults

        self.config.add_route('results_template_xls', '/results-template.xls')
        self.config.add_route('submit_results', '/submit-results')

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()
        self.config.testing_securitypolicy(userid=user.username)

        xlsfile = mock.Mock()
        xlsfile.file = open_test_file('SubmitResults_win_office_2010-submit_results.xlsx')
        xlsfile.type = 'application/vnd.ms-excel'

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()
        request.POST = {
            'xlsfile': xlsfile,
            'csrf_token': csrf_token,
        }
        # Assert we get redirected to avoid resubmission on reload.
        redirect = SubmitResults(request).submit_results()
        self.assertEquals(redirect.location, 'http://example.com/submit-results')

        # Assert the submission was persisted.
        session.flush()
        submission = session.query(CSVSubmission)\
                     .filter(CSVSubmission.kind == CSVSubmission.RESULT)\
                     .filter(School.id == user.school.id).first()
        self.assertEquals(submission.csv, (
            {'name': u'Akü Änkkä', 'number': 1, 'votes': 100},
            {'name': u'Rööpe Änkkä', 'number': 2, 'votes': 50},
            {'name': u'Kröisös Pennönen', 'number': 3, 'votes': 25}))

    @mock.patch('nuorisovaalitadmin.models.datetime')
    def test_submit_results__no_xls_submission_already_saved(self, mock_datetime):
        from datetime import datetime
        from nuorisovaalitadmin.models import CSVSubmission
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import SubmitResults

        self.config.add_route('results_template_xls', '/results-template.xls')
        self.config.add_route('submit_results', '/submit-results')

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()
        self.config.testing_securitypolicy(userid=user.username)

        # Make the datetime.now return a static datetime value.
        mock_datetime.now.return_value = datetime(2011, 1, 28, 9, 27)

        submission = (
            {'number': u'1',
             'name': u'Matti Meikäläinen',
             'votes': u'100'},
            {'number': u'2',
             'name': u'Liisa Läjä',
             'votes': u'200'},
        )
        session.add(CSVSubmission(submission, user.school, CSVSubmission.RESULT))
        session.flush()

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()

        self.assertEquals({
            'title': u'Tulostietojen lähetys',
            'errors': None,
            'errors_left': 0,
            'file_type_error': None,
            'csrf_token': csrf_token,
            'template_url': route_url('results_template_xls', request),
            'action_url': route_url('submit_results', request),
            'submission': {
                'timestamp': '28.01.2011 09:27',
                'data': (
                    {'number': u'1',
                     'name': u'Matti Meikäläinen',
                     'votes': u'100'},
                    {'number': u'2',
                     'name': u'Liisa Läjä',
                     'votes': u'200'},
                )
            }
        }, SubmitResults(request).submit_results())

    @mock.patch('nuorisovaalitadmin.models.datetime')
    def test_submit_results__replace_old_submission(self, mock_datetime):
        from datetime import datetime
        from nuorisovaalitadmin.models import CSVSubmission
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import SubmitResults

        self.config.add_route('results_template_xls', '/results-template.xls')
        self.config.add_route('submit_results', '/submit-results')

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()
        self.config.testing_securitypolicy(userid=user.username)

        # Make the datetime.now return a static datetime value.
        mock_datetime.now.return_value = datetime(2011, 1, 28, 9, 27)

        # Add the first submission to the session.
        submission = (
            {'number': u'1',
             'name': u'Matti Meikäläinen',
             'votes': u'100'},
            {'number': u'2',
             'name': u'xxxx xxxx',
             'votes': u'200'},
            {'number': u'10',
             'name': u'xxxx xxxx',
             'votes': u'16'},
        )
        session.add(CSVSubmission(submission, user.school, CSVSubmission.RESULT))
        session.flush()

        # Construct an updated submission.
        rows = (
            (u'1', u'Matti Meikäläinen', u'101'),
            (u'2', u'xxxx xxxx', u'202'),
        )
        xlsfile = mock.Mock()
        xlsfile.file = make_xls_file(rows, headers=SubmitResults.XLS_HEADER, formats=SubmitResults.XLS_FORMATS)
        xlsfile.type = 'application/vnd.ms-excel'

        request = DummyRequest()
        request.POST = {
            'csrf_token': request.session.new_csrf_token(),
            'xlsfile': xlsfile,
        }

        # Submit the new submission.
        response = SubmitResults(request).submit_results()
        self.assertTrue(isinstance(response, HTTPFound))
        self.assertEquals(route_url('submit_results', request), response.location)

        # Check that the latest submission in the session is indeed the one added last.
        submission = session.query(CSVSubmission)\
                        .filter_by(kind=CSVSubmission.RESULT, school_id=user.school.id)\
                        .first()
        self.assertEquals((
            {'number': 1,
             'name': u'Matti Meikäläinen',
             'votes': 101},
            {'number': 2,
             'name': u'xxxx xxxx',
             'votes': 202},
        ), submission.csv)

    def test_normalize(self):
        from nuorisovaalitadmin.views.school import SubmitResults

        submission = (
            {'number': u'1',
             'name': u'Matti Meikäläinen',
             'votes': u'100'},
            {'number': u'2',
             'name': u'xxxx xxxx',
             'votes': u'200'},
            {'number': u'10',
             'name': u'xxxx xxxxx',
             'votes': u'16'},
            {'number': u'',
             'name': u'',
             'votes': u''})

        self.assertEquals(SubmitResults(None).normalize(submission), (
            {'name': u'Matti Meikäläinen', 'number': 1, 'votes': 100},
            {'name': u'xxxx xxxx', 'number': 2, 'votes': 200},
            {'name': u'xxxx xxxx', 'number': 10, 'votes': 16}))

    def test_validate__empty_submission(self):
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import SubmitResults

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()
        self.config.testing_securitypolicy(userid=user.username)

        # There should be no validation errors.
        self.assertEquals([], SubmitResults(DummyRequest()).validate([]))

    def test_validate__valid_submission(self):
        from nuorisovaalit.models import Candidate
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import SubmitResults

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()
        self.config.testing_securitypolicy(userid=user.username)

        # Add all the valid candidates to the submission.
        candidates = session.query(Candidate)\
                     .filter(Candidate.district == user.school.district).all()
        self.assertTrue(len(candidates) >= 2)
        submission = [dict(number=str(c.number), name=c.fullname(), votes='100') for c in candidates]

        submit = SubmitResults(DummyRequest())
        submit.user = user
        self.assertEquals([], submit.validate(submission))

    def test_validate__invalid_submission(self):
        from nuorisovaalit.models import Candidate
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import SubmitResults

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()
        self.config.testing_securitypolicy(userid=user.username)

        # Select one candidate form user's district and one from another.
        candidate = session.query(Candidate)\
                    .filter(Candidate.district == user.school.district)\
                    .first()
        self.assertTrue(candidate is not None)
        candidate_bad = session.query(Candidate)\
                    .filter(Candidate.district != user.school.district)\
                    .first()
        self.assertTrue(candidate_bad is not None)

        submission = (
            {'number': u'', 'name': u'Näme', 'votes': u''},
            {'number': u'', 'name': u'', 'votes': u'1'},
            {'number': u'', 'name': u'', 'votes': u''},
            {'number': u'invalid', 'name': u'valid name', 'votes': u'invalid'},
            {'number': unicode(candidate.number), 'name': candidate.fullname(), 'votes': u'100'},
            {'number': u'9999', 'name': candidate_bad.fullname(), 'votes': u'bad'},
        )
        submit = SubmitResults(DummyRequest())
        submit.user = user
        self.assertEquals([
            {'lineno': 2, 'msg': u'Ehdokkaan äänimäärä puuttuu.'},
            {'lineno': 2, 'msg': u'Ehdokasnumero puuttuu.'},
            {'lineno': 3, 'msg': u'Ehdokkaan nimi puuttuu.'},
            {'lineno': 3, 'msg': u'Ehdokasnumero puuttuu.'},
            {'lineno': 5, 'msg': u'Äänimäärä on väärää muotoa. Tarkista, että äänimäärä on positiivinen kokonaisluku.'},
            {'lineno': 5, 'msg': u'Ehdokasnumero on väärää muotoa. Tarkista, että ehdokasnumero on positiivinen kokonaisluku.'},
            {'lineno': 7, 'msg': u'Äänimäärä on väärää muotoa. Tarkista, että äänimäärä on positiivinen kokonaisluku.'},
            {'lineno': 7, 'msg': u'Ehdokasnumero 9999 ei vastaa yhtään vaalipiirin ehdokasta.'},
        ], submit.validate(submission))


class XLSResponseTest(XlsTestCase):

    def test_xls_response__empty(self):
        from nuorisovaalitadmin.views.school import xls_response

        response = xls_response([])
        self.assertTrue(isinstance(response, Response))
        self.assertEquals('5632', response.headers['content-length'])
        self.assertEquals('application/vnd.ms-excel',
                          response.headers['content-type'])
        self.assertEquals('attachment; filename=response.xls',
                          response.headers['content-disposition'])

    def test_xls_response__changed_filename(self):
        from nuorisovaalitadmin.views.school import xls_response

        response = xls_response([], filename='changed.xls')
        self.assertEquals('application/vnd.ms-excel',
                          response.headers['content-type'])
        self.assertEquals('attachment; filename=changed.xls',
                          response.headers['content-disposition'])

    def test_xls_response__with_rows(self):
        from nuorisovaalitadmin.views.school import xls_response

        rows = [
            (555, u'other', u'thöörd cölümn'),
            (123, u'with, comma', u' field\twith  whitespace\t'),
        ]

        response = xls_response(rows, num_formats=('@', '@', None))
        self.assertTrue(isinstance(response, Response))
        self.assertEquals('application/vnd.ms-excel',
                          response.headers['content-type'])
        self.assertEquals('attachment; filename=response.xls',
                          response.headers['content-disposition'])

        self.assertXlsEquals(u'Nuorisovaalit 2011', rows, response.body, adapters=(int, None, None), skip_header=False)

    def test_xls_response__default_column_widths(self):
        from nuorisovaalitadmin.views.school import xls_response

        rows = [
            (1,
             u'very löng column näme repeating itself very löng column name repeating itself',
             u'läst'),
        ]
        response = xls_response(rows)
        self.assertTrue(isinstance(response, Response))
        self.assertEquals('application/vnd.ms-excel',
                          response.headers['content-type'])
        self.assertEquals('attachment; filename=response.xls',
                          response.headers['content-disposition'])

        self.assertXlsEquals(u'Nuorisovaalit 2011', rows, response.body,
                             adapters=(int, None, None),
                             skip_header=False,
                             col_widths=(2048, 2048, 2048))

    def test_xls_response__changed_column_widths(self):
        from nuorisovaalitadmin.views.school import xls_response

        rows = [
            (1,
             u'very löng column näme repeating itself very löng column name repeating itself',
             u'läst'),
        ]
        response = xls_response(rows, col_widths=(1024, 3000, 13000))
        self.assertTrue(isinstance(response, Response))
        self.assertEquals('application/vnd.ms-excel',
                          response.headers['content-type'])
        self.assertEquals('attachment; filename=response.xls',
                          response.headers['content-disposition'])

        self.assertXlsEquals(u'Nuorisovaalit 2011', rows, response.body,
                             adapters=(int, None, None),
                             skip_header=False,
                             col_widths=(1024, 3000, 13000))

    def test_xls_response__some_changed_column_widths(self):
        from nuorisovaalitadmin.views.school import xls_response

        rows = [
            (1,
             u'very löng column näme repeating itself very löng column name repeating itself',
             u'läst'),
        ]
        response = xls_response(rows, col_widths=(1024, None, 13000))
        self.assertTrue(isinstance(response, Response))
        self.assertEquals('application/vnd.ms-excel',
                          response.headers['content-type'])
        self.assertEquals('attachment; filename=response.xls',
                          response.headers['content-disposition'])

        self.assertXlsEquals(u'Nuorisovaalit 2011', rows, response.body,
                             adapters=(int, None, None),
                             skip_header=False,
                             col_widths=(1024, 2048, 13000))


class XLSReponseMultipleTest(XlsTestCase):

    def test_xls_response_multiple__empty(self):
        from nuorisovaalitadmin.views.school import xls_response_multiple

        res = xls_response_multiple([])
        self.assertTrue(isinstance(res, Response))
        self.assertEquals('5632', res.headers['content-length'])
        self.assertEquals('application/vnd.ms-excel',
                          res.headers['content-type'])
        self.assertEquals('attachment; filename=response.xls',
                          res.headers['content-disposition'])

    def test_xls_response_multiple__changed_filename(self):
        from nuorisovaalitadmin.views.school import xls_response_multiple

        res = xls_response_multiple([], filename='changed-filename.xls')
        self.assertEquals('application/vnd.ms-excel',
                          res.headers['content-type'])
        self.assertEquals('attachment; filename=changed-filename.xls',
                          res.headers['content-disposition'])

    def test_xls_response_multiple__one_sheet(self):
        from nuorisovaalitadmin.views.school import xls_response_multiple

        rows = [
            (16, u' cölymn\t', u'  anöther cöl\t'),
        ]
        sheets = [
            (u'Söme sheet', rows),
        ]
        res = xls_response_multiple(sheets)
        self.assertTrue(isinstance(res, Response))
        self.assertEquals('application/vnd.ms-excel',
                          res.headers['content-type'])
        self.assertEquals('attachment; filename=response.xls',
                          res.headers['content-disposition'])

        self.assertXlsEquals(u'Söme sheet', rows, res.body, adapters=(int, None, None), skip_header=False)

    def test_xls_response_multiple__several_sheet(self):
        from nuorisovaalitadmin.views.school import xls_response_multiple

        rows0 = [
            (16, u' cölymn\t', u'  anöther cöl\t'),
        ]
        rows1 = [
            (163, u'céll', u'läst'),
            (89, u' other välye', u' last'),
        ]
        rows2 = [
            (100, u'mörkö', u'ylläri'),
        ]
        sheets = [
            (u'Etelä-Savon vaalipiiri', rows0),
            (u'Hämeen vaalipiiri', rows1),
            (u'1234567890123456789012345678901234567890', rows2),
        ]
        res = xls_response_multiple(sheets, num_formats=('@', None, None))
        self.assertTrue(isinstance(res, Response))
        self.assertEquals('application/vnd.ms-excel',
                          res.headers['content-type'])
        self.assertEquals('attachment; filename=response.xls',
                          res.headers['content-disposition'])

        self.assertXlsEquals(u'Etelä-Savon vaalipiiri', rows0, res.body,
                             adapters=(int, None, None), skip_header=False, sheet=0)
        self.assertXlsEquals(u'Hämeen vaalipiiri', rows1, res.body,
                             adapters=(int, None, None), skip_header=False, sheet=1)
        self.assertXlsEquals(u'1234567890123456789012345678901',
                             rows2, res.body, adapters=(int, None, None), skip_header=False, sheet=2)


class CSVResponseTest(unittest.TestCase):

    def test_csv_response__empty(self):
        from nuorisovaalitadmin.views.school import csv_response

        response = csv_response([])
        self.assertTrue(isinstance(response, Response))
        self.assertEquals('', response.body)
        self.assertEquals('0', response.headers['content-length'])
        self.assertEquals('text/csv; charset=ISO-8859-1',
                          response.headers['content-type'])
        self.assertEquals('attachment; filename=response.csv',
                          response.headers['content-disposition'])

    def test_csv_response__with_payload(self):
        from nuorisovaalitadmin.views.school import csv_response

        content = u'söme cöntent ÅÄÖ-'
        response = csv_response([(content, )])

        self.assertEquals(content.encode('ISO-8859-1') + '\r\n', response.body)

        # \r\n is added to the end of the content (thus +2)
        self.assertEquals(len(content.encode('ISO-8859-1')) + 2,
                          int(response.headers['content-length']))

    def test_csv_response__changed_encoding(self):
        from nuorisovaalitadmin.views.school import csv_response

        response = csv_response([], encoding='utf-8')
        self.assertEquals('text/csv; charset=utf-8',
                          response.headers['content-type'])

    def test_csv_response__changed_encoding_with_payload(self):
        from nuorisovaalitadmin.views.school import csv_response

        content = u'söme cöntent ÅÄÖ-'
        response = csv_response([(content, )], encoding='utf-8')

        self.assertEquals('text/csv; charset=utf-8',
                          response.headers['content-type'])
        self.assertEquals(content.encode('utf-8') + '\r\n', response.body)

        # \r\n is added to the end of the content (thus +2)
        self.assertEquals(len(content.encode('utf-8')) + 2,
                          int(response.headers['content-length']))

    def test_csv_response__changed_filename(self):
        from nuorisovaalitadmin.views.school import csv_response

        response = csv_response([], filename='changed.csv')
        self.assertEquals('attachment; filename=changed.csv',
                          response.headers['content-disposition'])

    def test_csv_response__with_several_rows(self):
        from nuorisovaalitadmin.views.school import csv_response

        rows = (
            (u'cölümn 1', u'other', u'thöörd cölümn'),
            (123, u'with, comma', u' field\twith  whitespace\t'),
        )
        response = csv_response(rows)

        body = u'cölümn 1,other,thöörd cölümn\r\n' +\
               u'123,"with, comma", field\twith  whitespace\t\r\n'

        self.assertEquals(body.encode('ISO-8859-1'), response.body)
        self.assertEquals(len(body.encode('ISO-8859-1')),
                          int(response.headers['content-length']))


class VotingListTest(XlsTestCase):

    def setUp(self):
        self.config = testing.setUp()
        init_testing_db()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_voters_template_csv(self):
        from nuorisovaalitadmin.views.school import SubmitVoters
        from nuorisovaalitadmin.views.school import voters_template_csv

        response = voters_template_csv(DummyRequest())
        self.assertTrue(isinstance(response, Response))
        self.assertEquals('text/csv; charset=ISO-8859-1', response.headers['content-type'])
        self.assertEquals(','.join(SubmitVoters.CSV_HEADER).encode('latin-1') + '\r\n', response.body)

    def test_voters_template_xls(self):
        from nuorisovaalitadmin.views.school import SubmitVoters
        from nuorisovaalitadmin.views.school import voters_template_xls

        response = voters_template_xls(DummyRequest())
        self.assertTrue(isinstance(response, Response))
        self.assertEquals('application/vnd.ms-excel', response.headers['content-type'])
        self.assertXlsEquals(u'Nuorisovaalit 2011', [SubmitVoters.CSV_HEADER], response.body, skip_header=False)

    def test_voter_list__unauthenticated(self):
        from nuorisovaalitadmin.views.school import voter_list

        self.assertRaises(Forbidden, lambda: voter_list(DummyRequest()))

    def test_voter_list__authenticated(self):
        from nuorisovaalitadmin.views.school import voter_list
        from nuorisovaalitadmin.models import User

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()
        self.config.testing_securitypolicy(userid=user.username)
        self.config.add_route('voter_list_xls', '/voter-list.xls')

        request = DummyRequest()
        self.assertEquals({
            'title': u'Lista äänestäneistä',
            'school': user.school.name,
            'district': user.school.district.name,
            'voter_list_xls': route_url('voter_list_xls', request),
        }, voter_list(request))

    def test_voter_list_xls__unauthenticated(self):
        from nuorisovaalitadmin.views.school import voter_list_xls

        self.assertRaises(Forbidden, lambda: voter_list_xls(DummyRequest()))

    def test_voter_list_xls__no_votes(self):
        from nuorisovaalit.models import Vote
        from nuorisovaalit.models import VotingLog
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import voter_list_xls

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()
        self.config.testing_securitypolicy(userid=user.username)

        # Make sure there are no Votes.
        self.assertEquals(0, session.query(Vote).count())
        self.assertEquals(0, session.query(VotingLog).count())

        response = voter_list_xls(DummyRequest())
        expected = [
            (u'Sukunimi', u'Etunimi', u'Syntymäaika', u'Äänestänyt'),
            (u'Meikäläinen', u'Matti', u'01.01.1970', u''),
        ]
        self.assertXlsEquals(u'Nuorisovaalit 2011', expected, response.body, skip_header=False)

    @mock.patch('nuorisovaalit.models.time')
    def test_voter_list_xls__votes_only_for_own_school(self, time_mock):
        from datetime import datetime
        from nuorisovaalit.models import Candidate
        from nuorisovaalit.models import Vote
        from nuorisovaalit.models import Voter
        from nuorisovaalit.models import VotingLog
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import voter_list_xls

        d = datetime(2011, 5, 15, 12, 1, 45)
        time_mock.time.return_value = time.mktime(d.timetuple())

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()
        self.config.testing_securitypolicy(userid=user.username)

        voter = session.query(Voter).first()
        self.assertTrue(voter is not None)
        candidate = session.query(Candidate)\
                    .filter(Candidate.district == voter.school.district).first()
        self.assertTrue(candidate is not None)

        # Add a voting record for the voter.
        session.add(Vote(candidate, voter.school, Vote.ELECTRONIC))
        session.add(VotingLog(voter))

        response = voter_list_xls(DummyRequest())
        expected = [
            (voter.lastname, voter.firstname, voter.dob.strftime('%d.%m.%Y'), u'15.05.2011 12:01:45'),
            ]
        self.assertXlsEquals(u'Nuorisovaalit 2011', expected, response.body)

    @mock.patch('nuorisovaalit.models.time')
    def test_voter_list_xls__votes_for_different_schools(self, time_mock):
        from datetime import datetime
        from nuorisovaalit.models import Candidate
        from nuorisovaalit.models import Vote
        from nuorisovaalit.models import Voter
        from nuorisovaalit.models import VotingLog
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import voter_list_xls

        d = datetime(2011, 5, 15, 12, 1, 45)
        time_mock.time.return_value = time.mktime(d.timetuple())

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()
        self.config.testing_securitypolicy(userid=user.username)

        # Select two users with different schools.
        voter1 = session.query(Voter).filter(Voter.school == user.school).first()
        self.assertTrue(voter1 is not None)
        voter2 = session.query(Voter).filter(Voter.school != voter1.school).first()
        self.assertTrue(voter2 is not None)
        self.assertNotEqual(voter1.school, voter2.school)

        # Select a candidate from the voters' districts.
        candidate1 = session.query(Candidate)\
                     .filter(Candidate.district == voter1.school.district).first()
        self.assertTrue(candidate1 is not None)
        candidate2 = session.query(Candidate)\
                     .filter(Candidate.district == voter2.school.district).first()
        self.assertTrue(candidate2 is not None)

        # Add vote for each candidate.
        session.add(Vote(candidate1, voter1.school, Vote.ELECTRONIC))
        session.add(VotingLog(voter1))
        session.add(Vote(candidate2, voter2.school, Vote.ELECTRONIC))
        session.add(VotingLog(voter2))

        response = voter_list_xls(DummyRequest())

        # Only the first vote should be returned, since the other one
        # was given to a candidate not from the user's district.
        expected = [
            (voter1.lastname, voter1.firstname, voter1.dob.strftime('%d.%m.%Y'), u'15.05.2011 12:01:45'),
            ]
        self.assertXlsEquals(u'Nuorisovaalit 2011', expected, response.body)


class ResultsTest(XlsTestCase):

    def setUp(self):
        self.config = testing.setUp()
        init_testing_db()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def _populate(self, quota=3):
        """Populates the testing db."""
        from nuorisovaalit.models import Candidate
        from nuorisovaalit.models import Coalition
        from nuorisovaalit.models import District
        from nuorisovaalit.models import Party
        from nuorisovaalit.models import School

        session = DBSession()

        # Assert the initial conditions.
        self.assertEquals(0, session.query(Candidate).count())
        self.assertEquals(0, session.query(Coalition).count())
        self.assertEquals(0, session.query(District).count())
        self.assertEquals(0, session.query(Party).count())
        self.assertEquals(0, session.query(School).count())

        # Add parties.
        skp = Party(u'Suomen Kommunistinen Työväenpuolue')
        ktp = Party(u'Kommunistinen Työväenpuolue')
        kokoomus = Party(u'Kansallinen Kököömys')
        vihreat = Party(u'Vihreä liitto')
        session.add(skp)
        session.add(ktp)
        session.add(kokoomus)
        session.add(vihreat)

        # Add districts.
        district = District(u'Väälipiiri', 16, quota)
        session.add(district)
        session.flush()

        # Add candidates.
        dob = date(1945, 12, 13)
        session.add(Candidate(1, u'skp 1', u'', dob, u'', u'', skp, district))
        session.add(Candidate(2, u'skp 2', u'', dob, u'', u'', skp, district))
        session.add(Candidate(3, u'ktp 1', u'', dob, u'', u'', ktp, district))
        session.add(Candidate(4, u'kokoomus 1', u'', dob, u'', u'', kokoomus, district))

        session.add(Candidate(11, u'vihreät 11', u'', dob, u'', u'', vihreat, district))
        session.add(Candidate(12, u'vihreät 12', u'', dob, u'', u'', vihreat, district))
        session.add(Candidate(13, u'vihreät 13', u'', dob, u'', u'', vihreat, district))
        session.add(Candidate(14, u'vihreät 14', u'', dob, u'', u'', vihreat, district))
        session.add(Candidate(15, u'vihreät 15', u'', dob, u'', u'', vihreat, district))
        session.add(Candidate(16, u'vihreät 16', u'', dob, u'', u'', vihreat, district))
        session.add(Candidate(17, u'vihreät 17', u'', dob, u'', u'', vihreat, district))
        session.add(Candidate(18, u'vihreät 18', u'', dob, u'', u'', vihreat, district))
        session.add(Candidate(19, u'vihreät 19', u'', dob, u'', u'', vihreat, district))
        session.add(Candidate(20, u'vihreät 20', u'', dob, u'', u'', vihreat, district))

        # Add coalitions.
        coalition = Coalition(u'xxxx', district)
        coalition.parties.append(skp)
        coalition.parties.append(ktp)
        session.add(coalition)

        session.add(School(u'xxxx', district))
        session.flush()

    def test_results_template_xls__unauthenticated(self):
        from nuorisovaalitadmin.views.school import results_template_xls

        self.assertRaises(Forbidden, lambda: results_template_xls(DummyRequest()))

    def test_results_template_xls__authenticated(self):
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import results_template_xls

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()
        self.config.testing_securitypolicy(userid=user.username)

        response = results_template_xls(DummyRequest())
        self.assertTrue(isinstance(response, Response))
        self.assertEquals('application/vnd.ms-excel', response.headers['content-type'])
        self.assertEquals('attachment; filename=nuorisovaalit2011-uurnatulokset.xls', response.headers['content-disposition'])

        expected = [
            (1, u'Turhapuro, Uuno', u''),
            (2, u'Hartikainen, Härski', u''),
            (3, u'Sörsselssön, Sami', u''),
            ]
        self.assertXlsEquals(u'Nuorisovaalit 2011', expected, response.body)

    def test_results__unauthenticated(self):
        from nuorisovaalitadmin.views.school import results

        self.assertRaises(Forbidden, lambda: results(DummyRequest()))

    def test_results__authenticated(self):
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import results

        self.config.add_route('results_template_xls', '/results-template.csv')
        self.config.add_route('results_xls', '/results.xls')

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()
        self.config.testing_securitypolicy(userid=user.username)

        request = DummyRequest()
        self.assertEquals({
            'title': u'Tulokset',
            'district': user.school.district.name,
            'results_template_xls': route_url('results_template_xls', request),
            'results_xls': route_url('results_xls', request),
        }, results(request))

    def test_results_xls__unauthenticated(self):
        from nuorisovaalitadmin.views.school import results_xls

        self.assertRaises(Forbidden, lambda: results_xls(DummyRequest()))

    def test_results_xls__no_votes(self):
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import results_xls

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()
        self.config.testing_securitypolicy(userid=user.username)

        candidates = user.school.district.candidates
        # Check that there are three candidates in the user's district.
        self.assertTrue(len(candidates) == 3)
        cand1 = candidates[0]
        cand2 = candidates[1]
        cand3 = candidates[2]

        response = results_xls(DummyRequest())

        self.assertEquals('application/vnd.ms-excel', response.headers['content-type'])

        title = u'{0} ({1} kansanedustajapaikka'.format(user.school.district.name,
                                                        user.school.district.quota)
        title += ')' if user.school.district.quota == 1 else 'a)'

        expected = [
            (title, u'', u'', u'', u''),
            (u'', u'', u'', u'', u''),
            (u'Valitut ehdokkaat', u'', u'', u'', u''),
            (u'Numero', u'Nimi', u'Puolue', u'Äänimäärä', u'Vertailuluku'),
            (cand3.number, cand3.fullname(), cand3.party.name, 0, 0),
            (cand1.number, cand1.fullname(), cand1.party.name, 0, 0),
            (cand2.number, cand2.fullname(), cand2.party.name, 0, 0),
            ]
        self.assertXlsEquals(u'Nuorisovaalit 2011', expected, response.body, skip_header=False)

    def test_results_xls__with_votes(self):
        from nuorisovaalit.models import Vote
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import results_xls

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()
        self.config.testing_securitypolicy(userid=user.username)

        candidates = user.school.district.candidates
        # Check that there are three candidates in the user's district.
        self.assertTrue(len(candidates) == 3)
        cand1 = candidates[0]
        cand2 = candidates[1]
        cand3 = candidates[2]
        # Add votes.
        session.add(Vote(cand1, user.school, Vote.ELECTRONIC, 1))
        session.add(Vote(cand2, user.school, Vote.ELECTRONIC, 1))
        session.add(Vote(cand2, user.school, Vote.ELECTRONIC, 1))
        session.add(Vote(cand2, user.school, Vote.PAPER, 10))

        response = results_xls(DummyRequest())
        self.assertEquals('application/vnd.ms-excel', response.headers['content-type'])

        title = u'{0} ({1} kansanedustajapaikka'.format(user.school.district.name,
                                                        user.school.district.quota)
        title += ')' if user.school.district.quota == 1 else 'a)'

        expected = [
            (title, u'', u'', u'', u''),
            (u'', u'', u'', u'', u''),
            (u'Valitut ehdokkaat', u'', u'', u'', u''),
            (u'Numero', u'Nimi', u'Puolue', u'Äänimäärä', u'Vertailuluku'),
            (cand2.number, cand2.fullname(), cand2.party.name, 12, 12),
            (cand1.number, cand1.fullname(), cand1.party.name, 1, 1),
            (cand3.number, cand3.fullname(), cand3.party.name, 0, 0),
            ]
        self.assertXlsEquals(u'Nuorisovaalit 2011', expected, response.body, skip_header=False)

    def test_results_xls_with_votes2(self):
        from nuorisovaalit.models import Candidate
        from nuorisovaalit.models import School
        from nuorisovaalit.models import Vote
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import results_xls

        session = DBSession()
        self._populate(quota=4)
        school = session.query(School).first()
        user = User('keijo', u'secret', u'Keijö Kojootti', None, school_or_id=school)
        session.add(user)
        session.flush()
        self.config.testing_securitypolicy(userid=user.username)

        self.assertEquals(0, session.query(Vote).count())

        skp1 = session.query(Candidate).filter_by(firstname=u'skp 1').one()
        skp2 = session.query(Candidate).filter_by(firstname=u'skp 2').one()
        ktp1 = session.query(Candidate).filter_by(firstname=u'ktp 1').one()
        kok1 = session.query(Candidate).filter_by(firstname=u'kokoomus 1').one()

        # Add votes.
        session.add(Vote(skp1, user.school, Vote.ELECTRONIC, 1))
        session.add(Vote(skp2, user.school, Vote.ELECTRONIC, 1))
        session.add(Vote(skp2, user.school, Vote.ELECTRONIC, 1))
        session.add(Vote(skp2, user.school, Vote.PAPER, 12))
        session.add(Vote(kok1, user.school, Vote.ELECTRONIC, 1))
        session.flush()

        response = results_xls(DummyRequest())
        self.assertEquals('application/vnd.ms-excel', response.headers['content-type'])

        self.assertXlsEquals(u'Nuorisovaalit 2011', [
            (u'Väälipiiri (4 kansanedustajapaikkaa)', u'', u'', u'', u''),
            (u'', u'', u'', u'', u''),
            (u'Valitut ehdokkaat', u'', u'', u'', u''),
            (u'Numero', u'Nimi', u'Puolue', u'Äänimäärä', u'Vertailuluku'),
            (skp2.number, skp2.fullname(), skp2.party.name, 14, 15.0),
            (skp1.number, skp1.fullname(), skp1.party.name, 1, 7.5),
            (ktp1.number, ktp1.fullname(), ktp1.party.name, 0, 5.0),
            (kok1.number, kok1.fullname(), kok1.party.name, 1, 1.0),
            (u'', u'', u'', u'', u''),
            (u'Valitsematta jääneet ehdokkaat', u'', u'', u'', u''),
            (u'Numero', u'Nimi', u'Puolue', u'Äänimäärä', u'Vertailuluku'),
            (18, u'vihreät 18', u'Vihreä liitto', 0, 0.0),
            (12, u'vihreät 12', u'Vihreä liitto', 0, 0.0),
            (19, u'vihreät 19', u'Vihreä liitto', 0, 0.0),
            (17, u'vihreät 17', u'Vihreä liitto', 0, 0.0),
            (20, u'vihreät 20', u'Vihreä liitto', 0, 0.0),
            (15, u'vihreät 15', u'Vihreä liitto', 0, 0.0),
            (14, u'vihreät 14', u'Vihreä liitto', 0, 0.0),
            (16, u'vihreät 16', u'Vihreä liitto', 0, 0.0),
            (13, u'vihreät 13', u'Vihreä liitto', 0, 0.0),
            (11, u'vihreät 11', u'Vihreä liitto', 0, 0.0),
        ], response.body, (int, None, None, int, None), skip_header=False)

    def test_results_xls_with_votes3(self):
        from nuorisovaalit.models import Candidate
        from nuorisovaalit.models import School
        from nuorisovaalit.models import Vote
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.school import results_xls

        session = DBSession()
        self._populate(quota=10)
        school = session.query(School).first()
        user = User('keijo', u'secret', u'Keijö Kojootti', None, school_or_id=school)
        session.add(user)
        session.flush()
        self.config.testing_securitypolicy(userid=user.username)

        self.assertEquals(0, session.query(Vote).count())

        vih11 = session.query(Candidate).filter_by(firstname=u'vihreät 11').one()
        vih12 = session.query(Candidate).filter_by(firstname=u'vihreät 12').one()
        vih13 = session.query(Candidate).filter_by(firstname=u'vihreät 13').one()
        vih14 = session.query(Candidate).filter_by(firstname=u'vihreät 14').one()
        vih15 = session.query(Candidate).filter_by(firstname=u'vihreät 15').one()
        vih16 = session.query(Candidate).filter_by(firstname=u'vihreät 16').one()
        vih17 = session.query(Candidate).filter_by(firstname=u'vihreät 17').one()
        vih18 = session.query(Candidate).filter_by(firstname=u'vihreät 18').one()
        vih19 = session.query(Candidate).filter_by(firstname=u'vihreät 19').one()
        vih20 = session.query(Candidate).filter_by(firstname=u'vihreät 20').one()

        session.add(Vote(vih11, user.school, Vote.PAPER, 1))
        session.add(Vote(vih12, user.school, Vote.PAPER, 2))
        session.add(Vote(vih13, user.school, Vote.PAPER, 3))
        session.add(Vote(vih14, user.school, Vote.PAPER, 4))
        session.add(Vote(vih15, user.school, Vote.PAPER, 5))
        session.add(Vote(vih16, user.school, Vote.PAPER, 6))
        session.add(Vote(vih17, user.school, Vote.PAPER, 7))
        session.add(Vote(vih18, user.school, Vote.PAPER, 8))
        session.add(Vote(vih19, user.school, Vote.PAPER, 9))
        session.add(Vote(vih20, user.school, Vote.PAPER, 10))
        session.flush()

        response = results_xls(DummyRequest())
        self.assertEquals('application/vnd.ms-excel', response.headers['content-type'])

        strfloat = '{0:.6f}'.format

        self.assertXlsEquals(u'Nuorisovaalit 2011', [
            (u'Väälipiiri (10 kansanedustajapaikkaa)', u'', u'', u'', u''),
            (u'', u'', u'', u'', u''),
            (u'Valitut ehdokkaat', u'', u'', u'', u''),
            (u'Numero', u'Nimi', u'Puolue', u'Äänimäärä', u'Vertailuluku'),
            (vih20.number, vih20.fullname(), vih20.party.name, 10, strfloat(55.0 / 1)),
            (vih19.number, vih19.fullname(), vih19.party.name, 9, strfloat(55.0 / 2)),
            (vih18.number, vih18.fullname(), vih18.party.name, 8, strfloat(55.0 / 3)),
            (vih17.number, vih17.fullname(), vih17.party.name, 7, strfloat(55.0 / 4)),
            (vih16.number, vih16.fullname(), vih16.party.name, 6, strfloat(55.0 / 5)),
            (vih15.number, vih15.fullname(), vih15.party.name, 5, strfloat(55.0 / 6)),
            (vih14.number, vih14.fullname(), vih14.party.name, 4, strfloat(55.0 / 7)),
            (vih13.number, vih13.fullname(), vih13.party.name, 3, strfloat(55.0 / 8)),
            (vih12.number, vih12.fullname(), vih12.party.name, 2, strfloat(55.0 / 9)),
            (vih11.number, vih11.fullname(), vih11.party.name, 1, strfloat(55.0 / 10)),
            (u'', u'', u'', u'', u''),
            (u'Valitsematta jääneet ehdokkaat', u'', u'', u'', u''),
            (u'Numero', u'Nimi', u'Puolue', u'Äänimäärä', u'Vertailuluku'),
            (1, u'skp 1', u'Suomen Kommunistinen Työväenpuolue', 0, u'0.000000'),
            (3, u'ktp 1', u'Kommunistinen Työväenpuolue', 0, u'0.000000'),
            (2, u'skp 2', u'Suomen Kommunistinen Työväenpuolue', 0, u'0.000000'),
            (4, u'kokoomus 1', u'Kansallinen Kököömys', 0, u'0.000000'),
        ], response.body, (int, None, None, int, strfloat), skip_header=False)
