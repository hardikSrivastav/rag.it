# Gmail Connector Setup Guide

## 🔧 **Step 1: Create Google Cloud Project & OAuth Credentials**

### 1. Go to Google Cloud Console
- Visit: https://console.cloud.google.com/
- Create a new project or select existing one

### 2. Enable Gmail API
- Go to "APIs & Services" > "Library"
- Search for "Gmail API"
- Click "Enable"

### 3. Create OAuth 2.0 Credentials
- Go to "APIs & Services" > "Credentials"
- Click "Create Credentials" > "OAuth 2.0 Client IDs"
- Choose "Web application"
- Set these values:
  - **Name:** RAG System Gmail Connector
  - **Authorized redirect URIs:** `http://localhost:8792/api/v1/oauth/gmail/callback`

### 4. Download Credentials
- Copy the **Client ID** and **Client Secret**

## 🚀 **Step 2: Configure OAuth in RAG System**

### Configure Gmail OAuth:
```bash
curl -X POST "http://localhost:8792/api/v1/oauth/gmail/configure" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "YOUR_GOOGLE_CLIENT_ID",
    "client_secret": "YOUR_GOOGLE_CLIENT_SECRET", 
    "redirect_uri": "http://localhost:8792/api/v1/oauth/gmail/callback"
  }'
```

## 📧 **Step 3: Connect Your Gmail Account**

### Start OAuth Flow:
```bash
curl -X GET "http://localhost:8792/api/v1/oauth/gmail/authorize?connector_name=gmail-personal"
```

This will return an `auth_url`. Visit that URL in your browser to authorize the connector.

## ⚙️ **Step 4: Verify Connection**

### Check connector status:
```bash
curl -X GET "http://localhost:8792/api/v1/connectors/" 
```

### Trigger initial sync:
```bash
curl -X POST "http://localhost:8792/api/v1/connectors/gmail-personal/sync" \
  -H "Content-Type: application/json" \
  -d '{"incremental": false}'
```

## 🔒 **Required Gmail API Scopes**

The connector requests these permissions:
- `https://www.googleapis.com/auth/gmail.readonly` - Read emails
- `https://www.googleapis.com/auth/userinfo.email` - Get user email address

## ⚡ **Connector Settings**

Default settings (can be customized):
- **sync_interval_minutes:** 60 (sync every hour)
- **max_emails_per_sync:** 100 
- **days_back:** 30 (index emails from last 30 days)
- **include_sent:** true (index sent emails)
- **include_drafts:** false (skip draft emails)

## 🎯 **What Gets Indexed**

The Gmail connector will index:
- ✅ Inbox emails
- ✅ Sent emails (if enabled)
- ✅ Email subject, sender, recipient, date
- ✅ Email body content (text and HTML)
- ✅ Attachment metadata (filenames, types)
- ❌ Attachment content (not downloaded)

## 🔄 **Multiple Gmail Accounts**

To connect multiple Gmail accounts:
```bash
# Account 1
curl -X GET "http://localhost:8792/api/v1/oauth/gmail/authorize?connector_name=gmail-personal"

# Account 2  
curl -X GET "http://localhost:8792/api/v1/oauth/gmail/authorize?connector_name=gmail-work"
```

Each account gets its own connector with separate OAuth tokens.