"""测试API的简单脚本"""
import requests

BASE_URL = "http://localhost:8000"


def test_api():
    print("=" * 50)
    print("测试无尽幻境 API")
    print("=" * 50)

    # 1. 测试获取世界状态
    print("\n[1] 获取世界状态")
    resp = requests.get(f"{BASE_URL}/world-state")
    print(f"状态码: {resp.status_code}")
    print(f"响应: {resp.json()}")

    # 2. 测试获取氛围值
    print("\n[2] 获取氛围值")
    resp = requests.get(f"{BASE_URL}/atmosphere")
    print(f"响应: {resp.json()}")

    # 3. 测试更新氛围值
    print("\n[3] 更新氛围值 (+10)")
    resp = requests.post(f"{BASE_URL}/update-atmosphere", json={"change": 10})
    print(f"响应: {resp.json()}")

    # 4. 测试获取任务列表
    print("\n[4] 获取任务列表")
    resp = requests.get(f"{BASE_URL}/tasks")
    print(f"响应: {resp.json()}")

    # 5. 测试接受任务
    print("\n[5] 玩家A接受任务 task_001")
    resp = requests.post(f"{BASE_URL}/accept-task", json={
        "task_id": "task_001",
        "player": "玩家A"
    })
    print(f"响应: {resp.json()}")

    # 6. 测试完成任务
    print("\n[6] 玩家A完成任务 task_001")
    resp = requests.post(f"{BASE_URL}/complete-task", json={
        "task_id": "task_001",
        "player": "玩家A"
    })
    print(f"响应: {resp.json()}")

    # 7. 测试添加留言
    print("\n[7] 玩家A在图书馆留下遗言")
    resp = requests.post(f"{BASE_URL}/add-message", json={
        "location": "图书馆",
        "content": "日记在书架后面...小心触手...",
        "player": "玩家A",
        "player_status": "dead"
    })
    print(f"响应: {resp.json()}")

    # 8. 测试获取地点留言
    print("\n[8] 获取图书馆的留言")
    resp = requests.get(f"{BASE_URL}/messages/图书馆")
    print(f"响应: {resp.json()}")

    # 9. 测试统一更新接口
    print("\n[9] 使用统一接口更新氛围值 (-15)")
    resp = requests.post(f"{BASE_URL}/update-world", json={
        "action": "update_atmosphere",
        "change": -15
    })
    print(f"响应: {resp.json()}")

    # 10. 再次获取世界状态
    print("\n[10] 再次获取世界状态")
    resp = requests.get(f"{BASE_URL}/world-state")
    print(f"状态码: {resp.status_code}")
    print(f"响应: {resp.json()}")

    print("\n" + "=" * 50)
    print("测试完成!")
    print("=" * 50)


if __name__ == "__main__":
    try:
        test_api()
    except requests.exceptions.ConnectionError:
        print("错误: 无法连接到服务器，请确保 app.py 正在运行")
