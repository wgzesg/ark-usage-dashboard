# ARK Usage Dashboard

A web dashboard to track and visualize your Volc Engine ARK API token usage. Built with FastAPI and deployed on Vercel.

## Features

- 📊 Beautiful web UI with token usage charts
- 📈 Daily token and request breakdown
- 💾 Local data caching (persists across requests)
- 🔄 Auto-refresh from API every 5 minutes
- 📥 Export data as JSON
- ☁️ Deploy to Vercel with one click

## Prerequisites

- Python 3.9 or higher
- [Volc Engine ARK API credentials](https://www.volcengine.com/docs/6469) (Access Key ID and Secret Access Key)
- Node.js (for Vercel CLI)

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/wgzesg/ark-usage-dashboard.git
cd ark-usage-dashboard
```

### 2. Install Dependencies

```bash
# Using uv (recommended# Or using)
uv sync

 pip
pip install -r requirements.txt
```

**If using uv**, it will automatically read from `pyproject.toml` and create a virtual environment.

### 3. Configure Environment Variables

Set environment variables before running:

```bash
# Linux/macOS
export ARK_AK=your_volc_engine_access_key_id
export ARK_SK=your_volc_engine_secret_access_key

# Windows (PowerShell)
$env:ARK_AK="your_volc_engine_access_key_id"
$env:ARK_SK="your_volc_engine_secret_access_key"
```

**How to get your ARK credentials:**

1. Go to [Volc Engine Console](https://console.volcengine.com/)
2. Navigate to **Access Control** → **IAM** → **Users** (or **Access Keys**)
3. Create a new Access Key or use an existing one
4. Copy the **Access Key ID** (AK) and **Secret Access Key** (SK)

### 4. Run Locally

**Option A: Using Vercel Dev (recommended - matches production)**
```bash
npx vercel dev
```

**Option B: Using uvicorn**
```bash
uvicorn app:app --reload --port 8000
```

### 5. Open in Browser

Visit: http://localhost:3000 (vercel dev) or http://localhost:8000 (uvicorn)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard web UI |
| `/usage?days=N` | GET | Get usage for last N days (auto-fetches from API if ≤30 days) |
| `/export` | GET | Export all stored data as JSON |
| `/health` | GET | Health check |

### Usage Examples

```bash
# Get last 7 days usage
curl http://localhost:3000/usage?days=7

# Get last 30 days (will fetch fresh data from API)
curl http://localhost:3000/usage?days=30

# Get last 90 days (loads from local cache only)
curl http://localhost:3000/usage?days=90

# Export all data
curl http://localhost:3000/export

# Health check
curl http://localhost:3000/health
```

## Deployment to Vercel

### Option 1: Deploy from GitHub (Recommended)

1. **Push your code to GitHub:**
   ```bash
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

2. **Import to Vercel:**
   - Go to [vercel.com/new](https://vercel.com/new)
   - Click "Import Project"
   - Select your GitHub repository

3. **Configure Environment Variables:**
   - In Vercel dashboard, go to **Settings** → **Environment Variables**
   - Add these two variables:

   | Name | Value |
   |------|-------|
   | `ARK_AK` | your Access Key ID |
   | `ARK_SK` | your Secret Access Key |

4. **Deploy:**
   - Click "Deploy"
   - Wait ~1 minute for deployment to complete
   - Your app is live at `https://your-project.vercel.app`

### Option 2: Deploy with Vercel CLI

```bash
# Install Vercel CLI
npm i -g vercel

# Login
vercel login

# Deploy
vercel --prod
```

Follow the prompts. Make sure to add the environment variables in the Vercel web interface after deployment.

## How It Works

1. **Unified API Endpoint**: The `/usage` endpoint handles everything
   - For requests ≤30 days: Fetches fresh data from Volc Engine ARK API and stores locally
   - For requests >30 days: Loads from local cache only (no API call)

2. **Local Caching**: 
   - Local development: Data is stored in `~/.ark_usage_data/usage_data.json`
   - Vercel deployment: Data is stored in `/tmp` (ephemeral - data is lost on each cold start)

3. **Data Merging**: When fetching new data, it's merged with existing data. Newer data takes precedence for the same date.

## Project Structure

```
ark-usage-dashboard/
├── app.py              # Main FastAPI application (entrypoint)
├── static/             # Frontend assets
│   ├── index.html      # Dashboard HTML
│   ├── styles.css      # Styles
│   └── app.js          # Frontend JavaScript
├── requirements.txt    # Python dependencies
├── vercel.json         # Vercel configuration
└── README.md           # This file
```

## Dependencies

Listed in `pyproject.toml`:

- `fastapi` - Web framework
- `pydantic` - Data validation
- `requests` - HTTP client for ARK API

Install all with: `uv sync`

## Troubleshooting

### "No module named 'app'" error

Make sure you're in the project root directory and running:
```bash
uvicorn app:app --reload --port 8000
```

### API errors or empty data

1. Verify your ARK_AK and ARK_SK are correct
2. Check that your Volc Engine account has ARK API access
3. Ensure the credentials have proper permissions
4. Check the `/health` endpoint to verify credentials are loaded

### Charts not showing

- Open browser developer console (F12)
- Check for JavaScript errors
- Verify the `/usage` endpoint returns data: `curl http://localhost:3000/usage`

### Vercel deployment fails

Make sure your `vercel.json` is configured correctly:

```json
{
  "builds": [
    {
      "src": "app.py",
      "use": "@vercel/python",
      "config": {
        "installCommand": "pip install -r requirements.txt"
      }
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "/app.py"
    }
  ]
}
```

## License

MIT License - feel free to use and modify!

## Credits

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Python web framework
- [Chart.js](https://www.chartjs.org/) - Beautiful charts
- [Vercel](https://vercel.com/) - Cloud platform
