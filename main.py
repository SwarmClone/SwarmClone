import time
from core.api_server import APIServer
from flask import Request

def root_page_handler(request: Request):

    host = request.host

    html_content = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SwarmClone Backend</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background: #f0f2f5;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .container {
                background: #ffffff;
                padding: 3rem 4rem;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                text-align: center;
            }
            h1 { font-size: 2.5rem; margin-bottom: 0.5rem; color: #000; }
            .subtitle { color: #666; margin-bottom: 2rem; }
            .status {
                display: inline-flex;
                align-items: center;
                gap: 0.5rem;
                background: #000;
                color: white;
                padding: 0.5rem 1rem;
                border-radius: 8px;
                margin-bottom: 2rem;
                font-size: 0.9rem;
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
        </style>
    </head>
    <body>
        <div class="container">
            <div class="status">Running</div>
            <h1>SwarmClone</h1>
            <p class="subtitle">Backend is running on """ + host + """</p>
            <p style="color: #999; font-size: 0.9rem;">It's time to start!</p>
        </div>
    </body>
    </html>
    """
    return html_content

def main():
    port = 4927
    api_server = APIServer(port=port)

    try:
        api_server.start()
        api_server.add_route("/", methods=["GET"], handler=root_page_handler)

        print(f"Server running at http://127.0.0.1:{port}/")
        print("Press Ctrl+C to stop...")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nReceived stop signal...")
        api_server.stop()
    except Exception as e:
        print(f"Error: {e}")
        api_server.stop()
        raise


if __name__ == '__main__':
    main()