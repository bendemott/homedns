#!/bin/bash
set -e # fail on first error
# Installation Script for Debian/Ubuntu
if ! command -v python3 &> /dev/null
then
    echo "python3 is not installed or not on the path"
    exit 1
fi

if ! command -v pip3 &> /dev/null
then
  wget https://pip.pypa.io/en/stable/installation/#get-pip-py
  sudo python3 get-pip.py
fi


if ! command -v pip3 &> /dev/null
then
    echo "pip3 failed to install properly"
    exit 1
fi

# install from git
echo "Installing from: git+https://github.com/bendemott/homedns.git"
sudo pip3 install git+https://github.com/bendemott/homedns.git

# cleanup
sudo rm -f get-pip.py || true

echo "Done!"