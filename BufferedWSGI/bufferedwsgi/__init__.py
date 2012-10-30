# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
from paste.httpserver import WSGIHandler
from paste.httpserver import server_runner as paste_server_runner


class BufferedWSGIHandler(WSGIHandler):
    """Wrapper over paste.httpserver.WSGIHandler that sets the socket write
    interface to use buffered I/O.

    See SocketServer.StreamRequestHandler for details on setting up the write
    interface (self.wfile).
    """
    # Use the system default buffer size for buffering writes.
    wbufsize = -1


def server_runner(wsgi_app, global_conf, **kwargs):
    """Wrapper over paste.httpserver.server_runner() that injects the
    BufferedWSGIHandler as the handler class.
    """

    __doc__ = paste_server_runner.__doc__

    kwargs['handler'] = BufferedWSGIHandler
    return paste_server_runner(wsgi_app, global_conf, **kwargs)
