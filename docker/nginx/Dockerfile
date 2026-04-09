# Nginx Dockerfile for PD-Server
# Uses mounted certificates if available, generates self-signed only as fallback

FROM nginx:alpine

# Create ssl directory
RUN mkdir -p /etc/nginx/ssl

# Generate self-signed cert only if certificates are not mounted
# To use real certificates, mount them at runtime:
#   -v /path/to/server.crt:/etc/nginx/ssl/server.crt:ro
#   -v /path/to/server.key:/etc/nginx/ssl/server.key:ro
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80 443

CMD ["/docker-entrypoint.sh"]
