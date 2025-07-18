# Automated Expired Token Cleanup Setup

This document provides step-by-step instructions for setting up automated daily cleanup of expired JWT tokens using GitHub Actions and Render deployment.

## Overview

The solution consists of:

1. **Django Management Command**: Custom command to flush expired tokens
2. **Secure Django Endpoint**: HTTP endpoint to trigger the cleanup
3. **GitHub Actions Workflow**: Automated daily cron job
4. **Security**: Secret key authentication between GitHub and Django

## Architecture Concept: Scheduled API Trigger

### What This System Is

This is a **"Scheduled API Trigger"** or **"External Cron Job"** system that leverages GitHub Actions as a free scheduler to trigger Django management commands via HTTP requests.

### Architecture Flow

```
┌─────────────────┐    HTTP POST     ┌─────────────────┐
│  GitHub Actions │ ──────────────→  │ Django Endpoint │
│  (Scheduler)    │  (with secret)   │ (Token Cleanup) │
│  Runs Daily     │                  │ /cron/flush-    │
│  at Midnight    │                  │ tokens/         │
└─────────────────┘                  └─────────────────┘
        │                                     │
        │                                     ▼
        │                            ┌─────────────────┐
        │                            │ Management      │
        │                            │ Command         │
        │                            │ flushexpired    │
        │                            │ tokens_daily    │
        └────────────────────────────┴─────────────────┘
```

### How It Differs from Traditional Webhooks

| Aspect        | Traditional Webhook            | This Scheduled API Trigger            |
| ------------- | ------------------------------ | ------------------------------------- |
| **Trigger**   | External event occurs          | Time-based schedule                   |
| **Direction** | External Service → Your App    | GitHub Actions → Your App             |
| **Timing**    | Immediate (event-driven)       | Scheduled (time-driven)               |
| **Purpose**   | React to external events       | Execute periodic tasks                |
| **Example**   | Payment processed → Send email | Daily cleanup → Remove expired tokens |

### Why This Approach?

1. **Cost-Effective**:

   - Render's free tier doesn't support background workers or cron jobs
   - GitHub Actions provides free cron scheduling for public repositories
   - No need for paid background worker services

2. **Reliable Scheduling**:

   - GitHub's infrastructure handles the scheduling
   - Built-in retry mechanisms and logging
   - No need to manage your own cron daemon

3. **Secure**:

   - Uses secret key authentication (`X-Cron-Secret` header)
   - Only authorized requests can trigger the cleanup
   - Environment variables keep secrets secure

4. **Scalable**:
   - Can easily add more scheduled tasks
   - Modify schedules without touching server configuration
   - Monitor execution through GitHub Actions interface

### Benefits for Developers

- **No Server-Side Cron**: Eliminates need for server cron jobs
- **Free Solution**: Uses free GitHub Actions for scheduling
- **Easy Monitoring**: View execution logs in GitHub Actions
- **Version Controlled**: Schedules are part of your codebase
- **Flexible**: Easy to modify schedules and add new tasks
- **Cross-Platform**: Works with any hosting provider that supports HTTP endpoints

## Implementation Steps

### 1. Django Components Created

#### A. Management Command

- **Location**: `apps/authentication/management/commands/flushexpiredtokens_daily.py`
- **Purpose**: Wraps Django's built-in `flushexpiredtokens` command
- **Usage**: `python manage.py flushexpiredtokens_daily`

#### B. Secure Endpoint

- **Location**: `apps/authentication/views.py` (function: `run_flush_expired_tokens`)
- **URL**: `/api/v1/auth/cron/flush-tokens/`
- **Method**: POST only
- **Security**: Requires `X-Cron-Secret` header matching `CRON_SECRET_KEY` environment variable

#### C. URL Route

- **Location**: `apps/authentication/urls.py`
- **Pattern**: `path('cron/flush-tokens/', run_flush_expired_tokens, name='flush_tokens_cron')`

### 2. Environment Configuration

#### A. Environment Variables Added

Added to `.env.sample`:

```bash
# Cron Job Security
CRON_SECRET_KEY=your-secure-cron-secret-key-here
```

### 3. GitHub Actions Workflow

#### A. Workflow File

- **Location**: `.github/workflows/trigger_flush_endpoint.yml`
- **Schedule**: Daily at midnight UTC (`0 0 * * *`)
- **Action**: Sends POST request to Django endpoint with secret header

## Deployment Instructions

### Step 1: Render Environment Setup

1. **Go to Render Dashboard**

   - Navigate to your Django web service
   - Go to "Environment" settings

2. **Add Environment Variable**
   - Key: `CRON_SECRET_KEY`
   - Value: Generate a strong, unique secret string (e.g., use `openssl rand -hex 32`)
   - **Important**: Keep this secret secure and don't commit it to version control

### Step 2: GitHub Repository Setup

1. **Add GitHub Secret**

   - Go to your GitHub repository settings
   - Navigate to "Settings" → "Security" → "Secrets and variables" → "Actions"
   - Click "New repository secret"
   - Name: `CRON_SECRET_KEY`
   - Value: **Exact same secret** as used in Render environment variable

2. **Update Workflow URL**
   - Edit `.github/workflows/trigger_flush_endpoint.yml`
   - Replace `https://your-django-app.onrender.com` with your actual Render service URL
   - The full endpoint will be: `https://your-domain.onrender.com/api/v1/auth/cron/flush-tokens/`

### Step 3: Deployment

1. **Commit and Push Changes**

2. **Trigger Render Redeploy**
   - Render should automatically redeploy when you push to main
   - Alternatively, manually trigger redeploy from Render dashboard

### Step 4: Verification

#### A. Test the Endpoint Manually

```bash
# Test the endpoint (replace with your actual URL and secret)
curl -X POST \
     -H "X-Cron-Secret: your-actual-secret-key" \
     "https://your-app.onrender.com/api/v1/auth/cron/flush-tokens/"
```

Expected response:

```json
{ "status": "success", "message": "Expired tokens flushed successfully." }
```

#### B. Monitor GitHub Actions

1. Go to your repository's "Actions" tab
2. Look for "Trigger Flush Expired Tokens Endpoint Daily" workflow
3. The workflow will run daily at midnight UTC
4. Check workflow logs for successful execution

#### C. Monitor Render Logs

1. Go to Render Dashboard → Your service → Logs
2. Look for log entries when the endpoint is accessed
3. Should see success messages from the management command

## Security Considerations

1. **Secret Key**: Use a strong, randomly generated secret key
2. **HTTPS**: Ensure your Render service uses HTTPS
3. **Environment Variables**: Never commit secrets to version control
4. **Access Control**: The endpoint is only accessible with the correct secret header

## Troubleshooting

### Common Issues

1. **401 Unauthorized Error**

   - Check that `CRON_SECRET_KEY` matches in both Render and GitHub
   - Verify the header name is exactly `X-Cron-Secret`

2. **404 Not Found Error**

   - Verify the URL path in GitHub workflow matches your Django URL pattern
   - Check that the Django service is running and accessible

3. **500 Internal Server Error**

   - Check Render logs for Django errors
   - Ensure `rest_framework_simplejwt` is properly installed and configured

4. **GitHub Actions Failing**
   - Check that the repository secret `CRON_SECRET_KEY` is set
   - Verify the Render service URL is correct and accessible

### Manual Testing Commands

```bash
# Test management command directly
python manage.py flushexpiredtokens_daily

# Test with curl (replace values)
curl -X POST \
     -H "X-Cron-Secret: your-secret" \
     -v \
     "https://your-app.onrender.com/api/v1/auth/cron/flush-tokens/"
```

## Customization

### Change Schedule

Edit `.github/workflows/trigger_flush_endpoint.yml`:

```yaml
schedule:
  - cron: "0 2 * * *" # Run at 2 AM UTC daily
  - cron: "0 */6 * * *" # Run every 6 hours
```

### Add Logging

You can enhance the management command to add more detailed logging:

```python
import logging
logger = logging.getLogger(__name__)

def handle(self, *args, **options):
    logger.info('Starting expired token cleanup...')
    # ... existing code
    logger.info('Expired token cleanup completed successfully')
```

The system will now automatically clean up expired JWT tokens daily, helping maintain database performance and security.
