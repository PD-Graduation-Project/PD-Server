#!/bin/sh
# Entrypoint for nginx - HTTP only, SSL handled by upstream

exec nginx -g "daemon off;"
