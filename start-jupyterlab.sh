#!/usr/bin/env bash
cd "$HOME/vpn-traffic-fyp" || exit 1
source .venv/bin/activate
exec jupyter lab
