# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
import os
import sys

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.txt')).read()
CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()

requires = [
    'BeautifulSoup',
    'BufferedWSGI',
    'SQLAlchemy',
    'WebError',
    'WebTest',
    'isounidecode',
    'nuorisovaalit',
    'openpyxl',
    'pyramid',
    'pyramid_beaker',
    'pyramid_zcml',
    'repoze.filesafe',
    'repoze.sendmail',
    'repoze.tm2>=1.0b1', # default_commit_veto
    'repoze.vhm',
    'transaction',
    'unittest2',
    'xlrd',
    'xlwt',
    'z3c.bcrypt',
    'zope.sqlalchemy',
    ]

if sys.version_info[:3] < (2,5,0):
    requires.append('pysqlite')

setup(name='NuorisovaalitAdmin',
      version='0.0',
      description='NuorisovaalitAdmin',
      long_description=README + '\n\n' +  CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Pylons",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
      author='',
      author_email='',
      url='',
      license='BSD',
      keywords='web wsgi bfg pylons pyramid',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      test_suite='nuorisovaalitadmin',
      install_requires = requires,
      entry_points = """\
      [paste.app_factory]
      main = nuorisovaalitadmin:main
      
      [console_scripts]
      nuorisovaalitadmin_generate_labyrintti_batch3 = nuorisovaalitadmin.scripts.populate:generate_third_labyrintti_batch
      nuorisovaalitadmin_generate_labyrintti_remaining = nuorisovaalitadmin.scripts.populate:generate_labyrintti_batch_for_remaining_voters
      nuorisovaalitadmin_generate_email_remaining = nuorisovaalitadmin.scripts.populate:generate_email_batch_for_remaining_voters
      nuorisovaalitadmin_populate_demo = nuorisovaalitadmin.scripts.populate:populate_demo
      nuorisovaalitadmin_populate_paper_votes = nuorisovaalitadmin.scripts.populate:populate_voting_results_cli
      nuorisovaalitadmin_populate_schools = nuorisovaalitadmin.scripts.populate:populate_school_accounts
      nuorisovaalitadmin_populate_voters = nuorisovaalitadmin.scripts.populate:populate_voters
      nuorisovaalitadmin_stat_voter_submissions = nuorisovaalitadmin.scripts.stats:voter_submission_counts
      nuorisovaalitadmin_verify_voters = nuorisovaalitadmin.scripts.populate:verify_voters
      """,
      paster_plugins=['pyramid'],
      )

