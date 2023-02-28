# DGG Relay

DGG Relay is a Discord bot that relays messages from https://chat.destiny.gg/

## Getting Started

* [Click here](https://discord.com/api/oauth2/authorize?client_id=944248509937352764&permissions=2147863552&scope=bot%20applications.commands) to add DGG Relay to one of your servers.
* Create a channel in your server called **#dgg-relay**
* Create a role in your server called **dgg-relay-mod** and grant it to yourself
* Optional: Set the **#dgg-relay** channel to **adult-only** to include nsfw/nsfl messages.
* Type a forward slash ( / ) in any channel with DGG Relay to view all available commands.

## Commands

### /relay
Relays all messages from a DGG user to a server.

All commands:

![image](https://user-images.githubusercontent.com/4806938/221872244-1d7958ad-4a28-422d-afb8-4b56a067b5c6.png)

Example:

![image](https://user-images.githubusercontent.com/4806938/221875210-f6118cd5-6747-42b6-a070-38b74ff915bc.png)

Results (in a server):

![image](https://user-images.githubusercontent.com/4806938/221875454-eb8ef676-917f-4be1-a400-195b472077d9.png)

### /phrase
Adds a phrase (usually a username) that will be searched for and DMed to you when it's used in DGG.

All commands:

![image](https://user-images.githubusercontent.com/4806938/221875739-2d3e2ec7-e785-43eb-81b8-0f795dd986a3.png)

Example:

![image](https://user-images.githubusercontent.com/4806938/221876079-64a710a0-141f-42b8-b861-9480de3228e9.png)

Results (in DMs):

![image](https://user-images.githubusercontent.com/4806938/221876262-d363d4b6-2d97-4430-80ab-715d26eb7d49.png)

### /phrase detect-dgg-presence (True|False)
Changes when phrases from the /phrase command are relayed to you.

Options:
* **False (default)**: Always forward phrases
* **True**: Only relay phrases when not present in DGG. For example, when tena logs in to DGG chat, mentions of "tena" will not be DMed. 

## Authors

tena#5751 on Discord

## Packages used

* [dgg-bot](https://github.com/Fritz-02/dgg-bot)
* [discord.py](https://github.com/Rapptz/discord.py)
* [requests](https://pypi.org/project/requests/)
* [tldextract](https://pypi.org/project/tldextract/)
