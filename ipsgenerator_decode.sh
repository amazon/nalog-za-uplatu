#!/bin/sh
#
# Decodes share link parameter from https://ipsgenerator.rs/
TOKEN="$1"

printf '%s' "$TOKEN" |
tr -- '-_' '+/' |
awk '{ while (length % 4) $0=$0 "="; print }' |
openssl enc -d -a -A -aes-256-cbc -md md5 \
  -pass pass:97639e1e3a6ef373f28f79cb4e4f13872344e20f35ebebb7a789b35226273746
