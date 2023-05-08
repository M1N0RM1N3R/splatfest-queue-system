# Splatfest Queue System (A.K.A. Kolkra)
The Splatfest Queue System (SQS for short) is a custom Discord bot built to streamline matchmaking and other tasks in the [Splatfest Discord server](https://discord.gg/rhAH6vp).

Current features include:
* Custom webhook messages when members join/leave the server.
* Quick, easy conversion of natural-language dates/times to Discord timestamps.
* Random IP generator for [classic LAN play](https://github.com/spacemeowx2/switch-lan-play)
* Player profiles containing members':
  * NSO friend codes
  * Preferred classic LAN play server
  * XLink Kai username (XTag)
  * In-game name

Currently working on:
* Migrating from ZODB to [SurrealDB](https://surrealdb.com/) for data storage

Planned features include:
* Automated LANarchy results submission and tracking
* Strike system (Moving away from vulnerable role-based system)
* Session-based matchmaking system
* Handling server custom Splatfests

This repo is not necessarily intended for you to spin up your own instance. (if you really want to, live long and prosper) It's mainly intended to provide transparency into what makes the bot tick and to provide a quick and easy way to move updated code to production.
