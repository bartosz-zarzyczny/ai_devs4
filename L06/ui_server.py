import http.server
import socketserver
import json
import os
import subprocess
import threading
import sys

PORT = 8080
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
        if self.path == '/api/prompt':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            prompt = "Return exactly 1 word: 'NEU' or 'DNG'. 'NEU' for safe items, tools, and ALL 'reactor' items. 'DNG' for weapons/ammo/hazardous. No explanations. ID:{id} Desc:{desc}"
            if os.path.exists("prompt.txt"):
                with open("prompt.txt", "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content: prompt = content
            self.wfile.write(json.dumps({"prompt": prompt}).encode('utf-8'))
            
        elif self.path == '/api/logs':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            debug = ""
            if os.path.exists("debug.txt"):
                with open("debug.txt", "r", encoding="utf-8") as f:
                    debug = f.read()
                    
            results = []
            if os.path.exists("results.json"):
                with open("results.json", "r", encoding="utf-8") as f:
                    try:
                        results = json.load(f)
                    except:
                        pass
                        
            out_logs = ""
            if os.path.exists("out.txt"):
                with open("out.txt", "r", encoding="utf-8") as f:
                    out_logs = f.read()
                    
            self.wfile.write(json.dumps({
                "debug": debug, 
                "results": results, 
                "out": out_logs
            }).encode('utf-8'))
            
        elif self.path == '/':
            self.path = '/index.html'
            return super().do_GET()
        else:
            return super().do_GET()

    def do_POST(self):
        if self.path == '/api/prompt':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            with open("prompt.txt", "w", encoding="utf-8") as f:
                f.write(data.get("prompt", ""))
                
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))

        elif self.path == '/api/run':
            def run_task():
                with open("out.txt", "w", encoding="utf-8") as outf:
                    subprocess.run([sys.executable, "task.py"], stdout=outf, stderr=subprocess.STDOUT)
                    
            if os.path.exists("debug.txt"): os.remove("debug.txt")
            if os.path.exists("results.json"): os.remove("results.json")
            if os.path.exists("out.txt"): os.remove("out.txt")
            
            t = threading.Thread(target=run_task)
            t.start()
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "started"}).encode('utf-8'))

if __name__ == '__main__':
    with socketserver.TCPServer(("", PORT), MyHandler) as httpd:
        print(f"API Server is running on http://localhost:{PORT}")
        import webbrowser
        webbrowser.open(f"http://localhost:{PORT}")
        httpd.serve_forever()
