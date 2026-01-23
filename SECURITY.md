# Security Guide

This document provides security guidelines for deploying Reconly in production environments.

## Reporting Security Vulnerabilities

**Please do not report security vulnerabilities through public GitHub issues.**

If you discover a security vulnerability, please report it via one of these methods:

1. **GitHub Security Advisories** (Preferred): Use the "Report a vulnerability" button in the Security tab of this repository.
2. **Email**: Send details to security@reconly.eu

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fixes (optional)

### Response Timeline

| Severity | Initial Response | Fix Timeline |
|----------|------------------|--------------|
| Critical (RCE, data breach) | 72 hours | 7 days |
| High (auth bypass, SQLi) | 7 days | 14 days |
| Medium (XSS, info disclosure) | 14 days | 30 days |
| Low (minor issues) | 30 days | 60 days |

> **Note:** Reconly is maintained by a solo developer. Response times may be longer during holidays or personal time. Critical issues are always prioritized.

### Disclosure Policy

We follow responsible disclosure. We will:

- Acknowledge your report promptly
- Work with you to understand and resolve the issue
- Credit you in the release notes (unless you prefer anonymity)
- Not take legal action against researchers acting in good faith

---

## Table of Contents

- [Reporting Security Vulnerabilities](#reporting-security-vulnerabilities)
- [Secure Deployment Checklist](#secure-deployment-checklist)
- [SECRET_KEY Configuration](#secret_key-configuration)
- [HTTPS Setup](#https-setup)
- [Firewall Recommendations](#firewall-recommendations)
- [Rate Limiting](#rate-limiting)
- [Authentication](#authentication)
- [Environment Variables Reference](#environment-variables-reference)
- [Troubleshooting](#troubleshooting)

---

## Secure Deployment Checklist

Before deploying to production, ensure you have completed the following:

- [ ] **Set `RECONLY_ENV=production`** - Enables production security features
- [ ] **Generate a secure `SECRET_KEY`** - At least 32 characters (see below)
- [ ] **Set `RECONLY_AUTH_PASSWORD`** - Enable authentication protection
- [ ] **Configure HTTPS** - Use a reverse proxy with TLS certificates
- [ ] **Set `SECURE_COOKIES=true`** - Enable secure cookie flags
- [ ] **Configure CORS** - Restrict `CORS_ORIGINS` to your domain(s)
- [ ] **Set up firewall** - Restrict access to necessary ports only
- [ ] **Enable audit logging** - Monitor authentication events
- [ ] **Review rate limits** - Adjust `RATE_LIMIT_PER_MINUTE` if needed

---

## SECRET_KEY Configuration

The `SECRET_KEY` is used to sign session cookies. It must be:

- At least 32 characters long
- Randomly generated
- Kept secret (never commit to version control)
- Unique per deployment

### Generating a Secure Key

Using Python (recommended):

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Using OpenSSL:

```bash
openssl rand -base64 32
```

Using `/dev/urandom` (Linux/macOS):

```bash
head -c 32 /dev/urandom | base64
```

### Setting the Key

Add to your `.env` file:

```bash
SECRET_KEY=your-generated-secret-key-here
```

Or set as an environment variable:

```bash
export SECRET_KEY="your-generated-secret-key-here"
```

### Validation

In production mode (`RECONLY_ENV=production`), the application will:

- **Refuse to start** if `SECRET_KEY` is empty
- **Refuse to start** if `SECRET_KEY` is the default insecure value
- **Refuse to start** if `SECRET_KEY` is less than 32 characters

In development mode, these issues generate warnings but allow startup.

---

## HTTPS Setup

HTTPS is **required** for production deployments. The recommended approach is to use a reverse proxy that handles TLS termination.

### nginx

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL certificates (e.g., from Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

### Caddy

Caddy automatically obtains and renews TLS certificates:

```caddyfile
your-domain.com {
    reverse_proxy localhost:8000

    header {
        X-Frame-Options "SAMEORIGIN"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
    }
}
```

### Traefik

Using Docker Compose with Traefik:

```yaml
version: "3.8"

services:
  traefik:
    image: traefik:v2.10
    command:
      - "--api.insecure=false"
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge=true"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web"
      - "--certificatesresolvers.letsencrypt.acme.email=your-email@example.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./letsencrypt:/letsencrypt

  reconly:
    image: your-reconly-image
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.reconly.rule=Host(`your-domain.com`)"
      - "traefik.http.routers.reconly.entrypoints=websecure"
      - "traefik.http.routers.reconly.tls.certresolver=letsencrypt"
      # HTTP to HTTPS redirect
      - "traefik.http.middlewares.redirect-to-https.redirectscheme.scheme=https"
      - "traefik.http.routers.reconly-http.rule=Host(`your-domain.com`)"
      - "traefik.http.routers.reconly-http.entrypoints=web"
      - "traefik.http.routers.reconly-http.middlewares=redirect-to-https"
```

---

## Firewall Recommendations

### Minimum Required Ports

| Port | Protocol | Direction | Purpose |
|------|----------|-----------|---------|
| 443 | TCP | Inbound | HTTPS traffic |
| 80 | TCP | Inbound | HTTP (redirect to HTTPS) |

### Internal Ports (should NOT be exposed)

| Port | Purpose | Recommendation |
|------|---------|----------------|
| 8000 | Reconly API | Bind to localhost only |
| 5432 | PostgreSQL | Bind to localhost or internal network |

### UFW (Ubuntu)

```bash
# Allow HTTPS
sudo ufw allow 443/tcp

# Allow HTTP (for redirect)
sudo ufw allow 80/tcp

# Enable firewall
sudo ufw enable
```

### iptables

```bash
# Allow established connections
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# Allow loopback
iptables -A INPUT -i lo -j ACCEPT

# Allow HTTPS
iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# Allow HTTP (for redirect)
iptables -A INPUT -p tcp --dport 80 -j ACCEPT

# Drop everything else
iptables -A INPUT -j DROP
```

### Cloud Provider Security Groups

If deploying to AWS, GCP, or Azure, configure security groups to:

1. Allow inbound 443 (HTTPS) from 0.0.0.0/0
2. Allow inbound 80 (HTTP) from 0.0.0.0/0 (for redirect)
3. Deny all other inbound traffic
4. Allow outbound traffic as needed (API calls, etc.)

---

## Rate Limiting

Reconly includes built-in rate limiting to prevent abuse.

### Configuration

```bash
# General rate limit for all endpoints (requests per minute per IP)
RATE_LIMIT_PER_MINUTE=60
```

### Login Rate Limiting

Login attempts are rate-limited separately:

- **5 failed attempts per IP per minute**
- After 5 failures, the IP is blocked for 60 seconds
- Successful login clears the failure counter

### Monitoring Rate Limits

Rate limit events are logged via the audit system:

```json
{
  "audit_event": "rate.limited",
  "client_ip": "192.168.1.1",
  "audit_endpoint": "/auth/login",
  "audit_reason": "too_many_failed_attempts"
}
```

---

## Authentication

### Enabling Authentication

Set a password to enable authentication:

```bash
RECONLY_AUTH_PASSWORD=your-secure-password-here
```

### Authentication Methods

Reconly supports two authentication methods:

1. **Session Cookie** - For browser-based access
   - POST to `/api/v1/auth/login` with password
   - Cookie is set automatically
   - 7-day expiration

2. **HTTP Basic Auth** - For CLI and scripts
   - Username is ignored (can be empty)
   - Password must match `RECONLY_AUTH_PASSWORD`

### Protected Routes

When authentication is enabled:

- All API routes require authentication
- **Exceptions** (always public):
  - `/health` - Simple health check
  - `/docs` - API documentation
  - `/api/v1/auth/*` - Authentication endpoints

### Audit Logging

Authentication events are logged:

```json
// Successful login
{"audit_event": "auth.success", "client_ip": "192.168.1.1"}

// Failed login
{"audit_event": "auth.failure", "client_ip": "192.168.1.1", "audit_reason": "invalid_password"}
```

---

## Environment Variables Reference

Security-related environment variables:

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `RECONLY_ENV` | `development` | Production | Set to `production` for production mode |
| `SECRET_KEY` | (none) | Production | Signing key for session cookies (min 32 chars) |
| `RECONLY_AUTH_PASSWORD` | (none) | Recommended | Password for authentication |
| `SECURE_COOKIES` | `auto` | No | Cookie security: `auto`, `true`, `false` |
| `RATE_LIMIT_PER_MINUTE` | `60` | No | Rate limit per IP per minute |
| `CORS_ORIGINS` | `localhost` | Production | Allowed CORS origins (comma-separated) |
| `CSP_POLICY` | (default) | No | Content Security Policy header |

### Example Production `.env`

```bash
# Environment
RECONLY_ENV=production
DEBUG=false

# Security
SECRET_KEY=your-32-char-minimum-secret-key-here
RECONLY_AUTH_PASSWORD=your-secure-password
SECURE_COOKIES=true

# CORS (restrict to your domain)
CORS_ORIGINS=https://your-domain.com

# Rate limiting
RATE_LIMIT_PER_MINUTE=60

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/reconly
```

---

## Troubleshooting

### Common Issues

#### "SECRET_KEY is not set" Error

**Problem**: Application refuses to start in production mode.

**Solution**: Generate and set a secure `SECRET_KEY`:

```bash
SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export SECRET_KEY
```

#### "SECRET_KEY is too short" Error

**Problem**: Your `SECRET_KEY` is less than 32 characters.

**Solution**: Generate a longer key using the commands above.

#### Session Cookie Not Being Set

**Problem**: Login succeeds but cookie is not stored.

**Possible causes**:
1. `SECURE_COOKIES=true` but accessing via HTTP
2. Browser blocking third-party cookies
3. SameSite cookie policy conflicts

**Solutions**:
- Use HTTPS in production
- Set `SECURE_COOKIES=auto` to detect HTTPS automatically
- Ensure the app and UI are on the same domain

#### Rate Limit Triggering Too Quickly

**Problem**: Legitimate users are being rate limited.

**Solution**: Increase the rate limit:

```bash
RATE_LIMIT_PER_MINUTE=120
```

#### CORS Errors

**Problem**: Browser console shows CORS errors.

**Solution**: Add your frontend domain to `CORS_ORIGINS`:

```bash
CORS_ORIGINS=https://your-frontend.com,https://your-api.com
```

### Viewing Audit Logs

Audit events are logged to stdout with the logger name `audit`:

```bash
# Filter audit events (if using JSON logging)
grep '"logger": "audit"' /var/log/reconly/app.log

# Or with jq
cat /var/log/reconly/app.log | jq 'select(.logger == "audit")'
```

### Verifying Security Configuration

Check your configuration at startup in the logs:

```
Configuration summary
  edition=oss
  environment=production
  debug=false
  secret_key_length=43
  auth_required=true
  secure_cookies=true
  rate_limit_per_minute=60
```

---

## Security Contacts

For security vulnerability reports, see [Reporting Security Vulnerabilities](#reporting-security-vulnerabilities) at the top of this document.

For general security questions: security@reconly.eu

---

## Additional Resources

- [OWASP Secure Coding Practices](https://owasp.org/www-project-secure-coding-practices-quick-reference-guide/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
