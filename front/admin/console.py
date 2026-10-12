import time
import json
from collections import deque

from aiohttp import web

import settings

RING_SIZE = 200
_command_log = deque(maxlen = RING_SIZE)
_sb_log = deque(maxlen = RING_SIZE)
_seq = 0

def log_command(session_id, server_type, direction, command):
	global _seq
	_seq += 1
	_command_log.append({
		'seq': _seq,
		'ts': time.time(),
		'session': session_id,
		'type': server_type,
		'dir': direction,
		'cmd': command[:200],
	})

def log_sb_message(chat_id, sender, recipient, body):
	global _seq
	_seq += 1
	_sb_log.append({
		'seq': _seq,
		'ts': time.time(),
		'chat_id': chat_id,
		'sender': sender,
		'recipient': recipient,
		'body': body[:500],
	})

def register(app):
	app.router.add_get('/admin/console', handle_console_page)
	app.router.add_get('/admin/console-legacy', handle_console_legacy_page)
	app.router.add_get('/admin/console/api/sessions', api_sessions)
	app.router.add_get('/admin/console/api/log', api_log)
	app.router.add_get('/admin/console/api/sb', api_sb)
	app.router.add_get('/admin/console/api/users', api_users)
	app.router.add_post('/admin/console/api/send', api_send)
	app.router.add_post('/admin/console/api/msg', api_msg)
	app.router.add_post('/admin/console/api/boot', api_boot)
	app.router.add_post('/admin/console/api/broadcast', api_broadcast)
	app.router.add_get('/admin/console/api/stats', api_stats)
	app.router.add_post('/admin/console/api/debug', api_debug)
	app.router.add_post('/admin/console/api/welcome', api_welcome)
	app.router.add_get('/admin/console/api/robat/status', api_robat_status)
	app.router.add_post('/admin/console/api/robat/login', api_robat_login)
	app.router.add_post('/admin/console/api/robat/logout', api_robat_logout)
	app.router.add_post('/admin/console/api/robat/reload', api_robat_reload)
	app.router.add_post('/admin/console/api/robat/msg', api_robat_msg)
	app.router.add_post('/admin/console/api/robat/broadcast', api_robat_broadcast)
	app.router.add_get('/admin/console/api/robat/replies', api_robat_replies)
	app.router.add_post('/admin/console/api/robat/replies/add', api_robat_reply_add)
	app.router.add_post('/admin/console/api/robat/replies/delete', api_robat_reply_delete)
	app.router.add_get('/admin/console/api/robat/crons', api_robat_crons)
	app.router.add_post('/admin/console/api/robat/crons/add', api_robat_cron_add)
	app.router.add_post('/admin/console/api/robat/crons/delete', api_robat_cron_delete)
	app.router.add_post('/admin/console/api/robat/crons/toggle', api_robat_cron_toggle)

def _check_auth(req):
	from front.admin.entry import _check_auth as admin_auth
	return admin_auth(req)

def _json(data, status = 200):
	return web.json_response(data, status = status)

async def handle_console_page(req):
	if not _check_auth(req):
		return web.Response(status = 302, headers = {'Location': '/admin/login'})
	import os
	tmpl_path = os.path.join(os.path.dirname(__file__), 'tmpl', 'console.html')
	with open(tmpl_path) as f:
		html = f.read()
	return web.Response(content_type = 'text/html', text = html)

async def handle_console_legacy_page(req):
	if not _check_auth(req):
		return web.Response(status = 302, headers = {'Location': '/admin/login'})
	import os
	tmpl_path = os.path.join(os.path.dirname(__file__), 'tmpl', 'console-legacy.html')
	with open(tmpl_path) as f:
		html = f.read()
	return web.Response(content_type = 'text/html', text = html)

async def api_users(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	from db import Session as DBSession, User
	with DBSession() as sess:
		users = sess.query(User).order_by(User.email).all()
		user_list = [{'email': u.email, 'name': u.name} for u in users]
	return _json({'users': user_list})

def _get_sessions(backend):
	sessions = []
	for s in backend._sc.iter_sessions():
		if s.user is None:
			continue
		peername = s.get_peername() if hasattr(s, 'get_peername') else None
		sess_id = '%04x' % (hash(s) % 0xFFFF)
		dialect = getattr(s.state, 'dialect', None) or '?'
		client_ver = getattr(s.client, 'version', '?') if s.client else '?'
		status = s.user.status.substatus.name if s.user.status else '?'
		sessions.append({
			'id': sess_id,
			'email': s.user.email,
			'name': s.user.status.name if s.user.status else '',
			'ip': peername[0] if peername else 'unknown',
			'dialect': dialect,
			'client': client_ver,
			'status': status,
		})
	return sessions

async def api_sessions(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	backend = req.app['backend']
	return _json({'sessions': _get_sessions(backend)})

async def api_log(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	since = int(req.query.get('since', 0))
	entries = [e for e in list(_command_log) if e['seq'] > since]
	return _json({'entries': entries, 'latest_seq': _seq})

async def api_sb(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	since = int(req.query.get('since', 0))
	entries = [e for e in list(_sb_log) if e['seq'] > since]
	return _json({'entries': entries, 'latest_seq': _seq})

async def api_send(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	data = json.loads(await req.text())
	sess_id = data.get('session_id', '')
	command = data.get('command', '')
	backend = req.app['backend']
	for s in backend._sc.iter_sessions():
		if '%04x' % (hash(s) % 0xFFFF) == sess_id:
			parts = command.strip().split()
			if parts:
				s.send_reply(*parts)
			return _json({'ok': True})
	return _json({'error': 'session not found'}, 404)

async def api_msg(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	data = json.loads(await req.text())
	email = data.get('email', '')
	text = data.get('text', '')
	from_email = data.get('from_email', '')
	backend = req.app['backend']
	from core.user import UserService
	svc = UserService()
	user = svc.get_uuid(email)
	if user is None:
		return _json({'error': 'user not found'}, 404)
	u = backend._user_by_uuid.get(user)
	if u is None:
		return _json({'error': 'user not online'}, 400)
	sessions = backend._sc.get_sessions_by_user(u)
	if not sessions:
		return _json({'error': 'user not online'}, 400)
	if from_email:
		from_user = backend._user_by_uuid.get(svc.get_uuid(from_email))
		if from_user:
			from_name = from_user.status.name or from_email
		else:
			from_name = from_email
		msg_from = from_email
		msg_name = from_name
	else:
		msg_from = 'Server'
		msg_name = 'Server'
	payload = (
		'MIME-Version: 1.0\r\n'
		'Content-Type: text/plain; charset=UTF-8\r\n'
		'\r\n'
		'{}\r\n'
	).format(text).encode('utf-8')
	for s in sessions:
		s.send_reply('MSG', msg_from, msg_name, payload)
	return _json({'ok': True, 'sent_to': len(sessions), 'from': msg_from})

async def api_boot(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	data = json.loads(await req.text())
	email = data.get('email', '')
	backend = req.app['backend']
	from core.user import UserService
	svc = UserService()
	user = svc.get_uuid(email)
	if user is None:
		return _json({'error': 'user not found'}, 404)
	u = backend._user_by_uuid.get(user)
	if u is None:
		return _json({'error': 'user not online'}, 400)
	sessions = list(backend._sc.get_sessions_by_user(u))
	for s in sessions:
		try:
			s.send_event(__import__('core.event', fromlist = ['POPBootEvent']).POPBootEvent())
			s.close()
		except Exception:
			pass
	return _json({'ok': True, 'booted': len(sessions)})

async def api_broadcast(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	data = json.loads(await req.text())
	text = data.get('text', '')
	if not text:
		return _json({'error': 'no text'}, 400)
	backend = req.app['backend']
	payload = (
		'MIME-Version: 1.0\r\n'
		'Content-Type: text/plain; charset=UTF-8\r\n'
		'\r\n'
		'{}\r\n'
	).format(text).encode('utf-8')
	count = 0
	for s in backend._sc.iter_sessions():
		if s.user is None:
			continue
		try:
			s.send_reply('MSG', 'Server', 'Server', payload)
			count += 1
		except Exception:
			pass
	return _json({'ok': True, 'sent_to': count})

async def api_stats(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	backend = req.app['backend']
	sess_count = sum(1 for s in backend._sc.iter_sessions() if s.user is not None)
	chat_count = len(backend._chats)
	mem_mb = 0
	try:
		with open('/proc/meminfo') as f:
			for line in f:
				if line.startswith('MemAvailable:'):
					mem_mb = int(line.split()[1]) // 1024
					break
	except Exception:
		pass
	return _json({
		'sessions': sess_count,
		'chats': chat_count,
		'mem_mb': mem_mb,
		'debug': getattr(settings, 'DEBUG_MSNP', False),
		'welcome': getattr(settings, 'WELCOME_ENABLED', True),
	})

async def api_debug(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	data = json.loads(await req.text())
	enabled = data.get('enabled', False)
	settings.DEBUG_MSNP = bool(enabled)
	settings.DEBUG = bool(enabled)
	return _json({'ok': True, 'debug': bool(enabled)})

async def api_welcome(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	data = json.loads(await req.text())
	enabled = data.get('enabled', False)
	settings.WELCOME_ENABLED = bool(enabled)
	return _json({'ok': True, 'welcome_enabled': bool(enabled)})

def _get_robat(req):
	backend = req.app['backend']
	return getattr(backend, 'robat', None)

async def api_robat_status(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	r = _get_robat(req)
	if r is None:
		return _json({'online': False})
	return _json({'online': r.online})

async def api_robat_login(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	r = _get_robat(req)
	if r:
		r.login()
	return _json({'ok': True, 'online': r.online if r else False})

async def api_robat_logout(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	r = _get_robat(req)
	if r:
		r.logout()
	return _json({'ok': True, 'online': False})

async def api_robat_reload(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	r = _get_robat(req)
	if r:
		r.reload()
	return _json({'ok': True, 'online': r.online if r else False})

async def api_robat_msg(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	data = json.loads(await req.text())
	r = _get_robat(req)
	if r is None or not r.online:
		return _json({'error': 'robat offline'}, 400)
	ok = r.send_manual_msg(data.get('to', ''), data.get('text', ''))
	return _json({'ok': ok})

async def api_robat_broadcast(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	data = json.loads(await req.text())
	r = _get_robat(req)
	if r is None or not r.online:
		return _json({'error': 'robat offline'}, 400)
	count = r.broadcast(data.get('text', ''))
	return _json({'ok': True, 'sent_to': count})

async def api_robat_replies(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	r = _get_robat(req)
	if r is None:
		return _json({'replies': []})
	return _json({'replies': r.get_replies()})

async def api_robat_reply_add(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	data = json.loads(await req.text())
	r = _get_robat(req)
	if r:
		r.add_reply(data.get('en', ''), data.get('ga', ''))
	return _json({'ok': True})

async def api_robat_reply_delete(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	data = json.loads(await req.text())
	r = _get_robat(req)
	if r:
		r.delete_reply(int(data.get('id', 0)))
	return _json({'ok': True})

async def api_robat_crons(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	r = _get_robat(req)
	if r is None:
		return _json({'crons': []})
	return _json({'crons': r.get_crons()})

async def api_robat_cron_add(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	data = json.loads(await req.text())
	r = _get_robat(req)
	if r:
		r.add_cron(data.get('en', ''), data.get('ga', ''), int(data.get('interval', 0)), data.get('at_time'))
	return _json({'ok': True})

async def api_robat_cron_delete(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	data = json.loads(await req.text())
	r = _get_robat(req)
	if r:
		r.delete_cron(int(data.get('id', 0)))
	return _json({'ok': True})

async def api_robat_cron_toggle(req):
	if not _check_auth(req):
		return _json({'error': 'not authenticated'}, 401)
	data = json.loads(await req.text())
	r = _get_robat(req)
	if r:
		r.toggle_cron(int(data.get('id', 0)), bool(data.get('enabled', False)))
	return _json({'ok': True})