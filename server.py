import http.server
import socketserver
import json
import os
import base64
import time
import threading
import cgi
import shutil
from urllib.parse import urlparse, parse_qs

PORT = 8000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "database.json")
UPLOAD_URL = "uploads"
VIDEO_URL = "video"
PDF_URL = "pdf"
UPLOAD_DIR = os.path.join(BASE_DIR, UPLOAD_URL)
VIDEO_DIR = os.path.join(BASE_DIR, VIDEO_URL)
PDF_DIR = os.path.join(BASE_DIR, PDF_URL)
MAX_VIDEO_BYTES = 200 * 1024 * 1024
MAX_PDF_BYTES = 200 * 1024 * 1024
ALLOWED_VIDEO_EXTS = {"mp4", "webm", "mov", "ogg"}
ALLOWED_VIDEO_MIME = {"video/mp4", "video/webm", "video/quicktime", "video/ogg"}

# 自动创建必要的文件夹
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)

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
                self.wfile.write(json.dumps({'url': f'/{UPLOAD_URL}/{filename}'}).encode())
            except Exception as e:
                print(f"❌ 图片上传失败: {e}")
                self.send_response(500)
                self.end_headers()
            return

        # 1.5 处理视频上传 (自学成才)
        if self.path == '/api/upload_video':
            try:
                content_length = int(self.headers.get('Content-Length', '0'))
                if content_length <= 0:
                    self.send_response(411)
                    self.end_headers()
                    return
                if content_length > MAX_VIDEO_BYTES:
                    self.send_response(413)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': 'file_too_large'}).encode())
                    return

                content_type = self.headers.get('Content-Type', '')
                if not content_type.startswith('multipart/form-data'):
                    self.send_response(400)
                    self.end_headers()
                    return

                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': content_type}
                )
                if 'video' not in form:
                    self.send_response(400)
                    self.end_headers()
                    return

                file_item = form['video']
                if not file_item.file or not file_item.filename:
                    self.send_response(400)
                    self.end_headers()
                    return

                original_name = os.path.basename(file_item.filename)
                name_root, ext = os.path.splitext(original_name)
                ext = ext.lower().lstrip('.') or 'mp4'
                safe_root = (name_root.strip() or 'video').replace(' ', '_')
                safe_name = f"{safe_root}_{int(time.time() * 1000)}.{ext}"
                filepath = os.path.join(VIDEO_DIR, safe_name)
                with open(filepath, 'wb') as f:
                    shutil.copyfileobj(file_item.file, f)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'url': f'{VIDEO_URL}/{safe_name}'}).encode())
            except Exception as e:
                print(f"❌ 视频上传失败: {e}")
                self.send_response(500)
                self.end_headers()
            return

        # 1.6 处理 PDF 上传
        if self.path == '/api/upload_pdf':
            try:
                content_length = int(self.headers.get('Content-Length', '0'))
                if content_length <= 0:
                    self.send_response(411)
                    self.end_headers()
                    return
                if content_length > MAX_PDF_BYTES:
                    self.send_response(413)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': 'file_too_large'}).encode())
                    return

                content_type = self.headers.get('Content-Type', '')
                if not content_type.startswith('multipart/form-data'):
                    self.send_response(400)
                    self.end_headers()
                    return

                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': content_type}
                )
                if 'pdf' not in form:
                    self.send_response(400)
                    self.end_headers()
                    return

                file_item = form['pdf']
                if not file_item.file or not file_item.filename:
                    self.send_response(400)
                    self.end_headers()
                    return

                original_name = os.path.basename(file_item.filename)
                name_root, ext = os.path.splitext(original_name)
                ext = ext.lower().lstrip('.') or 'pdf'
                safe_root = (name_root.strip() or 'pdf').replace(' ', '_')
                safe_name = f"{safe_root}_{int(time.time() * 1000)}.{ext}"
                filepath = os.path.join(PDF_DIR, safe_name)
                with open(filepath, 'wb') as f:
                    shutil.copyfileobj(file_item.file, f)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'url': f'{PDF_URL}/{safe_name}'}).encode())
            except Exception as e:
                print(f"❌ PDF 上传失败: {e}")
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
        # 2.5 列出视频文件
        if self.path.startswith('/api/videos'):
            try:
                videos = []
                for name in os.listdir(VIDEO_DIR):
                    if name.startswith('.'):
                        continue
                    path = os.path.join(VIDEO_DIR, name)
                    if not os.path.isfile(path):
                        continue
                    stat = os.stat(path)
                    videos.append({
                        'name': name,
                        'size': stat.st_size,
                        'mtime': stat.st_mtime
                    })
                videos.sort(key=lambda v: v['mtime'], reverse=True)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(videos).encode('utf-8'))
            except Exception as e:
                print(f"❌ 视频列表读取失败: {e}")
                self.send_response(500)
                self.end_headers()
            return

        # 2.6 列出 PDF 文件
        if self.path.startswith('/api/pdfs'):
            try:
                pdfs = []
                for name in os.listdir(PDF_DIR):
                    if name.startswith('.'):
                        continue
                    path = os.path.join(PDF_DIR, name)
                    if not os.path.isfile(path):
                        continue
                    stat = os.stat(path)
                    pdfs.append({
                        'name': name,
                        'size': stat.st_size,
                        'mtime': stat.st_mtime
                    })
                pdfs.sort(key=lambda v: v['mtime'], reverse=True)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(pdfs).encode('utf-8'))
            except Exception as e:
                print(f"❌ PDF 列表读取失败: {e}")
                self.send_response(500)
                self.end_headers()
            return

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
    print(f"📄 PDF 将独立存储于: ./{PDF_DIR}/")
    print(f"👉 本机管理入口: http://localhost:{PORT}/admin.html")
    server.serve_forever()
