DB = 'sqlite:///msn.sqlite'
STATS_DB = 'sqlite:///stats.sqlite'
LOGIN_HOST = 'login.passport.com'
STORAGE_HOST = LOGIN_HOST
SB_HOST = LOGIN_HOST
SB_PORT = 1864
WEBMAIL_URL = 'http://172.16.0.20:8082/webmail/'
ADMIN_PASSWORD = 'changeme'
SESSION_TIMEOUT = 900
DEBUG = False
DEBUG_MSNP = False
DEBUG_HTTP_REQUEST = False
DEBUG_HTTP_REQUEST_FULL = False

ENABLE_FRONT_MSN = True
ENABLE_FRONT_YMSG = False
ENABLE_FRONT_BOT = False

try:
	from settings_local import *
except ImportError as ex:
	raise Exception("Please create settings_local.py") from ex
