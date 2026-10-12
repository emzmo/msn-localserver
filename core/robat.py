import time
import asyncio
from datetime import datetime

from db import Session as DBSession, User, RobatReply, RobatCron
from util.misc import gen_uuid
from util import hash
from core.client import Client
from core.models import UserStatus, Substatus
from core import event

ROBAT_EMAIL = 'robat@hotmail.com'
ROBAT_NAME = 'Robat'
ROBAT_PASSWORD = 'pasfhocal'

class RobatService:
	def __init__(self, backend):
		self.backend = backend
		self.session = None
		self.user = None
		self.online = False
		self.reply_step = {}
		self._cron_task = None

	def ensure_user_exists(self):
		with DBSession() as sess:
			existing = sess.query(User).filter(User.email == ROBAT_EMAIL).one_or_none()
			if existing is None:
				user = User(
					uuid = gen_uuid(), email = ROBAT_EMAIL, verified = True,
					name = ROBAT_NAME, message = '',
					settings = {}, groups = {}, contacts = {},
				)
				user.password = hash.hasher.encode(ROBAT_PASSWORD)
				user.password_md5 = hash.hasher_md5.encode(ROBAT_PASSWORD)
				sess.add(user)

	def login(self):
		if self.online:
			return
		from core.session import RobatSession
		from core.session import SessionState
		with DBSession() as sess:
			user = sess.query(User).filter(User.email == ROBAT_EMAIL).one_or_none()
			if user is None:
				return
			uuid = user.uuid
			name = user.name
		self.user = self.backend._user_service.get(uuid)
		if self.user is None:
			return
		self.user.status = UserStatus(name, '')
		self.user.status.substatus = Substatus.NLN
		self.user.detail = self.backend._user_service.get_detail(uuid)
		self.backend._user_by_uuid[uuid] = self.user
		state = SessionState()
		state.dialect = 8
		state.front_specific = {'msn_capabilities': 0}
		self.session = RobatSession(state, self)
		self.session.user = self.user
		self.session.client = Client('msn', 'robat', 'server')
		self.session.time_last_active = time.time()
		self.backend._sc.add_session(self.session)
		self.online = True
		self._notify_contacts_online()
		if self._cron_task is None:
			self._cron_task = self.backend._loop.create_task(self._cron_loop())

	def logout(self):
		if not self.online:
			return
		self.backend._sc.remove_session(self.session)
		self.backend.on_leave(self.session)
		self.session = None
		self.online = False
		if self._cron_task:
			self._cron_task.cancel()
			self._cron_task = None

	def reload(self):
		self.logout()
		self.login()

	def _notify_contacts_online(self):
		from front.msn.misc import build_msnp_presence_notif
		for sess in self.backend._sc.iter_sessions():
			if sess.user is None or sess == self.session:
				continue
			if sess.user.detail is None:
				continue
			ctc = sess.user.detail.contacts.get(self.user.uuid)
			if ctc is None:
				continue
			ctc.status.substatus = Substatus.NLN
			ctc.status.name = self.user.status.name
			try:
				for m in build_msnp_presence_notif(None, ctc, getattr(sess.state, 'dialect', 8) or 8, self.backend):
					sess.send_reply(*m)
			except Exception:
				pass

	def send_chat(self, user_email, message_text):
		return self.backend.robat_send_chat(user_email, message_text)

	def send_manual_msg(self, to_email, text):
		if not self.online:
			return False
		return self.backend.robat_send_chat(to_email, text)

	def broadcast(self, text):
		if not self.online:
			return 0
		count = 0
		for s in self.backend._sc.iter_sessions():
			if s.user is None or s.user.email == ROBAT_EMAIL:
				continue
			try:
				self.backend.robat_send_chat(s.user.email, text)
				count += 1
			except Exception:
				pass
		return count

	def on_chat_message(self, sender_email, message_text, chat):
		is_gaeilge = False
		try:
			sender_uuid = self.backend._user_service.get_uuid(sender_email)
			sender_user = self.backend._user_by_uuid.get(sender_uuid)
			if sender_user and sender_user.settings:
				is_gaeilge = sender_user.settings.get('gaeilge', False)
		except Exception:
			pass
		step = self.reply_step.get(sender_email, 0)
		with DBSession() as sess:
			replies = sess.query(RobatReply).order_by(RobatReply.step_order).all()
		if not replies:
			return
		if step >= len(replies):
			step = 0
		reply = replies[step]
		self.reply_step[sender_email] = step + 1
		text = reply.reply_ga if is_gaeilge else reply.reply_en
		msg_payload = (
			'MIME-Version: 1.0\r\n'
			'Content-Type: text/plain; charset=UTF-8\r\n'
			'\r\n'
			'{}\r\n'
		).format(text).encode('utf-8')
		from core import event as evt
		for sess in list(chat._users_by_sess.keys()):
			if sess.user is None or sess.user.email == ROBAT_EMAIL:
				continue
			if sess.user.email == sender_email:
				try:
					sess.send_event(evt.ChatMessage(self.user, msg_payload))
				except Exception:
					pass

	async def _cron_loop(self):
		while self.online:
			await asyncio.sleep(30)
			try:
				self._check_cron()
			except Exception:
				pass

	def _check_cron(self):
		if not self.online:
			return
		now = datetime.now()
		with DBSession() as sess:
			crons = sess.query(RobatCron).filter(RobatCron.enabled == True).all()
		for c in crons:
			if c.interval_min > 0:
				key = 'cron_%d' % c.id
				last = self.reply_step.get(key, 0)
				if time.time() - last >= c.interval_min * 60:
					self.reply_step[key] = time.time()
					self._broadcast_cron(c)
			elif c.at_time:
				key = 'cron_time_%d' % c.id
				try:
					hh, mm = c.at_time.split(':')
					target_hh, target_mm = int(hh), int(mm)
				except Exception:
					continue
				last_key = self.reply_step.get(key, '')
				today_key = now.strftime('%Y-%m-%d_%H:%M')
				if now.hour == target_hh and now.minute == target_mm:
					if last_key != today_key:
						self.reply_step[key] = today_key
						self._broadcast_cron(c)

	def _broadcast_cron(self, cron):
		for s in self.backend._sc.iter_sessions():
			if s.user is None or s.user.email == ROBAT_EMAIL:
				continue
			is_gaeilge = False
			try:
				if s.user.settings:
					is_gaeilge = s.user.settings.get('gaeilge', False)
			except Exception:
				pass
			text = cron.msg_ga if is_gaeilge else cron.msg_en
			try:
				self.backend.robat_send_chat(s.user.email, text)
			except Exception:
				pass

	def get_replies(self):
		with DBSession() as sess:
			replies = sess.query(RobatReply).order_by(RobatReply.step_order).all()
			return [{'id': r.id, 'step': r.step_order, 'en': r.reply_en, 'ga': r.reply_ga} for r in replies]

	def add_reply(self, en, ga):
		with DBSession() as sess:
			count = sess.query(RobatReply).count()
			sess.add(RobatReply(step_order = count, reply_en = en, reply_ga = ga))

	def delete_reply(self, reply_id):
		with DBSession() as sess:
			r = sess.query(RobatReply).filter(RobatReply.id == reply_id).one_or_none()
			if r:
				sess.delete(r)

	def get_crons(self):
		with DBSession() as sess:
			crons = sess.query(RobatCron).order_by(RobatCron.id).all()
			return [{'id': c.id, 'en': c.msg_en, 'ga': c.msg_ga, 'interval': c.interval_min, 'at_time': c.at_time, 'enabled': c.enabled} for c in crons]

	def add_cron(self, en, ga, interval_min, at_time = None):
		with DBSession() as sess:
			sess.add(RobatCron(msg_en = en, msg_ga = ga, interval_min = interval_min, at_time = at_time, enabled = True))

	def delete_cron(self, cron_id):
		with DBSession() as sess:
			c = sess.query(RobatCron).filter(RobatCron.id == cron_id).one_or_none()
			if c:
				sess.delete(c)

	def toggle_cron(self, cron_id, enabled):
		with DBSession() as sess:
			c = sess.query(RobatCron).filter(RobatCron.id == cron_id).one_or_none()
			if c:
				c.enabled = enabled
				sess.add(c)