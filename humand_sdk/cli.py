#!/usr/bin/env python3
"""
Humand CLI 工具
==============

命令行界面工具，用于管理 Humand 系统。
"""

import sys
import os
import argparse
import subprocess
from pathlib import Path
from typing import Optional


class HumandCLI:
    """Humand 命令行工具"""
    
    def __init__(self):
        self.project_root = self._find_project_root()
    
    def _find_project_root(self) -> Path:
        """查找项目根目录"""
        # 从当前目录开始向上查找
        current = Path.cwd()
        
        while current != current.parent:
            if (current / "server" / "main.py").exists():
                return current
            if (current / "setup.py").exists():
                return current
            current = current.parent
        
        # 如果找不到，返回当前目录
        return Path.cwd()
    
    def cmd_init(self, args):
        """初始化 Humand 项目"""
        print("🎯 初始化 Humand 项目...")
        
        # 检查是否在项目目录
        if not (self.project_root / "server").exists():
            print("❌ 当前目录不是 Humand 项目")
            print(f"   项目根目录: {self.project_root}")
            return 1
        
        # 运行配置向导
        wizard_script = self.project_root / "setup_wizard.py"
        
        if wizard_script.exists():
            print("启动配置向导...")
            subprocess.run([sys.executable, str(wizard_script)])
        else:
            print("⚠️ 配置向导未找到，手动创建配置...")
            self._create_default_config()
        
        print("\n✅ 初始化完成！")
        print("下一步: humand server")
        return 0
    
    def _create_default_config(self):
        """创建默认配置"""
        env_file = self.project_root / ".env"
        
        if env_file.exists():
            print(f"⚠️ 配置文件已存在: {env_file}")
            return
        
        default_config = """# Humand 默认配置
# 由 CLI 工具自动生成

# 存储配置
HUMAND_FORCE_MEMORY_STORAGE=true

# 服务器配置
WEB_HOST=0.0.0.0
WEB_PORT=8000
APPROVAL_TIMEOUT=3600

# 审批员
APPROVERS=admin@company.com

# Redis 配置（可选）
# REDIS_HOST=localhost
# REDIS_PORT=6379
# REDIS_DB=0

# IM 通知（可选）
# WECHAT_WEBHOOK_URL=
# FEISHU_WEBHOOK_URL=
# DINGTALK_WEBHOOK_URL=

# AI 配置（可选）
# DEEPSEEK_API_KEY=
# OPENAI_API_KEY=
"""
        
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(default_config)
        
        print(f"✅ 创建默认配置: {env_file}")
    
    def cmd_server(self, args):
        """启动服务器"""
        print("🚀 启动 Humand 服务器...")
        
        server_script = self.project_root / "server" / "main.py"
        
        if not server_script.exists():
            print(f"❌ 服务器脚本未找到: {server_script}")
            return 1
        
        # 构建启动命令
        cmd = [sys.executable, str(server_script)]
        
        if args.port:
            cmd.extend(["--port", str(args.port)])
        
        if args.host:
            cmd.extend(["--host", args.host])
        
        # 启动服务器
        try:
            subprocess.run(cmd, cwd=self.project_root)
            return 0
        except KeyboardInterrupt:
            print("\n\n👋 服务器已停止")
            return 0
        except Exception as e:
            print(f"❌ 启动失败: {e}")
            return 1
    
    def cmd_test(self, args):
        """测试系统连接"""
        print("🔍 测试 Humand 系统...")
        
        # 运行诊断
        diagnostics_module = self.project_root / "server" / "utils" / "diagnostics.py"
        
        if diagnostics_module.exists():
            subprocess.run([sys.executable, str(diagnostics_module)])
        else:
            print("⚠️ 诊断模块未找到，执行基础测试...")
            self._basic_test()
        
        return 0
    
    def _basic_test(self):
        """基础测试"""
        print("\n基础系统测试:")
        
        # 测试 Python 版本
        print(f"   ✅ Python {sys.version_info.major}.{sys.version_info.minor}")
        
        # 测试必需包
        required = ["fastapi", "uvicorn", "pydantic", "requests"]
        for package in required:
            try:
                __import__(package)
                print(f"   ✅ {package}")
            except ImportError:
                print(f"   ❌ {package} (缺失)")
        
        # 测试 Redis
        try:
            import redis
            client = redis.Redis(host='localhost', port=6379, socket_connect_timeout=2)
            client.ping()
            print(f"   ✅ Redis 连接")
        except:
            print(f"   ⚠️ Redis 未连接（将使用内存存储）")
    
    def cmd_status(self, args):
        """查看系统状态"""
        print("📊 Humand 系统状态\n")
        
        # 检查服务器是否运行
        import socket
        port = args.port or 8000
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                result = s.connect_ex(('localhost', port))
                if result == 0:
                    print(f"✅ 服务器运行中 (端口 {port})")
                    print(f"   Web 界面: http://localhost:{port}")
                    print(f"   API 文档: http://localhost:{port}/docs")
                else:
                    print(f"❌ 服务器未运行 (端口 {port})")
                    print(f"   启动: humand server")
        except Exception as e:
            print(f"⚠️ 无法检查服务器状态: {e}")
        
        # 检查配置
        env_file = self.project_root / ".env"
        if env_file.exists():
            print(f"\n✅ 配置文件: {env_file}")
        else:
            print(f"\n⚠️ 配置文件不存在")
            print(f"   创建: humand init")
    
    def cmd_logs(self, args):
        """查看日志"""
        print("📝 Humand 日志\n")
        
        log_dir = self.project_root / "logs"
        
        if not log_dir.exists():
            print("⚠️ 日志目录不存在")
            return 1
        
        log_files = list(log_dir.glob("*.log"))
        
        if not log_files:
            print("⚠️ 没有日志文件")
            return 1
        
        # 显示最新的日志文件
        latest_log = max(log_files, key=lambda p: p.stat().st_mtime)
        print(f"最新日志: {latest_log.name}\n")
        
        # 显示最后 N 行
        lines = args.lines or 50
        
        try:
            with open(latest_log, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                for line in all_lines[-lines:]:
                    print(line.rstrip())
        except Exception as e:
            print(f"❌ 读取日志失败: {e}")
            return 1
        
        return 0
    
    def cmd_version(self, args):
        """显示版本信息"""
        try:
            from humand_sdk import __version__
            print(f"Humand SDK v{__version__}")
        except:
            print("Humand SDK (开发版)")
        
        print(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        print(f"项目根目录: {self.project_root}")
        return 0
    
    def cmd_help(self, args):
        """显示帮助信息"""
        help_text = """
🎯 Humand CLI - 命令行工具

用法:
    humand <命令> [选项]

命令:
    init        初始化 Humand 项目（运行配置向导）
    server      启动 Humand 服务器
    test        测试系统连接和配置
    status      查看系统状态
    logs        查看系统日志
    version     显示版本信息
    help        显示此帮助信息

示例:
    # 初始化项目
    humand init
    
    # 启动服务器
    humand server
    
    # 在指定端口启动
    humand server --port 8080
    
    # 测试系统
    humand test
    
    # 查看状态
    humand status
    
    # 查看日志（最后50行）
    humand logs
    
    # 查看更多日志
    humand logs --lines 100

更多信息:
    文档: README.md
    问题: https://github.com/humand-io/humand/issues
"""
        print(help_text)
        return 0


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Humand CLI - Human-in-the-Loop 审批系统",
        add_help=False
    )
    
    subparsers = parser.add_subparsers(dest='command', help='命令')
    
    # init 命令
    parser_init = subparsers.add_parser('init', help='初始化项目')
    
    # server 命令
    parser_server = subparsers.add_parser('server', help='启动服务器')
    parser_server.add_argument('--port', type=int, help='服务器端口')
    parser_server.add_argument('--host', type=str, help='服务器主机')
    
    # test 命令
    parser_test = subparsers.add_parser('test', help='测试系统')
    
    # status 命令
    parser_status = subparsers.add_parser('status', help='查看状态')
    parser_status.add_argument('--port', type=int, help='服务器端口')
    
    # logs 命令
    parser_logs = subparsers.add_parser('logs', help='查看日志')
    parser_logs.add_argument('--lines', '-n', type=int, help='显示行数')
    
    # version 命令
    parser_version = subparsers.add_parser('version', help='显示版本')
    
    # help 命令
    parser_help = subparsers.add_parser('help', help='显示帮助')
    
    # 解析参数
    args = parser.parse_args()
    
    # 创建 CLI 实例
    cli = HumandCLI()
    
    # 执行命令
    if not args.command or args.command == 'help':
        return cli.cmd_help(args)
    elif args.command == 'init':
        return cli.cmd_init(args)
    elif args.command == 'server':
        return cli.cmd_server(args)
    elif args.command == 'test':
        return cli.cmd_test(args)
    elif args.command == 'status':
        return cli.cmd_status(args)
    elif args.command == 'logs':
        return cli.cmd_logs(args)
    elif args.command == 'version':
        return cli.cmd_version(args)
    else:
        print(f"❌ 未知命令: {args.command}")
        print("运行 'humand help' 查看帮助")
        return 1


if __name__ == "__main__":
    sys.exit(main())

