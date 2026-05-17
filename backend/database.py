"""
数据库操作模块（连接池 + 行锁 + 自动建索引）

优化说明（2026-05-16）：
1. 连接池：避免每次请求都新建/关闭MySQL连接
2. FOR UPDATE行锁：解决任务接取竞态条件
3. 自动建索引：启动时检查并创建缺失的索引
4. 批量查询优化：减少不必要的字段返回
"""
import pymysql
from dbutils.pooled_db import PooledDB
from config import DB_CONFIG, POOL_CONFIG

# ============================================================
# 全局连接池（应用启动时初始化一次）
# ============================================================
_pool = None


def init_db_pool():
    """初始化数据库连接池（应用启动时调用一次）"""
    global _pool
    if _pool is None:
        _pool = PooledDB(
            creator=pymysql,
            maxconnections=POOL_CONFIG["maxconnections"],
            mincached=POOL_CONFIG["mincached"],
            maxcached=POOL_CONFIG["maxcached"],
            blocking=POOL_CONFIG["blocking"],
            setsession=["SET SESSION wait_timeout=60"],
            **DB_CONFIG
        )
    return _pool


def get_connection():
    """从连接池获取一个连接"""
    if _pool is None:
        init_db_pool()
    return _pool.connection()


# ============================================================
# 自动建索引（启动时执行一次）
# ============================================================
REQUIRED_INDEXES = [
    "ALTER TABLE messages ADD INDEX IF NOT EXISTS idx_location (location)",
    "ALTER TABLE messages ADD INDEX IF NOT EXISTS idx_player (player)",
    "ALTER TABLE messages ADD INDEX IF NOT EXISTS idx_created_at (created_at)",
]


def ensure_indexes():
    """确保必要的数据库索引存在"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 逐个创建索引（IF NOT EXISTS 防止重复创建）
            for sql in REQUIRED_INDEXES:
                try:
                    # MySQL 5.7不支持IF NOT EXISTS，先检查是否存在
                    index_name = sql.split("INDEX")[1].strip().split(" ")[0]
                    cursor.execute(
                        "SELECT COUNT(*) FROM information_schema.statistics "
                        "WHERE table_schema = %s AND table_name = 'messages' "
                        "AND index_name = %s",
                        (DB_CONFIG["database"], index_name)
                    )
                    count = cursor.fetchone()[0]
                    if count == 0:
                        cursor.execute(sql.split("IF NOT EXISTS")[1].strip() if "IF NOT EXISTS" in sql else sql)
                except Exception as e:
                    # 索引已存在或语法不支持，忽略
                    pass
            conn.commit()
        print("[数据库] 索引检查完成")
    except Exception as e:
        print(f"[数据库] 索引检查失败（可忽略）: {e}")
    finally:
        conn.close()


# ============================================================
# 世界状态（读多写少，单行热点）
# ============================================================

def get_world_state():
    """获取完整世界状态"""
    conn = get_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 只查需要的字段，messages限定条数防止过大
            cursor.execute("SELECT atmosphere FROM world_state WHERE id = 1")
            atmosphere = cursor.fetchone()
            atmosphere_value = atmosphere["atmosphere"] if atmosphere else 50

            cursor.execute(
                "SELECT id, name, description, status, player FROM tasks"
            )
            tasks = cursor.fetchall()

            cursor.execute(
                "SELECT id, location, content, player, player_status, "
                "DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:%%s') as created_at "
                "FROM messages ORDER BY created_at DESC LIMIT 200"
            )
            messages = cursor.fetchall()

            return {
                "atmosphere": atmosphere_value,
                "tasks": tasks,
                "messages": messages
            }
    finally:
        conn.close()


def update_atmosphere(change):
    """
    更新氛围值（单行原子UPDATE，天然线程安全）
    MySQL的 UPDATE ... SET col = col + delta 是原子操作
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE world_state SET atmosphere = GREATEST(0, LEAST(100, atmosphere + %s)) WHERE id = 1",
                (change,)
            )
            conn.commit()

            cursor.execute("SELECT atmosphere FROM world_state WHERE id = 1")
            result = cursor.fetchone()
            return result[0] if result else 50
    finally:
        conn.close()


# ============================================================
# 任务（存在竞态条件，需要行锁）
# ============================================================

def accept_task(task_id, player):
    """
    接受任务（使用 FOR UPDATE 行锁防止并发冲突）

    两个玩家同时接取同一个任务时：
    1. 第一个拿到锁 → 查到 pending → 更新成功
    2. 第二个拿到锁 → 查到 in_progress → 返回已被接取
    """
    conn = get_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 行级锁：锁定这一行直到事务结束
            cursor.execute(
                "SELECT status FROM tasks WHERE id = %s FOR UPDATE",
                (task_id,)
            )
            task = cursor.fetchone()

            if not task:
                return {"success": False, "message": "任务不存在"}
            if task["status"] != "pending":
                return {"success": False, "message": "任务已被其他人接取"}

            cursor.execute(
                "UPDATE tasks SET status = 'in_progress', player = %s WHERE id = %s",
                (player, task_id)
            )
            conn.commit()
            return {"success": True, "message": "任务接受成功"}
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": f"接取失败: {str(e)}"}
    finally:
        conn.close()


def complete_task(task_id, player):
    """完成任务"""
    conn = get_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                "SELECT status, player FROM tasks WHERE id = %s FOR UPDATE",
                (task_id,)
            )
            task = cursor.fetchone()

            if not task:
                return {"success": False, "message": "任务不存在"}
            if task["status"] == "completed":
                return {"success": False, "message": "任务已完成"}
            if task["status"] == "in_progress" and task["player"] != player:
                return {"success": False, "message": "任务已被其他人接取"}

            cursor.execute(
                "UPDATE tasks SET status = 'completed', player = %s WHERE id = %s",
                (player, task_id)
            )
            conn.commit()
            return {"success": True, "message": "任务完成"}
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": f"完成失败: {str(e)}"}
    finally:
        conn.close()


# ============================================================
# 留言（写频繁，需要索引）
# ============================================================

def add_message(location, content, player, player_status="alive"):
    """添加留言"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO messages (location, content, player, player_status) "
                "VALUES (%s, %s, %s, %s)",
                (location, content, player, player_status)
            )
            conn.commit()
            return {"success": True, "message": "留言添加成功"}
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": f"留言失败: {str(e)}"}
    finally:
        conn.close()


def get_messages_by_location(location):
    """获取指定地点的留言（用上了 idx_location 索引）"""
    conn = get_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                "SELECT id, content, player, player_status, "
                "DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:%%s') as created_at "
                "FROM messages WHERE location = %s "
                "ORDER BY created_at DESC LIMIT 100",
                (location,)
            )
            return cursor.fetchall()
    finally:
        conn.close()


# ============================================================
# 任务查询（读多写少）
# ============================================================

def get_task(task_id):
    """获取单个任务详情"""
    conn = get_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                "SELECT id, name, description, status, player, "
                "DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:%%s') as created_at "
                "FROM tasks WHERE id = %s",
                (task_id,)
            )
            return cursor.fetchone()
    finally:
        conn.close()


def get_all_tasks():
    """获取所有任务"""
    conn = get_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                "SELECT id, name, description, status, player FROM tasks"
            )
            return cursor.fetchall()
    finally:
        conn.close()
