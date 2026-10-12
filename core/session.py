import time
from . import event

class Session:
	def __init__(self, state):
		self.closed = False
		self.user = None
		self.client = None
		self.state = state
	
	def send_event(self, outgoing_event):
		raise NotImplementedError('Session.send_event')
	
	def send_reply(self, *data):
		self.send_event(event.ReplyEvent(data))
	
	def close(self):
		if self.closed: return
		try:
			self.state.on_connection_lost(self)
		finally:
			self.closed = True

class PersistentSession(Session):
	def __init__(self, state, writer, transport):
		super().__init__(state)
		self.writer = writer
		self.transport = transport
	
	def send_event(self, outgoing_event):
		self.writer.write(outgoing_event)
		self.transport.write(self.writer.flush())
	
	def get_peername(self):
		return self.transport.get_extra_info('peername')
	
	def close(self):
		self.transport.close()
		super().close()

class PollingSession(Session):
	def __init__(self, state, logger, writer, hostname):
		super().__init__(state)
		self.logger = logger
		self.writer = writer
		self.hostname = hostname
		self.peername = None
		self.queue = [] # type: List[OutgoingEvent]
		self.time_last_connect = 0
		self.timeout = 30
	
	def send_event(self, outgoing_event):
		self.queue.append(outgoing_event)
	
	def get_peername(self):
		return self.peername
	
	def on_connect(self, transport):
		self.time_last_connect = time.time()
		self.peername = transport.get_extra_info('peername')
		self.logger.log_connect()
	
	def on_disconnect(self):
		writer = self.writer
		for outgoing_event in self.queue:
			writer.write(outgoing_event)
		self.queue = []
		data = writer.flush()
		self.logger.log_disconnect()
		return data

class SessionState:
	def __init__(self):
		self.front_specific = {}
	
	def on_connection_lost(self, sess: Session) -> None:
		raise NotImplementedError('SessionState.on_connection_lost')

class DirectSession(Session):
	def __init__(self):
		super().__init__(None)
	
	def send_event(self, outgoing_event):
		pass
	
	def close(self):
		self.closed = True

class RobatSession(Session):
	def __init__(self, state, robat_service):
		super().__init__(state)
		self.robat_service = robat_service
		self._chat = None
	
	def send_event(self, outgoing_event):
		if isinstance(outgoing_event, event.ChatMessage):
			sender = outgoing_event.user_sender
			data = outgoing_event.data
			if isinstance(data, bytes):
				data = data.decode('utf-8', errors = 'replace')
			sep = '\r\n\r\n'
			idx = data.find(sep)
			if idx >= 0:
				data = data[idx + len(sep):]
			body = data.strip()
			if body and self._chat:
				self.robat_service.on_chat_message(sender.email, body, self._chat)
		elif isinstance(outgoing_event, event.InvitedToChatEvent):
			pass
	
	def get_peername(self):
		return ('server', 0)
	
	def close(self):
		self.closed = True
