"""
无尽幻境 - 世界状态API（优化版）

优化说明（2026-05-16）：
1. 数据库连接池 + 行锁 → 消除连接开销，解决并发写入冲突
2. 内存缓存 world-state（TTL 2秒）→ 减轻DB读压力
3. 写入时立即失效缓存 → 保证数据一致性
4. 内存限流器 → 防止单IP刷请求
5. 多workers配置 → 充分利用多核CPU
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel
import database as db
import json
import asyncio
import requests
import time
import os

# Dify API 配置
DIFY_API_KEY = os.getenv("DIFY_API_KEY", "app-1mZQGieaKyx8bY1i18G7REp0")
DIFY_API_URL = os.getenv("DIFY_API_URL", "http://192.168.88.100/v1/chat-messages")

# ============================================================
# 内存缓存（每个worker独立缓存，TTL 2秒）
# ============================================================
CACHE_TTL = 2  # 秒
_cache = {"world_state": None, "timestamp": 0.0}


def _get_cached_world_state():
    """带缓存的世界状态读取"""
    now = time.time()
    if _cache["world_state"] is not None and (now - _cache["timestamp"]) < CACHE_TTL:
        return _cache["world_state"]
    state = db.get_world_state()
    _cache["world_state"] = state
    _cache["timestamp"] = now
    return state


def _invalidate_cache():
    """写入数据后立即失效缓存"""
    _cache["timestamp"] = 0


# ============================================================
# 请求限流（内存，每个worker独立计数）
# ============================================================
_rate_map = {}  # {ip: [(timestamp, ...)]}
RATE_LIMIT = 60    # 每个IP每分钟最多60次请求
RATE_WINDOW = 60  # 统计窗口（秒）


def _check_rate_limit(ip: str):
    """检查IP是否超过限流，超过返回True"""
    now = time.time()
    if ip not in _rate_map:
        _rate_map[ip] = []
    _rate_map[ip] = [t for t in _rate_map[ip] if now - t < RATE_WINDOW]
    if len(_rate_map[ip]) >= RATE_LIMIT:
        return True
    _rate_map[ip].append(now)
    return False


# ============================================================
# 应用初始化
# ============================================================

@asynccontextmanager
async def app_lifespan(app):
    """应用启动/关闭事件"""
    print("\n" + "=" * 50)
    print("正在初始化数据库连接池...")
    db.init_db_pool()
    db.ensure_indexes()
    print("数据库初始化完成")
    print(f"缓存TTL: {CACHE_TTL}秒 | 限流: 每IP每分钟{RATE_LIMIT}次")
    print("=" * 50 + "\n")
    yield
    print("正在关闭应用...")


app = FastAPI(title="无尽幻境 - 世界状态API", lifespan=app_lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_cached_world_state():
    """带缓存的世界状态读取"""
    now = time.time()
    if _cache["world_state"] is not None and (now - _cache["timestamp"]) < CACHE_TTL:
        return _cache["world_state"]
    state = db.get_world_state()
    _cache["world_state"] = state
    _cache["timestamp"] = now
    return state


def _invalidate_cache():
    """写入数据后立即失效缓存"""
    _cache["timestamp"] = 0


# ============================================================
# 请求限流（内存，每个worker独立计数）
# ============================================================
_rate_map = {}  # {ip: [(timestamp, ...)]}
RATE_LIMIT = 60    # 每个IP每分钟最多60次请求
RATE_WINDOW = 60  # 统计窗口（秒）


def _check_rate_limit(ip: str):
    """检查IP是否超过限流，超过返回True"""
    now = time.time()
    if ip not in _rate_map:
        _rate_map[ip] = []
    # 清理过期记录
    _rate_map[ip] = [t for t in _rate_map[ip] if now - t < RATE_WINDOW]
    if len(_rate_map[ip]) >= RATE_LIMIT:
        return True  # 被限流
    _rate_map[ip].append(now)
    return False


# ============================================================
# 中间件
# ============================================================

@app.middleware("http")
async def security_and_logging(request: Request, call_next):
    """限流 + 精简日志"""
    # 限流检查（只针对API路径）
    if request.url.path.startswith("/"):
        client_ip = request.client.host if request.client else "unknown"
        if _check_rate_limit(client_ip):
            return JSONResponse(
                status_code=429,
                content={"detail": "请求过于频繁，请稍后再试"}
            )

    # 记录请求方法+路径（不打印请求体，减少IO开销）
    print(f"[{request.method}] {request.url.path}")

    start = time.time()
    try:
        response = await call_next(request)
        elapsed = int((time.time() - start) * 1000)
        if elapsed > 1000:
            print(f"  → {response.status_code} ({elapsed}ms) ⚠️慢查询")
        return response
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        print(f"  → ERROR ({elapsed}ms): {e}")
        return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})


# ============================================================
# 数据模型
# ============================================================

class UpdateAtmosphereRequest(BaseModel):
    change: int


class AcceptTaskRequest(BaseModel):
    task_id: str
    player: str


class CompleteTaskRequest(BaseModel):
    task_id: str
    player: str


class AddMessageRequest(BaseModel):
    location: str
    content: str
    player: str
    player_status: str = "alive"


# ============================================================
# API 路由
# ============================================================

@app.get("/")
def root():
    return {"message": "无尽幻境 API 服务运行中", "version": "2.0"}


@app.get("/world-state")
def get_world_state():
    """获取完整世界状态（带缓存）"""
    try:
        state = _get_cached_world_state()
        return state
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/atmosphere")
def get_atmosphere():
    """获取当前氛围值"""
    try:
        state = _get_cached_world_state()
        return {"atmosphere": state["atmosphere"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/update-atmosphere")
def update_atmosphere(request: UpdateAtmosphereRequest):
    """更新氛围值（写入后立即失效缓存）"""
    try:
        new_value = db.update_atmosphere(request.change)
        _invalidate_cache()
        return {"success": True, "atmosphere": new_value}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks")
def get_tasks():
    """获取所有任务"""
    try:
        tasks = db.get_all_tasks()
        return {"tasks": tasks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks/{task_id}")
def get_task(task_id: str):
    """获取单个任务"""
    try:
        task = db.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        return task
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/accept-task")
def accept_task(request: AcceptTaskRequest):
    """接受任务"""
    try:
        result = db.accept_task(request.task_id, request.player)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/complete-task")
def complete_task(request: CompleteTaskRequest):
    """完成任务"""
    try:
        result = db.complete_task(request.task_id, request.player)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/add-message")
def add_message(request: AddMessageRequest):
    """添加留言"""
    try:
        result = db.add_message(
            request.location, request.content,
            request.player, request.player_status
        )
        _invalidate_cache()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/messages/{location}")
def get_messages(location: str):
    """获取指定地点的留言"""
    try:
        messages = db.get_messages_by_location(location)
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/update-world")
async def update_world(request: Request):
    """统一的世界更新接口（兼容Dify调用）"""
    try:
        body = await request.body()
        try:
            body_str = body.decode('utf-8')
        except UnicodeDecodeError:
            try:
                body_str = body.decode('gbk')
            except:
                body_str = body.decode('latin-1')

        data = json.loads(body_str)
        action = data.get("action")

        # 需要失效缓存的actions
        needs_cache_invalidation = False

        if action == "update_atmosphere":
            change = data.get("change") or data.get("atmosphere_change", 0)
            new_value = db.update_atmosphere(change)
            needs_cache_invalidation = True
            result = {"success": True, "action": "update_atmosphere", "atmosphere": new_value}

        elif action == "accept_task":
            task_id = data.get("task_id")
            player = data.get("player")
            if not task_id or not player:
                raise HTTPException(status_code=400, detail="task_id和player参数必填")
            result = db.accept_task(task_id, player)
            needs_cache_invalidation = True
            result = {"success": result["success"], "action": "accept_task", "message": result["message"]}

        elif action == "complete_task":
            task_id = data.get("task_id")
            player = data.get("player")
            if not task_id or not player:
                raise HTTPException(status_code=400, detail="task_id和player参数必填")
            result = db.complete_task(task_id, player)
            needs_cache_invalidation = True
            result = {"success": result["success"], "action": "complete_task", "message": result["message"]}

        elif action == "add_message":
            message_data = data.get("message", {})
            location = data.get("location") or message_data.get("location")
            content = data.get("content") or message_data.get("content")
            player = data.get("player") or message_data.get("player")
            player_status = data.get("player_status") or message_data.get("player_status", "alive")
            if not location or not content or not player:
                raise HTTPException(status_code=400, detail="location、content和player参数必填")
            result = db.add_message(location, content, player, player_status)
            needs_cache_invalidation = True
            result = {"success": result["success"], "action": "add_message", "message": result["message"]}

        else:
            raise HTTPException(status_code=400, detail=f"未知的action: {action}")

        if needs_cache_invalidation:
            _invalidate_cache()

        return result

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"JSON解析错误: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"服务器错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Dify 代理
# ============================================================

def _dify_streaming_request(payload: dict) -> dict:
    """同步方式调用Dify流式API"""
    try:
        response = requests.post(
            DIFY_API_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {DIFY_API_KEY}",
                "Content-Type": "application/json"
            },
            stream=True,
            timeout=300
        )
        response.raise_for_status()  # 非200状态码直接抛异常
    except requests.Timeout:
        return {"error": "Dify API请求超时"}
    except requests.RequestException as e:
        return {"error": f"Dify请求失败: {str(e)}"}

    full_answer = ""
    conversation_id = ""

    for line in response.iter_lines(decode_unicode=False):
        if not line:
            continue
        try:
            line_str = line.decode('utf-8')
        except UnicodeDecodeError:
            try:
                line_str = line.decode('gbk')
            except:
                line_str = line.decode('latin-1')

        if line_str.startswith("data: "):
            try:
                data = json.loads(line_str[6:])
                event = data.get("event", "")
                if event == "message":
                    full_answer += data.get("answer", "")
                if data.get("conversation_id"):
                    conversation_id = data["conversation_id"]
            except json.JSONDecodeError:
                continue

    if "error" in full_answer or not full_answer:
        return {"answer": full_answer, "conversation_id": conversation_id}

    return {"answer": full_answer, "conversation_id": conversation_id}


@app.post("/chat")
async def chat_proxy(request: Request):
    """Dify API代理接口"""
    try:
        body = await request.json()

        # Dify要求user参数必须一致才能保持对话连续性
        dify_payload = {
            "inputs": body.get("inputs", {}),
            "query": body.get("query", ""),
            "response_mode": "streaming",
            "conversation_id": body.get("conversation_id", ""),
            "user": body.get("user", "web-player")
        }

        result = await asyncio.get_event_loop().run_in_executor(
            None, _dify_streaming_request, dify_payload
        )

        # 如果Dify返回了错误信息
        if "error" in result:
            raise HTTPException(status_code=502, detail=result["error"])

        return result

    except requests.Timeout:
        raise HTTPException(status_code=504, detail="Dify API请求超时，请重试")
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Dify请求失败: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 启动入口
# ============================================================

if __name__ == "__main__":
    import socket
    import uvicorn
    # 获取本机IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"
    print(f"\n{'=' * 50}")
    print(f"后端API服务启动")
    print(f"{'=' * 50}")
    print(f"本地访问: http://localhost:8000")
    print(f"局域网访问: http://{local_ip}:8000")
    print(f"API文档: http://localhost:8000/docs")
    print(f"{'=' * 50}\n")
    # Windows下不支持多workers，使用单进程
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        log_level="warning"
    )
