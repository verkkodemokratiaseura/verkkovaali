# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
from paste.deploy import appconfig
import os
import sys


def get_config():
    if len(sys.argv) < 2:
        print("Usage: {0} <config>".format(sys.argv[0]))
        sys.exit(1)

    config_uri = 'config:{0}#nuorisovaalitadmin'.format(
        os.path.join(os.getcwd(), sys.argv[1].strip()))

    return appconfig(config_uri)
