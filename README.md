<p align="center"><img src="https://cdn.jsdelivr.net/gh/Hayston1001/astrbot_plugin_minecraft_motd@main/logo.png" width="96" alt="logo"></p>

# MC 服务器状态查询(AstrBot MOTD 查询插件)

一个用于查询 Minecraft 服务器状态的 AstrBot 插件. 支持 Java 版和基岩版服务器, **兼容 ViaVersion 多版本服务器**, **支持 Velocity 代理子服查询**. 

![插件输出图片效果预览图1](https://cdn.jsdelivr.net/gh/Hayston1001/astrbot_plugin_minecraft_motd@main/assets/preview_java.png)
![插件输出图片效果预览图2](https://cdn.jsdelivr.net/gh/Hayston1001/astrbot_plugin_minecraft_motd@main/assets/preview_bedrock.png)
![插件输出图片效果预览图3](https://cdn.jsdelivr.net/gh/Hayston1001/astrbot_plugin_minecraft_motd@main/assets/preview_proxy.png)

## 功能特性

- **MOTD 查询**: 查询 Minecraft 服务器的 MOTD、在线玩家、版本等信息
- **支持 SRV**: 直连查询自动解析 SRV 记录(与原版客户端行为一致), 显式指定端口时不查询 SRV(v2.4+)
- **像素风卡片**: 泥土纹理背景 + MC GUI 浮雕面板 + 物品栏格子槽 + XP 条式玩家进度条(v2)
- **彩色 MOTD 还原**: 支持 § 颜色码与粗体/斜体/下划线/删除线格式码、§r 重置、JSON 组件树, API 与直连两条查询路径渲染风格一致(v2)
- **服务器图标**: 直接展示服务器 64×64 图标(像素放大渲染), 无图标时显示像素占位块(v2)
- **在线玩家头像列表**: 展示最多 8 名在线玩家的头像与昵称, 超出显示 +N(v2)
- **查询延迟显示**: 卡片展示本次查询耗时(绿/金/红分级)(v2)
- **双平台支持**: 同时支持 Java 版和基岩版服务器查询
- **ViaVersion 兼容**: 智能识别 ViaVersion 多版本服务器, 正确显示版本范围
- **代理服务器查询**: 支持查询 Velocity 代理及其子服状态
- **无需斜杠触发**: 直接输入 `motd` 即可触发, 无需 `/` 前缀
- **默认服务器**: 可配置默认查询的服务器, 简化指令使用
- **头像/图标磁盘缓存**: 头像默认 12 小时刷新周期(可配置), 刷新失败自动沿用旧缓存；图标保留最后一次成功获取的值；重启不丢, `/motdr` 立即刷新(v2.1+)
- **离线玩家识别**: 自动识别离线玩家 UUID 并跳过头像下载(v2.2+)
- **会话控制**: 可设置对哪些群聊/私聊生效
- **管理员权限**: 插件配置仅管理员可修改
- **完善报错**: 详细的错误提示和帮助信息

## QQ 官方机器人使用前提

在 QQ 官方机器人(bot.q.qq.com)的群里使用无斜杠 `motd` 指令, 需要在 **手机 QQ 群设置** 中：

1. 开启「**机器人主动在群聊内发言**」
2. 消息范围设置为「**获取群内全部消息**」(否则仅 @机器人 可触发)

> 图片卡片经 AstrBot 图床以公网 URL 发送, QQ 官方平台仅支持 png/jpg 格式, 本插件固定输出 png, 无需额外配置. 

## ViaVersion 兼容性

本插件支持安装了 ViaVersion/ViaBackwards 的服务器：

| 情况 | 处理方式 |
|------|----------|
| `protocol.version = -1/0` | 识别为多版本模式, 显示 `多版本` 而非 `-1` |
| `version.name` 含版本范围 | 自动提取并显示 `支持客户端版本: 1.8 - 1.21.3` |
| Paper/Spigot + ViaVersion | 解析协议号范围并转换为版本号显示 |
| ViaVersion 字样检测 | 自动识别并标注 ViaVersion 兼容 |

## 代理服务器查询(v1.6+)

支持查询 Velocity/BungeeCord 代理服务器及其子服状态. 

### 查询模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| **普通查询** | 直接查询单个服务器 | 非代理服务器 |
| **代理服务器查询** | 查询代理及其子服 | Velocity/BungeeCord 代理 |

### 代理查询方式

| 方式 | 说明 | 支持的代理 |
|------|------|-----------|
| **velostat** | 通过 velostat 插件 HTTP API 查询 | 仅 Velocity |
| **子服直连** | 手动配置子服地址分别查询 | Velocity/BungeeCord |

### 使用 velostat 模式(推荐)

1. 在 Velocity 代理上安装 [velostat](https://modrinth.com/plugin/velostat) 插件
2. 配置插件：
   - 查询类型：代理服务器查询
   - 代理查询方式：通过 velostat 插件查询
   - velostat API 地址：`http://代理IP:8080`

### 使用子服直连模式

适用于：
- BungeeCord 代理(无 velostat 插件支持)
- 子服端口对外暴露的场景

配置：
- 查询类型：代理服务器查询
- 代理查询方式：子服直连查询
- 子服地址列表：`lobby:127.0.0.1:25566,survival:127.0.0.1:25567`

> ⚠️ **注意**: BungeeCord 目前没有类似 velostat 的 HTTP API 插件, 只能使用子服直连模式. 

## 安装方法

### 方法一: 在官方插件市场中搜索 "Minecraft 服务器 motd 查询"

### 方法二: 在本仓库下载插件 zip 文件, 在 WebUI 中选择从文件安装插件

⚠️**重启 AstrBot**(热重载可能无法正确加载配置)

## 配置方法

### 1. 在 WebUI 中配置

| 配置项 | 说明 | 建议值 |
|--------|------|--------|
| `default_server` | 默认服务器地址 | `n.rainplay.cn` |
| `default_port` | 默认服务器端口 | `46861` |
| `query_type` | 查询类型 | `normal` |
| `proxy_query_method` | 代理查询方式 | `velostat` |
| `velostat_api_url` | velostat API 地址 | `http://代理IP:8080` |
| `sub_servers` | 子服地址列表 | `lobby:host:port,survival:host:port` |
| `enable_all_sessions` | 对所有会话生效 | true |
| `use_api` | 使用 API 竞速查询(API 与直连并发, 谁先成功用谁, 共享 query_timeout 死线) | true |
| `output_mode` | 输出模式: `image` 渲染像素风图片卡片 / `text` 纯文本(跳过渲染与头像预取, 几乎零开销) | `image` |
| `card_height_mode` | 卡片高度: `auto` 随内容自适应(紧凑无留白) / `fixed` 固定高度 720px(玩家少时补白, 尺寸统一) | `auto` |
| `show_server_icon` | 显示服务器图标 | true |
| `show_player_list` | 显示在线玩家列表 | true |
| `show_latency` | 显示查询延迟 | true |
| `query_timeout` | 查询总超时时间(秒), 所有查询方式共享同一死线, 超时的分支返回各自的具体错误 | `5` |
| `prefetch_avatars` | 预取玩家头像并内嵌渲染图(带磁盘缓存) | true |
| `avatar_cache_ttl` | 头像刷新周期(小时), 过期后尝试重新下载, 失败继续用旧缓存 | `12` |
| `avatar_neg_cache_ttl` | 头像负缓存(分钟), 失败后该时长内不再重试下载; 0 为关闭; 混合登录的服务器应延长此时间 | `10` |

### 2. 配置文件方式

也可以直接编辑 `data/config/astrbot_plugin_minecraft_motd_config.json`：

**普通查询模式**：
```json
{
    "default_server": "",
    "default_port": 25565,
    "query_type": "normal",
    "enable_all_sessions": true,
    "enabled_sessions": [],
    "admin_only_config": true,
    "query_timeout": 5,
    "use_api": true,
    "output_mode": "image",
    "card_height_mode": "auto",
    "prefetch_avatars": true,
    "avatar_cache_ttl": 12,
    "avatar_neg_cache_ttl": 10,
    "show_server_icon": true,
    "show_player_list": true,
    "show_latency": true
}
```

**代理查询模式(velostat)**：
```json
{
    "default_server": "",
    "default_port": 25565,
    "query_type": "proxy",
    "proxy_query_method": "velostat",
    "velostat_api_url": "http://proxy.example.com:8080",
    "enable_all_sessions": true,
    "query_timeout": 5,
    "use_api": true,
    "output_mode": "image",
    "card_height_mode": "auto",
    "prefetch_avatars": true,
    "avatar_cache_ttl": 12,
    "avatar_neg_cache_ttl": 10,
    "show_server_icon": true,
    "show_player_list": true,
    "show_latency": true
}
```

**代理查询模式(子服直连)**：
```json
{
    "default_server": "proxy.example.com",
    "default_port": 25565,
    "query_type": "proxy",
    "proxy_query_method": "direct",
    "sub_servers": "lobby:127.0.0.1:25566,survival:127.0.0.1:25567",
    "enable_all_sessions": true,
    "query_timeout": 5,
    "use_api": true,
    "output_mode": "image",
    "card_height_mode": "auto",
    "prefetch_avatars": true,
    "avatar_cache_ttl": 12,
    "avatar_neg_cache_ttl": 10,
    "show_server_icon": true,
    "show_player_list": true,
    "show_latency": true
}
```

## 使用方法

### 基础指令(无需斜杠)

| 指令 | 说明 | 示例 |
|------|------|------|
| `motd` | 查询默认服务器 | `motd` |
| `motd <地址>` | 查询指定服务器(使用标准端口 25565) | `motd mc.hypixel.net` |
| `motd <地址:端口>` | 查询指定服务器(使用指定端口) | `motd n.rainplay.cn:46861` |
| `motd-bedrock` | 查询默认基岩版服务器 | `motd-bedrock` |
| `motd-bedrock <地址:端口>` | 查询指定基岩版服务器 | `motd-bedrock mc.example.com:19132` |

### 带斜杠前缀的指令

| 指令 | 说明 |
|------|------|
| `/motd [地址:端口]` | Java 版服务器查询 |
| `/motd-bedrock [地址:端口]` | 基岩版服务器查询 |

### 管理员配置指令

| 指令 | 说明 | 示例 |
|------|------|------|
| `/motdconfig default <地址:端口>` | 设置默认服务器 | `/motdconfig default n.rainplay.cn:46861` |
| `/motdconfig get` | 查看当前配置 | `/motdconfig get` |
| `/motdr` | 清空头像/图标缓存, 下次查询重新下载(立即刷新) | `/motdr` |

> ⚠️ **注意**: 配置指令仅管理员可用. 

## 故障排查

### 问题：发送 `motd` 没有反应？

**排查步骤：**

1. **检查插件是否加载**
   - 查看 AstrBot 日志, 搜索 `[MOTD]`
   - 应该看到类似：`[MOTD] 插件已加载 vX.X.X`

2. **检查配置是否正确**
   - 在 WebUI 中查看插件配置
   - 确认 `default_server` 和 `default_port` 已设置
   - 确认 `enable_all_sessions` 为 true

3. **检查日志级别**
   - 在 `data/cmd_config.json` 中设置 `"log_level": "DEBUG"`
   - 重启后查看是否有 `[MOTD] 收到消息` 的日志

4. **检查白名单**
   - 如果开启了 ID 白名单, 确保你的 QQ 号在白名单中
   - 或者在 WebUI 中关闭白名单限制

5. **QQ 官方机器人**
   - 确认群设置已开启「机器人主动在群聊内发言」与「获取群内全部消息」(见上文使用前提)

### 问题：ViaVersion 服务器版本显示异常？

本插件已内置 ViaVersion 兼容性处理：
- 自动检测 `protocol.version = -1/0` 的多版本模式
- 从 `version.name` 提取版本范围
- 支持 Paper/Spigot/Bukkit/Purpur 等常见服务端
- 支持 Velocity/BungeeCord/Waterfall 等代理软件

**排查步骤：**

1. **查看版本解析日志**
   - 在 AstrBot 日志中搜索 `[MOTD] 版本解析输入`
   - 日志会显示完整的解析链路：
     ```
     [MOTD] API 返回原始数据: version.name_raw='...', version.protocol=null
     [MOTD] 版本解析输入: name='...', protocol_raw=..., protocol=...
     [MOTD] 代理检测命中: 'velocity' -> Velocity
     [MOTD] 版本范围解析: all_versions=['1.8', '1.21.4'], mc_versions=['1.8', '1.21.4']
     [MOTD] 版本解析输出: server='1.8.x', client='1.8 ~ 1.21.4', via_hint='检测到: Velocity 代理'
     ```

2. **检查协议号来源**
   - 如果看到 `protocol_raw=null`, 表示 API 未返回协议号
   - 插件会自动从版本名反查或使用直连查询补全

3. **检查代理检测结果**
   - 如果服务器使用代理软件, 日志会显示 `代理检测命中`
   - 支持的代理：Velocity、BungeeCord、Waterfall、FlameCord、Geyser 等

4. **反馈问题时请提供**
   - 完整的 `[MOTD]` 相关日志
   - 服务器地址和端口
   - 服务器使用的代理软件(如有)

### 问题：代理服务器查询失败？

**velostat 模式：**

1. 确认 velostat 插件已安装并运行
2. 确认 velostat API 地址正确(默认端口 8080)
3. 检查 velostat API 是否可访问：`curl http://代理IP:8080/status`

**子服直连模式：**

1. 确认子服地址格式正确：`服务器名:host:port`
2. 确认子服端口对外暴露
3. 检查子服是否在线

### 问题：查询超时或连接被拒绝？

1. 确认服务器地址和端口是否正确
2. 保持 `use_api: true`(默认开启)开启 API 竞速查询(API 与直连并发, 谁先成功用谁, 共享 query_timeout 死线)
3. 增加 `query_timeout` 配置值
4. 检查服务器是否在线
5. 检查 AstrBot 运行的网络环境

### 问题：收到的卡片没有颜色 / 头像不显示？

- v2.1 起头像由插件预取并内嵌到渲染图(mc-heads → crafatar → minotar 三源自动回退 + 磁盘缓存, 默认 12 小时刷新周期), 加载失败率大幅降低；刷新失败自动沿用旧头像, 从未成功获取过的玩家才回退为「首字母 + 哈希色」占位块, 不影响卡片其余部分
- 头像显示为旧皮肤时属正常缓存现象, 可执行 `/motdr` 立即清空缓存, 或调低 `avatar_cache_ttl`
- 如完全不希望发起头像请求, 可在配置中关闭 `prefetch_avatars` 或 `show_player_list`
- 离线玩家一律显示占位块属正常现象: 插件通过 UUID 本地识别盗版服玩家并自动跳过头像下载(此类 UUID 在 Mojang 数据库中不存在, 头像必然获取失败), 避免每次查询的无效网络请求(v2.2.0+)
- 服务器图标保留最后一次成功获取的值：某次查询未返回图标时自动沿用旧图标, 从未获取到过图标才显示像素占位块；可在配置中关闭 `show_server_icon` 隐藏图标槽

## 日志解读指南

插件输出的所有日志都以 `[MOTD]` 为前缀, 以下是关键日志的含义：

### 启动日志

```
[MOTD] 插件初始化完成, 版本 X.X.X
[MOTD] 配置加载: default_server='xxx', port=25565
[MOTD] 查询类型: normal/proxy
[MOTD] 代理查询方式: velostat/direct
[MOTD] 使用 API 查询: True
[MOTD] 头像预取: 开启, 头像刷新周期 12 小时, 下载失败负缓存 10 分钟, 图标缓存保留最后一次成功获取
[MOTD] 插件已加载 vX.X.X
```

### 查询流程日志

```
[MOTD] 匹配到 motd 指令: motd mc.example.com    # 触发查询
[MOTD] 开始查询: server='mc.example.com', is_java=True
[MOTD] 使用指定服务器: mc.example.com:25565
[MOTD] 开始执行查询, 超时=5秒
[MOTD] 查询完成: source=direct, 版本=1.21.11, 玩家=10/100, 图标=有, 耗时=123ms   # 关键字段摘要
[MOTD] 头像预取完成: 4/4 个                            # 预取的玩家头像数(命中缓存则瞬间完成)
[MOTD] 查询流程完成
```

### 代理查询日志

```
[MOTD] 开始代理查询: method=velostat, server='proxy.example.com'
[MOTD] 代理查询流程完成
```

### 版本解析日志(关键)

```
# 1. API 返回的原始数据
[MOTD] API 返回原始数据: version.name_raw='Velocity 1.7.2-1.21.4', version.protocol=null

# 2. 版本解析输入
[MOTD] 版本解析输入: name='Velocity 1.7.2-1.21.4', protocol_raw=null, protocol=0

# 3. 协议号处理
[MOTD] 协议号无效(0), 从版本名 'Velocity 1.7.2-1.21.4' 反查到协议 47
[MOTD] 协议号映射: 47 -> display='1.8.x', major='1.8'

# 4. 代理检测
[MOTD] 代理检测命中: 'velocity' -> Velocity

# 5. 版本范围解析
[MOTD] 版本范围解析: all_versions=['1.7.2', '1.21.4'], mc_versions=['1.7.2', '1.21.4']

# 6. 最终输出
[MOTD] 版本解析输出: server='1.8.x', client='1.7.2 ~ 1.21.4', via_hint='检测到: Velocity 代理'
```

### 格式化结果日志

```
[MOTD] Java 版原始数据: version={...}, players={...}
[MOTD] 格式化结果: server_version='1.8.x', client_version='1.7.2 ~ 1.21.4', players=10/100
```

### 错误与降级日志

```
[MOTD] 竞速查询一支失败(...), 等待另一支              # 竞速中 API 或直连一支失败, 自动等另一支
[MOTD] 直连查询获胜: protocol=767, name='1.21'          # 直连先返回
[MOTD] API 查询获胜(823ms)                            # API 先返回
[MOTD] 玩家头像获取失败(渲染时用占位块回退): xxx       # 头像三源均失败, 不影响卡片
[MOTD] 查询超时
[MOTD] 查询异常: ...
[MOTD] 查询中提示发送失败(已忽略): ...           # 「查询中」提示发送失败, 不影响主查询
[MOTD] 图片渲染/发送失败, 回退到文本: ...          # 第一级降级：发送文本卡片
[MOTD] 文本回退发送失败(放弃): ...               # 文本也失败, 仅记日志, 不阻塞主流程
[MOTD] 统一死线已到, 放弃等待 API 补全版本名, 保留直连结果   # 代理服直连先成功但 API 未在死线内补全版本名
```

## 许可证

MIT License
