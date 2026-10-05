import os
import time
from collections import defaultdict, deque

from aiohttp import web
import jinja2

import settings
from db import Session as DBSession, User
from util import hash

PUBLIC_TMPL_DIR = 'front/public/tmpl'

TRANSLATIONS = {
	'ga': {
		'site_title': 'MSN Messenger',
		'welcome': 'Fáilte go MSN Messenger',
		'subtitle': 'Seirbhís chomhrá do Mhúsaem',
		'signup_link': 'Cláraigh',
		'info_link': 'Eolas',
		'protocol_link': 'Prótacal',
		'admin_link': 'Riarachán',
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
		'protocol_title': 'Prótacal MSNP',
		'info_title': 'Eolas an Phrótacail',
		'login_tab': 'Logáil Isteach',
		'conversation_tab': 'Comhrá',
		'sender': 'Seoltóir',
		'receiver': 'Faighteoir',
		'step1_title': 'Céim 1: suiteáil an Teastas CA',
		'step2_title': 'Céim 2: cuir isteach an chomhad hosts',
		'step3_title': 'Céim 3: glan an taisce chlár',
		'step4_title': 'Céim 4: suiteáil MSN Messenger',
		'step5_title': 'Céim 5: Sínigh Isteach',
		'note_75': 'Nóta: MSN 7.5 d\'fhéadfadh earráid a thaispeáint. Windows Messenger 4.7 atá molta.',
	},
	'en': {
		'site_title': 'MSN Messenger',
		'welcome': 'Welcome to MSN Messenger',
		'subtitle': 'Chat service for Museum',
		'signup_link': 'Sign Up',
		'info_link': 'Info',
		'protocol_link': 'Protocol',
		'admin_link': 'Admin',
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
		'protocol_title': 'MSNP Protocol',
		'info_title': 'Protocol Information',
		'login_tab': 'Login',
		'conversation_tab': 'Conversation',
		'sender': 'Sender',
		'receiver': 'Receiver',
		'step1_title': 'Step 1: Install the CA Certificate',
		'step2_title': 'Step 2: Edit the Hosts File',
		'step3_title': 'Step 3: Clear Registry Cache',
		'step4_title': 'Step 4: Install MSN Messenger',
		'step5_title': 'Step 5: Sign In',
		'note_75': 'Note: MSN 7.5 may show an error. Windows Messenger 4.7 is recommended.',
	},
}

_signup_log = defaultdict(deque)
SIGNUP_RATE = 1
SIGNUP_WINDOW = 15

SAFE_NAMES = [
	'Visitor', 'Aoife', 'Séamus', 'Cillian', 'Niamh', 'Liam', 'Saoirse',
	'Conor', 'Éabha', 'Tadhg', 'Maeve', 'Fionn', 'Róisín', 'Declan',
	'Ciara', 'Patrick', 'Bridget', 'Sean', 'Grace', 'Owen',
	'Cáit', 'Pádraig', 'Sinéad', 'Darragh', 'Aoibhinn', 'Eoin',
	'Clodagh', 'Niall', 'Meabh', 'Ruairi', 'Aisling', 'Cian',
]

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

	lang = _get_lang(req)

	if '@' not in email or '.' not in email.split('@')[-1]:
		return web.Response(status = 302, headers = {'Location': '/signup?error=invalid'})
	if len(password) < 3:
		return web.Response(status = 302, headers = {'Location': '/signup?error=short'})

	if not name or name not in SAFE_NAMES:
		import random
		name = random.choice(SAFE_NAMES)

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