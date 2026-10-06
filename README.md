# MSN Messenger Museum Server (Raspberry Pi 2 / MSNP 1-12)

A fork of [v1ckxy/MSN](https://github.com/v1ckxy/MSN) optimized for offline museum deployments on a Raspberry Pi 2 (32-bit ARM). Allows Windows XP clients to connect over a LAN and chat using MSN Messenger / Windows Messenger — just like the early 2000s.

## Features

- **Fully offline** — no internet or DNS required. All hostnames resolve to the Pi via XP hosts files.
- **Web Admin UI** — user management (create, edit, delete, reset, bulk-create, wipe & recreate), online status, conversation history with thread grouping and delete, server status dashboard, client setup guide with downloadable installers and CA certificate.
- **Public website** — bilingual (Irish/English) MSN 2003-style landing page, public self-signup with safe display name dictionary, animated MSNP protocol diagram (simulated login + Aoife & Séamus conversation), protocol info page.
- **SQLite conversation persistence** — all switchboard messages logged with sender, recipient, timestamp, and body. Thread view with per-conversation delete.
- **Rate limiting & session timeouts** — connection flood protection (5/10s per IP), message flood protection (10/5s per session), 4096-byte message cap, 15-minute idle timeout, signup rate limit (1/15s per IP). Designed for unattended kiosk use.
- **SSLv3/TLS 1.0 gateway** — a C-based reverse proxy using OpenSSL 1.0.2, enabling Passport/TWN authentication for MSNP 8+ clients on Windows XP.
- **Auto-restart** — both services (Python server + C gateway) use systemd `Restart=always`.
- **Local Hotmail** — a retro webmail interface at `http://<pi-ip>:8082/webmail/` where visitors can log in with their MSN account, read and compose emails to other museum visitors. Unread counts appear in MSN Messenger on login (MSNP 8+ clients).

## Architecture

```
XP Clients (stock, unpatched)                 Raspberry Pi 2
                               ┌──────────────────────────────────┐
  messenger.hotmail.com:1863 ──┤  Port 1863  NS (plaintext TCP)   ├─ Python
  (plain TCP MSNP)             │  Port 1864  SB (plaintext TCP)   │  asyncio
                               │  Port 8081  HTTP (Passport/SOAP) │  server
  nexus.passport.com:443 ──────┤  Port 443  SSLv3/TLS1.0 gateway  ├──┐
  login.passport.com:443  ─────┤  (OpenSSL 1.0.2u, C proxy)       │  │
                               │  Port 8082  Admin web UI         │  │
                               └──────────────────────────────────┘  │
                                                                     ↓
                                                           127.0.0.1:8081
```

| Component | Port | Technology | Purpose |
|---|---|---|---|
| Notification Server (NS) | 1863 | Python asyncio | MSNP protocol — presence, contact list, auth |
| Switchboard (SB) | 1864 | Python asyncio | Chat sessions (1:1 and group) |
| HTTP API | 8081 | Python aiohttp | Passport login, SOAP endpoints, MsgrConfig |
| Admin & Public UI | 8082 | Python aiohttp | Staff admin interface + bilingual public pages (landing, signup, info) + Local Hotmail webmail |
| SSLv3 Gateway | 443 | C + OpenSSL 1.0.2u | TLS termination → proxy to 8081 |

## Client Compatibility

| Client | MSNP | Auth | Status |
|---|---|---|---|
| Windows Messenger 4.7 | 8 | TWN (via SSLv3 gateway) | ✅ Fully working |
| MSN Messenger 5.0 | 8 | TWN (via SSLv3 gateway) | ✅ Fully working |
| MSN Messenger 6.2 | 9 | TWN (via SSLv3 gateway) | ✅ Expected to work |
| MSN Messenger 7.0 | 11 | TWN (via SSLv3 gateway) | ✅ Expected to work |
| MSN Messenger 7.5 | 12 | TWN (via SSLv3 gateway) | ⚠️ Fails — WinHTTP closes after TLS handshake (error 80048820) |
| MSN 1.0–4.7 (MD5) | 2–7 | MD5 (plaintext) | ✅ Expected to work |

**Recommended for museum use:** Windows Messenger 4.7 (built into Windows XP) or MSN Messenger 5.0.

## Installation

### Prerequisites
- Raspberry Pi 2 (or any ARMv7 Linux machine)
- Python 3.6+ (3.13 tested)
- GCC (for building the SSLv3 gateway)
- Network access to the Pi from XP clients on the same LAN

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_REPO/msn-museum.git
cd msn-museum
```

### 2. Create a virtual environment and install dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Create `settings_local.py`
Copy the variables from `settings.py` and override with your values:
```python
LOGIN_HOST = 'login.passport.com'   # Hostname for Passport/CVR responses
STORAGE_HOST = 'login.passport.com'
SB_HOST = '192.168.x.x'             # Your Pi's LAN IP
SB_PORT = 1864
WEBMAIL_URL = 'http://192.168.x.x:8082/webmail/'  # Local Hotmail base URL
ADMIN_PASSWORD = 'your-password'    # Change this!
SESSION_TIMEOUT = 900               # 15 minutes
DEBUG = False
DEBUG_MSNP = False
DEBUG_HTTP_REQUEST = False
```

### 4. Initialize the database
```bash
PYTHONPATH=. python cmd/dbcreate.py
```

### 5. Create a test user
```bash
PYTHONPATH=. python cmd/user.py test@hotmail.com testpass --old
```

### 6. Start the server
```bash
PYTHONPATH=. python run_all.py
```

### 7. (Optional) Set up the SSLv3 gateway
For MSNP 8+ clients (Windows Messenger 4.7, MSN 5.0), you need the SSLv3/TLS 1.0 gateway:

1. Build OpenSSL 1.0.2u from source (see `dev/openssl-1.0.2` instructions)
2. Build the gateway: `gcc -O2 -o msn-ssl3-gateway msn-ssl3-gateway.c -I/opt/openssl-1.0.2/include -L/opt/openssl-1.0.2/lib -lssl -lcrypto -lpthread`
3. Generate a CA cert and server cert with SANs for all MSN hostnames
4. Run: `./msn-ssl3-gateway cert.pem key.pem` (binds port 443, proxies to 127.0.0.1:8081)

### 8. (Optional) Set up as systemd services
See `etc/msn-server.service` for a template. Create two services:
- `msn-museum.service` — runs `run_all.py`
- `msn-gateway-ssl3.service` — runs the C gateway

### 9. Configure XP clients
Add the Pi's IP to each XP client's `C:\WINDOWS\system32\drivers\etc\hosts`:
```
PI_IP  messenger.hotmail.com
PI_IP  nexus.passport.com
PI_IP  login.passport.com
PI_IP  contacts.msn.com
PI_IP  storage.msn.com
... (full list in the admin Setup page)
```

Install the CA certificate on each XP client (Trusted Root Certification Authorities).

## Admin Interface

Access at `http://PI_IP:8082/admin` with the password from `settings_local.py`.

Features:
- **Dashboard** — user count, online count, active chats
- **Users** — create, delete, reset passwords, bulk-create visitor accounts
- **Online** — list of currently connected users with IP addresses
- **Conversations** — paginated message history with email filter
- **Setup** — step-by-step XP client setup guide with downloadable installers and CA cert

## Local Hotmail

The server includes a retro Hotmail-style webmail interface, accessible at `http://<pi-ip>:8082/webmail/`.

- **Login** — visitors sign in with the same email address and password they use for MSN Messenger.
- **Inbox** — shows all emails received, with unread messages in bold.
- **Compose** — send an email to another museum visitor (recipient must be a registered MSN user).
- **MSN integration** — when a user logs into MSN Messenger, the server sends the unread mail count so the client's inbox icon lights up (MSNP 8+ / MSN 6.0+ clients).
- **Configuration** — set `WEBMAIL_URL` in `settings_local.py` to the base URL of the webmail (e.g. `http://172.16.0.20:8082/webmail/`). This URL is embedded in the MSNP `MSG Hotmail` payload so the MSN client's "Inbox" and "Send email" links open the webmail.
- **Database** — the `t_mail` table is created automatically on server startup via `db.Base.metadata.create_all()`. No manual migration is required.

## Staff Guide

See `STAFF_GUIDE.md` for a non-technical guide written for museum staff.

## Credits

- **Original MSN server implementation:** [v1ckxy](https://github.com/v1ckxy/MSN) — the MSNP protocol engine, backend, and SOAP services are their work.
- **Museum fork modifications:** Offline-ization, admin UI, conversation logging, rate limiting, SSLv3 gateway, session timeouts, HLL crash fix, SB message drop fix.

## License

See `LICENSE` (Creative Commons BY-NC-SA 4.0, inherited from the original repo).