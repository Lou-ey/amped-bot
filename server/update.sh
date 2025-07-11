#!/bin/bash

cd /home/luis/Projects/discord_bot/amped-bot || exit

echo "Git pulling..."
git pull origin main

echo "Restarting bot service..."
systemctl restart bot.service
