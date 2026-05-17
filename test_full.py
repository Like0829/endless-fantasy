"""
完整系统测试脚本
测试后端API和模拟玩家对话
"""
import requests
import json

BASE_URL = "http://localhost:8000"


def print_separator(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_backend_api():
    """测试后端API"""
    print_separator("测试后端API")

    # 1. 测试根路径
    print("\n[1] 测试根路径")
    try:
        resp = requests.get(f"{BASE_URL}/")
        print(f"✓ 状态码: {resp.status_code}")
        print(f"  响应: {resp.json()}")
    except Exception as e:
        print(f"✗ 错误: {e}")
        return False

    # 2. 测试获取世界状态
    print("\n[2] 获取世界状态")
    try:
        resp = requests.get(f"{BASE_URL}/world-state")
        print(f"✓ 状态码: {resp.status_code}")
        data = resp.json()
        print(f"  氛围值: {data.get('atmosphere')}")
        print(f"  任务数: {len(data.get('tasks', []))}")
        print(f"  留言数: {len(data.get('messages', []))}")
    except Exception as e:
        print(f"✗ 错误: {e}")
        return False

    # 3. 测试获取任务列表
    print("\n[3] 获取任务列表")
    try:
        resp = requests.get(f"{BASE_URL}/tasks")
        print(f"✓ 状态码: {resp.status_code}")
        tasks = resp.json().get('tasks', [])
        for task in tasks:
            print(f"  - {task['id']}: {task['name']} [{task['status']}]")
    except Exception as e:
        print(f"✗ 错误: {e}")
        return False

    return True


def test_game_flow():
    """测试游戏流程"""
    print_separator("测试游戏流程")

    # 1. 玩家A接受任务
    print("\n[1] 玩家A接受任务: 寻找医生的日记")
    try:
        resp = requests.post(f"{BASE_URL}/accept-task", json={
            "task_id": "task_001",
            "player": "玩家A"
        })
        print(f"✓ 状态码: {resp.status_code}")
        print(f"  响应: {resp.json()}")
    except Exception as e:
        print(f"✗ 错误: {e}")

    # 2. 更新氛围值
    print("\n[2] 更新氛围值 (+10)")
    try:
        resp = requests.post(f"{BASE_URL}/update-atmosphere", json={"change": 10})
        print(f"✓ 状态码: {resp.status_code}")
        print(f"  新氛围值: {resp.json().get('atmosphere')}")
    except Exception as e:
        print(f"✗ 错误: {e}")

    # 3. 玩家A完成任务
    print("\n[3] 玩家A完成任务")
    try:
        resp = requests.post(f"{BASE_URL}/complete-task", json={
            "task_id": "task_001",
            "player": "玩家A"
        })
        print(f"✓ 状态码: {resp.status_code}")
        print(f"  响应: {resp.json()}")
    except Exception as e:
        print(f"✗ 错误: {e}")

    # 4. 玩家A留下遗言
    print("\n[4] 玩家A在图书馆留下遗言")
    try:
        resp = requests.post(f"{BASE_URL}/add-message", json={
            "location": "图书馆",
            "content": "日记在书架后面...小心触手...",
            "player": "玩家A",
            "player_status": "dead"
        })
        print(f"✓ 状态码: {resp.status_code}")
        print(f"  响应: {resp.json()}")
    except Exception as e:
        print(f"✗ 错误: {e}")

    # 5. 再次获取世界状态
    print("\n[5] 获取更新后的世界状态")
    try:
        resp = requests.get(f"{BASE_URL}/world-state")
        print(f"✓ 状态码: {resp.status_code}")
        data = resp.json()
        print(f"  氛围值: {data.get('atmosphere')}")
        print(f"  任务数: {len(data.get('tasks', []))}")
        print(f"  留言数: {len(data.get('messages', []))}")
        if data.get('messages'):
            print(f"  最新留言: {data['messages'][0].get('content')}")
    except Exception as e:
        print(f"✗ 错误: {e}")


def test_unified_api():
    """测试统一更新接口"""
    print_separator("测试统一更新接口")

    # 1. 更新氛围值
    print("\n[1] 使用统一接口更新氛围值 (-15)")
    try:
        resp = requests.post(f"{BASE_URL}/update-world", json={
            "action": "update_atmosphere",
            "change": -15
        })
        print(f"✓ 状态码: {resp.status_code}")
        print(f"  响应: {resp.json()}")
    except Exception as e:
        print(f"✗ 错误: {e}")

    # 2. 接受任务
    print("\n[2] 使用统一接口接受任务")
    try:
        resp = requests.post(f"{BASE_URL}/update-world", json={
            "action": "accept_task",
            "task_id": "task_002",
            "player": "玩家B"
        })
        print(f"✓ 状态码: {resp.status_code}")
        print(f"  响应: {resp.json()}")
    except Exception as e:
        print(f"✗ 错误: {e}")


def show_final_state():
    """显示最终世界状态"""
    print_separator("最终世界状态")

    try:
        resp = requests.get(f"{BASE_URL}/world-state")
        data = resp.json()

        print(f"\n氛围值: {data.get('atmosphere')}")

        print("\n任务列表:")
        for task in data.get('tasks', []):
            status_icon = "✓" if task['status'] == 'completed' else "○" if task['status'] == 'in_progress' else "□"
            player = f" (玩家: {task['player']})" if task['player'] else ""
            print(f"  {status_icon} {task['name']} [{task['status']}]{player}")

        print("\n留言列表:")
        for msg in data.get('messages', []):
            status = "💀" if msg.get('player_status') == 'dead' else "💬"
            print(f"  {status} [{msg.get('location')}] {msg.get('content')} - {msg.get('player')}")

    except Exception as e:
        print(f"✗ 错误: {e}")


def main():
    print("\n" + "🎮" * 20)
    print("  《无尽幻境》完整系统测试")
    print("🎮" * 20)

    # 测试后端API
    if not test_backend_api():
        print("\n❌ 后端API测试失败，请检查服务是否启动")
        return

    # 测试游戏流程
    test_game_flow()

    # 测试统一接口
    test_unified_api()

    # 显示最终状态
    show_final_state()

    print_separator("测试完成")
    print("\n✅ 后端API测试通过！")
    print("\n下一步：")
    print("1. 在Dify中进行对话测试")
    print("2. 访问 http://localhost:8000/docs 查看API文档")
    print("3. 开启新会话，验证世界状态是否同步")
    print()


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("\n❌ 无法连接到服务器")
        print("请确保后端服务正在运行：python backend/app.py")
