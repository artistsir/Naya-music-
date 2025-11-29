# AnonX Music Bot

A feature-rich Telegram Music Bot built with Pyrogram and PyTgCalls.

## Deployment

### Render.com (Recommended)
1. Fork this repository
2. Go to [Render](https://render.com)
3. Connect your GitHub repository
4. Create a new Web Service
5. Use the provided `render.yaml` configuration
6. Add your environment variables
7. Deploy!

### Environment Variables
Copy `.env.example` to `.env` and fill in your credentials:

```env
API_ID=123456
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
MONGO_URL=your_mongodb_url
LOGGER_ID=-1001234567890
OWNER_ID=123456789
SESSION1=your_session_string
