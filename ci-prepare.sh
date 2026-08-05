#!/bin/sh
set -e

# Script to run inside CI build container to install dependency

apt-get update
apt-get install -y curl jq

URL=$(curl -s https://api.github.com/repos/crosser/ppk2tool/releases/latest \
 | jq -r '.assets[]|select(.content_type == "application/x-debian-package")
 |.browser_download_url')
PKG=$(basename $URL)

TMP=$(mktemp -d)
trap "rm -rf $TMP" EXIT
curl --location --output $TMP/$PKG $URL
apt install -y $TMP/$PKG
