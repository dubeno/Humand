"""
系统诊断工具
============

提供友好的错误提示和系统健康检查。
"""

import sys
import os
from typing import Dict, List, Tuple, Optional
from pathlib import Path


class SystemDiagnostics:
    """系统诊断工具"""
    
    def __init__(self):
        self.issues: List[Tuple[str, str, str]] = []  # (级别, 标题, 解决方案)
        self.checks_passed = 0
        self.checks_failed = 0
    
    def check_python_version(self) -> bool:
        """检查 Python 版本"""
        min_version = (3, 8)
        current_version = sys.version_info[:2]
        
        if current_version >= min_version:
            self.checks_passed += 1
            return True
        else:
            self.checks_failed += 1
            self.issues.append((
                "ERROR",
                f"Python 版本过低: {current_version[0]}.{current_version[1]}",
                f"请升级到 Python {min_version[0]}.{min_version[1]} 或更高版本\n"
                f"   下载地址: https://www.python.org/downloads/"
            ))
            return False
    
    def check_redis_connection(self) -> bool:
        """检查 Redis 连接"""
        try:
            import redis
            from .config import config
            
            client = redis.Redis(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                db=config.REDIS_DB,
                socket_connect_timeout=2
            )
            client.ping()
            self.checks_passed += 1
            return True
            
        except ImportError:
            self.checks_failed += 1
            self.issues.append((
                "WARNING",
                "Redis 包未安装",
                "安装 Redis 客户端:\n"
                "   pip install redis>=5.0.0\n"
                "或使用内存存储模式:\n"
                "   export HUMAND_FORCE_MEMORY_STORAGE=true"
            ))
            return False
            
        except Exception as e:
            self.checks_failed += 1
            error_msg = str(e)
            
            # 提供针对性的解决方案
            if "Connection refused" in error_msg:
                solution = (
                    "Redis 服务未启动，请启动 Redis:\n\n"
                    "   # Ubuntu/Debian\n"
                    "   sudo systemctl start redis-server\n\n"
                    "   # macOS (Homebrew)\n"
                    "   brew services start redis\n\n"
                    "   # Windows\n"
                    "   下载: https://github.com/tporadowski/redis/releases\n\n"
                    "   # Docker\n"
                    "   docker run -d -p 6379:6379 --name redis redis:latest\n\n"
                    "或使用内存存储模式（适合开发）:\n"
                    "   export HUMAND_FORCE_MEMORY_STORAGE=true"
                )
            elif "timeout" in error_msg.lower():
                solution = (
                    "Redis 连接超时，请检查:\n"
                    "   1. Redis 是否正在运行\n"
                    "   2. 主机地址和端口是否正确\n"
                    f"      当前配置: {config.REDIS_HOST}:{config.REDIS_PORT}\n"
                    "   3. 防火墙是否阻止连接"
                )
            else:
                solution = (
                    f"Redis 连接失败: {error_msg}\n"
                    "请检查 Redis 配置或使用内存存储模式:\n"
                    "   export HUMAND_FORCE_MEMORY_STORAGE=true"
                )
            
            self.issues.append((
                "WARNING",
                "Redis 连接失败",
                solution
            ))
            return False
    
    def check_required_packages(self) -> bool:
        """检查必需的 Python 包"""
        required_packages = {
            "fastapi": "FastAPI Web 框架",
            "uvicorn": "ASGI 服务器",
            "pydantic": "数据验证",
            "requests": "HTTP 客户端",
            "jinja2": "模板引擎",
        }
        
        missing_packages = []
        
        for package, description in required_packages.items():
            try:
                __import__(package)
            except ImportError:
                missing_packages.append((package, description))
        
        if missing_packages:
            self.checks_failed += 1
            packages_list = "\n   ".join([f"{pkg} ({desc})" for pkg, desc in missing_packages])
            self.issues.append((
                "ERROR",
                f"缺少 {len(missing_packages)} 个必需的包",
                f"请安装以下包:\n   {packages_list}\n\n"
                f"快速安装:\n"
                f"   pip install " + " ".join([pkg for pkg, _ in missing_packages])
            ))
            return False
        else:
            self.checks_passed += 1
            return True
    
    def check_optional_packages(self) -> bool:
        """检查可选的 Python 包"""
        optional_packages = {
            "langgraph": "LangGraph 工作流",
            "langchain_core": "LangChain 核心",
            "langchain_openai": "OpenAI 集成",
            "openai": "OpenAI API",
        }
        
        missing_packages = []
        
        for package, description in optional_packages.items():
            try:
                __import__(package)
            except ImportError:
                missing_packages.append((package, description))
        
        if missing_packages:
            packages_list = "\n   ".join([f"{pkg} ({desc})" for pkg, desc in missing_packages])
            self.issues.append((
                "INFO",
                f"缺少 {len(missing_packages)} 个可选包（AI 功能需要）",
                f"如需 AI 功能，请安装:\n   {packages_list}\n\n"
                f"快速安装:\n"
                f"   pip install " + " ".join([pkg for pkg, _ in missing_packages])
            ))
        
        return True
    
    def check_configuration(self) -> bool:
        """检查配置"""
        try:
            from .config import config
            
            issues_found = []
            
            # 检查审批员配置
            if not config.get_approvers():
                issues_found.append(
                    "未配置审批员，审批将发送给默认地址"
                )
            
            # 检查 IM 通知配置
            if not config.WECHAT_WEBHOOK_URL:
                issues_found.append(
                    "未配置企业微信 Webhook，将使用模拟器"
                )
            
            if issues_found:
                self.issues.append((
                    "INFO",
                    "配置建议",
                    "以下配置可以优化体验:\n   " + "\n   ".join(issues_found) + "\n\n"
                    "创建 .env 文件配置:\n"
                    "   APPROVERS=user1@company.com,user2@company.com\n"
                    "   WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/..."
                ))
            
            self.checks_passed += 1
            return True
            
        except Exception as e:
            self.checks_failed += 1
            self.issues.append((
                "ERROR",
                "配置加载失败",
                f"配置文件可能有问题: {e}\n"
                "请检查 server/utils/config.py"
            ))
            return False
    
    def check_port_availability(self, port: int = 8000) -> bool:
        """检查端口是否可用"""
        import socket
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                self.checks_passed += 1
                return True
        except OSError:
            self.checks_failed += 1
            self.issues.append((
                "WARNING",
                f"端口 {port} 已被占用",
                f"请执行以下操作之一:\n"
                f"   1. 停止占用端口的程序\n"
                f"   2. 使用其他端口启动服务:\n"
                f"      python server/main.py --port 8001\n\n"
                f"查找占用端口的程序:\n"
                f"   # Windows\n"
                f"   netstat -ano | findstr :{port}\n\n"
                f"   # Linux/Mac\n"
                f"   lsof -i :{port}"
            ))
            return False
    
    def run_all_checks(self, verbose: bool = True) -> bool:
        """
        运行所有检查
        
        Args:
            verbose: 是否打印详细信息
            
        Returns:
            是否所有关键检查都通过
        """
        if verbose:
            print("\n🔍 系统诊断检查...")
            print("=" * 60)
        
        # 运行所有检查
        self.check_python_version()
        self.check_required_packages()
        self.check_optional_packages()
        self.check_redis_connection()
        self.check_configuration()
        self.check_port_availability()
        
        if verbose:
            self.print_report()
        
        # 只要没有 ERROR 级别的问题就算通过
        has_errors = any(level == "ERROR" for level, _, _ in self.issues)
        return not has_errors
    
    def print_report(self):
        """打印诊断报告"""
        print(f"\n📊 检查结果:")
        print(f"   ✅ 通过: {self.checks_passed}")
        print(f"   ❌ 失败: {self.checks_failed}")
        
        if not self.issues:
            print("\n🎉 所有检查通过！系统已准备就绪。")
            return
        
        # 按级别分组显示
        errors = [i for i in self.issues if i[0] == "ERROR"]
        warnings = [i for i in self.issues if i[0] == "WARNING"]
        infos = [i for i in self.issues if i[0] == "INFO"]
        
        if errors:
            print("\n❌ 错误 (必须修复):")
            for _, title, solution in errors:
                print(f"\n   {title}")
                for line in solution.split('\n'):
                    print(f"   {line}")
        
        if warnings:
            print("\n⚠️ 警告 (建议修复):")
            for _, title, solution in warnings:
                print(f"\n   {title}")
                for line in solution.split('\n'):
                    print(f"   {line}")
        
        if infos:
            print("\n💡 提示:")
            for _, title, solution in infos:
                print(f"\n   {title}")
                for line in solution.split('\n'):
                    print(f"   {line}")
        
        print("\n" + "=" * 60)
    
    def get_quick_start_guide(self) -> str:
        """获取快速启动指南"""
        guide = """
🚀 Humand 快速启动指南
==================

1️⃣ 安装依赖
   pip install -r server/requirements.txt

2️⃣ 启动 Redis（可选）
   # Docker 方式（推荐）
   docker run -d -p 6379:6379 --name redis redis:latest
   
   # 或使用本地 Redis
   redis-server

3️⃣ 启动服务
   python server/main.py
   
   # 或使用内存存储模式
   export HUMAND_FORCE_MEMORY_STORAGE=true
   python server/main.py

4️⃣ 访问界面
   Web 审批界面: http://localhost:8000
   IM 模拟器: http://localhost:5000
   API 文档: http://localhost:8000/docs

💡 遇到问题？
   运行诊断工具: python -m server.utils.diagnostics
"""
        return guide


def run_diagnostics():
    """运行诊断（命令行入口）"""
    diagnostics = SystemDiagnostics()
    success = diagnostics.run_all_checks()
    
    if not success:
        print("\n" + diagnostics.get_quick_start_guide())
        sys.exit(1)
    else:
        print("\n✅ 系统检查完成，可以启动服务！")
        print("\n启动命令:")
        print("   python server/main.py")
        sys.exit(0)


if __name__ == "__main__":
    run_diagnostics()


