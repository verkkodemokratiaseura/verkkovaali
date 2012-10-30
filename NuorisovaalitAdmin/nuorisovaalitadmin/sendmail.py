# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
from pyramid.threadlocal import get_current_registry
from repoze.sendmail.delivery import DirectMailDelivery
from repoze.sendmail.mailer import SMTPMailer

_delivery = None


def _setup_delivery():
    """Returns a function that will send mail according to the STMP
    configuration.
    """
    settings = get_current_registry().settings
    hostname = settings.get('nuorisovaalitadmin.smtp_host', 'localhost').strip()
    try:
        port = int(settings.get('nuorisovaalitadmin.smtp_port', '25').strip())
    except (ValueError, TypeError):
        port = 25
    debug = settings.get('nuorisovaalitadmin.smtp_debug', 'false').strip().lower() == 'true'

    mailer = SMTPMailer(hostname=hostname, port=port, debug_smtp=debug)
    return DirectMailDelivery(mailer)


def send_mail(*args, **kwargs):
    global _delivery
    if _delivery is None:
        _delivery = _setup_delivery()

    return _delivery.send(*args, **kwargs)

__all__ = ['send_mail']
