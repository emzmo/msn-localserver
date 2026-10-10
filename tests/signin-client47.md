# Windows Messenger 4.7 — Sign-in Protocol Capture

**Client:** Windows Messenger 4.7.3001 (`MSMSGS 4.7.3001 WindowsMessenger`)
**Account:** test@hotmail.com
**Protocol:** MSNP8, TWN auth (via SSLv3 gateway)
**Result:** SUCCESS

## Protocol Exchange (Session NS/6442 — the latest clean login)

```
NS/6442 con
NS/6442 >>> VER 1 MSNP8 CVR0
NS/6442 <<< VER 1 MSNP8
NS/6442 >>> CVR 2 0x0409 winnt 5.1 i386 MSMSGS 4.7.3001 WindowsMessenger test@hotmail.com
NS/6442 <<< CVR 2 4.7.3001 4.7.3001 4.7.3001 https://login.passport.com https://login.passport.com
NS/6442 >>> USR 3 TWN I test@hotmail.com
NS/6442 <<< USR 3 TWN S ct=1,rver=1,wp=FS_40SEC_0_COMPACT,lc=1,id=1
NS/6442 >>> USR 4 TWN S 64f67d1e73a0593112a3
NS/6442 <<< USR 4 OK test@hotmail.com test 1 0
NS/6442 >>> SYN 5 0
NS/6442 <<< SYN 5 1 1 1
NS/6442 <<< GTC A
NS/6442 <<< BLP AL
NS/6442 <<< LSG 0 Other%20Contacts 0
NS/6442 <<< LST museum@hotmail.com Museum%20Visitor 11 0
NS/6442 >>> CHG 6 NLN 32
NS/6442 <<< CHG 6 NLN 32
NS/6442 >>> CHG 7 NLN 32
NS/6442 <<< CHG 7 NLN 32
```

## Step-by-step Explanation

| Step | Command | Direction | Meaning |
|------|---------|-----------|---------|
| 1 | `VER 1 MSNP8 CVR0` | Client → Server | Client offers MSNP8 protocol version |
| 2 | `VER 1 MSNP8` | Server → Client | Server accepts MSNP8 |
| 3 | `CVR 2 0x0409 winnt 5.1 i386 MSMSGS 4.7.3001 WindowsMessenger test@hotmail.com` | Client → Server | Client version info: Windows Messenger 4.7.3001, locale 0x0409, OS winnt 5.1 (XP), account test@hotmail.com |
| 4 | `CVR 2 4.7.3001 ...` | Server → Client | Server acknowledges version, provides Passport URLs |
| 5 | `USR 3 TWN I test@hotmail.com` | Client → Server | Initial TWN (Passport) auth — "I want to sign in as test@hotmail.com" |
| 6 | `USR 3 TWN S ct=1,rver=1,...` | Server → Client | TWN challenge — client must now obtain a Passport ticket from the SSL gateway (login.passport.com:443 → Pi:443 SSLv3) |
| 7 | `USR 4 TWN S 64f67d1e73a0593112a3` | Client → Server | Client returns the Passport ticket obtained via TLS |
| 8 | `USR 4 OK test@hotmail.com test 1 0` | Server → Client | **Auth success!** Server confirms identity. "test" = verified status, 1 = verified flag, 0 = unused |
| 9 | `SYN 5 0` | Client → Server | Request contact list sync (serial 0 = full sync) |
| 10 | `SYN 5 1 1 1` | Server → Client | Sync response: 1 contact, 1 group, 1 property |
| 11 | `GTC A` | Server → Client | Prompt behavior: Alert when added |
| 12 | `BLP AL` | Server → Client | Privacy: Allow all |
| 13 | `LSG 0 Other%20Contacts 0` | Server → Client | Group: "Other Contacts" (group 0) |
| 14 | `LST museum@hotmail.com Museum%20Visitor 11 0` | Server → Client | Contact: museum@hotmail.com, display name "Museum Visitor", lists 11 (FL+AL+RL), group 0 |
| 15 | `CHG 6 NLN 32` | Client → Server | Change status to Online (NLN), capability flags 32 |
| 16 | `CHG 6 NLN 32` | Server → Client | Status change confirmed |
| 17 | `CHG 7 NLN 32` | Client → Server | Client reconfirms Online status |
| 18 | `CHG 7 NLN 32` | Server → Client | Confirmed again |

## First successful login (Session NS/fafd) — included ILN (presence notification)

The first 4.7 login (NS/fafd) was identical, but also shows an `ILN` (Initial Presence Notification):

```
NS/fafd <<< ILN 6 NLN museum@hotmail.com Museum%20Visitor 805306404
```

This means museum@hotmail.com was already online when test@hotmail.com signed in,
so the server immediately notified test that museum was Online (NLN) with
capability flags 805306404.

## Notes

- Windows Messenger 4.7 uses MSNP8 with TWN auth (not MD5 as sometimes assumed).
  The SSLv3 gateway handles the TLS handshake for the Passport ticket.
- The earlier failed attempts in the log were from MSN Messenger 5.0.0575
  (session NS/437e, NS/8b91) which disconnected after receiving the TWN challenge.
  Those were from a different XP installation, not the fresh one.
- The `OUT` command in session NS/6e5b shows the previous MSN 6.2 session
  (museum@hotmail.com) signing out cleanly, followed by `FLN museum@hotmail.com`
  being sent to the still-connected test@hotmail.com session.