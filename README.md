# DGG Relay

DGG Relay is a Discord bot that relays messages from https://chat.destiny.gg/.

## Getting Started

* [Click here](https://discord.com/api/oauth2/authorize?client_id=944248509937352764&permissions=2147863552&scope=bot%20applications.commands) to add DGG Relay to one of your servers.
* To get started, type a forward slash ( / ) in any channel with DGG Relay to view all available commands.

## Commands

### /relay (mode) (dgg_username)
Relays all messages from a DGG user to a server. To use this command, set up the following on your server:
* A channel called **#dgg-relay**
* A role named **dgg-relay-mod**
* Optional: Set the **#dgg-relay** channel to adult-only to include nsfw messages.

Example:

![image](https://user-images.githubusercontent.com/4806938/170265102-1a178696-d9a8-455f-a9ed-1cd49d17f196.png)

Results in:

![image](https://user-images.githubusercontent.com/4806938/170265661-baada230-d176-4794-9f01-b7c9a21f8351.png)

## Authors

tena#5751 on Discord

## Packages used

* [dgg-bot](https://github.com/Fritz-02/dgg-bot)
* [py-cord](https://github.com/Pycord-Development/pycord)
* [requests](https://pypi.org/project/requests/)
* [tldextract](https://pypi.org/project/tldextract/)
