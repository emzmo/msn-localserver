import asyncio
import time
from collections import defaultdict, deque

from core.session import PersistentSession
from util.misc import Logger

from .msnp import MSNPReader, MSNPWriter

_conn_log = defaultdict(deque)
MAX_CONN_RATE = 5
CONN_RATE_WINDOW = 10

def register(loop, backend, *, http_port = None, devmode = False):
	from util.misc import AIOHTTPRunner, ProtocolRunner
	from .http import create_app
	from .msnp import MSNP_NS_SessState, MSNP_SB_SessState
	
	assert http_port, "Please specify `http_port`."
	
	if devmode:
		http_host = '0.0.0.0'
	else:
		http_host = '0.0.0.0'
	
	backend.add_runner(ProtocolRunner('0.0.0.0', 1863, ListenerMSNP, args = ['NS', backend, MSNP_NS_SessState]))
	backend.add_runner(ProtocolRunner('0.0.0.0', 1864, ListenerMSNP, args = ['SB', backend, MSNP_SB_SessState]))
	backend.add_runner(AIOHTTPRunner(http_host, http_port, create_app(backend)))
	if devmode:
		from dev import autossl
		ssl_context = autossl.create_context()
		backend.add_runner(AIOHTTPRunner(http_host, 443, create_app(backend), ssl = ssl_context))

class ListenerMSNP(asyncio.Protocol):
	def __init__(self, logger_prefix, backend, sess_state_factory):
		super().__init__()
		self.logger_prefix = logger_prefix
		self.backend = backend
		self.sess_state_factory = sess_state_factory
		self.transport = None
		self.logger = None
		self.sess = None
	
	def connection_made(self, transport):
		peername = transport.get_extra_info('peername')
		ip = peername[0] if peername else 'unknown'
		now = time.time()
		log = _conn_log[ip]
		while log and log[0] < now - CONN_RATE_WINDOW:
			log.popleft()
		if len(log) >= MAX_CONN_RATE:
			transport.close()
			return
		log.append(now)
		
		self.transport = transport
		self.logger = Logger(self.logger_prefix, transport)
		sess_state = self.sess_state_factory(MSNPReader(self.logger), self.backend)
		self.sess = PersistentSession(sess_state, MSNPWriter(self.logger, sess_state), transport)
		self.sess.time_last_active = now
		self.logger.log_connect()
	
	def connection_lost(self, exc):
		self.logger.log_disconnect()
		self.sess.close()
		self.sess = None
		self.logger = None
		self.transport = None
	
	def data_received(self, data):
		self.sess.time_last_active = time.time()
		try:
			from front.admin.console import log_command
			sess_id = self.logger.prefix if self.logger else '????'
			text = data.decode('utf-8', errors = 'replace')[:200]
			for line in text.split('\r\n'):
				if line.strip():
					log_command(sess_id, self.logger_prefix, '>>>', line.strip()[:200])
		except Exception:
			pass
		self.sess.state.data_received(data, self.sess)