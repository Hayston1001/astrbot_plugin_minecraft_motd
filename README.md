<p align="center"><img src="https://cdn.jsdelivr.net/gh/Hayston1001/astrbot_plugin_minecraft_motd@main/logo.png?v=2" width="96" alt="logo"></p>

# MC 服务器状态查询(AstrBot MOTD 查询插件)

默认直连查询; 支持图片渲染/文本输出; 支持 Java/基岩; 兼容 ViaVersion; 支持代理子服查询

<!-- 随图片同步更新cache buster ?v=版本 -->
![插件输出图片效果预览图1](https://cdn.jsdelivr.net/gh/Hayston1001/astrbot_plugin_minecraft_motd@main/assets/preview_java.png?v=2)
![插件输出图片效果预览图2](https://cdn.jsdelivr.net/gh/Hayston1001/astrbot_plugin_minecraft_motd@main/assets/preview_bedrock.png?v=2)
![插件输出图片效果预览图3](https://cdn.jsdelivr.net/gh/Hayston1001/astrbot_plugin_minecraft_motd@main/assets/preview_proxy.png?v=2)

## 功能特性

- **无需斜杠**: 直接输入 `motd` 即可, 无需 `/`
- **直连查询**: 支持失败回退 API 查询
- **支持 SRV**: 直连查询自动解析 SRV 记录(与原版客户端行为一致), 显式指定端口时不查询 SRV(v2.4+)
- **像素风卡片**: 泥土纹理背景 + MC GUI 浮雕面板 + 物品栏格子槽 + XP 条式玩家进度条(v2+)
- **MOTD 还原**: 支持颜色码/格式码/JSON 组件树(v2+)
- **服务器图标**: 无图标时显示像素占位块(v2+)
- **在线玩家头像列表**: 展示最多 8 名在线玩家的头像与昵称(v2+)
- **双平台支持**: 同时支持 Java 版和基岩版服务器查询
- **ViaVersion 兼容**: 正确识别 ViaVersion 多版本(`send-supported-versions: true`)(v3+)
- **代理服务器查询**: 支持查询 Velocity 代理及其子服状态
- **默认服务器**: 可配置默认查询的服务器, 简化指令使用
- **头像/图标磁盘缓存**: 头像后台静默刷新, 查询零等待, 刷新失败自动沿用旧缓存. `/motdr` 立即刷新(v2.1+)
- **离线玩家识别**: 自动识别离线玩家 UUID 并跳过头像下载(v2.2+)
- **会话控制**: 可设置对哪些群聊/私聊生效
- **管理员权限**: 插件配置仅管理员可修改
- **完善报错**: 详细的错误提示和帮助信息

## QQ 官方机器人使用前提

在 QQ 官方机器人(bot.q.qq.com)的群里使用无斜杠 `motd` 指令, 需要在 **手机 QQ 群设置** 中：

1. 开启「**机器人主动在群聊内发言**」
2. 消息范围设置为「**获取群内全部消息**」(否则仅 @机器人 可触发)

> [!NOTE]
> 图片卡片经 AstrBot 图床以公网 URL 发送, QQ 官方平台仅支持 png/jpg 格式, 本插件固定输出 png, 无需额外配置. 

## ViaVersion 兼容性

| 服务器形态 | 上报内容 | 插件显示 |
|------|----------|----------|
| Velocity / BungeeCord / Waterfall 代理 | 版本名自带范围 | 版本范围 |
| ping 响应携带 `supportedVersions` | 协议号数组 | 版本范围 |
| 版本名自带范围/列举 | 版本名即范围 | 解析为版本区间 |
| 协议号 `-1/0`(部分代理/网关) | 识别为多版本模式 | 正确显示 |

显示版本范围的场景: 

1. `plugins/ViaVersion/config.yml` 设置 `send-supported-versions: true`
2. 使用 Velocity/BungeeCord 代理

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

> [!NOTE]
> BungeeCord 目前没有类似 velostat 的 HTTP API 插件, 只能使用子服直连模式. 

## 安装方法

### 方法一: 在官方插件市场中搜索 "Minecraft 服务器 motd 查询"

### 方法二: 在本仓库下载插件 zip 文件, 在 WebUI 中选择从文件安装插件

> [!WARNING]
> 使用`方法二`会导致无法自动检测更新! 解决方法: 已安装的插件卡片 → 右下角三个点 → 更换插件源 → 默认插件源 → 使用该插件源

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
| `enabled_sessions` | 会话白名单(关闭"对所有会话生效"后生效, 填会话 ID, 可用 `/sid` 获取) | `[]` |
| `admin_only_config` | 仅管理员可修改本插件配置(影响 `/motdconfig` 指令) | true |
| `use_api` | 直连失败后兜底: 回退调用 mcstatus.io API | true |
| `output_mode` | 输出模式: `image` 渲染像素风图片卡片 / `text` 纯文本(跳过渲染与头像预取, 几乎零开销) | `image` |
| `card_height_mode` | 卡片高度: `auto` 随内容自适应(紧凑无留白) / `fixed` 固定高度 720px(玩家少时补白, 尺寸统一) | `auto` |
| `show_server_icon` | 显示服务器图标 | true |
| `show_player_list` | 显示在线玩家列表 | true |
| `show_latency` | 显示查询延迟 | true |
| `query_timeout` | 查询总超时时间(秒), 单次查询的总死线 | `5` |
| `prefetch_avatars` | 从本地获取玩家头像并内嵌渲染图(过期/缺失项后台静默刷新) | true |
| `avatar_cache_ttl` | 头像刷新周期(小时), 过期后由后台静默刷新 | `12` |
| `avatar_neg_cache_ttl` | 头像后台下载失败负缓存(分钟), 该时长内不再重复入队重试; 0 为关闭 | `30` |

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
    "avatar_neg_cache_ttl": 30,
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
    "avatar_neg_cache_ttl": 30,
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
    "avatar_neg_cache_ttl": 30,
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
| `motdb` | 查询默认基岩版服务器(`motd-bedrock` 的短别名) | `motdb` |
| `motdb <地址:端口>` | 查询指定基岩版服务器(`motd-bedrock` 的短别名) | `motdb mc.example.com:19132` |

### 带斜杠前缀的指令

| 指令 | 说明 |
|------|------|
| `/motd [地址:端口]` | Java 版服务器查询 |
| `/motd-bedrock [地址:端口]` | 基岩版服务器查询 |
| `/motdb [地址:端口]` | 基岩版服务器查询(`/motd-bedrock` 的短别名) |

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
   - INFO 级别下发送 motd 查询, 应看到成对的 `[MOTD] 开始查询: ...` 与 `[MOTD] 查询完成: ...`; 没有则说明指令未被触发
   - 指令路由细节(如 `[MOTD] 匹配到 motd 指令`、`[MOTD] 收到 /motd 指令`)为 DEBUG 级别, 在 `data/cmd_config.json` 中设置 `"log_level": "DEBUG"` 并重启后可见

4. **检查白名单**
   - 如果关闭了"对所有会话生效", 需要将会话 ID(不是 QQ 号)加入 `enabled_sessions` 白名单, 会话 ID 可用 `/sid` 指令获取
   - 或者在 WebUI 中重新开启"对所有会话生效"

5. **QQ 官方机器人**
   - 确认群设置已开启「机器人主动在群聊内发言」与「获取群内全部消息」(见上文使用前提)

### 问题：ViaVersion 服务器版本显示异常？

本插件已内置 ViaVersion 兼容性处理：
- 版本名原样展示, 代理/多版本识别靠四条名称启发式(代理软件关键词、范围格式、多版本列举、`supportedVersions` 协议号数组经映射表翻译)
- 支持 Paper/Spigot/Bukkit/Purpur 等常见服务端
- 支持 Velocity/BungeeCord/Waterfall 等代理软件

**排查步骤：**

1. **查看版本解析日志(DEBUG 级别)**
   - 在 `data/cmd_config.json` 中设置 `"log_level": "DEBUG"` 并重启, 发送查询后在日志中搜索 `[MOTD] 版本解析输出`
   - DEBUG 日志会显示完整的解析链路：
     ```
     [MOTD] API 返回原始数据: version.name_raw='Velocity 1.7.2-1.21.4', version.name_clean='...', version.name='...', version.protocol=null
     [MOTD] 代理检测命中: 'velocity' -> Velocity
     [MOTD] 版本范围解析: all_versions=['1.7.2', '1.21.4'], sv=[], mc_versions=['1.7.2', '1.21.4']
     [MOTD] 版本解析输出: server='Velocity 1.7.2-1.21.4', client='1.7.2 ~ 1.21.4', via_hint='Velocity', is_multi_version=True, detect_reason='关键词匹配: velocity'
     ```

2. **检查代理检测结果**
   - 如果服务器使用代理软件, DEBUG 日志会显示 `代理检测命中` 或 `多版本检测命中 supportedVersions`
   - 支持的代理：Velocity、BungeeCord、Waterfall、FlameCord、Geyser 等

3. **反馈问题时请提供**
   - DEBUG 级别下完整的 `[MOTD]` 相关日志
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
2. 保持 `use_api: true`(默认开启)开启 API 失败回退(直连查询失败时自动回退调用 mcstatus.io API, 直连被墙/被过滤的外服也可获取状态)
3. 增加 `query_timeout` 配置值
4. 检查服务器是否在线
5. 检查 AstrBot 运行的网络环境

### 问题：收到的卡片没有颜色 / 头像不显示？

- 头像由插件预取并内嵌到渲染图(mc-heads → crafatar → minotar 三源自动回退 + 磁盘缓存, 默认 12 小时刷新周期), 查询路径零网络等待；缓存过期/缺失时本次照常显示旧图或占位块, 同时在**后台静默刷新**(低带宽下也不会拖慢查询), 新图下次查询生效
- 启动时插件会按「最近玩家名单」限速预热头像(每张间隔约 5 秒, 并发上限 2), 重启或长期无人查询后的第一次查询也能命中缓存；预热完成会输出一行 INFO
- 从未成功获取过的玩家回退为「首字母 + 哈希色」占位块, 后台下载成功后下次查询自动变为真实头像, 不影响卡片其余部分
- 头像显示为旧皮肤时属正常缓存现象(后台尚未刷新完成), 可执行 `/motdr` 立即清空缓存, 或调低 `avatar_cache_ttl`
- 如完全不希望发起头像请求, 可在配置中关闭 `prefetch_avatars` 或 `show_player_list`
- 离线玩家一律显示占位块属正常现象: 插件通过 UUID 本地识别盗版服玩家并自动跳过头像下载(此类 UUID 在 Mojang 数据库中不存在, 头像必然获取失败), 避免每次查询的无效网络请求(v2.2.0+)
- 服务器图标保留最后一次成功获取的值：某次查询未返回图标时自动沿用旧图标, 从未获取到过图标才显示像素占位块；可在配置中关闭 `show_server_icon` 隐藏图标槽

## 日志解读指南

插件输出的所有日志都以 `[MOTD]` 为前缀, 按级别分层：

- **INFO**: 精简主干, 每次查询通常只有「开始查询 + 查询完成」两条(发生直连失败回退 API 或代理子服查询时, 另加对应行)
- **DEBUG**: 详细诊断(指令路由、SRV 解析、版本解析链路、原始数据等), 默认不显示; 在 `data/cmd_config.json` 中设置 `"log_level": "DEBUG"` 并重启后可见
- **WARNING**: 可自动恢复的降级(缓存写入失败、畸形数据丢弃等)
- **ERROR**: 最终失败(发送失败、查询异常等, 附完整堆栈)

### 启动日志(INFO)

```
[MOTD] 插件初始化完成, 版本 X.X.X
[MOTD] 插件已加载 vX.X.X(Java/基岩 MOTD 查询, ViaVersion/Velocity/BungeeCord 多版本兼容)
[MOTD] 配置摘要: 默认服务器=xxx:25565, 查询类型=normal, 超时=5s, 输出模式=图片, API回退=开, 头像预取=开, 生效范围=全部会话
[MOTD] 代理模式: 方式=velostat, 详情=http://代理IP:8080      # 仅 query_type=proxy 时输出
```

### 查询流程日志(INFO)

```
[MOTD] 开始查询: server='mc.example.com', is_java=True, 超时=5s, 会话=aiocqhttp:GroupMessage:123456
[MOTD] 查询完成: source=direct, 版本=1.21.11, 玩家=10/100, 图标=有, 耗时=123ms   # source=direct/api 标明数据来源
```

直连失败触发 API 回退时, 两条之间会出现回退链 INFO:

```
[MOTD] 直连失败(连接被拒绝), 回退 API 查询(剩余死线 3.2s)
[MOTD] API 回退成功(823ms)
```

### 代理查询日志(INFO)

```
[MOTD] 开始代理查询: method=velostat, server='proxy.example.com', 超时=5s
[MOTD] 子服查询汇总: 成功 3 个, 失败/异常 0 条
```

### 管理操作日志(INFO)

```
[MOTD] 收到 /motdr 指令
[MOTD] 手动清空缓存(/motdr): 玩家头像 12 个, 服务器图标 3 个, 会话=...
[MOTD] 收到 /motdconfig 指令: action=default, value=...
[MOTD] 配置已保存: mc.example.com:25565
[MOTD] 头像预热完成: 名单 32 人, 入队后台刷新 5 个    # 启动预热, 仅实际入队时输出(后台限速逐张刷新)
```

### 诊断细节日志(DEBUG)

```
[MOTD] 匹配到 motd 指令: motd mc.example.com              # 无斜杠指令路由
[MOTD] 收到 /motd 指令: server='mc.example.com'           # 斜杠指令路由
[MOTD] 使用指定服务器: mc.example.com:25565
[MOTD] SRV 解析成功: mc.example.com -> play.example.com:25565
[MOTD] API 返回原始数据: version.name_raw='...', version.protocol=...
[MOTD] 代理检测命中: 'velocity' -> Velocity
[MOTD] 版本范围解析: all_versions=['1.7.2', '1.21.4'], sv=[], mc_versions=['1.7.2', '1.21.4']
[MOTD] 版本解析输出: server='Velocity 1.7.2-1.21.4', client='1.7.2 ~ 1.21.4', via_hint='Velocity', is_multi_version=True, detect_reason='关键词匹配: velocity'
[MOTD] Java 版原始数据: version={...}, players=10/100, 样例(前8)=[...]
[MOTD] 格式化结果: server_version='...', client_version='...', players=10/100, via_hint='...'
[MOTD] 头像缓存命中: 4/4 个
[MOTD] 头像后台刷新入队 2 个(新图下次查询生效)          # 过期/缺失项转入后台, 查询零等待
```

### 错误与降级日志(WARNING/ERROR)

```
[MOTD] 子服配置解析失败: ... (错误原因)                   # WARNING: 配置写错, 其余子服照常解析
[MOTD] 服务器上报图标未通过校验, 已丢弃: ...              # WARNING: 畸形/恶意图标, 自动丢弃
[MOTD] MOTD 组件树解析失败, 降级纯文本: ...               # WARNING: 畸形描述, 渲染为纯文本
[MOTD] 玩家头像预取失败(不影响查询结果): ...              # WARNING
[MOTD] 查询完成(失败): 连接超时, 请检查服务器地址和端口是否正确   # INFO: 服务器离线属预期失败
[MOTD] 查询超时(>5s): mc.example.com:25565                # ERROR
[MOTD] 查询异常: mc.example.com:25565 ...                 # ERROR: 附完整堆栈
[MOTD] 图片渲染/发送失败, 回退到文本: ...                 # ERROR: 第一级降级, 自动改发文本卡片
[MOTD] 文本回退发送失败(放弃): ...                        # ERROR: 文本也失败, 仅记日志, 不阻塞主流程
```

## 许可证

[MIT](LICENSE)
