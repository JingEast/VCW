#!/usr/bin/env python3
"""
港籍升学热点文案批量生成器 - 启动入口
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from vcw_copywriter.main import main  # noqa: E402

if __name__ == "__main__":
    main()
