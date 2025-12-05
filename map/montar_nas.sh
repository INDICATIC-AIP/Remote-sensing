#!/bin/bash
source /home/jjaen/Documents/indicatic/Remote-sensing/.env
sudo mount -t cifs "//$NAS_IP/DATOS API ISS" /mnt/nas -o credentials=/root/.smbcredentials,vers=3.0,uid=$(id -u),gid=$(id -g),file_mode=0644,dir_mode=0755 

