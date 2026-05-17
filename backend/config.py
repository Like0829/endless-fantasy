# MySQL数据库配置
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "123456",
    "database": "endless_fantasy",
    "charset": "utf8mb4",
    "autocommit": False,     # 手动控制事务
}

# 连接池配置（注意：4个worker各有一个独立pool，总数会×4）
POOL_CONFIG = {
    "maxconnections": 8,     # 每个worker最多8个连接（4worker×8=32个MySQL连接）
    "mincached": 2,          # 每个worker启动时预建2个连接
    "maxcached": 4,          # 每个worker最多保持4个空闲连接
    "blocking": True,        # 连接不够时排队等待（不报错）
}
