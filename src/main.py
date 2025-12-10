#!/usr/bin/env python3
# SwarmCloneBackend
# Copyright (c) 2025 SwarmClone <github.com/SwarmClone> and contributors

import uvicorn
from core.app_factory import app


def main() -> None:
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info",
        access_log=True,
        reload=False
    )


if __name__ == "__main__":
    main()