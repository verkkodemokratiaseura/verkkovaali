# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
from setuptools import find_packages
from setuptools import setup

import os
import sys

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.txt')).read()
CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()

requires = [
    'BufferedWSGI',
    'OpenIDAlchemy',
    'SQLAlchemy',
    'WebError',
    'pyramid',
    'pyramid_beaker',
    'pyramid_zcml',
    'python-memcached',
    'python-openid',
    'repoze.tm2',
    'repoze.vhm',
    'transaction',
    'unittest2',
    'xlrd',
    'zope.sqlalchemy',
    ]

if sys.version_info[:3] < (2,5,0):
    requires.append('pysqlite')

setup(name='Nuorisovaalit',
      version='0.0',
      description='Nuorisovaalit',
      long_description=README + '\n\n' +  CHANGES,
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
      test_suite='nuorisovaalit',
      install_requires = requires,
      entry_points = """\
      [paste.app_factory]
      main = nuorisovaalit.run:main

      [console_scripts]
      nuorisovaalit_populate_demo = nuorisovaalit.scripts.populate:populate_demo
      nuorisovaalit_populate_districts = nuorisovaalit.scripts.populate:populate_districts
      nuorisovaalit_populate_candidates = nuorisovaalit.scripts.populate:populate_candidates
      """
      )

