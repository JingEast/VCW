"""
CLI主程序
提供交互式命令行界面，支持文案生成、记忆管理、质量检查
"""
import sys
import io
from pathlib import Path

# Fix Windows console encoding for UTF-8 characters
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
        sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
    except (AttributeError, OSError):
        pass

from .config import Config, ensure_dirs
from .memory import MemoryBank
from .prompt_builder import build_full_prompts
from .generator import CopywriterGenerator
from .checker import check_and_report


def print_banner():
    print(r"""
===============================================================

        港籍升学热点文案批量生成器 v1.0

        基于AI + 记忆机制 + 时效性保障的文案生成系统

===============================================================
""")


def get_input(prompt_text: str, required: bool = True, default: str = "") -> str:
    """获取用户输入"""
    if default:
        display = f"{prompt_text} [{default}]: "
    else:
        display = f"{prompt_text}: "

    value = input(display).strip()
    if not value and default:
        value = default

    while required and not value:
        value = input(f"  [提示] 此项必填，请重新输入 {prompt_text}: ").strip()

    return value


def interactive_generate(config: Config, memory_bank: MemoryBank):
    """交互式生成文案"""
    print("\n[表单] 请输入文案生成参数（直接回车可使用默认值）：\n")

    # 收集输入
    topic = get_input("主题", default="DSE考砸后的保底路径")
    audience = get_input("目标受众", default="港宝家长")
    core_data = get_input("核心数据（含年份）", default="DSE 2025年报考人数约5万人；港八大录取率约21%")
    policy_points = get_input("政策要点（含有效期）", default="副学士六科全2分可读；内地暨南大学独立招生英文2分也收（2025-2026学年有效）")
    hidden_path = get_input("隐藏路径", default="英国澳洲部分大学接受DSE英文2分+雅思5.5（需确认目标院校最新语言要求）")
    call_to_action = get_input("行动号召", default="留言领取'DSE英文不及格升学路径全图'")
    sample_ref = get_input("参考样本", required=False, default="")
    extra_requirements = get_input("额外要求", required=False, default="")

    print("\n" + "=" * 60)
    print("[编辑] 正在构建提示词...")

    # 构建提示词
    system_prompt, user_prompt = build_full_prompts(
        memory_bank=memory_bank,
        topic=topic,
        audience=audience,
        core_data=core_data,
        policy_points=policy_points,
        hidden_path=hidden_path,
        call_to_action=call_to_action,
        sample_ref=sample_ref,
        extra_requirements=extra_requirements
    )

    print("[OK] 提示词构建完成")
    print(f"   系统提示词长度: {len(system_prompt)} 字符")
    print(f"   用户提示词长度: {len(user_prompt)} 字符")

    # 初始化生成器
    try:
        llm_config = config.get("llm")
        generator = CopywriterGenerator(llm_config)
    except ValueError as e:
        print(f"\n[错误] {e}")
        print("   请编辑 config.json 配置API Key后再试。")
        return
    except ImportError as e:
        print(f"\n[错误] {e}")
        return

    print("\n[AI] 正在调用LLM生成文案，请稍候...\n")
    success, content, meta = generator.generate(system_prompt, user_prompt)

    if not success:
        print(f"[错误] 生成失败: {meta}")
        return

    print(f"[OK] 生成成功！{meta}\n")
    print("=" * 60)
    print(content)
    print("=" * 60)

    # 质量检查
    strict_mode = config.get("quality_check", "strict_mode", default=False)
    passed, report = check_and_report(content, strict_mode)
    print(f"\n{report}")

    # 保存
    auto_save = config.get("output", "auto_save", default=True)
    if auto_save:
        output_dir = config.get("output", "save_dir", default="data/generated")
        filepath = generator.save_generated(content, topic, meta, output_dir)
        print(f"[保存] 文案已保存到: {filepath}")

    # 询问是否添加到记忆库
    print("\n[提示] 如果需要记录修改意见到记忆库（下次生成时自动规避），请输入问题描述。")
    print("   直接回车则跳过。")
    issue = input("   修改意见: ").strip()

    if issue:
        print("   请选择问题标签（可多选，用空格分隔）:")
        print("     1. 数据时效  2. 政策准确性  3. 语言风格  4. 结构逻辑  5. 平台适配")
        tags_input = input("   标签编号: ").strip()
        tag_map = {
            "1": "数据时效", "2": "政策准确性", "3": "语言风格",
            "4": "结构逻辑", "5": "平台适配"
        }
        tags = [tag_map.get(t, t) for t in tags_input.split() if t in tag_map]
        if not tags:
            tags = ["其他"]

        correction = input("   修正方案: ").strip()

        entry_id = memory_bank.add_entry(
            topic=topic,
            issue_description=issue,
            issue_tags=tags,
            correction_plan=correction,
            original_text=content[:200]
        )
        print(f"[OK] 已记录到记忆库，条目ID: {entry_id}")

    print("\n[完成] 本次生成流程结束！")


def view_memory(memory_bank: MemoryBank):
    """查看记忆库"""
    print("\n" + memory_bank.generate_report())

    print("\n最近10条记忆:")
    entries = memory_bank.get_recent_entries(limit=10)
    if not entries:
        print("  （记忆库为空）")
    for e in entries:
        status = "[OK]已规避" if e["is_avoided"] else "[待办]待规避"
        print(f"  [{e['id']}] {status} {e['topic']} | {', '.join(e['issue_tags'])}: {e['issue_description'][:40]}...")


def manage_memory(memory_bank: MemoryBank):
    """管理记忆库"""
    while True:
        print("\n=== 记忆库管理 ===")
        print("1. 查看记忆库统计")
        print("2. 手动添加记忆条目")
        print("3. 标记条目为已规避")
        print("4. 返回主菜单")

        choice = input("\n请选择: ").strip()

        if choice == "1":
            view_memory(memory_bank)

        elif choice == "2":
            topic = get_input("主题")
            issue = get_input("问题描述")
            tags = get_input("问题标签（用空格分隔）").split()
            correction = get_input("修正方案")
            entry_id = memory_bank.add_entry(topic, issue, tags, correction)
            print(f"[OK] 已添加，ID: {entry_id}")

        elif choice == "3":
            entry_id = get_input("条目ID")
            memory_bank.mark_avoided(entry_id)
            print(f"[OK] 条目 {entry_id} 已标记为已规避")

        elif choice == "4":
            break


def setup_config(config: Config):
    """配置向导"""
    print("\n=== 配置向导 ===")
    print(f"当前API Key: {'已设置' if config.get('llm', 'api_key') else '未设置'}")
    print(f"当前模型: {config.get('llm', 'model')}")
    print(f"当前Base URL: {config.get('llm', 'base_url')}")

    api_key = input("\n请输入API Key（直接回车保持当前）: ").strip()
    if api_key:
        config.set("llm", "api_key", value=api_key)

    model = input("请输入模型名称 [gpt-4o]: ").strip()
    if model:
        config.set("llm", "model", value=model)

    base_url = input("请输入Base URL [https://api.openai.com/v1]: ").strip()
    if base_url:
        config.set("llm", "base_url", value=base_url)

    config.save()
    print("[OK] 配置已保存")


def main():
    """主入口"""
    print_banner()

    # 确保目录存在
    ensure_dirs()

    # 加载配置
    config = Config("config.json")
    if not Path("config.json").exists():
        config.save()
        print("[文件] 已创建默认配置文件 config.json")

    # 加载记忆库
    memory_db_path = config.get("memory", "db_path", default="data/memory_db.json")
    memory_bank = MemoryBank(memory_db_path)

    # 检查API Key
    if not config.get("llm", "api_key"):
        print("[提示] 警告: API Key未设置，请先进入配置向导设置。\n")

    while True:
        print("\n=== 主菜单 ===")
        print("1. [生成] 生成文案")
        print("2. [查看] 查看记忆库")
        print("3. [管理] 记忆库管理")
        print("4. [配置] 配置设置")
        print("5. [退出] 退出")

        choice = input("\n请选择操作: ").strip()

        if choice == "1":
            interactive_generate(config, memory_bank)

        elif choice == "2":
            view_memory(memory_bank)

        elif choice == "3":
            manage_memory(memory_bank)

        elif choice == "4":
            setup_config(config)

        elif choice == "5":
            print("\n[再见] 再见！")
            break

        else:
            print("\n[提示] 无效选择，请重新输入。")


if __name__ == "__main__":
    main()
