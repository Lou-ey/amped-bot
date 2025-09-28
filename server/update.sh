#!/bin/bash

set -e

cd /home/luis/Projects/discord_bot/amped-bot || exit
git remote set-url origin git@github.com:Lou-ey/amped-bot.git

echo -e "\033[1;33mGit pulling...\033[0m"
git pull origin master
if [ $? -eq 0 ]; then
    echo -e "\033[0;32mGit pull successful.\033[0m"
else
    echo -e "\033[0;31mGit pull failed. Exiting.\033[0m"
    exit 1
fi


echo -e "\033[1;33mRestarting bot service...\033[0m"
sudo systemctl restart bot.service
if [ $? -eq 0 ]; then
    echo -e "\033[0;32mBot service restarted successfully.\033[0m"
else
    echo -e "\033[0;31mFailed to restart bot service.\033[0m"
fi