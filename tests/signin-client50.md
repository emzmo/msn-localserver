# MSN Messenger 5.0 — Sign-in Protocol Capture

**Client:** MSN Messenger 5.0.0575 (`MSNMSGR 5.0.0575`)
**Account:** test@hotmail.com
**Protocol:** MSNP8, TWN auth (via SSLv3 gateway)
**Result:** SUCCESS

## Protocol Exchange (Session NS/9c58)

```
NS/9c58 con
NS/9c58 >>> VER 1 MSNP8 CVR0
NS/9c58 <<< VER 1 MSNP8
NS/9c58 >>> CVR 2 0x0409 winnt 5.1 i386 MSNMSGR 5.0.0575 MSMSGS test@hotmail.com
NS/9c58 <<< CVR 2 5.0.0575 5.0.0575 5.0.0575 https://login.passport.com https://login.passport.com
NS/9c58 >>> USR 3 TWN I test@hotmail.com
NS/9c58 <<< USR 3 TWN S ct=1,rver=1,wp=FS_40SEC_0_COMPACT,lc=1,id=1
NS/9c58 >>> USR 4 TWN S cb61681e0523f4150446
NS/9c58 <<< USR 4 OK test@hotmail.com test 1 0
NS/9c58 >>> SYN 5 4
NS/9c58 <<< SYN 5 5 1 1
NS/9c58 <<< GTC A
NS/9c58 <<< BLP AL
NS/9c58 <<< LSG 0 Other%20Contacts 0
NS/9c58 <<< LST museum@hotmail.com Museum%20Visitor 11 0
NS/9c58 >>> CHG 6 NLN 0
NS/9c58 <<< CHG 6 NLN 0
```

## Step-by-step Explanation

| Step | Command | Direction | Meaning |
|------|---------|-----------|---------|
| 1 | `VER 1 MSNP8 CVR0` | Client → Server | Client offers MSNP8 |
| 2 | `VER 1 MSNP8` | Server → Client | Server accepts MSNP8 |
| 3 | `CVR 2 ... MSNMSGR 5.0.0575 ... test@hotmail.com` | Client → Server | Client version: MSN Messenger 5.0.0575 |
| 4 | `CVR 2 5.0.0575 ...` | Server → Client | Version acknowledged, Passport URLs provided |
| 5 | `USR 3 TWN I test@hotmail.com` | Client → Server | Initial TWN auth |
| 6 | `USR 3 TWN S ct=1,...` | Server → Client | TWN challenge — client must get Passport ticket via SSL gateway |
| 7 | `USR 4 TWN S cb61681e0523f4150446` | Client → Server | Passport ticket returned (obtained via login.passport.com:443 SSLv3) |
| 8 | `USR 4 OK test@hotmail.com test 1 0` | Server → Client | **Auth success!** |
| 9 | `SYN 5 4` | Client → Server | Request contact sync (serial 4 = incremental) |
| 10 | `SYN 5 5 1 1` | Server → Client | Sync response: 5 serial, 1 contact, 1 group |
| 11 | `GTC A` | Server → Client | Prompt: Alert when added |
| 12 | `BLP AL` | Server → Client | Privacy: Allow all |
| 13 | `LSG 0 Other%20Contacts 0` | Server → Client | Group: "Other Contacts" |
| 14 | `LST museum@hotmail.com Museum%20Visitor 11 0` | Server → Client | Contact: museum@hotmail.com, display name "Museum Visitor", lists 11 (FL+AL+RL) |
| 15 | `CHG 6 NLN 0` | Client → Server | Change status to Online (NLN), capability 0 |
| 16 | `CHG 6 NLN 0` | Server → Client | Status confirmed |

## Notes

- MSN 5.0 uses the same MSNP8 + TWN auth path as Windows Messenger 4.7.
- The SYN serial here is 4 (incremental sync), whereas 4.7 used serial 0 (full sync).
  This is because 5.0 had previously synced and cached the contact list state.
- No ILN (presence notification) appears because museum@hotmail.com was offline
  at the time of this login (it had signed out with OUT before this session started).
- Earlier 5.0 attempts (sessions NS/437e, NS/8b91, NS/ec70) failed at the TWN
  challenge — the client disconnected without returning a ticket. Those were from
  a different XP installation. This fresh XP with proper SSL certificate setup
  completes the handshake successfully.