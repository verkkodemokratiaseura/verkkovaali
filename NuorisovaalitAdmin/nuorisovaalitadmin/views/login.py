# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from datetime import datetime
from datetime import timedelta
from email.header import Header
from email.message import Message
from nuorisovaalitadmin.models import DBSession
from nuorisovaalitadmin.models import PasswordReset
from nuorisovaalitadmin.models import User
from nuorisovaalitadmin.sendmail import send_mail
from nuorisovaalitadmin.views import disable_caching
from pyramid.exceptions import Forbidden
from pyramid.exceptions import NotFound
from pyramid.security import authenticated_userid
from pyramid.security import forget
from pyramid.security import remember
from pyramid.url import route_url
from webob.exc import HTTPFound

import logging
import textwrap


def groupfinder(userid, request):
    """Returns a list of group identifiers for the given ``userid``.

    :param userid: Username of the user whose groups will be returned.
    :type userid: str

    :param request: The currently active request.
    :type request: :py:class:`pyramid.request.Request`

    :rtype: list or ``None``
    """
    user = DBSession().query(User).filter_by(username=userid).first()
    if user is not None:
        groups = ['group:{0}'.format(g.name) for g in user.groups]
        return groups

    return None


def authenticated_user(request):
    """Returns the currently authenticated
    :py:class:`nuorisovaalitadmin.models.User` instance or ``None``.

    :param request: The currently active request.
    :type request: :py:class:`pyramid.request.Request`
    :rtype: :py:class:`nuorisovaalitadmin.models.User` or ``None``
    """
    userid = authenticated_userid(request)
    if userid is not None:
        return DBSession().query(User).filter_by(username=userid).first()


def index(request):
    user = authenticated_user(request)
    if user is None:
        raise Forbidden

    options = {}
    return options


def login(request):
    """Renders a login form and logs in a user if given the correct
    credentials.
    """
    session = DBSession()
    username = u''
    log = logging.getLogger('nuorisovaalitadmin')

    if 'form.submitted' in request.POST:
        username = request.POST['username']

        if request.session.get_csrf_token() != request.POST.get('csrf_token'):
            log.warn('CSRF attempt at {0}.'.format(request.url))
            raise Forbidden(u'CSRF attempt detected.')
        else:
            user = session.query(User).filter_by(username=username).first()
            password = request.POST['password']

            if user is not None and user.check_password(password):
                headers = remember(request, user.username)
                request.session.flash(u'Olet kirjautunut sisään.')
                log.info('Successful login for "{0}".'.format(user.username))
                return HTTPFound(location=request.application_url, headers=headers)

            log.warn('Failed login attempt for {0}'.format(request.POST.get('username').encode('utf-8')))
            request.session.flash(u'Kirjautuminen epäonnistui')

    request.add_response_callback(disable_caching)
    return {
        'title': u'Kirjaudu sisään',
        'action_url': route_url('login', request),
        'username': username,
        'reset_url': route_url('reset_password', request),
        'csrf_token': request.session.get_csrf_token(),
    }


def logout(request):
    """Logs out the currently authenticated user."""
    headers = forget(request)
    request.session.flash(u'Olet kirjautunut ulos')
    return HTTPFound(location=request.application_url, headers=headers)


class PasswordResetView(object):
    """Password reset logic."""

    def __init__(self, request):
        self.request = request
        self.session = DBSession()
        self.prune_expired()

    def prune_expired(self):
        """Prunes password reset requests that have expired."""
        self.session.query(PasswordReset)\
                .filter(PasswordReset.expires < datetime.now())\
                .delete()

    def render_form(self):
        """Renders the password reset form."""
        return {
            'action_url': route_url('reset_password_initiate', self.request),
            'title': u'Nollaa salasana',
        }

    def password_change_form(self):
        """Renders the form for changing a password for a valid token."""
        log = logging.getLogger('nuorisovaalitadmin')
        reset = self.session.query(PasswordReset)\
            .filter(PasswordReset.token == self.request.matchdict['token'])\
            .filter(PasswordReset.expires >= datetime.now())\
            .first()
        if reset is None:
            log.warn('Unknown password reset token: {token}.'.format(**self.request.matchdict))
            # No matching password reset found
            raise NotFound

        user = self.session.query(User).get(reset.user_id)
        if user is None:
            log.warn('Unknown user "{0}" for password reset.'.format(reset.user_id))
            raise NotFound

        return {
            'action_url': route_url('reset_password_process', self.request),
            'title': u'Vaihda salasana',
            'token': reset.token,
            'username': user.username,
            }

    def send_confirmation_message(self):
        """Sends an email confirmation message to the user."""
        username = self.request.POST.get('username', '').strip()
        redirect_url = route_url('reset_password', self.request)
        log = logging.getLogger('nuorisovaalitadmin')

        if not username:
            self.request.session.flash(u'Anna käyttäjätunnus.')
        else:
            user = self.session.query(User).filter(User.username == username).first()
            if user is None:
                self.request.session.flash(u'Annettua käyttäjätunnusta ei löydy.')
            else:
                # Create a password reset request that is valid for 24 hours
                reset = PasswordReset(user.id, datetime.now() + timedelta(hours=24))
                self.session.add(reset)
                message = self.create_message(user, reset)
                from_address = self.request.registry.settings['nuorisovaalitadmin.from_address'].strip()
                # TODO add sendmail to project to include it here
                send_mail(from_address, [user.email], message)
                self.request.session.flash(u'Ohjeet salasanan vaihtamiseen on lähetetty sähköpostissa.')
                redirect_url = self.request.application_url
                log.info('Sending password reset instructions to {0}.'.format(user.email))

        return HTTPFound(location=redirect_url)

    def create_message(self, user, reset):
        """Returns an email.message.Message object representing the password
        reset message.
        """
        from_address = self.request.registry.settings['nuorisovaalitadmin.from_address'].strip()
        date_format = self.request.registry.settings['nuorisovaalitadmin.date_format'].strip()

        subject = user.username

        message = Message()
        message['From'] = Header(from_address, 'utf-8')
        message['To'] = Header(u'{0} <{1}>'.format(user.username, user.email), 'utf-8')
        message['Subject'] = Header(subject, 'utf-8')

        message.set_payload(textwrap.dedent(u'''
            Hyvä {username},

            Nuorisovaalit 2011 -ylläpitosivustolta on tehty pyyntö
            salasanasi uusimiseksi.

            Jos teit pyynnön itse, voit uusia salasanasi avaamalla
            seuraavan linkin selaimessa:

              {reset_url}

            Linkki vanhentuu {expiration}.

            Mikäli tämä viesti on mielestäsi aiheeton voit poistaa ja
            unohtaa sen. Salasanaasi ei ole muutettu.
            '''.encode('utf-8')).lstrip().format(username=user.username,
                                                 expiration=reset.expires.strftime(date_format),
                                                 reset_url=route_url('reset_password_token',
                                                                     self.request,
                                                                     token=reset.token)))

        return message

    def change_password(self):
        """Changes the password for a user."""
        token = self.request.POST.get('token', '').strip()
        log = logging.getLogger('nuorisovaalitadmin')

        if token:
            password = self.request.POST.get('password', '')
            confirm_password = self.request.POST.get('confirm_password', '')
            if len(password.strip()) < 5:
                self.request.session.flash(u'Salasanan on oltava vähintään viisi merkkiä pitkä')
                return HTTPFound(
                    location=route_url('reset_password_token', self.request, token=token))
            elif password != confirm_password:
                self.request.session.flash(u'Annetut salasanat eivät vastaa toisiaan')
                return HTTPFound(
                    location=route_url('reset_password_token', self.request, token=token))
            else:
                reset = self.session.query(PasswordReset)\
                    .filter(PasswordReset.token == token)\
                    .filter(PasswordReset.expires >= datetime.now())\
                    .first()
                if reset is None:
                    raise NotFound

                user = self.session.query(User).get(reset.user_id)
                if user is None:
                    raise NotFound

                # Update the user password
                user.password = password
                self.session.add(user)
                self.session.delete(reset)

                self.request.session.flash(u'Salasana vaihdettu.')
                log.info('Changed password for {0}.'.format(user.username))

                headers = remember(self.request, user.username)
                return HTTPFound(location=self.request.application_url, headers=headers)

        raise NotFound
