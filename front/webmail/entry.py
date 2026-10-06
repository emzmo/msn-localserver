import os
import time
import hmac
import secrets
from datetime import datetime
from urllib.parse import quote as url_quote

from aiohttp import web
import jinja2

import settings
from db import Session as DBSession, User, MailMessage
from util import hash

WEBMAIL_TMPL_DIR = 'front/webmail/tmpl'
COOKIE_NAME = 'msn_webmail'
COOKIE_MAX_AGE = 8 * 3600

_sessions = {}

def register(app):
	app['webmail_jinja_env'] = jinja2.Environment(
		loader = jinja2.FileSystemLoader(WEBMAIL_TMPL_DIR),
		autoescape = jinja2.select_autoescape(default = True),
	)
	app.router.add_get('/webmail', handle_inbox)
	app.router.add_get('/webmail/', handle_inbox)
	app.router.add_get('/webmail/login', handle_login_form)
	app.router.add_post('/webmail/login', handle_login_post)
	app.router.add_get('/webmail/logout', handle_logout)
	app.router.add_get('/webmail/inbox', handle_inbox)
	app.router.add_get('/webmail/read/{id:\\d+}', handle_read)
	app.router.add_get('/webmail/compose', handle_compose_form)
	app.router.add_post('/webmail/compose', handle_compose_post)

def _sign(token):
	secret = (settings.ADMIN_PASSWORD or 'changeme') + ':webmail'
	return hmac.new(secret.encode(), token.encode(), 'sha256').hexdigest()

def _make_cookie():
	token = secrets.token_hex(16)
	_sessions[token] = {'email': None, 'expires': time.time() + COOKIE_MAX_AGE}
	return '{}:{}'.format(token, _sign(token))

def _check_auth(req):
	cookie = req.cookies.get(COOKIE_NAME)
	if not cookie:
		return None
	parts = cookie.split(':', 1)
	if len(parts) != 2:
		return None
	token, sig = parts
	if not hmac.compare_digest(sig, _sign(token)):
		return None
	sess = _sessions.get(token)
	if sess is None or sess['expires'] < time.time():
		_sessions.pop(token, None)
		return None
	return sess['email']

def _login_user(email):
	token = secrets.token_hex(16)
	_sessions[token] = {'email': email, 'expires': time.time() + COOKIE_MAX_AGE}
	return '{}:{}'.format(token, _sign(token))

def _render(req, tmpl_name, ctxt = None, status = 200):
	tmpl = req.app['webmail_jinja_env'].get_template(tmpl_name)
	content = tmpl.render(**(ctxt or {}))
	return web.Response(status = status, content_type = 'text/html', text = content)

def _redirect(path):
	return web.Response(status = 302, headers = {'Location': path})

async def handle_login_form(req):
	if _check_auth(req):
		return _redirect('/webmail/inbox')
	error = req.query.get('error', '')
	return _render(req, 'login.html', {'error': error})

async def handle_login_post(req):
	form = await req.post()
	email = (form.get('email', '') or '').strip()
	password = form.get('password', '') or ''
	if not email or not password:
		return _redirect('/webmail/login?error=invalid')
	with DBSession() as sess:
		user = sess.query(User).filter(User.email == email).one_or_none()
		if user is None or not hash.hasher.verify(password, user.password):
			return _redirect('/webmail/login?error=invalid')
	resp = _redirect('/webmail/inbox')
	resp.set_cookie(COOKIE_NAME, _login_user(email), max_age = COOKIE_MAX_AGE, httponly = True)
	return resp

async def handle_logout(req):
	cookie = req.cookies.get(COOKIE_NAME)
	if cookie:
		parts = cookie.split(':', 1)
		if len(parts) == 2:
			_sessions.pop(parts[0], None)
	resp = _redirect('/webmail/login')
	resp.del_cookie(COOKIE_NAME)
	return resp

async def handle_inbox(req):
	email = _check_auth(req)
	if email is None:
		return _redirect('/webmail/login')
	with DBSession() as sess:
		messages = sess.query(MailMessage).filter(
			MailMessage.recipient_email == email
		).order_by(MailMessage.timestamp.desc()).all()
		unread_count = sum(1 for m in messages if not m.is_read)
		msg_list = [{
			'id': m.id,
			'sender': m.sender_email,
			'subject': m.subject or '(no subject)',
			'timestamp': m.timestamp,
			'is_read': m.is_read,
		} for m in messages]
	return _render(req, 'inbox.html', {
		'email': email,
		'messages': msg_list,
		'unread_count': unread_count,
		'total_count': len(msg_list),
	})

async def handle_read(req):
	email = _check_auth(req)
	if email is None:
		return _redirect('/webmail/login')
	msg_id = int(req.match_info['id'])
	with DBSession() as sess:
		msg = sess.query(MailMessage).filter(
			MailMessage.id == msg_id,
			MailMessage.recipient_email == email,
		).one_or_none()
		if msg is None:
			return _render(req, 'read.html', {
				'email': email, 'not_found': True,
			})
		if not msg.is_read:
			msg.is_read = True
		msg_data = {
			'id': msg.id,
			'sender': msg.sender_email,
			'recipient': msg.recipient_email,
			'subject': msg.subject or '(no subject)',
			'body': msg.body,
			'timestamp': msg.timestamp,
		}
	return _render(req, 'read.html', {'email': email, 'msg': msg_data})

async def handle_compose_form(req):
	email = _check_auth(req)
	if email is None:
		return _redirect('/webmail/login')
	to = req.query.get('to', '')
	prefill_error = req.query.get('error', '')
	return _render(req, 'compose.html', {
		'email': email,
		'to': to,
		'error': prefill_error,
	})

async def handle_compose_post(req):
	email = _check_auth(req)
	if email is None:
		return _redirect('/webmail/login')
	form = await req.post()
	to = (form.get('to', '') or '').strip()
	subject = (form.get('subject', '') or '').strip()
	body = (form.get('body', '') or '')
	if not to:
		return _redirect('/webmail/compose?error=no_recipient')
	if len(to) > 320 or len(subject) > 200 or len(body) > 50000:
		return _redirect('/webmail/compose?error=too_long&to=' + url_quote(to))
	with DBSession() as sess:
		recipient = sess.query(User).filter(User.email == to).one_or_none()
		if recipient is None:
			return _redirect('/webmail/compose?error=unknown_recipient&to=' + url_quote(to))
		sess.add(MailMessage(
			sender_email = email,
			recipient_email = to,
			subject = subject or '',
			body = body or '',
			timestamp = datetime.utcnow(),
			is_read = False,
		))
	return _redirect('/webmail/inbox')