from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse

app = FastAPI()


@app.get("/")
async def root():
    """Root endpoint"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ARK Usage Dashboard</title>
        <style>
            body { font-family: -apple-system, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            h1 { color: #667eea; }
            a { display: inline-block; margin-right: 15px; padding: 10px 20px; 
                  background: #667eea; color: white; text-decoration: none; border-radius: 8px; }
            a:hover { background: #5568d3; }
        </style>
    </head>
    <body>
        <h1>ARK Usage Dashboard</h1>
        <p>FastAPI server running on Vercel</p>
        <p>
            <a href="/health">Health Check</a>
            <a href="/usage?days=7">Get Usage</a>
        </p>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "ark-usage-dashboard", "framework": "fastapi"}


@app.get("/usage")
async def get_usage(days: int = 7):
    """Get usage data"""
    return {
        "success": True,
        "message": "FastAPI endpoint working - ARK implementation pending",
        "days": days,
        "data": {
            "total_tokens": 0,
            "total_requests": 0,
            "daily_breakdown": []
        }
    }
