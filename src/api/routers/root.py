from fastapi import APIRouter
from fastapi.responses import HTMLResponse

roots = APIRouter()

@roots.get("/", response_class=HTMLResponse)
def root():
    # 虽然没有什么用但我觉得很酷
    return """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SwarmClone Backend</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                background: #f0f2f5;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                color: rgba(0, 0, 0, 0.88);
            }

            .container {
                background: #ffffff;
                padding: 3rem 4rem;
                border-radius: 8px;
                border: 1px solid #f0f0f0;
                box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03), 
                            0 4px 12px 0 rgba(0, 0, 0, 0.05);
                text-align: center;
                max-width: 600px;
                width: 90%;
            }

            h1 {
                font-size: 2.5rem;
                margin-bottom: 0.5rem;
                color: rgba(0, 0, 0, 0.88);
                font-weight: 600;
                letter-spacing: -0.5px;
            }

            .subtitle {
                color: rgba(0, 0, 0, 0.45);
                margin-bottom: 2rem;
                font-size: 1.1rem;
            }

            .status {
                display: inline-flex;
                align-items: center;
                gap: 0.5rem;
                background: rgba(20, 20, 20, 0.88);
                color: white;
                padding: 0.5rem 1rem;
                border-radius: 8px;
                font-size: 0.9rem;
                margin-bottom: 2rem;
                font-weight: 500;
            }

            .status::before {
                content: "";
                width: 8px;
                height: 8px;
                background: #08d983;
                border-radius: 50%;
                animation: pulse 2s infinite;
            }

            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.4; }
            }

            .divider {
                height: 1px;
                background: linear-gradient(90deg, transparent, #f0f0f0, transparent);
                margin: 2rem 0;
            }

            .section-title {
                color: rgba(0, 0, 0, 0.45);
                font-size: 0.85rem;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                margin-bottom: 1rem;
                font-weight: 500;
            }

            .doc-links {
                display: flex;
                gap: 0.75rem;
                justify-content: center;
                flex-wrap: wrap;
            }

            .doc-link {
                display: inline-flex;
                align-items: center;
                gap: 0.5rem;
                padding: 0.6rem 1.2rem;
                border-radius: 6px;
                text-decoration: none;
                font-weight: 500;
                transition: all 0.2s;
                font-size: 0.95rem;
                border: 1px solid transparent;
                cursor: pointer;
            }

            .doc-link.primary {
                background: #000000;
                color: #ffffff;
                border-color: #000000;
            }

            .doc-link.primary:hover {
                background: #262626;
                border-color: #262626;
            }

            .doc-link.secondary {
                background: #ffffff;
                color: rgba(0, 0, 0, 0.88);
                border-color: #d9d9d9;
            }

            .doc-link.secondary:hover {
                color: #000000;
                border-color: #000000;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="status">Running</div>
            <h1>SwarmClone</h1>
            <p class="subtitle">SwarmClone backend is running on your device!</p>

            <div class="divider"></div>

            <div class="section-title">API Doc</div>
            <div class="doc-links">
                <a href="/docs" class="doc-link primary" target="_blank">
                    <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
                    </svg>
                    Swagger UI
                </a>
                <a href="/redoc" class="doc-link secondary" target="_blank">
                    <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
                    </svg>
                    ReDoc
                </a>
            </div>
        </div>
    </body>
    </html>
    """