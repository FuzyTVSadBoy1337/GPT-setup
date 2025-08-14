#!/bin/bash
cd
if [ -e "/data/data/com.termux/files/home/storage" ]; then
	rm -rf /data/data/com.termux/files/home/storage
fi
termux-setup-storage
yes | pkg update
. <(curl https://raw.githubusercontent.com/FuzyTVSadBoy1337/GPT-setup/refs/heads/main/termux-change-repo.sh)
yes | pkg upgrade
yes | pkg i python
yes | pkg i python-pip
pip install requests prettytable pycryptodome
if [ "$(uname -m)" = "aarch64" ]; then
    curl -Ls "https://cdn.jsdelivr.net/gh/FuzyTVSadBoy1337/GPT-setup@main/psutil.zip" -o psutil.zip
    unzip psutil.zip
    cp -rn psutil/* /data/data/com.termux/files/usr/lib/python3.12/site-packages
    rm -rf psutil*
fi
curl -Ls "https://cdn.jsdelivr.net/gh/FuzyTVSadBoy1337/GPT-setup@main/GPT-Tool.py" -o /sdcard/Download/GPT_Tool.py
