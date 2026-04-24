from __future__ import annotations

import argparse
import http.server
import os
import socketserver
import webbrowser
from pathlib import Path


WEB_ROOT = Path(__file__).resolve().parent / "rehab_web"


def main() -> None:
    parser = argparse.ArgumentParser(description="启动关节康复网站本地服务")
    parser.add_argument("--port", type=int, default=8000, help="本地端口，默认 8000")
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="只启动服务，不自动打开浏览器",
    )
    args = parser.parse_args()

    if not WEB_ROOT.exists():
        raise FileNotFoundError(f"找不到网页目录：{WEB_ROOT}")

    os.chdir(WEB_ROOT)
    handler = http.server.SimpleHTTPRequestHandler
    socketserver.ThreadingTCPServer.allow_reuse_address = True

    with socketserver.ThreadingTCPServer(("127.0.0.1", args.port), handler) as server:
        url = f"http://127.0.0.1:{args.port}/"
        print(f"康复网站已启动：{url}")
        print("按 Ctrl+C 停止服务。")
        if not args.no_open:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n服务已停止。")


if __name__ == "__main__":
    main()
