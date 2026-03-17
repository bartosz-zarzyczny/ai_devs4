import http.server
import json
import os
import socket
import socketserver
from pathlib import Path

from electricity_solver import analyze_board, apply_plan, download_current_image, ensure_target_image, extract_meta_flag, rotate_tile

PORT = int(os.environ.get('PORT', '8080'))

# Set working directory to this file's directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))


class MyHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path.startswith('/api/download'):
            try:
                download_current_image(reset=False)
                self.write_json({'status': 'downloaded'})
            except Exception as error:
                self.write_json({'error': str(error)}, status=500)
            return

        if self.path.startswith('/api/reset'):
            try:
                download_current_image(reset=True)
                self.write_json({'status': 'reset'})
            except Exception as error:
                self.write_json({'error': str(error)}, status=500)
            return

        if self.path.startswith('/api/status'):
            current_path = Path('electricity.png')
            target_path = ensure_target_image()
            info = {
                'exists': current_path.exists(),
                'size': current_path.stat().st_size if current_path.exists() else 0,
                'target_exists': target_path.exists(),
                'target_size': target_path.stat().st_size if target_path.exists() else 0,
            }
            self.write_json(info)
            return

        if self.path.startswith('/api/analyze'):
            try:
                analysis = analyze_board().to_dict()
                self.write_json(analysis)
            except Exception as error:
                self.write_json({'error': str(error)}, status=500)
            return

        if self.path.startswith('/api/meta-flag'):
            try:
                self.write_json(extract_meta_flag())
            except Exception as error:
                self.write_json({'error': str(error)}, status=500)
            return

        return super().do_GET()

    def do_POST(self):
        if self.path == '/api/rotate':
            data = self.read_json_body()
            rotate = data.get('rotate')
            if not rotate:
                self.write_json({'error': 'missing rotate field'}, status=400)
                return

            try:
                result = rotate_tile(rotate)
                download_current_image()
                self.write_json({'result': result, 'analysis': analyze_board().to_dict()})
            except Exception as error:
                self.write_json({'error': str(error)}, status=500)
            return

        if self.path == '/api/apply-plan':
            try:
                result = apply_plan()
                self.write_json(result)
            except Exception as error:
                self.write_json({'error': str(error)}, status=500)
            return

        self.write_json({'error': 'not found'}, status=404)

    def read_json_body(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            return {}
        raw = self.rfile.read(content_length)
        try:
            return json.loads(raw.decode('utf-8'))
        except Exception:
            return {}

    def write_json(self, payload, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        try:
            self.wfile.write(json.dumps(payload).encode('utf-8'))
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return


class ReusableTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def choose_port(start_port: int, attempts: int = 20) -> int:
    for port in range(start_port, start_port + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(('127.0.0.1', port)) != 0:
                return port
    raise RuntimeError(f'Nie znaleziono wolnego portu w zakresie {start_port}-{start_port + attempts - 1}')


if __name__ == '__main__':
    selected_port = choose_port(PORT)
    with ReusableTCPServer(('', selected_port), MyHandler) as httpd:
        print(f"UI Server is running on http://localhost:{selected_port}")
        import webbrowser
        webbrowser.open(f"http://localhost:{selected_port}/ui.html")
        httpd.serve_forever()
