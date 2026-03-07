# ============================================
# TorStream - Tor Hidden Service Dockerfile
# ============================================

FROM alpine:latest

# Install Tor
RUN apk add --no-cache tor

# Create tor user and directories
RUN mkdir -p /var/lib/tor/torstream && \
    chmod 700 /var/lib/tor && \
    chown -R tor:tor /var/lib/tor

# Copy torrc config
COPY torrc /etc/tor/torrc

# Fix permissions
RUN chown -R tor:tor /etc/tor && \
    chmod 644 /etc/tor/torrc

# Expose Tor SOCKS proxy (optional)
EXPOSE 9050

# Switch to tor user
USER tor

# Start Tor
CMD ["tor", "-f", "/etc/tor/torrc"]
