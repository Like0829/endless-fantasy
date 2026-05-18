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
('task_003', '调查图书馆', '图书馆是小镇的知识中心，里面可能藏着重要的线索', 'pending'),
('task_004', '教堂地下的秘密', '神父安东尼在教堂地下室发现了一扇紧锁的古门，门缝中透出诡异的气息', 'pending'),
('task_005', '码头上的可疑货物', '码头最近到了一批印有奇异符号的木箱，散发着令人不安的气息', 'pending'),
('task_006', '废弃医院的实验记录', '医院停诊前曾进行过秘密研究，院长办公室可能还保留着实验记录', 'pending'),
('task_007', '矿洞深处的低语', '矿工们反映矿洞深处最近总能听到奇怪的低语声，没人敢深入探查', 'pending'),
('task_008', '老船长的委托', '老船长莫里斯需要一个帮手，帮他从破损的船舱中取回一件重要的私人物品', 'pending'),
('task_009', '图书馆的古籍封印', '图书管理员艾琳发现古籍区有一本会自动翻页的书，怀疑上面附着某种力量', 'pending'),
('task_010', '迷雾中的求救声', '夜晚的小镇入口附近偶尔能听到微弱的求救声，但没人敢在夜里出去查看', 'pending')
ON DUPLICATE KEY UPDATE name = name;

-- ============================================================
-- 玩家表（PvP多人在线状态）
-- 存储每个玩家的共享状态，供其他玩家可见
-- ============================================================
CREATE TABLE IF NOT EXISTS players (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    hp INT DEFAULT 100,
    max_hp INT DEFAULT 100,
    san INT DEFAULT 100,
    max_san INT DEFAULT 100,
    current_location VARCHAR(100) DEFAULT '小镇入口',
    inventory TEXT,
    is_dead BOOLEAN DEFAULT FALSE,
    is_crazy BOOLEAN DEFAULT FALSE,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_p_location (current_location),
    INDEX idx_p_name (name),
    INDEX idx_p_last_active (last_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
