import http.server
import socketserver
import json
import os
import base64
import time
import threading
from urllib.parse import urlparse, parse_qs

PORT = 8000
DB_FILE = "database.json"
UPLOAD_DIR = "uploads"
VIDEO_DIR = "video"

# 自动创建必要的文件夹
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

# 初始化数据库
if not os.path.exists(DB_FILE):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump({}, f)

# 核心黑科技：文件读写锁 (防止百人同时交卷导致数据损坏)
db_lock = threading.Lock()

class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        # 1. 处理图片独立上传
        if self.path == '/api/upload':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                b64_str = data.get('image', '')
                
                if b64_str.startswith('data:image'):
                    header, b64_str = b64_str.split(',', 1)
                    ext = header.split('/')[1].split(';')[0]
                else:
                    ext = 'png'
                
                img_data = base64.b64decode(b64_str)
                filename = f"img_{int(time.time() * 1000)}_{threading.get_native_id()}.{ext}"
                filepath = os.path.join(UPLOAD_DIR, filename)
                
                with open(filepath, 'wb') as f:
                    f.write(img_data)
                    
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'url': f'/{UPLOAD_DIR}/{filename}'}).encode())
            except Exception as e:
                print(f"❌ 图片上传失败: {e}")
                self.send_response(500)
                self.end_headers()
            return

        # 2. 处理 JSON 数据的保存 (已修复并发写入逻辑)
        if self.path == '/api/submit':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                req = json.loads(post_data.decode('utf-8'))
                action = req.get('action')  # 获取前端的暗号
                key = req.get('key')
                new_data = req.get('data')

                # 加锁！严格排队写入数据库
                with db_lock:
                    with open(DB_FILE, 'r', encoding='utf-8') as f:
                        db = json.load(f)
                    
                    if action == 'submit_paper':
                        # 🚀 核心修复：安全追加模式，防止百人并发互相覆盖
                        if 'studentAnswers' not in db or not isinstance(db['studentAnswers'], list):
                            db['studentAnswers'] = []
                        db['studentAnswers'].append(new_data)
                    else:
                        # 正常覆盖模式 (后台修改配置用)
                        if key is not None:
                            db[key] = new_data
                    
                    with open(DB_FILE, 'w', encoding='utf-8') as f:
                        json.dump(db, f, ensure_ascii=False, indent=2)
                        
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'success'}).encode())
            except Exception as e:
                print(f"❌ 数据保存失败: {e}")
                self.send_response(500)
                self.end_headers()
            return

    def do_GET(self):
        # 3. 处理数据的读取
        if self.path.startswith('/api/data'):
            query = parse_qs(urlparse(self.path).query)
            key = query.get('key', [None])[0]
            
            with db_lock:
                with open(DB_FILE, 'r', encoding='utf-8') as f:
                    db = json.load(f)
                    
            data = db.get(key)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
            return
            
        return super().do_GET()

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

if __name__ == '__main__':
    server = ThreadedHTTPServer(('0.0.0.0', PORT), RequestHandler)
    print(f"🚀 服务器已启动！(企业级多线程防爆卡模式)")
    print(f"📁 图片将独立存储于: ./{UPLOAD_DIR}/")
    print(f"👉 本机管理入口: http://localhost:{PORT}/admin.html")
    server.serve_forever()