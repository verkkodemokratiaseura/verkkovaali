# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
import os
import sys

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.txt')).read()
CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()

requires = [
    'Babel',
    'BufferedWSGI',
    'OpenIDAlchemy',
    'SQLAlchemy',
    'WebError',
    'coverage',
    'mock',
    'nose',
    'pycrypto',
    'pyramid',
    'pyramid_beaker',
    'pyramid_zcml',
    'python-openid',
    'repoze.browserid',
    'repoze.sendmail',
    'repoze.tm2',
    'repoze.vhm',
    'transaction',
    'z3c.bcrypt',
    'zope.sqlalchemy',
    ]

if sys.version_info[:3] < (2, 5, 0):
    requires.append('pysqlite')

setup(name='WebIdentity',
      version='0.0',
      description='WebIdentity',
      long_description=README + '\n\n' + CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Framework :: BFG",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
      author='',
      author_email='',
      url='',
      license='BSD',
      keywords='web wsgi bfg',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      test_suite='webidentity',
      install_requires=requires,
      entry_points="""\
      [paste.app_factory]
      main = webidentity.run:main

      [console_scripts]
      webidentity_populate_demo = webidentity.scripts.populate:populate_demo
      webidentity_populate_accounts = webidentity.scripts.populate:populate_accounts
      webidentity_verify_accounts = webidentity.scripts.populate:verify_accounts
      """,
      message_extractors={".": [
        ("**.py", "chameleon_python", None),
        ("**.pt", "chameleon_xml", None),
      ]},
      )
