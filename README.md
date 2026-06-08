# AstrBot MOTD 查询插件

一个用于查询 Minecraft 服务器状态的 AstrBot 插件，支持 Java 版和基岩版服务器，**完美兼容 ViaVersion 多版本服务器**。

## 功能特性

- ✅ **MOTD 查询**: 查询 Minecraft 服务器的 MOTD、在线玩家、版本等信息
- ✅ **双版本支持**: 同时支持 Java 版和基岩版服务器查询
- ✅ **ViaVersion 兼容**: 智能识别 ViaVersion 多版本服务器，正确显示版本范围
- ✅ **无需斜杠**: 直接输入 `motd` 即可触发，无需 `/` 前缀
- ✅ **默认服务器**: 可配置默认查询的服务器，简化指令使用
- ✅ **标准端口**: 查询其他服务器时不带端口自动使用标准端口 25565
- ✅ **API 查询**: 使用 mcstatus.io API 查询，更稳定可靠
- ✅ **会话控制**: 可设置对哪些群聊/私聊生效
- ✅ **管理员权限**: 插件配置仅管理员可修改
- ✅ **完善报错**: 详细的错误提示和帮助信息

## ViaVersion 兼容性

本插件完美支持安装了 ViaVersion/ViaBackwards 的服务器：

| 情况 | 处理方式 |
|------|----------|
| `protocol.version = -1/0` | 识别为多版本模式，显示 `多版本` 而非 `-1` |
| `version.name` 含版本范围 | 自动提取并显示 `支持客户端版本: 1.8 - 1.21.3` |
| Paper/Spigot + ViaVersion | 解析协议号范围并转换为版本号显示 |
| ViaVersion 字样检测 | 自动识别并标注 ViaVersion 兼容 |

**示例输出：**
```
🎮 Minecraft 服务器状态
━━━━━━━━━━━━━━━━━━
📍 地址: play.example.com:25565
📋 版本: Paper 1.21.1 (Protocol: 767-768)
🔄 支持客户端版本: 1.21 - 1.21.2
👥 玩家: 42/100
━━━━━━━━━━━━━━━━━━
📝 MOTD:
欢迎来到示例服务器！
```

## 安装方法

1. 将插件文件夹 `astrbot_plugin_motd` 复制到 AstrBot 的 `plugins` 目录下
2. **重启 AstrBot**（重要！热重载可能无法正确加载配置）
3. 在 WebUI 的插件配置中设置相关参数
4. 保存配置并重启 AstrBot

## 配置方法

### 1. 在 WebUI 中配置

访问 AstrBot WebUI → 插件 → MOTD查询 → 配置：

| 配置项 | 说明 | 建议值 |
|--------|------|--------|
| `default_server` | 默认服务器地址 | `n.rainplay.cn` |
| `default_port` | 默认服务器端口 | `46861` |
| `enable_all_sessions` | 对所有会话生效 | ✅ 勾选 |
| `use_api` | 使用 API 查询 | ✅ 勾选（更稳定） |
| `query_timeout` | 查询超时时间 | `5` |

**配置完成后必须重启 AstrBot！**

### 2. 配置文件方式

也可以直接编辑 `data/config/astrbot_plugin_motd_config.json`：

```json
{
    "default_server": "n.rainplay.cn",
    "default_port": 46861,
    "enable_all_sessions": true,
    "enabled_sessions": [],
    "admin_only_config": true,
    "query_timeout": 5,
    "use_api": true
}
```

## 使用方法

### 基础指令（无需斜杠）

| 指令 | 说明 | 示例 |
|------|------|------|
| `motd` | 查询默认服务器 | `motd` |
| `motd <地址>` | 查询指定服务器（使用标准端口 25565） | `motd mc.hypixel.net` |
| `motd <地址:端口>` | 查询指定服务器（使用指定端口） | `motd n.rainplay.cn:46861` |
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

> ⚠️ **注意**: 配置指令仅管理员可用。

## 管理员配置

### 设置管理员

编辑 `data/cmd_config.json` 文件，在 `admins_id` 列表中添加管理员 QQ 号：

```json
{
    "admins_id": ["123456789", "987654321"]
}
```

或者在 AstrBot 控制台使用指令：
- `/op <QQ号>` - 添加管理员
- `/deop <QQ号>` - 移除管理员

## 故障排查

### 问题：发送 `motd` 没有反应？

**排查步骤：**

1. **检查插件是否加载**
   - 查看 AstrBot 日志，搜索 `[MOTD]`
   - 应该看到类似：`[MOTD] 插件已加载 v1.0.9`

2. **检查配置是否正确**
   - 在 WebUI 中查看插件配置
   - 确认 `default_server` 和 `default_port` 已设置
   - 确认 `enable_all_sessions` 为 true

3. **检查日志级别**
   - 在 `data/cmd_config.json` 中设置 `"log_level": "DEBUG"`
   - 重启后查看是否有 `[MOTD] 收到消息` 的日志

4. **检查白名单**
   - 如果开启了 ID 白名单，确保你的 QQ 号在白名单中
   - 或者在 WebUI 中关闭白名单限制

### 问题：ViaVersion 服务器版本显示异常？

本插件已内置 ViaVersion 兼容性处理：
- 自动检测 `protocol.version = -1/0` 的多版本模式
- 从 `version.name` 提取版本范围
- 支持 Paper/Spigot/Bukkit/Purpur 等常见服务端

如果仍有问题，请提供服务器返回的原始 JSON 数据以便调试。

### 问题：查询超时或连接被拒绝？

1. 确认服务器地址和端口是否正确
2. 尝试使用 `use_api: true`（默认开启）使用 API 查询
3. 增加 `query_timeout` 配置值
4. 检查服务器是否在线

### 问题：返回两次消息？

此问题已在 v1.0.8+ 修复。如果仍有问题：
1. 确保使用的是最新版本
2. 重启 AstrBot

## 查询结果示例

### 普通服务器
```
🎮 Minecraft 服务器状态
━━━━━━━━━━━━━━━━━━
📍 地址: mc.hypixel.net:25565
📋 版本: 1.8.9 (协议 47)
👥 玩家: 42000/50000
━━━━━━━━━━━━━━━━━━
📝 MOTD:
Hypixel Network
```

### ViaVersion 多版本服务器
```
🎮 Minecraft 服务器状态
━━━━━━━━━━━━━━━━━━
📍 地址: play.example.com:25565
📋 版本: Paper 1.21.1 (Protocol: 767-768)
🔄 支持客户端版本: 1.21 - 1.21.2
👥 玩家: 42/100
━━━━━━━━━━━━━━━━━━
📝 MOTD:
欢迎来到示例服务器！
```

## 更新日志

### v1.0.9
- ✅ **新增 ViaVersion 兼容性支持**
- 智能识别多版本服务器（protocol = -1/0）
- 自动提取版本范围并显示
- 支持 Paper/Spigot/Bukkit/Purpur 等常见服务端

### v1.0.8
- 添加 mcstatus.io API 查询支持
- 修复端口解析问题（不带端口时使用标准端口 25565）
- 修复重复响应问题

### v1.0.0
- 初始版本发布

## 支持与反馈

如有问题或建议，欢迎提交 Issue 或 Pull Request。

## 许可证

MIT License
