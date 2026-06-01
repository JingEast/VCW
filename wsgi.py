"""
港籍升学热点文案批量生成器 - Web版
基于Flask，浏览器访问即可运行

Application Factory 入口文件
"""
import os
import sys

# 确保项目根目录在 Python 路径中（兼容直接运行和导入）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    print("=" * 60)
    print("港籍升学热点文案批量生成器 - Web版")
    print("=" * 60)
    print("访问地址: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=True)  # nosec B104: development server
