# MSN Messenger 6.2 — Sign-in Protocol Capture

**Client:** MSN Messenger 6.2.0208 (`MSNMSGR 6.2.0208`)
**Account:** test@hotmail.com
**Protocol:** MSNP10, TWN auth (via SSLv3 gateway)
**Result:** SUCCESS

## Protocol Exchange (Session NS/db09)

```
NS/db09 con
NS/db09 >>> VER 1 MSNP10 MSNP9 CVR0
NS/db09 <<< VER 1 MSNP10
NS/db09 >>> CVR 2 0x0409 winnt 5.1 i386 MSNMSGR 6.2.0208 MSMSGS test@hotmail.com
NS/db09 <<< CVR 2 6.2.0208 6.2.0208 6.2.0208 https://login.passport.com https://login.passport.com
NS/db09 >>> USR 3 TWN I test@hotmail.com
NS/db09 <<< USR 3 TWN S ct=1,rver=1,wp=FS_40SEC_0_COMPACT,lc=1,id=1
NS/db09 >>> USR 4 TWN S d739184729913a36fc94
NS/db09 <<< USR 4 OK test@hotmail.com 1 0
NS/db09 >>> SYN 5 0 0
NS/db09 <<< SYN 5 2000-01-01T00:00:00.0-00:00 2000-01-01T00:00:00.0-00:00 1 0
NS/db09 <<< GTC A
NS/db09 <<< BLP AL
NS/db09 <<< PRP MFN test
NS/db09 <<< LST N=museum@hotmail.com F=Museum%20Visitor C=e79cf039-2f84-429a-af99-b2341d0e570a 11
NS/db09 >>> CHG 6 NLN 805306404
NS/db09 <<< CHG 6 NLN 805306404
NS/db09 >>> CHG 7 NLN 805306404 <truncated>
NS/db09 <<< CHG 7 NLN 805306404 <truncated>
NS/db09 >>> OUT
NS/db09 <<< OUT
NS/db09 dis
```

## Step-by-step Explanation

| Step | Command | Direction | Meaning |
|------|---------|-----------|---------|
| 1 | `VER 1 MSNP10 MSNP9 CVR0` | Client → Server | Client offers MSNP10 (fallback MSNP9) |
| 2 | `VER 1 MSNP10` | Server → Client | Server accepts MSNP10 |
| 3 | `CVR 2 ... MSNMSGR 6.2.0208 ... test@hotmail.com` | Client → Server | Client version: MSN Messenger 6.2.0208 |
| 4 | `CVR 2 6.2.0208 ...` | Server → Client | Version acknowledged, Passport URLs |
| 5 | `USR 3 TWN I test@hotmail.com` | Client → Server | Initial TWN auth |
| 6 | `USR 3 TWN S ct=1,...` | Server → Client | TWN challenge — get Passport ticket via SSL gateway |
| 7 | `USR 4 TWN S d739184729913a36fc94` | Client → Server | Passport ticket returned |
| 8 | `USR 4 OK test@hotmail.com 1 0` | Server → Client | **Auth success!** (Note: no "test" verified-name field — MSNP10 format differs from MSNP8) |
| 9 | `SYN 5 0 0` | Client → Server | Request full contact sync (serial 0 0) |
| 10 | `SYN 5 2000-01-01... 1 0` | Server → Client | Sync response with timestamp, 1 contact, 0 groups |
| 11 | `GTC A` | Server → Client | Prompt: Alert when added |
| 12 | `BLP AL` | Server → Client | Privacy: Allow all |
| 13 | `PRP MFN test` | Server → Client | My friendly name: "test" |
| 14 | `LST N=museum@hotmail.com F=Museum%20Visitor C=e79cf039... 11` | Server → Client | Contact with UUID (C= field), lists 11 (FL+AL+RL) |
| 15 | `CHG 6 NLN 805306404` | Client → Server | Change status to Online, capability 805306404 (MSNC1 + ink + winks + search) |
| 16 | `CHG 6 NLN 805306404` | Server → Client | Status confirmed |
| 17 | `CHG 7 NLN 805306404 <truncated>` | Client → Server | Status reconfirm (likely with MSNObject payload for display picture) |
| 18 | `CHG 7 NLN 805306404 <truncated>` | Server → Client | Confirmed |
| 19 | `OUT` | Client → Server | Sign out |
| 20 | `OUT` | Server → Client | Sign out acknowledged |

## Notes

- MSN 6.2 uses MSNP10 (higher than 4.7/5.0 which use MSNP8).
- The LST format differs: MSNP10 uses `N=email F=name C=uuid` key-value format,
  while MSNP8 uses positional `email name lists group` format.
- PRP (personal properties) appears here — MSNP10 sends MFN (My Friendly Name)
  during sync, which MSNP8 doesn't.
- Capability flags 805306404 = 0x30000044 — includes MSNC1, ink, winks support.
- The `<truncated>` on CHG 7 indicates a payload (likely an MSNObject for
  display picture or personal message) that the logger truncated for readability.
- Full clean sign-out: `OUT` sent and acknowledged, then `dis` (disconnected).

## Differences from 4.7/5.0

| Feature | MSN 4.7/5.0 (MSNP8) | MSN 6.2 (MSNP10) |
|---------|---------------------|-------------------|
| Protocol | MSNP8 | MSNP10 |
| LST format | Positional: `email name lists group` | Key-value: `N=email F=name C=uuid lists` |
| PRP during sync | No | Yes (MFN = friendly name) |
| SYN serial | Single number | Two numbers (serial + timestamp) |
| Capability flags | 32 (0x20) or 0 | 805306404 (0x30000044) |
| CHG payload | None | Truncated (MSNObject for display picture) |