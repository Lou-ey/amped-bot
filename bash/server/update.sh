#!/bin/bash
cd ./ # path to the bot
git pull origin main
systemctl restart bot.service
