from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
import os
import sys
import uvicorn
import datetime
import signal
import time
import socket
import json

app = FastAPI()
server = None  # 用于存储uvicorn服务器实例
base_directory = "."
waiting_for_input = False  # 用于标记是否正在等待用户输入
should_restart = False  # 用于标记是否需要重启服务器
path_history_file = "path_history.json"  # 存储历史路径的文件
max_history_paths = 10  # 最多保存的历史路径数量

def save_path_to_history(path):
    """保存有效路径到历史记录文件"""
    paths = load_path_history()
    
    # 如果路径已存在，先移除它（后面会重新添加到最前面）
    if path in paths:
        paths.remove(path)
    
    # 将新路径添加到列表开头
    paths.insert(0, path)
    
    # 保持列表长度不超过最大值
    if len(paths) > max_history_paths:
        paths = paths[:max_history_paths]
    
    # 保存到文件
    try:
        with open(path_history_file, 'w', encoding='utf-8') as f:
            json.dump(paths, f, ensure_ascii=False)
    except Exception as e:
        print(f"保存路径历史记录失败: {str(e)}")

def load_path_history():
    """加载历史路径记录"""
    if not os.path.exists(path_history_file):
        return []
    
    try:
        with open(path_history_file, 'r', encoding='utf-8') as f:
            paths = json.load(f)
            # 过滤掉不存在的路径
            return [p for p in paths if os.path.isdir(p)]
    except Exception as e:
        print(f"加载路径历史记录失败: {str(e)}")
        return []

def signal_handler(signum, frame):
    global base_directory, waiting_for_input, server, should_restart
    
    # 如果正在等待输入，则退出程序
    if waiting_for_input:
        print("\n检测到Ctrl+C，正在退出程序...")
        should_restart = False
        if server:
            server.should_exit = True
        return
    
    print("\n检测到Ctrl+C，请输入新的文件夹路径（直接回车保持当前路径，输入q退出）：")
    waiting_for_input = True  # 设置等待输入标志
    try:
        waiting_for_input = True  # 设置等待输入标志
        new_path = input(">>> ").strip()
        waiting_for_input = False  # 重置等待输入标志
        if new_path == "q":
            print("退出程序")
            should_restart = False
            return

        if not os.path.isdir(new_path):
            print("提供的路径不是一个有效的文件夹，保持当前路径")
        else:
            base_directory = new_path
            # 保存有效路径到历史记录
            save_path_to_history(base_directory)
            print(f"文件夹路径已更新为: {base_directory}")
        should_restart = True  # 标记需要重启服务器
        if server:
            server.should_exit = True  # 关闭当前服务器实例
    finally:
        pass

@app.get("/")
async def root():
    with open('index.html', 'r', encoding='utf-8') as f:
        content = f.read()
    return HTMLResponse(content)


@app.get("/file/{file_path:path}")
async def get_file(file_path: str):
    # 构造完整文件路径
    full_path = os.path.join(base_directory, file_path)
    
    # 检查文件是否存在且是一个文件
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="文件未找到")
    
    return FileResponse(full_path)


@app.get("/files-detail/{file_path:path}", response_class=JSONResponse)
async def list_files_detail(file_path: str):
    full_path = os.path.join(base_directory, file_path)

    if not os.path.isdir(full_path):
        raise HTTPException(status_code=404, detail="文件夹未找到")

    items = os.listdir(full_path)
    file_details = []

    for item in items:
        item_full_path = os.path.join(full_path, item)
        isFile = os.path.isfile(item_full_path)
        item_info = {
            "name": item,
            "size": os.path.getsize(item_full_path) if isFile else None,
            "modified_time": datetime.datetime.fromtimestamp(
                os.path.getmtime(item_full_path)
            ).isoformat() if isFile else None,
            "type": "file" if isFile else "dir"
        }
        file_details.append(item_info)

    return JSONResponse(content=file_details)

def get_ipv4_addresses():
    ipv4_addresses = []
    hostname = socket.gethostname()
    # Get all IP addresses associated with the hostname
    for ip in socket.getaddrinfo(hostname, None):
        if ip[0] == socket.AF_INET:  # Check if it's an IPv4 address
            ipv4_addresses.append(ip[4][0])
    return list(set(ipv4_addresses))  # Remove duplicates


if __name__ == "__main__":
    port = 8888

    # 从命令行获取文件夹路径
    if len(sys.argv) < 2:
        # 加载历史路径
        path_history = load_path_history()
        
        if path_history:
            print("请选择一个历史路径或输入新的文件夹路径:")
            for i, path in enumerate(path_history, 1):
                print(f"{i}. {path}")
            print("0. 输入新路径")
            
            choice = input("请选择 [0-{}]: ".format(len(path_history))).strip()
            
            if choice.isdigit():
                choice_num = int(choice)
                if 1 <= choice_num <= len(path_history):
                    base_directory = path_history[choice_num - 1]
                elif choice_num == 0:
                    print("请输入新的文件夹路径:")
                    base_directory = input(">>> ").strip()
                else:
                    print("无效选择，请输入文件夹路径:")
                    base_directory = input(">>> ").strip()
            else:
                print("无效选择，请输入文件夹路径:")
                base_directory = input(">>> ").strip()
        else:
            print("请提供文件夹路径:")
            base_directory = input(">>> ").strip()
    else:
        base_directory = sys.argv[1]

    # 检查文件夹路径是否存在
    if not os.path.isdir(base_directory):
        print("提供的路径不是一个有效的文件夹")
        sys.exit(1)
    
    # 保存有效路径到历史记录
    save_path_to_history(base_directory)

    # 设置信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    
    while True:  # 主循环，用于处理服务器重启
        ipv4_addresses = get_ipv4_addresses()
        address = "localhost" if len(ipv4_addresses) == 0 else ipv4_addresses[0]
        print(f"\n服务即将启动，请稍后访问 http://{address}:{port}\n")

        config = uvicorn.Config(app, host="0.0.0.0", port=port)
        server = uvicorn.Server(config)
        should_restart = False  # 重置重启标志
        
        try:
            server.run()
            if not should_restart:  # 如果不是要重启，则退出循环
                break
        except Exception as e:
            # print(f'发生错误: {str(e)}')
            break
        
    print("服务器已关闭。")