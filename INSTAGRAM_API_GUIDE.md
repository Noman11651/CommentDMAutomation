# Instagram Comment-to-DM Automation — API Setup Guide

## Architecture

```
Instagram Comment
      ↓
Meta Webhook → /webhook (FastAPI on Vercel)
      ↓
Comment Reply  →  graph.facebook.com/{comment_id}/replies  (User token)
DM / Flow      →  graph.facebook.com/me/messages           (Page token)
```

---

## Two Tokens Required

| Token | Env Var | Used For | Expires |
|-------|---------|----------|---------|
| Long-lived User token | `INSTAGRAM_ACCESS_TOKEN` | Comment replies | Never (if generated correctly) |
| Page token | `INSTAGRAM_PAGE_TOKEN` | DMs via /me/messages | Never |

**Why two tokens:**
- `/{comment_id}/replies` requires a **User access token** with `instagram_basic` + `instagram_manage_comments`
- `/me/messages` requires a **Page access token**
- Page tokens are rejected by the comment replies endpoint (error 100/33)
- User tokens are rejected by the messaging endpoint (error 190)

---

## Endpoints

| Operation | Base URL | Path | Token |
|-----------|----------|------|-------|
| Reply to comment | `graph.facebook.com/v21.0` | `/{comment_id}/replies` | User token |
| Send DM | `graph.facebook.com/v21.0` | `/me/messages` | Page token |
| Get media list | `graph.facebook.com/v21.0` | `/me/media` | User token |
| Get follow status | `graph.facebook.com/v21.0` | `/{user_id}` | User token |

**Do NOT use `graph.instagram.com` for business account operations.** That endpoint requires Instagram Login OAuth tokens (different flow). Business account automation goes through `graph.facebook.com`.

---

## Token Generation (Step by Step)

### Step 1 — Get Short-lived User Token via Graph API Explorer

1. Go to [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. Select your app (e.g. "Noman Automates")
3. Select **User Token** in the dropdown
4. Add ALL these permissions:
   - `instagram_basic`
   - `instagram_manage_comments`
   - `instagram_manage_messages`
   - `instagram_manage_insights`
   - `instagram_content_publish`
   - `pages_show_list`
   - `pages_read_engagement`
   - `business_management`
   - `ads_management`
   - `ads_read`
5. Click **Generate Access Token** → complete Facebook login → grant all permissions

> **Note:** `ads_management` / `ads_read` are required when your Page role was granted via Business Manager. Without them, comment replies return error 100/33.

### Step 2 — Exchange for Long-lived User Token (Never Expires)

Run this in terminal (replace `YOUR_APP_SECRET`):

```bash
curl "https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=36021795997419817&client_secret=YOUR_APP_SECRET&fb_exchange_token=SHORT_LIVED_TOKEN_HERE"
```

- App ID: `36021795997419817`
- App Secret: App Dashboard → Settings → Basic → App Secret (click Show)
- Result: `{"access_token": "EAHZ...", "token_type": "bearer"}` with no `expires_in` = never expires

> **Warning:** Do NOT run this exchange in Graph API Explorer — it replaces the token with a session-scoped short-lived one. Always use curl/terminal.

### Step 3 — Verify Token

1. Go to [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/)
2. Paste the token → Debug
3. Confirm:
   - **Type:** User
   - **Expires:** Never
   - **Scopes include:** `instagram_basic`, `instagram_manage_comments`, `ads_management`

### Step 4 — Get Never-Expiring Page Token

Run in terminal (using the long-lived user token from Step 2):

```bash
curl "https://graph.facebook.com/v25.0/me/accounts?access_token=LONG_LIVED_USER_TOKEN_HERE"
```

Find your Page in the result → copy its `access_token` field.

Verify in debugger:
- **Type:** Page
- **Expires:** Never

> **Do NOT use Graph API Explorer** to call `/me/accounts` — it injects its own short-lived session token even if you put the long-lived token in the URL, resulting in a Page token that expires in 1 hour.

---

## Vercel Environment Variables

| Variable | Value | Notes |
|----------|-------|-------|
| `INSTAGRAM_ACCESS_TOKEN` | Long-lived User token | Comment replies |
| `INSTAGRAM_PAGE_TOKEN` | Never-expiring Page token | DMs |
| `SUPABASE_URL` | `https://xxx.supabase.co` | Required — missing = 500 on every webhook |
| `SUPABASE_SERVICE_ROLE_KEY` | `eyJ...` | Supabase auth |
| `VERIFY_TOKEN` | Your webhook verify string | Meta webhook verification |
| `IG_BUSINESS_ACCOUNT_ID` | Instagram Business Account numeric ID | Prevents bot replying to itself |

After adding/changing env vars → **manually redeploy** (Vercel does not auto-redeploy on env changes).

---

## Common Errors and Fixes

### Error 190 — "Invalid OAuth access token - Cannot parse access token"

**Cause:** Token is empty, wrong type, or has whitespace.

**Fixes:**
1. Token not set in Vercel env vars → add it
2. Token is a System User token → System User tokens are rejected by Instagram messaging endpoints. Use User token or Page token instead.
3. Whitespace in token → code calls `.strip()` on load (already fixed in `config.py`)
4. Using `graph.instagram.com` for messaging → use `graph.facebook.com` instead

### Error 100/33 — "Object does not exist / missing permissions"

**Cause:** Wrong token type for the endpoint, or missing scopes.

**Fixes:**
1. Comment replies called with Page token → use User token instead
2. Missing `instagram_basic` scope → regenerate token with it
3. Missing `ads_management` / `ads_read` → required when Page role granted via Business Manager
4. Using `graph.instagram.com` for business comment replies → use `graph.facebook.com`

### Error 101 — "Cannot get application info"

**Cause:** Wrong `client_secret` in token exchange URL.

**Fix:** App Dashboard → Settings → Basic → App Secret. Note: there are two secrets — use the **main app secret**, not the Instagram product secret.

### Supabase Timeout (500 on webhook)

**Cause:** Supabase free tier pauses after inactivity. First request takes >15s to wake up.

**Fix:** Timeout reduced to 8s with fallback to local file config (already in `config_manager.py`). Upgrade to paid Supabase tier to avoid cold starts.

---

## Token Expiry Summary

| Token Type | Expires | How Generated |
|------------|---------|---------------|
| Short-lived User (Graph Explorer) | 1 hour | Explorer "Generate Access Token" |
| Long-lived User | Never* | curl exchange with app secret |
| Page (from short-lived user) | 1 hour | `/me/accounts` via Explorer |
| Page (from long-lived user) | Never | `/me/accounts` via curl |
| System User | Never | Business Manager system users |

*Long-lived user tokens technically say "never" but are invalidated if the user changes their Facebook password or revokes app access.

---

## App Requirements

- App must be in **Live mode** (not Development) for Page tokens to be permanent
- App must have `instagram_manage_comments` and `instagram_manage_messages` approved
- Instagram Business Account must be connected to a Facebook Page
- Facebook Page must be connected to the app

---

## Token Refresh Strategy

Long-lived user tokens can be refreshed before expiry (if they do expire):

```bash
curl "https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=CURRENT_LONG_LIVED_TOKEN"
```

Run this every 30-45 days to keep the token alive. Update `INSTAGRAM_ACCESS_TOKEN` in Vercel after refresh.
