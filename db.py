import json
from contextlib import contextmanager
from datetime import datetime, timedelta
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from util import hash
from util.json_type import JSONType
import settings

class Base(declarative_base()):
	__abstract__ = True

TYPE_ESCARGOT = 1
TYPE_LIVE = 2

class User(Base):
	__tablename__ = 't_user'
	
	id = sa.Column(sa.Integer, nullable = False, primary_key = True)
	type = sa.Column(sa.Integer, nullable = False, default = TYPE_ESCARGOT)
	date_created = sa.Column(sa.DateTime, nullable = True, default = datetime.utcnow)
	date_login = sa.Column(sa.DateTime, nullable = True)
	uuid = sa.Column(sa.String, nullable = False, unique = True)
	email = sa.Column(sa.String, nullable = False, unique = True)
	verified = sa.Column(sa.Boolean, nullable = False)
	name = sa.Column(sa.String, nullable = False)
	message = sa.Column(sa.String, nullable = False)
	password = sa.Column(sa.String, nullable = False)
	password_md5 = sa.Column(sa.String, nullable = False)
	settings = sa.Column(JSONType, nullable = False)
	groups = sa.Column(JSONType, nullable = False)
	contacts = sa.Column(JSONType, nullable = False)

class Sound(Base):
	__tablename__ = 't_sound'
	
	hash = sa.Column(sa.String, nullable = False, primary_key = True)
	title = sa.Column(sa.String, nullable = False)
	category = sa.Column(sa.Integer, nullable = False)
	language = sa.Column(sa.Integer, nullable = False)
	is_public = sa.Column(sa.Boolean, nullable = False)

class Conversation(Base):
	__tablename__ = 't_conversation'
	
	id = sa.Column(sa.Integer, primary_key = True)
	chat_id = sa.Column(sa.String, nullable = False)
	sender_email = sa.Column(sa.String, nullable = False)
	recipient_email = sa.Column(sa.String, nullable = False)
	body = sa.Column(sa.Text, nullable = False)
	timestamp = sa.Column(sa.DateTime, default = datetime.utcnow)

class MailMessage(Base):
	__tablename__ = 't_mail'
	
	id = sa.Column(sa.Integer, primary_key = True)
	sender_email = sa.Column(sa.String, nullable = False)
	recipient_email = sa.Column(sa.String, nullable = False)
	subject = sa.Column(sa.String, nullable = False)
	body = sa.Column(sa.Text, nullable = False)
	timestamp = sa.Column(sa.DateTime, default = datetime.utcnow)
	is_read = sa.Column(sa.Boolean, default = False)

class RobatReply(Base):
	__tablename__ = 't_robat_reply'
	
	id = sa.Column(sa.Integer, primary_key = True)
	step_order = sa.Column(sa.Integer, nullable = False)
	reply_en = sa.Column(sa.Text, nullable = False)
	reply_ga = sa.Column(sa.Text, nullable = False)

class RobatCron(Base):
	__tablename__ = 't_robat_cron'
	
	id = sa.Column(sa.Integer, primary_key = True)
	msg_en = sa.Column(sa.Text, nullable = False)
	msg_ga = sa.Column(sa.Text, nullable = False)
	interval_min = sa.Column(sa.Integer, nullable = False, default = 0)
	at_time = sa.Column(sa.String, nullable = True)
	enabled = sa.Column(sa.Boolean, default = True)


engine = sa.create_engine(settings.DB)
session_factory = sessionmaker(bind = engine)

@contextmanager
def Session():
	if Session._depth > 0:
		yield Session._global
		return
	session = session_factory()
	Session._global = session
	Session._depth += 1
	try:
		yield session
		session.commit()
	except:
		session.rollback()
		raise
	finally:
		session.close()
		Session._global = None
		Session._depth -= 1
Session._global = None
Session._depth = 0
