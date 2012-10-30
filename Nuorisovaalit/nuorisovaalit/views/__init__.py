# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# package


def disable_caching(request, response):
    """Disables caching for the given response by setting the appropriate
    HTTP headers.
    """
    response.headerlist.extend([
        # HTTP 1.1
        ('Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0'),
        # IE cache extensions, http://aspnetresources.com/blog/cache_control_extensions
        ('Cache-Control', 'post-check=0, pre-check=0'),
        # HTTP 1.0
        ('Expires', ' Tue, 03 Jul 2001 06:00:00 GMT'),
        ('Pragma', 'no-cache'),
    ])
