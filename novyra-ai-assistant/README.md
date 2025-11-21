# Novyra AI Assistant

AI-powered chat assistant system for Novyra Marketing Agency.

## Vercel Deployment

This project is configured for deployment on Vercel.

### Environment Variables

Set these in your Vercel project settings:

- `SECRET_KEY`: Django secret key
- `DEBUG`: Set to `False` for production
- `ALLOWED_HOSTS`: Your Vercel domain (e.g., `your-app.vercel.app`)
- `DB_ENGINE`: `postgresql` (required for Vercel)
- `DB_NAME`: PostgreSQL database name
- `DB_USER`: PostgreSQL username
- `DB_PASSWORD`: PostgreSQL password
- `DB_HOST`: PostgreSQL host
- `DB_PORT`: PostgreSQL port (usually `5432`)
- `DEEPSEEK_API_KEY`: Your DeepSeek API key
- `CORS_ALLOWED_ORIGINS`: Comma-separated list of allowed origins

### Important Notes

- **Database**: SQLite will NOT work on Vercel. You must use PostgreSQL.
- **WebSockets**: Django Channels WebSockets may not work on Vercel's serverless environment. Consider using a different service for WebSocket support.
- **Static Files**: Static files should be served via Vercel's CDN or a separate service.

### Deployment

1. Connect your repository to Vercel
2. Set environment variables in Vercel dashboard
3. Deploy

The `vercel.json` file is already configured.
