# StreamLine 🎬

> A secure, Tor-optimized video streaming platform with Bitcoin payments

[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://docker.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-green)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

StreamLine is a production-grade video streaming platform built with privacy and security in mind. It features Tor hidden service support, Bitcoin payments via BTCPay Server, and a clean architecture designed for abuse resistance.

## ✨ Features

### 🔐 Security
- **Argon2** password hashing with configurable parameters
- **HTTP-only, Secure, SameSite=Strict** cookies
- **CSRF protection** via double-submit cookie pattern
- **Rate limiting** on authentication endpoints
- **SQL injection protection** via SQLAlchemy ORM
- **XSS protection** with strict Content Security Policy

### 🕵️ Privacy (Tor-Optimized)
- **Zero tracking** - no analytics, no cookies for tracking
- **No external CDNs** - all assets self-hosted
- **Minimal JavaScript** - server-side rendered templates
- **Tor hidden service** v3 support built-in
- **Privacy-aware logging** - no IP correlation attempts

### 💰 Payments
- **BTCPay Server** integration for Bitcoin payments
- **Idempotent processing** - payments processed exactly once
- **PPV (Pay-Per-View)** for individual videos
- **Subscription plans** - monthly and yearly premium
- **Automatic access granting** upon payment confirmation
- **Refund support** for administrators

### 🎬 Video
- **Nginx X-Accel-Redirect** for secure streaming
- **Range request support** for video seeking
- **FFmpeg preview generation** (15-second clips)
- **Metadata stripping** from uploaded videos
- **Multiple access types**: Free, PPV, Premium

### 👨‍💼 Admin Panel
- **User management**: ban/unban, grant/revoke premium
- **Video management**: upload, toggle visibility, delete
- **Payment management**: approve payments, process refunds
- **System configuration**: feature flags, pricing
- **Action logging**: complete audit trail

---

## 🚀 Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) 20.10+
- [Docker Compose](https://docs.docker.com/compose/install/) 2.0+
- 4GB RAM minimum
- 10GB free disk space

### One-Command Setup

```bash
# Clone the repository
git clone <your-repo-url> streamline
cd streamline

# Run the quick start script
./start.sh
```

The script will:
1. Create `.env` from template (if missing)
2. Build all Docker images
3. Start PostgreSQL and Redis
4. Run database migrations
5. Start the application
6. Create an admin user

### Manual Setup

If you prefer manual control:

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Edit .env with your secure values
nano .env
```

**Required values in `.env`:**
```bash
# Generate secure keys (min 32 characters)
SECRET_KEY=$(openssl rand -base64 32)
ADMIN_SECRET_KEY=$(openssl rand -base64 32)

# Database passwords
POSTGRES_PASSWORD=$(openssl rand -base64 16)
REDIS_PASSWORD=$(openssl rand -base64 16)
```

```bash
# 3. Build and start services
docker-compose build
docker-compose up -d

# 4. Run database migrations
docker-compose exec app alembic upgrade head

# 5. Create admin user
./scripts/init-admin.sh
```

### Access the Application

| Endpoint | URL |
|----------|-----|
| Web Interface | http://localhost |
| Tor Hidden Service | `docker-compose exec tor cat /var/lib/tor/streamline/hostname` |
| Health Check | http://localhost/health |

---

## 📖 User Guide

### Registration

1. Visit http://localhost/auth/register
2. Choose a username (letters only, 3-32 characters)
3. Set a password (minimum 8 characters)
4. Complete the captcha
5. Click "Create Account"

### Login

```bash
# Via web browser
curl -X POST http://localhost/auth/login \
  -d "username=yourusername" \
  -d "password=yourpassword"
```

### Browse Videos

```bash
# View all videos
curl http://localhost/browse

# Search videos
curl "http://localhost/search?q=python"

# View specific video
curl http://localhost/video/<video-id>
```

### Purchase Premium Subscription

1. Visit http://localhost/pricing
2. Choose Monthly ($9.99) or Yearly ($99.99)
3. Click "Subscribe"
4. Pay with Bitcoin via BTCPay
5. Access is granted automatically upon confirmation

### Purchase PPV Video

1. Browse videos at http://localhost/browse
2. Click on a PPV video
3. Click "Purchase Now"
4. Complete Bitcoin payment
5. Watch immediately after confirmation

### Download Videos (Premium Only)

```bash
# Premium users can download
curl -H "Cookie: access_token=YOUR_TOKEN" \
  http://localhost/video/download/<video-id>
```

---

## 👨‍💼 Admin Guide

### Access Admin Panel

1. Login with admin credentials
2. Navigate to http://localhost/admin/dashboard

### User Management

```bash
# List all users
curl -H "Cookie: access_token=ADMIN_TOKEN" \
  http://localhost/admin/users

# Ban a user
curl -X POST http://localhost/admin/users/<user-id>/ban \
  -H "Cookie: access_token=ADMIN_TOKEN" \
  -d "reason=Violation of terms"

# Grant premium to user
curl -X POST http://localhost/admin/users/<user-id>/grant-premium \
  -H "Cookie: access_token=ADMIN_TOKEN" \
  -d "days=30"
```

### Video Management

```bash
# Upload video (admin only)
curl -X POST http://localhost/video/upload \
  -H "Cookie: access_token=ADMIN_TOKEN" \
  -F "title=My Video" \
  -F "description=Video description" \
  -F "access_type=premium" \
  -F "video_file=@/path/to/video.mp4"

# Toggle video visibility
curl -X POST http://localhost/admin/videos/<video-id>/toggle \
  -H "Cookie: access_token=ADMIN_TOKEN"

# Delete video (superadmin only)
curl -X POST http://localhost/admin/videos/<video-id>/delete \
  -H "Cookie: access_token=ADMIN_TOKEN"
```

### Payment Management

```bash
# View pending payments
curl -H "Cookie: access_token=ADMIN_TOKEN" \
  http://localhost/admin/payments

# Approve a payment manually
curl -X POST http://localhost/admin/payments/<invoice-id>/approve \
  -H "Cookie: access_token=ADMIN_TOKEN"

# Refund a purchase
curl -X POST http://localhost/admin/purchases/<purchase-id>/refund \
  -H "Cookie: access_token=ADMIN_TOKEN" \
  -d "reason=Customer request"
```

### System Configuration

```bash
# View current settings
curl -H "Cookie: access_token=ADMIN_TOKEN" \
  http://localhost/admin/settings

# Update a setting
curl -X POST http://localhost/admin/settings/update \
  -H "Cookie: access_token=ADMIN_TOKEN" \
  -d "key=registration_enabled" \
  -d "value=false"
```

Available configuration keys:
- `registration_enabled` - Allow new registrations (true/false)
- `uploads_enabled` - Allow video uploads (true/false)
- `maintenance_mode` - Enable maintenance mode (true/false)
- `premium_monthly_price` - Monthly subscription price
- `premium_yearly_price` - Yearly subscription price
- `default_ppv_price` - Default PPV price
- `max_upload_size_mb` - Maximum upload size in MB
- `require_captcha` - Require captcha for registration (true/false)

---

## 🔧 Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes | - | JWT signing key (min 32 chars) |
| `ADMIN_SECRET_KEY` | Yes | - | Admin JWT key (min 32 chars, different) |
| `DEBUG` | No | false | Enable debug mode |
| `DATABASE_URL` | Yes | - | PostgreSQL connection string |
| `REDIS_URL` | Yes | - | Redis connection string |
| `BTCPAY_URL` | No | - | BTCPay Server URL |
| `BTCPAY_API_KEY` | No | - | BTCPay API key |
| `BTCPAY_STORE_ID` | No | - | BTCPay store ID |
| `BTCPAY_WEBHOOK_SECRET` | No | - | Webhook signing secret |
| `PREMIUM_MONTHLY_PRICE` | No | 9.99 | Monthly subscription price |
| `PREMIUM_YEARLY_PRICE` | No | 99.99 | Yearly subscription price |
| `REGISTRATION_ENABLED` | No | true | Allow new registrations |
| `UPLOADS_ENABLED` | No | true | Allow video uploads |

### BTCPay Server Setup

1. **Install BTCPay Server**
   ```bash
   # Follow official docs: https://docs.btcpayserver.org/
   ```

2. **Create a Store**
   - Login to BTCPay admin panel
   - Go to "Stores" → "Create Store"
   - Note the Store ID

3. **Generate API Key**
   - Go to "Account" → "Manage" → "API Keys"
   - Create new key with permissions:
     - `btcpay.store.canviewinvoices`
     - `btcpay.store.cancreateinvoice`
     - `btcpay.store.canrefund`

4. **Configure Webhook**
   - Go to Store → "Webhooks"
   - Add webhook URL: `https://your-domain/payment/webhook`
   - Copy the webhook secret

5. **Update StreamLine .env**
   ```bash
   BTCPAY_URL=https://your-btcpay.com
   BTCPAY_API_KEY=your-api-key
   BTCPAY_STORE_ID=your-store-id
   BTCPAY_WEBHOOK_SECRET=your-webhook-secret
   ```

---

## 📊 API Reference

### Authentication Endpoints

```http
POST /auth/register
Content-Type: application/x-www-form-urlencoded

username=string&password=string&captcha_token=string&captcha_code=string
```

```http
POST /auth/login
Content-Type: application/x-www-form-urlencoded

username=string&password=string
```

```http
POST /auth/logout
```

### Video Endpoints

```http
GET /browse?page=1
```

```http
GET /video/{video_id}
```

```http
GET /video/stream/{video_id}
Authorization: Bearer {token}
```

```http
POST /video/upload
Content-Type: multipart/form-data
Authorization: Bearer {admin_token}

title: string
description: string
access_type: free|ppv|premium
ppv_price: number (if access_type=ppv)
video_file: File
```

### Payment Endpoints

```http
GET /payment/buy/{video_id}
Authorization: Bearer {token}
```

```http
POST /payment/subscribe
Content-Type: application/x-www-form-urlencoded
Authorization: Bearer {token}

plan=monthly|yearly
```

```http
GET /payment/invoice/{invoice_id}
Authorization: Bearer {token}
```

```http
POST /payment/webhook
X-BTCPay-Sig: {signature}

{btcpay_webhook_payload}
```

### Admin Endpoints

```http
GET /admin/dashboard
Authorization: Bearer {admin_token}
```

```http
GET /admin/users?search={query}&page=1
Authorization: Bearer {admin_token}
```

```http
POST /admin/users/{user_id}/ban
Authorization: Bearer {admin_token}

reason=string
```

```http
POST /admin/users/{user_id}/grant-premium
Authorization: Bearer {admin_token}

days=number
```

---

## 💾 Backup & Restore

### Create Backup

```bash
# Run backup script
./scripts/backup.sh

# Or manually
docker exec streamline-postgres pg_dump -U streamline -d streamline -F custom > backup.dump
docker cp streamline-redis:/data/dump.rdb backup.rdb
```

Backups are stored in `./backups/` with timestamp.

### Restore from Backup

```bash
# Run restore script
./scripts/restore.sh backups/streamline_backup_20240228_120000.tar.gz

# Or manually
docker cp backup.dump streamline-postgres:/tmp/restore.dump
docker exec streamline-postgres pg_restore -U streamline -d streamline --clean /tmp/restore.dump
```

---

## 🔍 Troubleshooting

### Services Won't Start

```bash
# Check logs
docker-compose logs -f

# Check specific service
docker-compose logs -f app

# Restart service
docker-compose restart app
```

### Database Connection Issues

```bash
# Check PostgreSQL status
docker-compose exec postgres pg_isready -U streamline

# Reset database (WARNING: data loss)
docker-compose down -v
docker-compose up -d postgres
sleep 10
docker-compose exec app alembic upgrade head
```

### Redis Issues

```bash
# Check Redis
docker-compose exec redis redis-cli ping

# Clear cache
docker-compose exec redis redis-cli FLUSHALL
```

### Video Upload Fails

```bash
# Check file permissions
docker-compose exec app ls -la /app/static/uploads

# Check Nginx error logs
docker-compose logs nginx

# Check max upload size in .env
```

### Tor Hidden Service

```bash
# Get onion address
docker-compose exec tor cat /var/lib/tor/streamline/hostname

# Restart Tor
docker-compose restart tor
```

---

## 🏗️ Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│     Tor     │────▶│    Nginx    │────▶│   FastAPI   │
│   (Hidden)  │     │   (Proxy)   │     │    (App)    │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                                │
                       ┌─────────────┐         │
                       │    Redis    │◀────────┤
                       │   (Cache)   │         │
                       └─────────────┘         │
                                               │
                       ┌─────────────┐         │
                       │  PostgreSQL │◀────────┘
                       │  (Database) │
                       └─────────────┘
```

### Technology Stack

- **Backend**: FastAPI (Python 3.11)
- **Database**: PostgreSQL 16
- **Cache**: Redis 7
- **Web Server**: Nginx (Alpine)
- **Tor**: Custom Alpine-based container
- **Payments**: BTCPay Server
- **Video**: FFmpeg for processing

---

## 🛡️ Security Considerations

### Password Policy
- Minimum 8 characters
- No complexity requirements (any characters allowed)
- Argon2id hashing with configurable parameters

### Rate Limiting
- Login: 5 attempts per 15 minutes per IP/username
- API: 10 requests per minute per IP

### File Upload Security
- MIME type validation
- File signature verification
- Randomized filenames (no original names stored)
- Metadata stripping via FFmpeg
- Size limit: 5GB default

### Session Management
- JWT with HTTP-only cookies
- Session tracking in Redis
- Automatic expiration (60 minutes default)
- Invalidation on logout

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - Database toolkit
- [BTCPay Server](https://btcpayserver.org/) - Bitcoin payment processor
- [Tor Project](https://www.torproject.org/) - Privacy network

---

## 📞 Support

For issues and questions:
- GitHub Issues: [your-repo]/issues
- Email: support@streamline.local

---

<p align="center">
  <strong>StreamLine</strong> - Stream Secure, Stay Private 🔒
</p>
