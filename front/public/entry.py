import os
import time
from collections import defaultdict, deque

from aiohttp import web
import jinja2

import settings
from db import Session as DBSession, User
from util import hash

PUBLIC_TMPL_DIR = 'front/public/tmpl'
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'static')

TRANSLATIONS = {
	'ga': {
		'site_title': 'MSN Messenger Revival',
		'welcome': 'Fáilte go MSN Messenger',
		'subtitle': 'Seirbhís chomhrá do Mhúsaem',
		'signup_link': 'Cláraigh',
		'info_link': 'MSNP Prótacal',
		'home_link': 'Baile',
		'lang_switch': 'English',
		'lang_switch_code': 'en',
		'years_since': 'bliain ó dúnadh MSN Messenger',
		'messages_sent': 'teachtaireacht seolta',
		'users_registered': 'úsáideoir cláraithe',
		'signup_title': 'Cruthaigh Cuntas Nua',
		'signup_desc': 'Cláraigh chun labhairt le do chairde ar MSN Messenger.',
		'email': 'Ríomhphost',
		'password': 'Pasfhocal',
		'display_name': 'Ainm Taispeána',
		'create_account': 'Cruthaigh Cuntas',
		'signup_success': 'Fáilte! Tá do chuntas cruthaithe.',
		'signup_success_desc': 'Is féidir leat síniú isteach anois ar MSN Messenger.',
		'signup_error_exists': 'Tá an ríomhphost seo ann cheana.',
		'signup_error_invalid': 'Ní ríomhphost bailí é seo.',
		'signup_error_short': 'Ní mór 3 charactar ar a laghad a bheith sa phasfhocal.',
		'signup_error_rate': 'Fan 15 soicind sula n-úsáideann tú arís.',
		'back_home': 'Ar ais go dtí an leathanach baile',
		'info_title': 'Eolas an Phrótacail',
		'login_tab': 'Logáil Isteach',
		'conversation_tab': 'Comhrá',
		'sender': 'Seoltóir',
		'receiver': 'Glacadóir',
		'client': 'Cliant',
		'server': 'Freastalaí',
		'protocol_title': 'Prótacal MSNP',
		'protocol_versions': 'Leaganacha Prótacail',
		'protocol_client': 'Cliant',
		'protocol_auth': 'Fíordheimhniú',
		'key_commands': 'Príomhorduithe',
		'command': 'Ordú',
		'description': 'Tuairisc',
		'auth_methods': 'Modhanna Fíordheimhnithe',
		'ver_negotiate': 'Déan caibidlíocht ar leagan an phrótacail',
		'cvr_report': 'Tuairisc ar leagan an chliant',
		'inf_security': 'Iarr ar phacáistí slándála (MD5)',
		'usr_auth': 'Fíordheimhniú úsáideora',
		'syn_contacts': 'Sioncrónaigh liosta teagmhálacha',
		'chg_status': 'Athraigh stádas (Ar Líne, As Láthair, et al.)',
		'xfr_transfer': 'Aistriú go Switchboard',
		'cal_invite': 'Cuir cuireadh chun comhrá chuig úsáideoir',
		'msg_send': 'Seol teachtaireacht',
		'bye_left': 'D\'fhág an rannpháirtí an comhrá',
	},
	'en': {
		'site_title': 'MSN Messenger Revival',
		'welcome': 'Welcome to MSN Messenger',
		'subtitle': 'Chat service for Museum',
		'signup_link': 'Sign Up',
		'info_link': 'MSNP Protocol',
		'home_link': 'Home',
		'lang_switch': 'Gaeilge',
		'lang_switch_code': 'ga',
		'years_since': 'years since MSN Messenger was shut down',
		'messages_sent': 'messages sent',
		'users_registered': 'users registered',
		'signup_title': 'Create New Account',
		'signup_desc': 'Sign up to chat with your friends on MSN Messenger.',
		'email': 'Email',
		'password': 'Password',
		'display_name': 'Display Name',
		'create_account': 'Create Account',
		'signup_success': 'Welcome! Your account has been created.',
		'signup_success_desc': 'You can now sign in on MSN Messenger.',
		'signup_error_exists': 'This email is already registered.',
		'signup_error_invalid': 'Please enter a valid email address.',
		'signup_error_short': 'Password must be at least 3 characters.',
		'signup_error_rate': 'Please wait 15 seconds before trying again.',
		'back_home': 'Back to home page',
		'info_title': 'Protocol Information',
		'login_tab': 'Login',
		'conversation_tab': 'Chat',
		'sender': 'Sender',
		'receiver': 'Receiver',
		'client': 'Client',
		'server': 'Server',
		'protocol_title': 'MSNP Protocol',
		'protocol_versions': 'Protocol Versions',
		'protocol_client': 'Client',
		'protocol_auth': 'Auth',
		'key_commands': 'Key Commands',
		'command': 'Command',
		'description': 'Description',
		'auth_methods': 'Authentication Methods',
		'ver_negotiate': 'Negotiate protocol version',
		'cvr_report': 'Report client version',
		'inf_security': 'Request security packages (MD5)',
		'usr_auth': 'User authentication',
		'syn_contacts': 'Synchronize contact list',
		'chg_status': 'Change status (Online, Away, etc.)',
		'xfr_transfer': 'Transfer to Switchboard',
		'cal_invite': 'Invite user to chat',
		'msg_send': 'Send message',
		'bye_left': 'Participant left chat',
	},
}

_signup_log = defaultdict(deque)
SIGNUP_RATE = 1
SIGNUP_WINDOW = 15

def register(app):
	app['public_jinja_env'] = jinja2.Environment(
		loader = jinja2.FileSystemLoader(PUBLIC_TMPL_DIR),
		autoescape = jinja2.select_autoescape(default = True),
	)
	app.router.add_get('/', handle_index)
	app.router.add_get('/info', handle_info)
	app.router.add_get('/info/protocol', handle_protocol)
	app.router.add_get('/signup', handle_signup_form)
	app.router.add_post('/signup', handle_signup_submit)
	app.router.add_get('/emoticons_list', handle_emoticons)
	if os.path.isdir(STATIC_DIR):
		app.router.add_static('/static', STATIC_DIR)

def _get_lang(req):
	lang = req.cookies.get('LANG', 'ga')
	if lang not in ('ga', 'en'):
		lang = 'ga'
	return lang

def _check_lang_switch(req):
	lang_param = req.query.get('lang')
	if lang_param in ('ga', 'en'):
		return lang_param
	return None

def _render_public(req, tmpl_name, ctxt = None, status = 200):
	lang = _get_lang(req)
	t = TRANSLATIONS[lang]
	env = req.app['public_jinja_env']
	tmpl = env.get_template(tmpl_name)
	data = {'t': t, 'lang': lang, 'lang_switch_code': t['lang_switch_code'], 'lang_switch_label': t['lang_switch']}
	if ctxt:
		data.update(ctxt)
	content = tmpl.render(**data)
	return web.Response(status = status, content_type = 'text/html', text = content)

def _set_lang_cookie(resp, lang):
	resp.set_cookie('LANG', lang, max_age = 365 * 86400, httponly = False)

async def handle_index(req):
	switch = _check_lang_switch(req)
	if switch:
		resp = web.Response(status = 302, headers = {'Location': '/'})
		_set_lang_cookie(resp, switch)
		return resp
	lang = _get_lang(req)
	t = TRANSLATIONS[lang]
	from datetime import date
	shutdown_date = date(2013, 10, 24)
	today = date.today()
	years_since = today.year - shutdown_date.year - ((today.month, today.day) < (shutdown_date.month, shutdown_date.day))
	from db import Conversation
	with DBSession() as sess:
		msg_count = sess.query(Conversation).count()
		user_count = sess.query(User).count()
	return _render_public(req, 'index.html', {
		'years_since': years_since,
		'msg_count': msg_count,
		'user_count': user_count,
	})

async def handle_info(req):
	switch = _check_lang_switch(req)
	if switch:
		resp = web.Response(status = 302, headers = {'Location': '/info'})
		_set_lang_cookie(resp, switch)
		return resp
	return _render_public(req, 'info.html', {'server_ip': settings.SB_HOST})

async def handle_protocol(req):
	switch = _check_lang_switch(req)
	if switch:
		resp = web.Response(status = 302, headers = {'Location': '/info/protocol'})
		_set_lang_cookie(resp, switch)
		return resp
	return _render_public(req, 'protocol.html')

async def handle_signup_form(req):
	switch = _check_lang_switch(req)
	if switch:
		resp = web.Response(status = 302, headers = {'Location': '/signup'})
		_set_lang_cookie(resp, switch)
		return resp
	lang = _get_lang(req)
	error = req.query.get('error', '')
	error_msg = TRANSLATIONS[lang].get('signup_error_' + error, '') if error else ''
	return _render_public(req, 'signup.html', {'error_msg': error_msg})

async def handle_signup_submit(req):
	ip = req.remote or 'unknown'
	now = time.time()
	log = _signup_log[ip]
	while log and log[0] < now - SIGNUP_WINDOW:
		log.popleft()
	if len(log) >= SIGNUP_RATE:
		return web.Response(status = 302, headers = {'Location': '/signup?error=rate'})
	log.append(now)

	form = await req.post()
	email = form.get('email', '').strip()
	password = form.get('password', '')
	name = form.get('name', '').strip()

	if '@' not in email or '.' not in email.split('@')[-1]:
		return web.Response(status = 302, headers = {'Location': '/signup?error=invalid'})
	if len(password) < 3:
		return web.Response(status = 302, headers = {'Location': '/signup?error=short'})

	if not name:
		name = email.split('@')[0]
	if len(name) > 50:
		name = name[:50]

	from util.misc import gen_uuid
	with DBSession() as sess:
		existing = sess.query(User).filter(User.email == email).one_or_none()
		if existing:
			return web.Response(status = 302, headers = {'Location': '/signup?error=exists'})
		user = User(
			uuid = gen_uuid(), email = email, verified = True,
			name = name, message = '',
			settings = {}, groups = {}, contacts = {},
		)
		user.password = hash.hasher.encode(password)
		user.password_md5 = hash.hasher_md5.encode(password)
		sess.add(user)

	return _render_public(req, 'signup_success.html')

async def handle_emoticons(req):
	env = req.app['public_jinja_env']
	tmpl = env.get_template('emoticons_list.html')
	content = tmpl.render()
	return web.Response(content_type = 'text/html', text = content)