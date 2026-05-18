"""
前端服务器 - 多线程版

优化说明（2026-05-16）：
1. ThreadingHTTPServer → 支持多并发请求，一个请求卡住不影响其他人
2. 设置线程数上限，防止资源耗尽
"""
import os
import socket
import socketserver
from http.server import SimpleHTTPRequestHandler

# 配置
PORT = 3001
HOST = "0.0.0.0"
BACKEND_URL = "http://192.168.25.29:8000"


def get_local_ip():
    """获取本机局域网IP地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# 切换到frontend目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))


class GameHTTPRequestHandler(SimpleHTTPRequestHandler):
    """游戏页面请求处理器"""

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        """精简日志：只记录非静态文件的请求"""
        if len(args) >= 2 and args[1] == 200:
            return  # 不记录200静态资源请求
        super().log_message(format, *args)


class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """多线程HTTP服务器"""
    allow_reuse_address = True
    daemon_threads = True
    max_children = 30  # 最大同时处理线程数


if __name__ == "__main__":
    local_ip = get_local_ip()
    server = ThreadingHTTPServer((HOST, PORT), GameHTTPRequestHandler)
    print(f"\n{'=' * 50}")
    print(f"前端服务器已启动（多线程版）")
    print(f"{'=' * 50}")
    print(f"本地访问: http://localhost:{PORT}")
    print(f"局域网访问: http://{local_ip}:{PORT}")
    print(f"后端API: {BACKEND_URL}")
    print(f"最大并发连接: {ThreadingHTTPServer.max_children}")
    print(f"{'=' * 50}")
    print(f"按 Ctrl+C 停止服务器")
    print(f"{'=' * 50}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在关闭服务器...")
        server.server_close()
        print("服务器已关闭")
