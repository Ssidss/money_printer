#!/usr/bin/env python3
"""
Money Printer — 股票自動分析系統
用法：
  conda activate money_printer
  python main.py [--host HOST] [--port PORT] [--no-reload]
"""

import argparse
import logging
import sys

import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def main():
    parser = argparse.ArgumentParser(description="Money Printer 股票分析系統")
    parser.add_argument("--host", default="0.0.0.0", help="監聽 host (預設 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="監聽 port (預設 8000)")
    parser.add_argument("--no-reload", action="store_true", help="關閉熱重載（production 用）")
    args = parser.parse_args()

    print("""
╔══════════════════════════════════════╗
║   💰 Money Printer v2  啟動中...     ║
║   後端 API: http://localhost:8000    ║
║   API 文件: http://localhost:8000/docs ║
║   前端:     http://localhost:3000    ║
╚══════════════════════════════════════╝
    """)

    uvicorn.run(
        "backend.app.main:app",
        host=args.host,
        port=args.port,
        reload=not args.no_reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
