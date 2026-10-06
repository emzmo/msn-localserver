import hmac
import secrets
import time
from datetime import datetime

from aiohttp import web
import jinja2

import settings
from db import Session as DBSession, User
from util import hash

COOKIE_NAME = 'msn_admin'
COOKIE_MAX_AGE = 8 * 3600
ADMIN_TMPL_DIR = 'front/admin/tmpl'

_session_keys = {}

def register(loop, backend, *, http_port):
	from util.misc import AIOHTTPRunner
	app = _create_admin_app(backend)
	from front.public import entry as public_entry
	public_entry.register(app)
	from front.webmail import entry as webmail_entry
	webmail_entry.register(app)
	backend.add_runner(AIOHTTPRunner('0.0.0.0', http_port + 1, app))

def _create_admin_app(backend):
	app = web.Application()
	app['backend'] = backend
	app['jinja_env'] = jinja2.Environment(
		loader = jinja2.FileSystemLoader(ADMIN_TMPL_DIR),
		autoescape = jinja2.select_autoescape(default = True),
	)
	
	app.router.add_get('/admin', handle_dashboard)
	app.router.add_get('/admin/', handle_dashboard)
	app.router.add_get('/admin/login', handle_login_form)
	app.router.add_post('/admin/login', handle_login_post)
	app.router.add_get('/admin/logout', handle_logout)
	app.router.add_get('/admin/users', handle_users)
	app.router.add_post('/admin/users/create', handle_user_create)
	app.router.add_post('/admin/users/delete', handle_user_delete)
	app.router.add_post('/admin/users/reset', handle_user_reset)
	app.router.add_post('/admin/users/bulk', handle_user_bulk)
	app.router.add_get('/admin/users/edit/{email:.+}', handle_user_edit_form)
	app.router.add_post('/admin/users/edit', handle_user_edit_save)
	app.router.add_post('/admin/users/wipe', handle_user_wipe)
	app.router.add_get('/admin/online', handle_online)
	app.router.add_get('/admin/conversations', handle_conversations)
	app.router.add_post('/admin/conversations/delete', handle_conversation_delete)
	app.router.add_get('/admin/status', handle_status)
	app.router.add_get('/admin/setup', handle_setup)
	app.router.add_get('/admin/download/{filename}', handle_download)
	
	return app

def _check_auth(req):
	cookie = req.cookies.get(COOKIE_NAME)
	if not cookie:
		return False
	parts = cookie.split(':', 1)
	if len(parts) != 2:
		return False
	email, sig = parts
	expected = _sign(email)
	return hmac.compare_digest(sig, expected)

def _sign(email):
	secret = settings.ADMIN_PASSWORD
	return hmac.new(secret.encode(), email.encode(), 'sha256').hexdigest()

def _make_cookie():
	token = secrets.token_hex(16)
	_session_keys[token] = time.time() + COOKIE_MAX_AGE
	sig = _sign(token)
	return '{}:{}'.format(token, sig)

def _render(req, tmpl_name, ctxt = None, status = 200):
	tmpl = req.app['jinja_env'].get_template(tmpl_name)
	content = tmpl.render(**(ctxt or {}))
	return web.Response(status = status, content_type = 'text/html', text = content)

def _redirect(path):
	return web.Response(status = 302, headers = {'Location': path})

async def handle_login_form(req):
	return _render(req, 'login.html')

async def handle_login_post(req):
	form = await req.post()
	password = form.get('password', '')
	if hmac.compare_digest(password, settings.ADMIN_PASSWORD):
		resp = _redirect('/admin')
		resp.set_cookie(COOKIE_NAME, _make_cookie(), max_age = COOKIE_MAX_AGE, httponly = True)
		return resp
	return _render(req, 'login.html', {'error': 'Wrong password'}, status = 401)

async def handle_logout(req):
	resp = _redirect('/admin/login')
	resp.del_cookie(COOKIE_NAME)
	return resp

async def handle_dashboard(req):
	if not _check_auth(req):
		return _redirect('/admin/login')
	backend = req.app['backend']
	with DBSession() as sess:
		user_count = sess.query(User).count()
	online_count = sum(1 for s in backend._sc.iter_sessions() if s.user is not None)
	chat_count = len(backend._chats)
	return _render(req, 'dashboard.html', {
		'user_count': user_count,
		'online_count': online_count,
		'chat_count': chat_count,
	})

async def handle_users(req):
	if not _check_auth(req):
		return _redirect('/admin/login')
	with DBSession() as sess:
		users = sess.query(User).order_by(User.email).all()
		user_list = [{'email': u.email, 'name': u.name, 'verified': u.verified, 'date_created': u.date_created} for u in users]
	return _render(req, 'users.html', {'users': user_list})

async def handle_user_create(req):
	if not _check_auth(req):
		return _redirect('/admin/login')
	form = await req.post()
	email = form.get('email', '').strip()
	password = form.get('password', '')
	name = form.get('name', '').strip() or email
	old_msn = form.get('old_msn') == 'on'
	if not email or not password:
		return _render(req, 'users.html', {'error': 'Email and password required'}, status = 400)
	_create_or_update_user(email, password, name, old_msn)
	return _redirect('/admin/users')

async def handle_user_delete(req):
	if not _check_auth(req):
		return _redirect('/admin/login')
	form = await req.post()
	email = form.get('email', '')
	if not email:
		return _redirect('/admin/users')
	with DBSession() as sess:
		user = sess.query(User).filter(User.email == email).one_or_none()
		if user:
			from db import MailMessage
			sess.query(MailMessage).filter(
				(MailMessage.sender_email == email) |
				(MailMessage.recipient_email == email)
			).delete()
			sess.delete(user)
	return _redirect('/admin/users')

async def handle_user_reset(req):
	if not _check_auth(req):
		return _redirect('/admin/login')
	form = await req.post()
	email = form.get('email', '')
	password = form.get('password', '')
	if not email or not password:
		return _redirect('/admin/users')
	with DBSession() as sess:
		user = sess.query(User).filter(User.email == email).one_or_none()
		has_md5 = bool(user.password_md5) if user else False
	_create_or_update_user(email, password, None, has_md5)
	return _redirect('/admin/users')

async def handle_user_bulk(req):
	if not _check_auth(req):
		return _redirect('/admin/login')
	form = await req.post()
	prefix = form.get('prefix', 'visitor').strip()
	domain = form.get('domain', 'hotmail.com').strip()
	count = int(form.get('count', '10'))
	password = form.get('password', 'visitor')
	old_msn = form.get('old_msn') == 'on'
	for i in range(1, count + 1):
		email = '{}{}@{}'.format(prefix, i, domain)
		_create_or_update_user(email, password, '{} {}'.format(prefix.capitalize(), i), old_msn)
	return _redirect('/admin/users')

async def handle_user_edit_form(req):
	if not _check_auth(req):
		return _redirect('/admin/login')
	email = req.match_info['email']
	with DBSession() as sess:
		user = sess.query(User).filter(User.email == email).one_or_none()
		if not user:
			return _redirect('/admin/users')
		user_data = {'email': user.email, 'name': user.name}
	return _render(req, 'edit_user.html', {'user': user_data})

async def handle_user_edit_save(req):
	if not _check_auth(req):
		return _redirect('/admin/login')
	form = await req.post()
	email = form.get('email', '')
	name = form.get('name', '').strip()
	if not email or not name:
		return _redirect('/admin/users')
	with DBSession() as sess:
		user = sess.query(User).filter(User.email == email).one_or_none()
		if user:
			user.name = name
			sess.add(user)
	return _redirect('/admin/users')

async def handle_user_wipe(req):
	if not _check_auth(req):
		return _redirect('/admin/login')
	form = await req.post()
	confirm_password = form.get('confirm_password', '')
	if not hmac.compare_digest(confirm_password, settings.ADMIN_PASSWORD):
		return _render(req, 'users.html', {'error': 'Wrong admin password for wipe confirmation'}, status = 403)
	prefix = form.get('prefix', 'visitor').strip()
	domain = form.get('domain', 'hotmail.com').strip()
	recreate = form.get('recreate') == 'on'
	count = int(form.get('count', '20'))
	password = form.get('password', 'visitor')
	old_msn = form.get('old_msn') == 'on'
	pattern = '{}%@{}'.format(prefix, domain)
	with DBSession() as sess:
		from db import MailMessage
		sess.query(MailMessage).filter(
			(MailMessage.sender_email.like(pattern)) |
			(MailMessage.recipient_email.like(pattern))
		).delete()
		sess.query(User).filter(User.email.like(pattern)).delete()
	if recreate:
		for i in range(1, count + 1):
			email = '{}{}@{}'.format(prefix, i, domain)
			_create_or_update_user(email, password, '{} {}'.format(prefix.capitalize(), i), old_msn)
	return _redirect('/admin/users')

async def handle_online(req):
	if not _check_auth(req):
		return _redirect('/admin/login')
	backend = req.app['backend']
	online = []
	for s in backend._sc.iter_sessions():
		if s.user is None:
			continue
		peername = s.get_peername() if hasattr(s, 'get_peername') else None
		online.append({
			'email': s.user.email,
			'name': s.user.status.name if s.user.status else '',
			'ip': peername[0] if peername else 'unknown',
		})
	return _render(req, 'online.html', {'online': online})

async def handle_conversations(req):
	if not _check_auth(req):
		return _redirect('/admin/login')
	from db import Conversation
	from sqlalchemy import func
	filter_email = req.query.get('email', '')
	page = int(req.query.get('page', '1'))
	per_page = 20
	with DBSession() as sess:
		subq = sess.query(
			Conversation.chat_id,
			func.min(Conversation.timestamp).label('first_ts'),
			func.max(Conversation.timestamp).label('last_ts'),
			func.count(Conversation.id).label('msg_count'),
		).group_by(Conversation.chat_id)
		if filter_email:
			subq = subq.filter(
				(Conversation.sender_email == filter_email) |
				(Conversation.recipient_email == filter_email))
		subq = subq.subquery()
		total = sess.query(subq).count()
		threads = sess.query(subq).order_by(subq.c.last_ts.desc()).offset((page - 1) * per_page).limit(per_page).all()
		thread_list = []
		for t in threads:
			msgs = sess.query(Conversation).filter(Conversation.chat_id == t.chat_id).order_by(Conversation.timestamp.asc()).all()
			participants = set()
			for m in msgs:
				participants.add(m.sender_email)
				participants.add(m.recipient_email)
			thread_list.append({
				'chat_id': t.chat_id,
				'participants': ' <-> '.join(sorted(participants)),
				'msg_count': t.msg_count,
				'first_ts': t.first_ts,
				'last_ts': t.last_ts,
				'messages': [{
					'sender': m.sender_email,
					'body': m.body[:500] if m.body else '',
					'timestamp': m.timestamp,
				} for m in msgs],
			})
	pages = (total + per_page - 1) // per_page
	return _render(req, 'conversations.html', {
		'threads': thread_list,
		'filter_email': filter_email,
		'page': page,
		'pages': pages,
		'total': total,
	})

async def handle_conversation_delete(req):
	if not _check_auth(req):
		return _redirect('/admin/login')
	form = await req.post()
	chat_id = form.get('chat_id', '')
	if not chat_id:
		return _redirect('/admin/conversations')
	from db import Conversation
	with DBSession() as sess:
		sess.query(Conversation).filter(Conversation.chat_id == chat_id).delete()
	return _redirect('/admin/conversations')

async def handle_status(req):
	if not _check_auth(req):
		return _redirect('/admin/login')
	import subprocess
	status = {}
	for svc in ['msn-museum.service', 'msn-gateway-ssl3.service']:
		try:
			r = subprocess.run(['systemctl', 'is-active', svc], capture_output=True, text=True, timeout=5)
			status[svc] = r.stdout.strip()
		except Exception:
			status[svc] = 'unknown'
	try:
		with open('/proc/uptime') as f:
			uptime_secs = float(f.read().split()[0])
		hours = int(uptime_secs // 3600)
		mins = int((uptime_secs % 3600) // 60)
		status['uptime'] = '%dh %dm' % (hours, mins)
	except Exception:
		status['uptime'] = 'unknown'
	try:
		with open('/proc/meminfo') as f:
			for line in f:
				if line.startswith('MemAvailable:'):
					status['mem_available'] = int(line.split()[1]) // 1024
					break
	except Exception:
		status['mem_available'] = 0
	try:
		r = subprocess.run(['ss', '-tlnp'], capture_output=True, text=True, timeout=5)
		lines = r.stdout.strip().split('\n')
		status['ports'] = {}
		for port in ['443', '1863', '1864', '8081', '8082']:
			status['ports'][port] = any((':' + port) in line for line in lines)
	except Exception:
		status['ports'] = {}
	try:
		r = subprocess.run(['journalctl', '-u', 'msn-museum.service', '-n', '20', '--no-pager'], capture_output=True, text=True, timeout=5)
		status['logs'] = r.stdout.strip().split('\n')
	except Exception:
		status['logs'] = ['Unable to read logs']
	return _render(req, 'status.html', {'status': status})

def _create_or_update_user(email, password, name, old_msn):
	from util.misc import gen_uuid
	with DBSession() as sess:
		user = sess.query(User).filter(User.email == email).one_or_none()
		if user is None:
			user = User(
				uuid = gen_uuid(), email = email, verified = True,
				name = name or email, message = '',
				settings = {}, groups = {}, contacts = {},
			)
		else:
			if name:
				user.name = name
		user.password = hash.hasher.encode(password)
		user.password_md5 = hash.hasher_md5.encode(password) if old_msn else ''
		sess.add(user)

import os

DOWNLOAD_DIR = os.path.expanduser('~/msn-museum/downloads')

async def handle_setup(req):
	if not _check_auth(req):
		return _redirect('/admin/login')
	downloads = []
	if os.path.isdir(DOWNLOAD_DIR):
		for f in sorted(os.listdir(DOWNLOAD_DIR)):
			if f.startswith('.'):
				continue
			path = os.path.join(DOWNLOAD_DIR, f)
			if not os.path.isfile(path):
				continue
			size = os.path.getsize(path)
			if size > 1024 * 1024:
				size_str = '%.1f MB' % (size / (1024 * 1024))
			else:
				size_str = '%d KB' % (size // 1024)
			downloads.append({'name': f, 'size': size_str})
	return _render(req, 'setup.html', {'downloads': downloads, 'server_ip': settings.SB_HOST})

async def handle_download(req):
	if not _check_auth(req):
		return _redirect('/admin/login')
	filename = req.match_info['filename']
	safe = os.path.basename(filename)
	path = os.path.join(DOWNLOAD_DIR, safe)
	if not os.path.isfile(path):
		return web.Response(status = 404, text = 'File not found')
	with open(path, 'rb') as f:
		data = f.read()
	if safe.endswith('.crt'):
		ct = 'application/x-x509-ca-cert'
	elif safe.endswith('.exe'):
		ct = 'application/octet-stream'
	else:
		ct = 'application/octet-stream'
	return web.Response(body = data, content_type = ct, headers = {
		'Content-Disposition': 'attachment; filename="{}"'.format(safe),
	})