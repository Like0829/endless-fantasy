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
    "ALTER TABLE players ADD INDEX IF NOT EXISTS idx_p_location (current_location)",
    "ALTER TABLE players ADD INDEX IF NOT EXISTS idx_p_name (name)",
    "ALTER TABLE players ADD INDEX IF NOT EXISTS idx_p_last_active (last_active)",
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

            # 查询在线玩家（5分钟内活跃）
            cursor.execute(
                "SELECT name, hp, max_hp, san, max_san, current_location, "
                "is_dead, is_crazy, "
                "DATE_FORMAT(last_active, '%%Y-%%m-%%d %%H:%%i:%%s') as last_active "
                "FROM players WHERE last_active > NOW() - INTERVAL 5 MINUTE"
            )
            online_players = cursor.fetchall()

            return {
                "atmosphere": atmosphere_value,
                "tasks": tasks,
                "messages": messages,
                "players": online_players
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

    规则：
    1. 每个玩家同时只能接取一个任务
    2. 必须完成当前任务后才能接取下一个
    """
    conn = get_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 检查该玩家是否已有进行中的任务
            cursor.execute(
                "SELECT id, name FROM tasks WHERE player = %s AND status = 'in_progress'",
                (player,)
            )
            existing = cursor.fetchone()
            if existing:
                return {
                    "success": False,
                    "message": f"你已有进行中的任务「{existing['name']}」，完成后才能接取新任务"
                }

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


# ============================================================
# 玩家表（PvP多人在线状态）
# ============================================================

def register_player(name, hp=100, max_hp=100, san=100, max_san=100,
                    current_location='小镇入口', inventory='手电筒,笔记本,急救包'):
    """注册玩家（已存在则更新活跃时间）"""
    conn = get_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                "INSERT INTO players (name, hp, max_hp, san, max_san, current_location, inventory) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE last_active = CURRENT_TIMESTAMP",
                (name, hp, max_hp, san, max_san, current_location, inventory)
            )
            conn.commit()
            cursor.execute("SELECT * FROM players WHERE name = %s", (name,))
            player = cursor.fetchone()
            return {"success": True, "player": player}
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def get_player(name):
    """查询单个玩家"""
    conn = get_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT * FROM players WHERE name = %s", (name,))
            return cursor.fetchone()
    finally:
        conn.close()


def get_all_players():
    """查询所有玩家"""
    conn = get_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                "SELECT name, hp, max_hp, san, max_san, current_location, "
                "is_dead, is_crazy, "
                "DATE_FORMAT(last_active, '%%Y-%%m-%%d %%H:%%i:%%s') as last_active "
                "FROM players ORDER BY last_active DESC"
            )
            return cursor.fetchall()
    finally:
        conn.close()


def get_online_players():
    """查询在线玩家（5分钟内活跃）"""
    conn = get_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                "SELECT name, hp, max_hp, san, max_san, current_location, "
                "is_dead, is_crazy, inventory, "
                "DATE_FORMAT(last_active, '%%Y-%%m-%%d %%H:%%i:%%s') as last_active "
                "FROM players WHERE last_active > NOW() - INTERVAL 5 MINUTE "
                "ORDER BY last_active DESC"
            )
            return cursor.fetchall()
    finally:
        conn.close()


def get_players_at_location(location):
    """查询指定位置的在线玩家"""
    conn = get_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                "SELECT name, hp, max_hp, san, max_san, current_location, "
                "is_dead, is_crazy "
                "FROM players "
                "WHERE current_location = %s AND last_active > NOW() - INTERVAL 5 MINUTE",
                (location,)
            )
            return cursor.fetchall()
    finally:
        conn.close()


def update_player_state(name, hp=None, san=None, current_location=None,
                        inventory=None, is_dead=None, is_crazy=None):
    """动态更新玩家状态（只更新非None字段）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sets = []
            params = []
            if hp is not None:
                sets.append("hp = %s")
                params.append(hp)
            if san is not None:
                sets.append("san = %s")
                params.append(san)
            if current_location is not None:
                sets.append("current_location = %s")
                params.append(current_location)
            if inventory is not None:
                sets.append("inventory = %s")
                params.append(inventory)
            if is_dead is not None:
                sets.append("is_dead = %s")
                params.append(is_dead)
            if is_crazy is not None:
                sets.append("is_crazy = %s")
                params.append(is_crazy)

            if not sets:
                return {"success": True, "message": "无更新"}

            sets.append("last_active = CURRENT_TIMESTAMP")
            params.append(name)

            sql = f"UPDATE players SET {', '.join(sets)} WHERE name = %s"
            cursor.execute(sql, params)
            conn.commit()
            return {"success": True, "affected": cursor.rowcount}
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def update_player_hp(name, hp_change):
    """原子更新玩家HP（用于PvP伤害），返回新HP值"""
    conn = get_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                "SELECT hp, max_hp FROM players WHERE name = %s FOR UPDATE",
                (name,)
            )
            player = cursor.fetchone()
            if not player:
                return {"success": False, "message": "玩家不存在"}

            new_hp = max(0, min(player["max_hp"], player["hp"] + hp_change))
            is_dead = new_hp <= 0

            cursor.execute(
                "UPDATE players SET hp = %s, is_dead = %s, last_active = CURRENT_TIMESTAMP WHERE name = %s",
                (new_hp, is_dead, name)
            )
            conn.commit()
            return {"success": True, "new_hp": new_hp, "is_dead": is_dead}
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": str(e)}
    finally:
        conn.close()
