#!/usr/bin/env python3
"""
21点游戏模拟器 - 一键启动
"""
import webbrowser
import threading
import time
import os
import subprocess
import sys

def start_simulator():
    print("🎮 启动21点游戏模拟器...")
    print("🌐 游戏地址: http://localhost:8888")
    print("� 访问权限: 仅本机访问")
    print("�🔧 按 Ctrl+C 停止服务器")
    print("💡 如需局域网访问，请使用: python3 server.py --public")
    print()
    
    # 延迟2秒后自动打开浏览器
    def open_browser():
        time.sleep(2)
        try:
            webbrowser.open('http://localhost:8888')
            print("🌐 已在浏览器中打开游戏")
        except Exception as e:
            print(f"⚠️  无法自动打开浏览器: {e}")
            print("💡 请手动访问: http://localhost:8888")
    
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()
    
    # 启动服务器
    try:
        os.execv(sys.executable, [sys.executable, 'server.py'])
    except KeyboardInterrupt:
        print("\n🛑 游戏已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        print("💡 请确保已安装Flask: pip install flask flask-cors")

if __name__ == "__main__":
    start_simulator()
