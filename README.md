# 无尽幻境 (Endless Fantasy)

> 克苏鲁风格 AI 驱动多人异步角色扮演游戏

玩家通过自然语言与 AI 游戏主持人（DM）交互，在克苏鲁世界观下自由冒险。所有玩家共享同一个世界，每个人的选择都会影响其他人的游戏体验。

---

## 功能特性

- **AI 游戏主持** — 基于 LLM 的动态叙事，无需真人主持人
- **共享世界** — 玩家的行为实时改变世界状态，影响其他玩家
- **属性与技能** — 力量、敏捷、意志、体质、智力六维属性 + 10 项技能
- **d100 检定系统** — 成功/失败/大成功/大失败判定
- **理智系统** — SAN 值管理、临时疯狂、恐怖等级
- **战斗系统** — 先手判定、命中/闪避、武器伤害
- **线索系统** — 三级线索（★★☆ ~ ★★★）推进调查
- **NPC 交互** — 态度系统、说服/恐吓交涉
- **异步留言** — 死亡遗言、地点留言跨玩家传递信息

---

## 技术栈

| 层级 | 技术 |
|------|------|
| AI 引擎 | Dify Chatflow |
| 大模型 | GPT-4o / Claude |
| 后端 API | Python FastAPI |
| 数据库 | MySQL (utf8mb4) |
| 前端 | HTML + CSS + JavaScript |
| 部署 | Docker / Railway / 云服务器 |

---

## 快速开始

### 1. 后端

```bash
cd backend
pip install -r requirements.txt
```

修改 `config.py` 中的数据库连接配置，然后：

```bash
python app.py
```

API 服务启动在 `http://localhost:8000`。

### 2. 数据库

```sql
source backend/init.sql;
```

### 3. 前端

```bash
python frontend/server.py
```

页面访问 `http://localhost:3001`。

### 4. Dify Chatflow

在 Dify 中导入 `dify/` 目录下的配置文件，配置 LLM 模型和 API 地址。

---

## 项目结构

```
├── backend/                  # 后端 API 服务
│   ├── app.py               # FastAPI 主程序
│   ├── database.py           # 数据库连接与操作
│   ├── config.py             # 配置文件
│   ├── init.sql              # 数据库初始化脚本
│   ├── requirements.txt      # Python 依赖
│   └── 数据库文档.md          # 数据库字段说明
├── frontend/                 # 前端页面
│   ├── index.html            # 游戏界面
│   ├── server.py             # 前端 HTTP 服务器
│   └── welcome.jpg           # 欢迎界面背景图
├── dify/                     # Dify Chatflow 配置
│   ├── chatflow配置说明.md    # 详细搭建指南
│   └── chatflow节点详细设置.md # 节点配置手册
```

---

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/world-state` | GET | 获取完整世界状态 |
| `/atmosphere` | GET | 获取当前氛围值 |
| `/update-atmosphere` | POST | 更新氛围值 |
| `/tasks` | GET | 获取所有任务 |
| `/accept-task` | POST | 接受任务 |
| `/complete-task` | POST | 完成任务 |
| `/add-message` | POST | 添加留言 |
| `/messages/{location}` | GET | 获取指定地点留言 |
| `/update-world` | POST | 统一世界更新接口 |
| `/chat` | POST | Dify API 代理 |

---

## 游戏规则概要

### 六维属性

| 属性 | 范围 | 用途 |
|------|------|------|
| STR 力量 | 3-18 | 推开重物、近战伤害 |
| DEX 敏捷 | 3-18 | 闪避、潜行、先手 |
| POW 意志 | 3-18 | 抵抗恐惧、说服 |
| CON 体质 | 3-18 | 抵抗毒素、奔跑 |
| INT 智力 | 3-18 | 推理、解谜 |
| APP 外貌 | 3-18 | 社交、交涉 |

### 检定规则

行动 → 确定技能/属性 → 计算成功率(属性×5%) → 投 d100 → 判定结果

| 骰值 | 结果 |
|------|------|
| ≤ 成功率 | 成功 |
| > 成功率 | 失败 |
| ≤ 成功率/5 | 大成功 |
| = 100 或 > 成功率95% | 大失败 |

---

## License

MIT
