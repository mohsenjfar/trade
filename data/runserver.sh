#!/bin/bash

nano /etc/apt/sources.list
deb https://mirror.iranserver.com/debian bullseye main contrib non-free
apt update
apt install task-xfce-desktop
apt install xrdp
apt install network-manager-openvpn
adduser 