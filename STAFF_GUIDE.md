# MSN Museum — Staff Guide

## What This Is

This is a recreation of the classic MSN Messenger chat service, running on a small computer (Raspberry Pi) in the museum. Visitors sit at the Windows XP computers and use MSN Messenger to chat with each other, just like people did in the early 2000s.

## Visitor Setup

1. Visitors sit at any XP computer and open **Windows Messenger** (Start menu → Windows Messenger, or the MSN Messenger icon on the desktop).
2. They sign in with an email address and password you give them. A set of visitor accounts may already be created (e.g. visitor1@hotmail.com, visitor2@hotmail.com, etc.).
3. To start chatting, a visitor clicks "Add a contact" or types another visitor's email address to start a conversation.
4. The other visitor's computer will pop up a chat invitation. They accept it, and the conversation begins.

**Recommended client:** Windows Messenger 4.7 (included with Windows XP) or MSN Messenger 5.0. These versions work reliably with the museum server.

## Admin Interface

The admin website lets you manage accounts and monitor the server.

1. Open a web browser on any computer on the same network.
2. Go to: **http://SERVER_IP:8082/admin** (replace SERVER_IP with your Pi's IP address)
3. Enter the admin password (configured during installation)

### Creating a New Account
1. Click **Users** in the top menu.
2. Scroll down to **Create User**.
3. Enter the visitor's email (e.g. john@hotmail.com), a password, and a display name.
4. Check the **Old MSN (MD5)** box.
5. Click **Create**.

### Creating a Pool of Visitor Accounts
1. Click **Users** → scroll to **Bulk Create Visitors**.
2. Set the prefix (e.g. "visitor"), domain (e.g. "hotmail.com"), count (e.g. 20), and password.
3. Check **Old MSN (MD5)**.
4. Click **Create Pool**. This creates visitor1@hotmail.com through visitor20@hotmail.com with the same password.

### Viewing Who Is Online
1. Click **Online** in the top menu.
2. You will see a list of everyone currently signed in, with their email, display name, and IP address.

### Viewing Conversation History
1. Click **Conversations** in the top menu.
2. You will see all messages sent between visitors, with timestamps.
3. To filter by a specific person, type their email in the **Filter by email** box and click **Filter**.

### Resetting a Forgotten Password
1. Click **Users** in the top menu.
2. Find the visitor's email in the list.
3. Type a new password in the **new pass** box next to their name.
4. Click **Reset**.

### Setting Up a New XP Computer
1. Click **Setup** in the top menu for step-by-step instructions.
2. You can download the CA certificate and MSN Messenger installers from this page.
3. Follow the instructions to edit the hosts file and install the certificate on the XP computer.

## Troubleshooting

### A visitor can't sign in
- Check that the small Raspberry Pi computer is powered on (the red LED should be on, the green LED should be blinking).
- Check that the Pi is connected to the network (the network cable should be plugged in).
- Try restarting the Pi: unplug the power cable, wait 5 seconds, plug it back in. Wait about 2 minutes for it to fully start up.
- Verify the visitor is using the correct email and password. You can reset their password via the admin interface.

### The admin page won't load
- Make sure you are using the correct address: **http://SERVER_IP:8082/admin**
- Make sure your computer is on the same network as the Pi.
- Try restarting the Pi (unplug power, wait 5 seconds, plug back in, wait 2 minutes).

### A visitor forgot their password
- Go to the admin page → **Users** → find their email → type a new password → click **Reset**.
- Tell the visitor their new password.

### Visitors can't see each other in their contact lists
- This is normal. Visitors need to add each other as contacts first, or simply type the other person's email address to start a chat directly.

## Server Info

| Item | Value |
|---|---|
| Pi IP address | (set during installation) |
| Admin URL | http://SERVER_IP:8082/admin |
| Admin password | (set during installation) |
| Supported clients | Windows Messenger 4.7, MSN Messenger 5.0 |
| MSN 7.5 | Not recommended (known sign-in issue) |