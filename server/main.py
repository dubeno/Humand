#!/usr/bin/env python3
"""
Humand 服务端启动脚本
====================

启动 Web 审批界面和 IM 模拟器服务
"""

import os
import sys
import asyncio
import multiprocessing
import time
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def start_web_server():
    """启动 Web 服务器"""
    try:
        import uvicorn
        from server.web.app import app
        from server.utils.config import config
        
        print(f"🌐 启动 Web 服务器...")
        print(f"   地址: http://{config.WEB_HOST}:{config.WEB_PORT}")
        print(f"   API 文档: http://{config.WEB_HOST}:{config.WEB_PORT}/docs")
        
        uvicorn.run(
            app, 
            host=config.WEB_HOST, 
            port=config.WEB_PORT,
            log_level="info"
        )
    except Exception as e:
        print(f"❌ Web 服务器启动失败: {e}")

def start_im_simulator():
    """启动 IM 模拟器"""
    try:
        from server.notification.simulator import app as simulator_app
        
        print(f"📱 启动 IM 模拟器...")
        print(f"   地址: http://localhost:5000")
        
        simulator_app.run(
            host="0.0.0.0",
            port=5000,
            debug=False
        )
    except Exception as e:
        print(f"❌ IM 模拟器启动失败: {e}")

def check_dependencies():
    """检查依赖"""
    print("🔍 检查系统依赖...")
    
    # 检查 Redis 连接
    try:
        from server.storage import approval_storage
        # 尝试连接当前存储（Redis 或内存）
        ping_ok = getattr(approval_storage, "ping", None)
        if callable(ping_ok) and approval_storage.ping():
            print("   ✅ 存储后端连接正常")
        else:
            print("   ⚠️ 存储后端未提供 ping()，已跳过连接检查")
    except Exception as e:
        print(f"   ⚠️ 存储后端检查失败: {e}")
        print(f"   💡 如需 Redis，请确保 Redis 服务正在运行；否则可使用内存存储模式")
    
    # 检查配置
    try:
        from server.utils.config import config
        print(f"   ✅ 配置加载成功")
        print(f"   📋 审批超时: {config.APPROVAL_TIMEOUT // 60} 分钟")
        print(f"   👥 审批员: {', '.join(config.get_approvers())}")
        print(f"   🌍 对外地址: {config.get_public_base_url()}")
        
        if config.WECHAT_WEBHOOK_URL:
            print(f"   ✅ 企业微信已配置")
        else:
            print(f"   ⚠️ 企业微信未配置，将使用模拟器")

        if config.FEISHU_APP_ID and config.FEISHU_APP_SECRET and config.FEISHU_RECEIVE_ID:
            print(f"   ✅ 飞书交互卡片已配置")
        elif config.FEISHU_WEBHOOK_URL:
            print(f"   ⚠️ 飞书仅配置了 webhook，将以简化消息模式运行")
        else:
            print(f"   ⚠️ 飞书未配置")
            
    except Exception as e:
        print(f"   ❌ 配置加载失败: {e}")
        return False
    
    return True

def main():
    """主函数"""
    print("🎯 Humand 服务端启动")
    print("=" * 50)
    
    # 检查依赖
    if not check_dependencies():
        print("\n❌ 依赖检查失败，请修复后重试")
        sys.exit(1)
    
    print(f"\n🚀 启动服务...")
    
    # 使用多进程启动服务
    processes = []
    
    try:
        # 启动 IM 模拟器
        simulator_process = multiprocessing.Process(target=start_im_simulator)
        simulator_process.start()
        processes.append(simulator_process)
        
        # 等待模拟器启动
        time.sleep(2)
        
        # 启动 Web 服务器（主进程）
        start_web_server()
        
    except KeyboardInterrupt:
        print(f"\n🛑 收到停止信号，正在关闭服务...")
        
        # 停止所有子进程
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()
        
        print(f"✅ 所有服务已停止")
    
    except Exception as e:
        print(f"❌ 服务启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
