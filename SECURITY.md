# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Security Features

### Authentication
- Argon2 password hashing
- HTTP-only, Secure, SameSite=Strict cookies
- JWT tokens with expiration
- CSRF protection via double-submit cookie
- Rate limiting on login attempts

### Data Protection
- SQL injection prevention via SQLAlchemy ORM
- XSS protection with Content Security Policy
- No external CDNs or analytics
- Metadata stripping from uploaded videos

### Network Security
- Tor hidden service support
- No IP-based geo logic
- Privacy-aware logging
- Nginx reverse proxy with security headers

## Reporting a Vulnerability

If you discover a security vulnerability, please:

1. **DO NOT** open a public issue
2. Email security@torstream.local with details
3. Allow 48 hours for initial response
4. Allow 7 days for vulnerability assessment

## Security Checklist

Before deploying to production:

- [ ] Change all default passwords
- [ ] Generate strong SECRET_KEY and ADMIN_SECRET_KEY
- [ ] Configure BTCPay webhook secret
- [ ] Enable HTTPS (if not using Tor only)
- [ ] Set DEBUG=false
- [ ] Review firewall rules
- [ ] Enable automatic security updates
- [ ] Configure log rotation
- [ ] Set up monitoring and alerting
- [ ] Test backup and restore procedures

## Security Headers

The following security headers are configured:

- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: no-referrer`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`
- `Content-Security-Policy` (strict, no external resources)

## Rate Limits

- Login attempts: 5 per 15 minutes per IP/username
- API requests: 10 per minute
- Upload size: 5GB maximum

## Password Requirements

- Minimum 8 characters
- Any characters allowed (no complexity requirements)
- Argon2 hashing with configurable parameters

## Audit Logging

All admin actions are logged:
- User bans/unbans
- Premium grants/revocations
- Video uploads/deletions
- Payment approvals/refunds
- Configuration changes
