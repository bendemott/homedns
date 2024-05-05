#!/bin/bash
set -e # fail on first error
# Installation Script for Debian/Ubuntu
if ! command -v python3 &> /dev/null
then
    echo "python3 is not installed or not on the path"
    exit 1
fi

sudo apt update

# ====== pip3 ===========================================
if ! command -v pip3 &> /dev/null
then
  sudo apt install python3-pip -y
fi


if ! command -v pip3 &> /dev/null
then
    echo "pip3 failed to install properly"
    exit 1
fi

# ====== git ============================================
if ! command -v git &> /dev/null
then
  sudo apt install git -y
fi


# install from git
echo "Installing from: git+https://github.com/bendemott/homedns.git"
sudo pip3 install git+https://github.com/bendemott/homedns.git --break-system-packages

echo "Done!"