from flask import Flask, render_template, request, jsonify, Response
import json
import os
import time
from openai import OpenAI
import uuid

app = Flask(__name__)

# 配置文件路径
CONFIG_FILE = 'config.json'
HISTORY_FILE = 'chat_history.json'

# 确保数据文件存在
def ensure_files_exist():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({'api_key': '', 'base_url': ''}, f, ensure_ascii=False, indent=2)
    
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)

# 加载配置
def load_config():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# 保存配置
def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# 加载历史记录
def load_history():
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# 保存历史记录
def save_history(history):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

# 主页路由
@app.route('/')
def index():
    return render_template('index.html')

# 获取配置路由
@app.route('/get_config', methods=['GET'])
def get_config():
    return jsonify(load_config())

# 保存配置路由
@app.route('/save_config', methods=['POST'])
def save_config_route():
    config = request.json
    save_config(config)
    return jsonify({'success': True})

# 获取历史记录路由
@app.route('/get_history', methods=['GET'])
def get_history():
    history = load_history()
    return jsonify(history)

# 新增或更新对话路由
@app.route('/update_conversation', methods=['POST'])
def update_conversation():
    data = request.json
    history = load_history()
    
    # 查找是否已存在该对话
    found = False
    for i, conv in enumerate(history):
        if conv['id'] == data['id']:
            history[i] = data
            found = True
            break
    
    # 如果不存在，添加新对话
    if not found:
        history.append(data)
    
    # 限制历史记录数量
    if len(history) > 50:
        history = history[-50:]
    
    save_history(history)
    return jsonify({'success': True})

# 删除对话路由
@app.route('/delete_conversation/<conv_id>', methods=['DELETE'])
def delete_conversation(conv_id):
    history = load_history()
    history = [conv for conv in history if conv['id'] != conv_id]
    save_history(history)
    return jsonify({'success': True})

# 对话流式输出路由
@app.route('/chat_stream', methods=['POST'])
def chat_stream():
    data = request.json
    messages = data.get('messages', [])
    show_reasoning = data.get('show_reasoning', False)
    
    config = load_config()
    api_key = config.get('api_key', '')
    base_url = config.get('base_url', '')
    
    if not api_key or not base_url:
        return jsonify({'error': '请先在设置中配置API Key和Base URL'}), 400
    
    def generate():
        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
            completion = client.chat.completions.create(
                model="deepseek-r1:70b",
                temperature=0.6,
                messages=messages,
                stream=True
            )
            
            for chunk in completion:
                if hasattr(chunk.choices[0].delta, "reasoning_content") and chunk.choices[0].delta.reasoning_content:
                    if show_reasoning:
                        yield f"data: {{\"type\": \"reasoning\", \"content\": \"{chunk.choices[0].delta.reasoning_content.replace('"', '\\"')}\"}}\n\n"
                elif chunk.choices[0].delta.content:
                    yield f"data: {{\"type\": \"content\", \"content\": \"{chunk.choices[0].delta.content.replace('"', '\\"')}\"}}\n\n"
            
            yield f"data: {{\"type\": \"done\"}}\n\n"
        except Exception as e:
            yield f"data: {{\"type\": \"error\", \"content\": \"{str(e).replace('"', '\\"')}\"}}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    ensure_files_exist()
    # 创建templates目录（如果不存在）
    if not os.path.exists('templates'):
        os.makedirs('templates')
    app.run(debug=True, host='0.0.0.0', port=5000)