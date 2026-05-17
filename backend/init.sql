-- ============================================================
-- 无尽幻境 数据库初始化脚本
-- 优化版：增加了索引、字符集统一
-- ============================================================

CREATE DATABASE IF NOT EXISTS endless_fantasy
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE endless_fantasy;

-- ============================================================
-- 世界状态表（单行热点表）
-- atmosphere 被所有玩家频繁读取，偶尔写入
-- 用单行+原子UPDATE避免并发问题
-- ============================================================
CREATE TABLE IF NOT EXISTS world_state (
    id INT PRIMARY KEY DEFAULT 1,
    atmosphere INT DEFAULT 50 COMMENT '城镇氛围值 0-100',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 任务表
-- 玩家接取任务时存在并发写入，应用层使用FOR UPDATE行锁
-- ============================================================
CREATE TABLE IF NOT EXISTS tasks (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    status ENUM('pending', 'in_progress', 'completed') DEFAULT 'pending',
    player VARCHAR(100) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status (status),          -- 按状态查询已接取/待完成的任务
    INDEX idx_player (player)           -- 按玩家查询任务
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 留言表（写入频繁，需要索引）
-- 按location查询最多，所以 idx_location 最重要
-- ============================================================
CREATE TABLE IF NOT EXISTS messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    location VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    player VARCHAR(100) NOT NULL,
    player_status ENUM('alive', 'dead') DEFAULT 'alive',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_location (location),      -- 按地点查询留言（最关键）
    INDEX idx_player (player),          -- 按玩家查询留言
    INDEX idx_created_at (created_at)   -- 按时间排序留言
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 初始化数据
-- ============================================================

-- 插入初始世界状态
INSERT INTO world_state (id, atmosphere) VALUES (1, 50)
ON DUPLICATE KEY UPDATE atmosphere = atmosphere;

-- 插入初始任务
INSERT INTO tasks (id, name, description, status) VALUES
('task_001', '寻找医生的日记', '在小镇中寻找失踪医生留下的日记，据说里面记载了迷雾的真相', 'pending'),
('task_002', '点亮灯塔', '小镇的灯塔已经熄灭多年，重新点亮它或许能驱散一些迷雾', 'pending'),
('task_003', '调查图书馆', '图书馆是小镇的知识中心，里面可能藏着重要的线索', 'pending')
ON DUPLICATE KEY UPDATE name = name;
