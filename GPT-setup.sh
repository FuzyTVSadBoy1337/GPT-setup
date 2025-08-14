#!/bin/bash
cd
if [ -e "/data/data/com.termux/files/home/storage" ]; then
	rm -rf /data/data/com.termux/files/home/storage
fi
termux-setup-storage
yes | pkg update
. <(curl https://raw.githubusercontent.com/Wraith1vs11/Rejoin/refs/heads/main/termux-change-repo.sh)
yes | pkg upgrade
yes | pkg i python
yes | pkg i python-pip
pip install requests rich prettytable pytz
export CFLAGS="-Wno-error=implicit-function-declaration"
pip install psutil
curl -Ls "https://raw.githubusercontent.com/Wraith1vs11/Rejoin/refs/heads/main/OldShouko.py" -o /sdcard/Download/OldShouko.py
