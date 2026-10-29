# WeCom Bot Setup Guide

## Step 1: Create Your WeCom Bot

1. Go to **https://work.weixin.qq.com/**
2. Log in with your WeCom account
3. Go to **应用管理** (App Management)
4. Click **创建应用** (Create Application)
5. Fill in:
   - **应用名称**: CASHFLOW Banking Bot
   - **应用图标**: Upload an icon
   - **可见范围**: Select your department/users
6. Click **提交** (Submit)

## 2. Get Your Bot Credentials

In the app management page, click on your new app to see:

| Field | Where to Find | Example Value |
|-------|---------------|---------------|
| **Agent ID** | Under "基本信息" → **AgentId** | `1000005` |
| **Secret** | Click **查看密钥** next to Secret | `xxxxx-xxxxx-xxxxx` |

## 3. Get Your User ID

In WeCom app:
1. Go to **通讯录** (Contacts)
2. Click on your profile
3. Copy your **企业微信ID** (WeCom ID)

## 4. Update .env File

Edit `app/.env` and add:

```env
WECOM_BOT_ID=1000005
WECOM_BOT_SECRET=your_actual_secret_here
WECOM_BOT_TOKEN=your_optional_token
WECOM_ADMIN_IDS=your_wecom_user_id
```

Replace the values with your actual credentials.

## 5. Restart the Backend

```bash
cd D:\Downloads\CASHFLOW-emmanuel(1)\CASHFLOW-emmanuel
& "D:\Downloads\CASHFLOW-emmanuel(1)\CASHFLOW-emmanuel\banking-agent\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 6. Test the Bot

1. Open **企业微信** (WeChat Work)
2. Search for your bot by its name
3. Send: `转账 ¥600 给 测试用户`
4. The bot should respond with processing status

## Troubleshooting

| Problem | Solution |
|---------|-----------|
| Bot not responding | Check WECOM_BOT_ID and WECOM_BOT_SECRET are correct |
| "Bot not configured" error | Make sure both WECOM_BOT_ID and WECOM_BOT_SECRET are set in .env |
| Admin commands don't work | Add your WeCom user ID to WECOM_ADMIN_IDS |
| Bot not receiving messages | Make sure you added the bot to your WeCom contacts |
