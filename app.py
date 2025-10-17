import os
from flask import Flask, Response, jsonify
from flask_cors import CORS
import time
import json
import random
import threading
import psutil
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Performance tracking variables
sse_connections = 0
sse_messages_sent = 0   
sse_start_time = time.time()

server_running = False

# Hàm này tạo ra dữ liệu ngẫu nhiên mỗi giây để gửi đến client.
def generate_data():
    global sse_messages_sent
    while True:
        # Generate random data
        data = {
            "value": random.randint(0, 100),
            "timestamp": time.strftime("%H:%M:%S"),
            "message_id": sse_messages_sent + 1,
            "send_time": time.time()
        }
        sse_messages_sent += 1
        yield f"data: {json.dumps(data)}\n\n"
        time.sleep(1)
# Hàm này thu thập và gửi đi các chỉ số hiệu năng của server mỗi 2 giây.
def generate_performance_data():
    global sse_connections, sse_messages_sent, sse_start_time
    while True:
        # Get system metrics
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        
        uptime = time.time() - sse_start_time
        throughput = sse_messages_sent / uptime if uptime > 0 else 0
        
        performance_data = {
            "type": "performance",
            "connections": sse_connections,
            "messages_sent": sse_messages_sent,
            "throughput": round(throughput, 2),
            "cpu_usage": cpu_percent,
            "memory_usage": memory.percent,
            "uptime": round(uptime, 2),
            "timestamp": time.strftime("%H:%M:%S")
        }
        yield f"data: {json.dumps(performance_data)}\n\n"
        time.sleep(2)
# Client đăng ký nhận luồng dữ liệu ngẫu nhiên.
@app.route("/stream")
def stream():
    global sse_connections
    sse_connections += 1
    print(f"SSE Client connected. Total connections: {sse_connections}")
    
    def event_stream():
        global sse_connections
        try:
            # Gửi retry time để client tự động reconnect sau 3 giây
            yield "retry: 3000\n\n"
            for data in generate_data():
                yield data
        except GeneratorExit:
            # Client đã ngắt kết nối
            pass
        except Exception as e:
            print(f"SSE Error: {e}")
        finally:
            sse_connections -= 1
            print(f"SSE Client disconnected. Total connections: {sse_connections}")
    
    response = Response(event_stream(), mimetype="text/event-stream")
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['X-Accel-Buffering'] = 'no'  # Disable Nginx buffering
    return response
# cung cấp luồng dữ liệu về hiệu năng của server.
@app.route("/performance")
def performance_stream():
    def performance_event_stream():
        try:
            # Gửi retry time cho performance stream
            yield "retry: 5000\n\n"
            for data in generate_performance_data():
                yield data
        except GeneratorExit:
            pass
        except Exception as e:
            print(f"Performance SSE Error: {e}")
    
    response = Response(performance_event_stream(), mimetype="text/event-stream")
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['X-Accel-Buffering'] = 'no'
    return response

@app.route("/stats")
def get_stats():
    global sse_connections, sse_messages_sent, sse_start_time
    uptime = time.time() - sse_start_time
    return jsonify({
        "server_type": "SSE",
        "connections": sse_connections,
        "messages_sent": sse_messages_sent,
        "uptime": round(uptime, 2),
        "throughput": round(sse_messages_sent / uptime if uptime > 0 else 0, 2),
        "current_value": random.randint(0, 100),
        "timestamp": time.strftime("%H:%M:%S"),
        "fallback_mode": True
    })

@app.route("/fallback")
def fallback_endpoint():
    """Endpoint fallback khi SSE EventSource thất bại"""
    global sse_messages_sent
    
    # Tăng message count cho fallback
    sse_messages_sent += 1
    
    return jsonify({
        "value": random.randint(0, 100),
        "timestamp": time.strftime("%H:%M:%S"),
        "message_id": sse_messages_sent,
        "send_time": time.time(),
        "fallback": True,
        "message": "Dữ liệu từ SSE fallback endpoint"
    })

@app.route("/fallback/polling")
def fallback_polling():
    """Endpoint polling cho SSE fallback với nhiều message"""
    global sse_messages_sent
    messages = []
    
    # Tạo 5 message mới cho mỗi lần polling
    for i in range(5):
        sse_messages_sent += 1
        messages.append({
            "value": random.randint(0, 100),
            "timestamp": time.strftime("%H:%M:%S"),
            "message_id": sse_messages_sent,
            "send_time": time.time(),
            "fallback": True
        })
        time.sleep(0.2)  # Delay nhỏ giữa các message
    
    return jsonify({
        "messages": messages,
        "count": len(messages),
        "fallback_type": "polling"
    })

@app.route("/fallback/stream")
def fallback_stream():
    """HTTP stream fallback khi EventSource không hoạt động"""
    def generate_fallback_stream():
        global sse_messages_sent
        for i in range(10):  # Gửi 10 message rồi đóng
            sse_messages_sent += 1
            data = {
                "value": random.randint(0, 100),
                "timestamp": time.strftime("%H:%M:%S"),
                "message_id": sse_messages_sent,
                "send_time": time.time(),
                "fallback": True,
                "stream_position": i + 1
            }
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(1)
        
        # Gửi message kết thúc
        yield f"data: {json.dumps({'end': True, 'message': 'Fallback stream ended'})}\n\n"
    
    return Response(generate_fallback_stream(), 
                   mimetype="text/plain",
                   headers={
                       'X-Fallback-Mode': 'true',
                       'Cache-Control': 'no-cache'
                   })

@app.route("/health")
def health_check():
    """Health check endpoint - kiểm tra tình trạng server"""
    return jsonify({
        "status": "healthy",
        "server": "SSE",
        "timestamp": time.strftime("%H:%M:%S"),
        "connections": sse_connections,
        "messages_sent": sse_messages_sent,
        "uptime": round(time.time() - sse_start_time, 2),
        "fallback_available": True
    })

@app.route("/fallback/performance")
def fallback_performance():
    """Fallback cho performance monitoring"""
    global sse_connections, sse_messages_sent, sse_start_time
    
    # Lấy system metrics
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    uptime = time.time() - sse_start_time
    throughput = sse_messages_sent / uptime if uptime > 0 else 0
    
    return jsonify({
        "type": "performance",
        "connections": sse_connections,
        "messages_sent": sse_messages_sent,
        "throughput": round(throughput, 2),
        "cpu_usage": cpu_percent,
        "memory_usage": memory.percent,
        "uptime": round(uptime, 2),
        "timestamp": time.strftime("%H:%M:%S"),
        "fallback": True,
        "mode": "HTTP polling"
    })

@app.errorhandler(404)
def not_found(error):
    """Custom 404 handler với thông tin fallback"""
    return jsonify({
        "error": "Endpoint không tìm thấy",
        "fallback_endpoints": [
            "/fallback",
            "/fallback/polling", 
            "/fallback/stream",
            "/fallback/performance",
            "/stats",
            "/health"
        ],
        "message": "Sử dụng các endpoint fallback ở trên"
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Custom 500 handler"""
    return jsonify({
        "error": "Lỗi server nội bộ",
        "fallback_available": True,
        "message": "Thử sử dụng endpoint /fallback"
    }), 500

@app.route("/control/start", methods=['POST'])
def start_server():
    global server_running, sse_start_time
    server_running = True
    if sse_start_time == 0:
        sse_start_time = time.time()
    print("SSE Server STARTED")
    return jsonify({"status": "running", "message": "Server started"})

@app.route("/control/stop", methods=['POST'])
def stop_server():
    global server_running, sse_messages_sent
    server_running = False
    sse_messages_sent = 0
    print("SSE Server STOPPED")
    return jsonify({"status": "stopped", "message": "Server stopped"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
