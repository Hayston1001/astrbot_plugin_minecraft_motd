"""
AstrBot MOTD 查询插件
用于查询 Minecraft 服务器状态
"""

import socket
import struct
import json
import time
import re
import random
import os
import base64
import hashlib
from pathlib import Path
import asyncio
from urllib.parse import quote
import aiohttp
from typing import Optional, Dict, Any, Tuple

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, StarTools, register
from astrbot.api import logger, AstrBotConfig
import astrbot.api.message_components as Comp


# Java 版标准端口
JAVA_DEFAULT_PORT = 25565
# 基岩版标准端口
BEDROCK_DEFAULT_PORT = 19132

# ============================================================
# 协议号 → 版本名 完整映射（2026-06 更新）
# 格式: protocol: (显示版本, 主版本号)
# 注: 26.x 起 Minecraft 采用年份.版本的新命名规则
# ============================================================
PROTOCOL_VERSION_MAP: Dict[int, Tuple[str, str]] = {
    4:    ("1.7.2-1.7.5", "1.7"),
    5:    ("1.7.6-1.7.10", "1.7"),
    47:   ("1.8.x", "1.8"),
    107:  ("1.9", "1.9"),
    108:  ("1.9.1", "1.9"),
    109:  ("1.9.2", "1.9"),
    110:  ("1.9.3-1.9.4", "1.9"),
    210:  ("1.10.x", "1.10"),
    315:  ("1.11", "1.11"),
    316:  ("1.11.1-1.11.2", "1.11"),
    335:  ("1.12", "1.12"),
    338:  ("1.12.1", "1.12"),
    340:  ("1.12.2", "1.12"),
    393:  ("1.13", "1.13"),
    401:  ("1.13.1", "1.13"),
    404:  ("1.13.2", "1.13"),
    477:  ("1.14", "1.14"),
    480:  ("1.14.1", "1.14"),
    485:  ("1.14.2", "1.14"),
    490:  ("1.14.3", "1.14"),
    498:  ("1.14.4", "1.14"),
    573:  ("1.15", "1.15"),
    575:  ("1.15.1", "1.15"),
    578:  ("1.15.2", "1.15"),
    735:  ("1.16", "1.16"),
    736:  ("1.16.1", "1.16"),
    751:  ("1.16.2", "1.16"),
    753:  ("1.16.3", "1.16"),
    754:  ("1.16.4-1.16.5", "1.16"),
    755:  ("1.17", "1.17"),
    756:  ("1.17.1", "1.17"),
    757:  ("1.18-1.18.1", "1.18"),
    758:  ("1.18.2", "1.18"),
    759:  ("1.19", "1.19"),
    760:  ("1.19.1-1.19.2", "1.19"),
    761:  ("1.19.3", "1.19"),
    762:  ("1.19.4", "1.19"),
    763:  ("1.20-1.20.1", "1.20"),
    764:  ("1.20.2", "1.20"),
    765:  ("1.20.3-1.20.4", "1.20"),
    766:  ("1.20.5-1.20.6", "1.20"),
    767:  ("1.21-1.21.1", "1.21"),
    768:  ("1.21.2-1.21.3", "1.21"),
    769:  ("1.21.4", "1.21"),
    770:  ("1.21.5", "1.21"),
    771:  ("1.21.6", "1.21"),
    772:  ("1.21.7-1.21.8", "1.21"),
    773:  ("1.21.9-1.21.10", "1.21"),
    774:  ("1.21.11", "1.21"),
    775:  ("26.1-26.1.2", "26.1"),
    776:  ("26.2", "26.2"),
}

# 已知代理/跨版本软件关键词 → 显示名
_PROXY_KEYWORDS = {
    "velocity": "Velocity",
    "bungeecord": "BungeeCord",
    "bungee": "BungeeCord",
    "waterfall": "Waterfall",
    "flamecord": "FlameCord",
    "viaversion": "ViaVersion",
    "viabackwards": "ViaBackwards",
    "viaforwarders": "ViaForwarders",
    "geyser": "Geyser",
    "wynnproxy": "WynnProxy",
}

# Minecraft 颜色码 → CSS 颜色值
MINECRAFT_COLOR_MAP = {
    '0': '#000000', '1': '#0000aa', '2': '#00aa00', '3': '#00aaaa',
    '4': '#aa0000', '5': '#aa00aa', '6': '#ffaa00', '7': '#aaaaaa',
    '8': '#555555', '9': '#5555ff', 'a': '#55ff55', 'b': '#55ffff',
    'c': '#ff5555', 'd': '#ff55ff', 'e': '#ffff55', 'f': '#ffffff',
}

# Minecraft JSON 组件 color 字段命名色 → CSS 颜色值
_MC_NAMED_COLORS = {
    'black': '#000000', 'dark_blue': '#0000AA', 'dark_green': '#00AA00', 'dark_aqua': '#00AAAA',
    'dark_red': '#AA0000', 'dark_purple': '#AA00AA', 'gold': '#FFAA00', 'gray': '#AAAAAA',
    'dark_gray': '#555555', 'blue': '#5555FF', 'green': '#55FF55', 'aqua': '#55FFFF',
    'red': '#FF5555', 'light_purple': '#FF55FF', 'yellow': '#FFFF55', 'white': '#FFFFFF',
}

# § 格式码 → 状态键（颜色码在 MINECRAFT_COLOR_MAP 中处理，§k 混淆码忽略）
_MC_FORMAT_CODES = {'l': 'bold', 'o': 'italic', 'n': 'underline', 'm': 'strike'}

# MOTD § 码切分正则（含大小写变体）
_MOTD_SECTION_RE = re.compile(r'(§[0-9a-fk-or])', re.IGNORECASE)

# 无头像时玩家占位块配色（MC 调色板，按玩家名哈希取色，保证同名稳定）
_PLAYER_AVATAR_COLORS = ['#55FF55', '#FFAA00', '#55FFFF', '#FF5555', '#FF55FF', '#FFFF55', '#5555FF', '#00AAAA', '#AA00AA', '#AAAAAA']

# 查询数据源 → 展示名
_SOURCE_LABELS = {
    'api': 'mcstatus.io API',
    'direct': 'TCP 直连',
    'bedrock_udp': 'UDP 直连',
}

# ============================================================
# QQ 官方平台表情映射（type=1 系统表情）
# 值: (QQ 系统表情 ID 或 None, 各平台通用 Unicode emoji)
# ID 来源: https://bot.q.qq.com/wiki/develop/api-v2/openapi/emoji/model.html
# 说明: QQ 无对应系统表情时 qq_id 置 None，全平台统一用 Unicode emoji
# ============================================================
EMOJI_MAP = {
    'searching': '🔍',  # 查询中
    'success':   '✅',  # 查询成功
    'fail':      '❌',  # 查询失败
    'online':    '🟢',  # 在线
    'offline':   '🟠',  # 离线/未启动
    'proxy':     '🌐',  # 代理
}


def _player_color(name: str) -> str:
    """根据玩家名生成稳定的标识色（无头像时的占位块边框/文字色）"""
    idx = sum(ord(c) for c in (name or '?')) % len(_PLAYER_AVATAR_COLORS)
    return _PLAYER_AVATAR_COLORS[idx]


def _default_motd_state() -> dict:
    """MOTD 渲染默认样式状态（MC 默认文字为白色、无格式）"""
    return {"color": "#FFFFFF", "bold": False, "italic": False, "underline": False, "strike": False}


def _apply_section_code(state: dict, code: str) -> None:
    """将一个 § 格式码应用到状态上（MC 语义：颜色码会重置已有格式，§r 全部重置）"""
    code = code.lower()
    if code == 'r':
        state.update(_default_motd_state())
    elif code in MINECRAFT_COLOR_MAP:
        state.update(_default_motd_state())
        state["color"] = MINECRAFT_COLOR_MAP[code]
    elif code == 'k':
        pass  # 混淆码（§k）：静态渲染环境无动态效果，忽略
    elif code in _MC_FORMAT_CODES:
        state[_MC_FORMAT_CODES[code]] = True


def _parse_motd_segments(data, state: dict, out: list) -> None:
    """递归解析 MOTD 数据（§ 码字符串 / JSON 组件树 / 列表）为样式段列表
    JSON 组件树语义：子组件继承父组件样式，自身字段可覆盖（显式 false 也覆盖）
    """
    if data is None:
        return
    if isinstance(data, str):
        cur = dict(state)
        for seg in _MOTD_SECTION_RE.split(data):
            if not seg:
                continue
            if len(seg) == 2 and seg.startswith('§'):
                _apply_section_code(cur, seg[1])
            else:
                out.append({"text": seg, **cur})
    elif isinstance(data, dict):
        cur = dict(state)
        color = data.get('color')
        if isinstance(color, str):
            color_l = color.lower()
            resolved = MINECRAFT_COLOR_MAP.get(color_l) or _MC_NAMED_COLORS.get(color_l)
            if resolved is None and color_l.startswith('#'):
                # 直接使用 hex 颜色（JSON 组件树允许 #RRGGBB）
                resolved = color
            if resolved:
                cur['color'] = resolved
            elif color_l == 'reset':
                cur = _default_motd_state()
        # JSON 组件格式字段：存在即覆盖（含显式 false）
        for key, fmt in (('bold', 'bold'), ('italic', 'italic'),
                         ('underlined', 'underline'), ('strikethrough', 'strike')):
            if data.get(key) is not None:
                cur[fmt] = bool(data[key])
        _parse_motd_segments(data.get('text', ''), cur, out)
        for item in data.get('extra') or []:
            _parse_motd_segments(item, cur, out)
    elif isinstance(data, list):
        for item in data:
            _parse_motd_segments(item, state, out)
    else:
        out.append({"text": str(data), **state})


def _render_motd_segments(segments: list) -> str:
    """合并相邻同样式段并渲染为 HTML span 序列（默认样式不加 span，减少体积）"""
    merged = []
    for seg in segments:
        text = seg.get('text', '')
        if not text:
            continue
        style = (seg.get('color'), seg.get('bold'), seg.get('italic'), seg.get('underline'), seg.get('strike'))
        if merged and merged[-1][0] == style:
            merged[-1] = (style, merged[-1][1] + text)
        else:
            merged.append((style, text))

    html = []
    for (color, bold, italic, underline, strike), text in merged:
        esc = _html_escape(text)
        props = []
        if color and color.upper() != '#FFFFFF':
            props.append(f'color:{color}')
        if bold:
            props.append('font-weight:bold')
        if italic:
            props.append('font-style:italic')
        deco = []
        if underline:
            deco.append('underline')
        if strike:
            deco.append('line-through')
        if deco:
            props.append('text-decoration:' + ' '.join(deco))
        if props:
            html.append(f'<span style="{";".join(props)}">{esc}</span>')
        else:
            html.append(esc)
    return ''.join(html)

# 版本号正则（匹配 1.x.y 或 1.x）
_VERSION_RE = re.compile(r'(\d+\.\d+(?:\.\d+)?)')

# 版本名 → 协议号 反向查找表（从 PROTOCOL_VERSION_MAP 构建）
_VERSION_TO_PROTOCOL: Dict[str, int] = {}


def _build_version_to_protocol():
    """从 PROTOCOL_VERSION_MAP 构建版本名到协议号的反向映射"""
    for proto, (ver_str, _major) in PROTOCOL_VERSION_MAP.items():
        parts = ver_str.split("-")
        start = parts[0]
        end = parts[-1] if len(parts) > 1 else start

        start_m = _VERSION_RE.search(start)
        end_m = _VERSION_RE.search(end)
        if not start_m or not end_m:
            continue

        start_parts = [int(x) for x in start_m.group(1).split(".")]
        end_parts = [int(x) for x in end_m.group(1).split(".")]

        # 补齐到三段
        while len(start_parts) < 3:
            start_parts.append(0)
        while len(end_parts) < 3:
            end_parts.append(0)

        if start_parts == end_parts:
            _VERSION_TO_PROTOCOL[".".join(str(x) for x in start_parts)] = proto
        else:
            # 范围映射：首尾版本都指向同一个协议号
            for ver in [
                ".".join(str(x) for x in start_parts),
                ".".join(str(x) for x in end_parts),
            ]:
                _VERSION_TO_PROTOCOL[ver] = proto

    # 特殊映射：范围内未被自动覆盖的中间版本
    _VERSION_TO_PROTOCOL["26.1.1"] = 775  # 26.1.1 在 26.1.0 和 26.1.2 之间，共享协议 775


_build_version_to_protocol()


def _lookup_protocol_from_name(version_name: str) -> Optional[int]:
    """从版本名中提取最高版本号，反查协议号。未找到返回 None。"""
    if not version_name:
        return None
    matches = _VERSION_RE.findall(version_name)
    if not matches:
        return None
    # 取最高版本号
    best = max(matches, key=lambda v: [int(x) for x in v.split(".") if x.isdigit()])
    # 先精确查找，再尝试补齐到三段查找（如 1.8 → 1.8.0）
    result = _VERSION_TO_PROTOCOL.get(best)
    if result is not None:
        return result
    parts = best.split(".")
    if len(parts) == 2:
        result = _VERSION_TO_PROTOCOL.get(f"{best}.0")
        if result is not None:
            return result
    return None


def _html_escape(text: str) -> str:
    """HTML 转义"""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# ============================================================
# 共享 HTTP 会话（避免每次查询重建连接 / TLS 握手）
# ============================================================
_HTTP_SESSION: Optional[aiohttp.ClientSession] = None


def _get_http_session() -> aiohttp.ClientSession:
    """获取全局共享的 aiohttp 会话（懒加载，由插件 terminate() 释放）"""
    global _HTTP_SESSION
    if _HTTP_SESSION is None or _HTTP_SESSION.closed:
        _HTTP_SESSION = aiohttp.ClientSession()
    return _HTTP_SESSION


async def _close_http_session() -> None:
    """关闭并释放共享会话（插件卸载/重载时调用）"""
    global _HTTP_SESSION
    if _HTTP_SESSION is not None and not _HTTP_SESSION.closed:
        await _HTTP_SESSION.close()
    _HTTP_SESSION = None


# ============================================================
# 磁盘持久缓存：玩家头像 / 服务器图标
# 目录规范（AstrBot 插件大文件存储标准）:
#   data/plugin_data/astrbot_plugin_minecraft_motd/avatars/  玩家头像
#   data/plugin_data/astrbot_plugin_minecraft_motd/icons/    服务器图标
# 下载时间写入文件 mtime；TTL 仅作为刷新周期：过期后下次查询尝试重新下载，
# 下载失败继续使用旧缓存（文件永不因过期删除，仅 /motdr 手动清空）
# ============================================================
AVATAR_TTL_HOURS_DEFAULT = 12   # 玩家头像刷新周期（小时，可在配置中调整）
NEG_CACHE_TTL_MINUTES_DEFAULT = 10   # 头像下载失败负缓存默认时长（分钟，可在配置 avatar_neg_cache_ttl 中调整，0=关闭）
_NEG_CACHE: Dict[str, float] = {}
_AVATAR_FETCH_SEM = asyncio.Semaphore(4)  # 头像并发下载上限: 削弱冷缓存时 8 路并发 TLS 握手在单核弱机上的 CPU 尖刺


def _get_cache_dir(subdir: str) -> Optional[Path]:
    """获取缓存子目录（自动创建），失败返回 None"""
    base: Path
    try:
        base = Path(StarTools.get_data_dir("astrbot_plugin_minecraft_motd"))
    except Exception as e:
        logger.warning(f"[MOTD] 获取插件数据目录失败，回退到相对路径: {e}")
        base = Path("data") / "plugin_data" / "astrbot_plugin_minecraft_motd"
    try:
        d = base / subdir
        d.mkdir(parents=True, exist_ok=True)
        return d
    except OSError as e:
        logger.warning(f"[MOTD] 创建缓存目录失败（{subdir}）: {e}")
        return None


def _safe_filename(key: str) -> str:
    """将缓存键转为安全文件名"""
    return re.sub(r'[^0-9a-zA-Z._-]', '_', key)[:100]


def _cache_read_any(path: Path) -> Optional[bytes]:
    """读取缓存文件（不检查 TTL：即使过期也返回，供“刷新失败沿用旧缓存”使用）"""
    try:
        return path.read_bytes()
    except OSError:
        return None


def _cache_write(path: Path, data: bytes) -> bool:
    """写入缓存文件（mtime 即下载时间），失败不抛出"""
    try:
        path.write_bytes(data)
        os.utime(path, None)
        return True
    except OSError as e:
        logger.warning(f"[MOTD] 缓存写入失败（{path.name}）: {e}")
        return False


def clear_disk_cache() -> Tuple[int, int]:
    """清空头像与图标磁盘缓存及失败负缓存，返回（删除头像数, 删除图标数）"""
    counts = []
    for subdir in ("avatars", "icons"):
        n = 0
        cache_dir = _get_cache_dir(subdir)
        if cache_dir is not None:
            for f in cache_dir.iterdir():
                try:
                    if f.is_file():
                        f.unlink()
                        n += 1
                except OSError:
                    pass
        counts.append(n)
    _NEG_CACHE.clear()
    return counts[0], counts[1]


def _normalize_uuid(uuid: str) -> str:
    """UUID 规范化为带连字符形式（crafatar 等下载源要求），无效返回空串"""
    u = (uuid or "").strip().lower().replace("-", "")
    if len(u) != 32 or any(c not in "0123456789abcdef" for c in u):
        return ""
    return f"{u[0:8]}-{u[8:12]}-{u[12:16]}-{u[16:20]}-{u[20:32]}"


def _avatar_cache_key(uuid: str, name: str) -> str:
    """头像缓存键：有 UUID 用 UUID，否则用玩家名（保证查询与渲染两侧一致）"""
    u = _normalize_uuid(uuid)
    if u:
        return f"u:{u}"
    return f"n:{(name or '?').strip().lower()}"


def _offline_uuid(name: str) -> str:
    """离线模式玩家 UUID：等价 Java UUID.nameUUIDFromBytes("OfflinePlayer:" + name)

    盗版服（离线模式）按玩家名 MD5 推导 UUID，Mojang 数据库中不存在对应档案，
    头像源按 UUID 查询必然查无此人。
    """
    data = bytearray(hashlib.md5(("OfflinePlayer:" + name).encode("utf-8")).digest())
    data[6] = (data[6] & 0x0F) | 0x30   # 版本位置 3
    data[8] = (data[8] & 0x3F) | 0x80   # 变体位置 IETF RFC 4122
    h = data.hex()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def _is_offline_uuid(uuid: str, name: str) -> bool:
    """判断服务器下发的 UUID 是否为离线模式推导 UUID（盗版服玩家标志）"""
    norm = _normalize_uuid(uuid)
    if not norm or not name or name == '?':
        return False
    return norm == _offline_uuid(name)


def _avatar_source_urls(uuid: str, name: str) -> list:
    """头像下载源列表（按顺序回退）：UUID 优先，无 UUID 时用玩家名"""
    urls = []
    if uuid:
        urls.append(f"https://mc-heads.net/avatar/{uuid}/32")
        urls.append(f"https://crafatar.com/avatars/{uuid}?overlay&size=32")
        urls.append(f"https://minotar.net/helm/{uuid}/32")
    if name and name != '?':
        urls.append(f"https://mc-heads.net/avatar/{quote(name)}/32")
        urls.append(f"https://minotar.net/helm/{quote(name)}/32")
    return urls


async def _fetch_image_bytes(url: str, timeout: float = 2.5) -> Optional[bytes]:
    """下载图片字节，失败返回 None"""
    try:
        async with _get_http_session().get(
                url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            if resp.status != 200:
                return None
            data = await resp.read()
            if data and len(data) <= 100_000:  # 32px 头像通常 <5KB，防御异常大响应
                return data
    except Exception:
        pass
    return None


async def get_player_avatars(players: list, ttl_hours: float = AVATAR_TTL_HOURS_DEFAULT,
                             neg_ttl_minutes: float = NEG_CACHE_TTL_MINUTES_DEFAULT) -> Dict[str, str]:
    """批量获取玩家头像 data URI（磁盘持久缓存 + 多源回退 + 失败负缓存）

    TTL 语义（stale-while-revalidate）：TTL 仅作为刷新周期——
    - 缓存未过期：直接使用，不发起下载；
    - 已过期或无缓存：本次查询尝试重新下载；
    - 离线模式 UUID（盗版服按名推导）：本地判定后完全跳过下载，渲染用占位块；
    - 下载失败/超时：有旧缓存则继续用旧缓存，从未成功获取过才用占位块；
    - 下载失败负缓存（neg_ttl_minutes，分钟，0=关闭）：失败后该时长内不再重试，仅限制重试频率，不影响旧缓存展示。
    - 缓存文件永不因过期删除（仅 /motdr 手动清空）。

    players: [{"name": str, "uuid": str}, ...]
    返回: {缓存键: data:image/png;base64,...}
    """
    ttl = max(1, int(ttl_hours * 3600))
    neg_ttl = max(0.0, float(neg_ttl_minutes)) * 60  # 负缓存时长（秒），0=关闭负缓存
    cache_dir = _get_cache_dir("avatars")

    result: Dict[str, str] = {}
    todo: Dict[str, Tuple[str, str]] = {}  # key -> (uuid, name)
    offline_names: list = []  # 本次检测到的离线模式玩家名（仅用于日志）
    now = time.time()
    for p in players:
        if not isinstance(p, dict):
            continue
        name = (p.get("name") or "?").strip() or "?"
        uuid = p.get("uuid") or p.get("id") or ""
        key = _avatar_cache_key(uuid, name)
        path = cache_dir / f"{_safe_filename(key)}.png" if cache_dir else None
        data = _cache_read_any(path) if path else None
        if data is not None:
            result[key] = "data:image/png;base64," + base64.b64encode(data).decode()
            try:
                stale = now - path.stat().st_mtime > ttl
            except OSError:
                stale = True
            if not stale:
                continue  # 缓存未过期：直接使用，不发起下载
        # 无缓存或已过期：尝试刷新（负缓存仅限制重试频率，不影响旧缓存展示）
        if neg_ttl > 0 and _NEG_CACHE.get(key, 0) + neg_ttl > now:
            continue
        if _is_offline_uuid(uuid, name):
            # 离线模式 UUID（盗版服）：Mojang 库无此档案，UUID 头像源必然 404，
            # 直接跳过下载（渲染时用占位块）；纯本地判定零网络成本，也不进负缓存
            offline_names.append(name)
            continue
        todo[key] = (uuid, name)

    if offline_names:
        logger.info(f"[MOTD] 检测到离线模式玩家（盗版服 UUID），跳过头像下载: {', '.join(offline_names)}")

    if not todo:
        return result

    async def _fetch_one(key: str, uuid: str, name: str) -> None:
        # 并发闸门: 限制同时在飞的下载/TLS 握手数, 避免冷缓存时瞬时 CPU 尖刺拖慢单核弱机
        async with _AVATAR_FETCH_SEM:
            for url in _avatar_source_urls(_normalize_uuid(uuid), name):
                data = await _fetch_image_bytes(url)
                if data:
                    result[key] = "data:image/png;base64," + base64.b64encode(data).decode()
                    if cache_dir is not None:
                        _cache_write(cache_dir / f"{_safe_filename(key)}.png", data)
                    return
            _NEG_CACHE[key] = time.time()
        if key in result:
            logger.info(f"[MOTD] 玩家头像刷新失败，继续使用旧缓存: {name}")
        else:
            logger.info(f"[MOTD] 玩家头像获取失败（渲染时用占位块回退）: {name}")

    # 并发拉取(最多 _AVATAR_FETCH_SEM 路同时在飞)；整体限时，超时的玩家沿用旧缓存/占位块，已完成的正常缓存
    try:
        await asyncio.wait_for(
            asyncio.gather(*(_fetch_one(k, u, n) for k, (u, n) in todo.items())),
            timeout=4.0,
        )
    except asyncio.TimeoutError:
        missed = len(todo) - sum(1 for k in todo if k in result)
        logger.info(f"[MOTD] 玩家头像批量获取超时，{missed} 个沿用旧缓存/占位块")
    return result


def cache_server_icon(server_address: str, icon_data_uri: str) -> None:
    """将查询结果自带的服务器图标 data URI 写入磁盘缓存（每次成功查询自动刷新）"""
    if not icon_data_uri or not icon_data_uri.startswith("data:image"):
        return
    try:
        data = base64.b64decode(icon_data_uri.split(",", 1)[1])
    except Exception:
        return
    cache_dir = _get_cache_dir("icons")
    if cache_dir is not None:
        _cache_write(cache_dir / f"{_safe_filename(server_address)}.png", data)


def get_cached_server_icon(server_address: str) -> Optional[str]:
    """读取磁盘缓存的服务器图标 data URI（本次查询未返回图标时回退显示）

    不设 TTL 门限：图标随每次查询自带最新值（即“尝试获取”），
    只要曾经成功获取过就持续沿用旧缓存，从未获取过才返回 None。
    """
    cache_dir = _get_cache_dir("icons")
    if cache_dir is None:
        return None
    data = _cache_read_any(cache_dir / f"{_safe_filename(server_address)}.png")
    if not data:
        return None
    return "data:image/png;base64," + base64.b64encode(data).decode()


async def query_java_server_api(host: str, port: int = JAVA_DEFAULT_PORT) -> Dict[str, Any]:
    """使用第三方 API 查询 Java 版服务器状态"""
    _t0 = time.perf_counter()
    try:
        # 复用全局共享 HTTP 会话：省去每次查询的 TCP+TLS 握手（弱机 CPU 更省、延迟更低），会话由 terminate() 统一释放
        session = _get_http_session()
        url = f"https://api.mcstatus.io/v2/status/java/{host}:{port}"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("online"):
                    version_data = data.get("version", {})
                    # Bug Fix: API 返回的是 name_raw/name_clean，不是 name
                    version_name_raw = version_data.get("name_raw") or version_data.get("name_clean") or version_data.get("name", "")
                    protocol_raw = version_data.get("protocol")

                    logger.info(f"[MOTD] API 返回原始数据: version.name_raw='{version_data.get('name_raw')}', "
                                f"version.name_clean='{version_data.get('name_clean')}', "
                                f"version.name='{version_data.get('name')}', "
                                f"version.protocol={protocol_raw}")

                    # API 返回 protocol: null 时，尝试从版本名反查协议号
                    if protocol_raw is None:
                        logger.info(f"[MOTD] API 返回 protocol=null，尝试从版本名反查")
                        protocol_raw = _lookup_protocol_from_name(version_name_raw)
                        if protocol_raw is not None:
                            logger.info(f"[MOTD] 从版本名 '{version_name_raw}' 反查到协议 {protocol_raw}")
                        else:
                            # 反查失败，尝试直连查询补全协议号
                            logger.info(f"[MOTD] 版本名反查失败，尝试直连查询补全")
                            direct = await query_java_server_direct(host, port)
                            if "error" not in direct and "version" in direct:
                                protocol_raw = direct["version"].get("protocol")
                                if protocol_raw is not None:
                                    logger.info(f"[MOTD] 直连查询补全协议号: {protocol_raw}")
                                else:
                                    logger.info(f"[MOTD] 直连查询也未返回协议号")

                    players_data = data.get("players", {})
                    # 玩家样例列表（mcstatus.io v2 字段为 list，直连为 sample，统一映射为 sample）
                    sample = [
                        {"name": p.get("name_clean") or p.get("name_raw") or p.get("name", ""), "uuid": p.get("uuid", "")}
                        for p in (players_data.get("list") or []) if isinstance(p, dict)
                    ]
                    # MOTD 自渲染：优先取 raw JSON 组件树（保留颜色/格式），回退纯文本
                    motd_data = data.get("motd", {})
                    if isinstance(motd_data, dict):
                        description = motd_data.get("raw") or motd_data.get("clean") or "无描述"
                    else:
                        description = motd_data or "无描述"

                    return {
                        "version": {"name": version_name_raw, "protocol": protocol_raw if protocol_raw is not None else 0},
                        "players": {"online": players_data.get("online", 0), "max": players_data.get("max", 0), "sample": sample},
                        "description": description,
                        "icon": data.get("icon"),
                        "latency_ms": round((time.perf_counter() - _t0) * 1000),
                        "source": "api",
                    }
                else:
                    return {"error": "服务器离线或无法访问"}
            else:
                return {"error": f"API 请求失败: {resp.status}"}
    except asyncio.TimeoutError:
        return {"error": "API 请求超时"}
    except Exception as e:
        return {"error": f"API 查询失败: {str(e)}"}


async def query_java_server_direct(host: str, port: int = JAVA_DEFAULT_PORT, timeout: int = 5) -> Dict[str, Any]:
    """直接查询 Java 版服务器状态（asyncio 异步 TCP，不阻塞事件循环）"""

    def _pack_varint(value: int) -> bytes:
        result = b""
        while True:
            byte = value & 0x7F
            value >>= 7
            if value:
                result += struct.pack("B", byte | 0x80)
            else:
                result += struct.pack("B", byte)
                break
        return result

    async def _unpack_varint(reader: asyncio.StreamReader) -> int:
        result = 0
        for i in range(5):
            data = await reader.readexactly(1)
            byte = data[0]
            result |= (byte & 0x7F) << (7 * i)
            if not (byte & 0x80):
                return result
        raise ValueError("变长整数过大")

    def _pack_data(data: bytes) -> bytes:
        return _pack_varint(len(data)) + data

    async def _do_query() -> Dict[str, Any]:
        reader, writer = await asyncio.open_connection(host, port)
        try:
            # 发送握手包
            handshake_data = (
                _pack_varint(-1) +  # 协议版本 -1
                _pack_data(host.encode('utf-8')) +
                struct.pack('>H', port) +
                _pack_varint(1)  # 状态请求
            )
            packet = _pack_varint(0) + handshake_data
            writer.write(_pack_data(packet))

            # 发送状态请求
            writer.write(_pack_data(_pack_varint(0)))
            await writer.drain()

            # 读取响应长度
            await _unpack_varint(reader)
            await _unpack_varint(reader)

            # 读取 JSON 长度
            json_length = await _unpack_varint(reader)

            # 读取 JSON 数据
            json_data = await reader.readexactly(json_length)

            return json.loads(json_data.decode('utf-8'))
        finally:
            writer.close()

    try:
        _t0 = time.perf_counter()
        data = await asyncio.wait_for(_do_query(), timeout=timeout)
        if isinstance(data, dict):
            # 服务器图标：直连 JSON 的 favicon 字段（base64 data URI）
            data["icon"] = data.get("icon") or data.get("favicon")
            data["latency_ms"] = round((time.perf_counter() - _t0) * 1000)
            data["source"] = "direct"
        return data
    except asyncio.TimeoutError:
        return {"error": "连接超时，请检查服务器地址和端口是否正确"}
    except socket.gaierror:
        return {"error": "无法解析服务器地址，请检查主机名是否正确"}
    except ConnectionRefusedError:
        return {"error": "连接被拒绝，服务器可能未运行或端口不正确"}
    except Exception as e:
        return {"error": f"查询失败: {str(e)}"}


async def query_java_server(host: str, port: int = JAVA_DEFAULT_PORT, timeout: int = 5, use_api: bool = True) -> Dict[str, Any]:
    """查询 Java 版服务器状态：API 与 TCP 直连并发竞速，谁先成功用谁

    - use_api=False 时仅直连查询；
    - 直连先成功且协议号 ≤ 0（代理服务器）时，复用竞速中的 API 任务补全带范围的版本名，
      不再额外发起第二次 API 请求；
    - 两支都失败时优先返回直连的错误信息（对用户更有指向性）。
    """
    if not use_api:
        return await query_java_server_direct(host, port, timeout)

    api_task = asyncio.create_task(query_java_server_api(host, port))
    direct_task = asyncio.create_task(query_java_server_direct(host, port, timeout))
    pending = {api_task, direct_task}

    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            # 两个查询函数内部均捕获异常并返回 {"error": ...}，task.result() 不会抛出
            result = task.result()
            if "error" in result:
                logger.info(f"[MOTD] 竞速查询一支失败（{result.get('error')}），等待另一支")
                continue
            if task is direct_task:
                # 直连成功
                proto = result.get("version", {}).get("protocol", 0)
                version_name = result.get("version", {}).get("name", "")
                logger.info(f"[MOTD] 直连查询获胜: protocol={proto}, name='{version_name}'")
                if proto is not None and proto <= 0:
                    # 代理服务器：等待竞速中的 API 任务补全版本范围
                    logger.info(f"[MOTD] 直连协议号 {proto} ≤ 0，等待 API 任务补全版本范围")
                    api_result = await api_task
                    if "error" not in api_result:
                        api_name = api_result.get("version", {}).get("name", "")
                        if api_name and api_name != version_name:
                            result["version"]["name"] = api_name
                            logger.info(f"[MOTD] API 补全版本名: '{version_name}' -> '{api_name}'")
                        else:
                            logger.info(f"[MOTD] API 版本名相同或为空，无需补全")
                api_task.cancel()
                return result
            # API 先成功：取消直连任务，直接采用（直连通常更快，能被 API 抢先说明直连不可达）
            direct_task.cancel()
            logger.info(f"[MOTD] API 查询获胜（{result.get('latency_ms')}ms）")
            return result

    # 两支都失败：返回直连的错误信息
    return direct_task.result()


async def query_bedrock_server(host: str, port: int = BEDROCK_DEFAULT_PORT, timeout: int = 5) -> Dict[str, Any]:
    """异步查询基岩版服务器状态"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        _t0 = time.perf_counter()
        
        # 发送 Unconnected Ping
        ping_data = b'\x01' + struct.pack('>Q', int(time.time() * 1000)) + b'\x00\x00\x00\x00\x00\x00\x00\x00'
        sock.sendto(ping_data, (host, port))
        
        # 接收响应
        data, addr = sock.recvfrom(2048)
        sock.close()
        _latency_ms = round((time.perf_counter() - _t0) * 1000)
        
        # 解析响应
        if len(data) < 35:
            return {"error": "响应数据无效"}
        
        # 跳过头部
        server_info = data[35:].decode('utf-8', errors='ignore').split(';')
        
        if len(server_info) >= 6:
            return {
                "edition": server_info[0],
                "motd": server_info[1],
                "protocol": server_info[2],
                "version": server_info[3],
                "online_players": server_info[4],
                "max_players": server_info[5],
                "server_id": server_info[6] if len(server_info) > 6 else "未知",
                "latency_ms": _latency_ms,
                "source": "bedrock_udp",
            }
        else:
            return {"error": "无法解析服务器响应"}
            
    except socket.timeout:
        return {"error": "连接超时，请检查服务器地址和端口是否正确"}
    except Exception as e:
        return {"error": f"查询失败: {str(e)}"}


def parse_sub_servers_config(config_str: str) -> list:
    """
    解析子服配置字符串
    格式: 服务器名:host:port,服务器名:host:port
    返回: [{"name": "lobby", "host": "127.0.0.1", "port": 25566}, ...]
    """
    if not config_str or not config_str.strip():
        return []

    servers = []
    for item in config_str.split(","):
        item = item.strip()
        if not item:
            continue

        parts = item.split(":")
        if len(parts) == 3:
            name, host, port_str = parts
            try:
                port = int(port_str)
                servers.append({"name": name.strip(), "host": host.strip(), "port": port})
            except ValueError:
                logger.warning(f"[MOTD] 子服配置解析失败，端口不是数字: {item}")
        elif len(parts) == 2:
            # 没有服务器名，用 host:port 作为名称
            host, port_str = parts
            try:
                port = int(port_str)
                servers.append({"name": f"{host}:{port}", "host": host.strip(), "port": port})
            except ValueError:
                logger.warning(f"[MOTD] 子服配置解析失败，端口不是数字: {item}")
        else:
            logger.warning(f"[MOTD] 子服配置格式错误: {item}")

    return servers


async def query_velostat_servers(api_url: str, timeout: int = 10) -> Dict[str, Any]:
    """
    通过 velostat HTTP API 查询所有子服状态
    api_url: http://代理IP:port
    返回: {"servers": {"lobby": {...}, "survival": {...}}, "error": None}
    """
    try:
        # 确保 URL 末尾有 /status
        url = api_url.rstrip("/") + "/status"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {"servers": data, "error": None}
                else:
                    return {"servers": {}, "error": f"velostat API 请求失败: HTTP {resp.status}"}
    except asyncio.TimeoutError:
        return {"servers": {}, "error": "velostat API 请求超时"}
    except aiohttp.ClientError as e:
        return {"servers": {}, "error": f"velostat API 连接失败: {str(e)}"}
    except Exception as e:
        return {"servers": {}, "error": f"velostat 查询异常: {str(e)}"}


async def query_sub_servers_direct(sub_servers: list, timeout: int = 5, use_api: bool = True) -> Dict[str, Any]:
    """
    直连查询多个子服状态
    sub_servers: [{"name": "lobby", "host": "127.0.0.1", "port": 25566}, ...]
    返回: {"servers": {"lobby": {...}, ...}, "errors": ["...", ...]}
    """
    results = {}
    errors = []

    async def query_one(server_info: Dict[str, Any]) -> tuple:
        name = server_info["name"]
        host = server_info["host"]
        port = server_info["port"]
        try:
            result = await asyncio.wait_for(
                query_java_server(host, port, timeout, use_api),
                timeout=timeout + 5
            )
            if "error" in result:
                return name, None, result['error']
            else:
                return name, result, None
        except asyncio.TimeoutError:
            return name, None, "查询超时"
        except Exception as e:
            return name, None, str(e)

    # 并发查询所有子服
    tasks = [query_one(server) for server in sub_servers]
    task_results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in task_results:
        if isinstance(result, Exception):
            errors.append(str(result))
        else:
            name, data, error = result
            if data:
                results[name] = data
            elif error:
                # 查询失败的子服也保留，显示连接错误而非静默忽略
                results[name] = {"error": error}
            if error:
                errors.append(f"{name}: {error}")

    return {"servers": results, "errors": errors}


# ============================================================
# HTML 模板：MOTD 服务器状态卡片
# 视觉方向：「方块世界」MC 原生像素风
#  - CSS 变量设计 token（三张卡共用一套）
#  - 高度内容自适应（无 height:100%，配合 full_page 截图）
#  - MC GUI 浮雕边框（上左亮 / 下右暗）
# ============================================================


def _build_dirt_tile_data_uri() -> str:
    """生成 8x8 像素泥土纹理的 SVG data URI（固定种子伪随机，结果确定）
    用于卡片背景，模拟 Minecraft 主菜单的泥土方块背景
    """
    rng = random.Random(20260829)
    palette = ['#6B4A2B', '#5F4126', '#7A5432', '#553A21', '#6F4C2E', '#5A3E24', '#825A36', '#4E3620']
    weights = [4, 6, 2, 3, 3, 5, 1, 2]
    rects = []
    for y in range(8):
        for x in range(8):
            c = rng.choices(palette, weights)[0]
            rects.append(f'<rect x="{x}" y="{y}" width="1" height="1" fill="{c}"/>')
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" '
           'shape-rendering="crispEdges">' + ''.join(rects) + '</svg>')
    return "data:image/svg+xml," + quote(svg, safe="")


_DIRT_TILE = _build_dirt_tile_data_uri()


_MOTD_TEMPLATE_SRC = '''
<!-- astrbot-t2i-shiki-runtime: 本卡片无代码块, 携带此标记 ID 使 AstrBot 跳过注入 1.2MB Shiki 代码高亮运行时,
     上传到云端渲染服务(t2i_endpoint)的体积从 ~1.3MB 降到 ~50KB, 弱机/小水管显著减负 -->
<meta name="viewport" content="width=1280; height=1">
<style>
@import url('https://cdn.jsdelivr.net/npm/@fontsource/press-start-2p@5/index.min.css');
html, body {
    margin: 0; padding: 0;
}
body {
    /* ── 设计 token：MC 调色板 ── */
    --green: #55FF55; --green-xp: #7EFC20; --gold: #FFAA00;
    --red: #FF5555; --aqua: #55FFFF;
    --panel: #3F3F3F; --panel-hi: #757575; --panel-lo: #191919;
    --slot: #2B2B2B; --slot-hi: #141414; --slot-lo: #4E4E4E;
    --ink: #EDEDED; --muted: #A6A6A6;
    --pixel: 'Press Start 2P', 'Microsoft YaHei', monospace;
    --sans: 'Microsoft YaHei', 'PingFang SC', 'Noto Sans SC', sans-serif;
    font-family: var(--sans);
    color: var(--ink);
    width: 1280px;
    box-sizing: border-box;
    padding: 30px;
    background-color: #5A3E24;
    background-image: url("__DIRT_TILE__");
    background-size: 96px 96px;
    image-rendering: pixelated;
    /* 卡片高度: card_height_mode=auto → 100vh(视口高1px, 高度贴内容自适应);
       fixed → 显式固定高度, 观感与 v2.2.0 及以前的固定尺寸一致(矮内容补白, 超出自然撑开) */
    min-height: {{ body_min_height }};
    display: flex;
    flex-direction: column;
}

/* 卡片容器: 拉伸填满 body, 面板再填满卡片 */
.card {
    display: flex;
    flex-direction: column;
    flex: 1 0 auto;
}

/* ── MC GUI 浮雕面板：上左亮 / 下右暗 ── */
.panel {
    background: var(--panel);
    border-style: solid;
    border-width: 4px;
    border-color: var(--panel-hi) var(--panel-lo) var(--panel-lo) var(--panel-hi);
    padding: 30px 34px 34px;
    box-sizing: border-box;
    flex: 1 0 auto;
}
/* ── 物品栏格子槽：凹陷浮雕（与面板反向） ── */
.slot {
    background: var(--slot);
    border-style: solid;
    border-width: 4px;
    border-color: var(--slot-hi) var(--slot-lo) var(--slot-lo) var(--slot-hi);
    box-sizing: border-box;
    display: flex;
    align-items: center;
    justify-content: center;
}

.head {
    display: flex;
    align-items: center;
    gap: 24px;
    margin-bottom: 24px;
    min-width: 0;
}
.icon-slot {
    width: 112px;
    height: 112px;
    flex: 0 0 auto;
}
.icon-slot img {
    width: 92px;
    height: 92px;
    image-rendering: pixelated;
}
.icon-letter {
    font-family: var(--pixel);
    font-size: 36px;
    color: var(--muted);
    text-shadow: 3px 3px 0 #000;
}
.head-main {
    flex: 1;
    min-width: 0;
}
.addr-row {
    display: flex;
    align-items: center;
    gap: 16px;
    min-width: 0;
}
.addr {
    font-size: 60px;
    font-weight: 700;
    color: #fff;
    text-shadow: 3px 3px 0 #000;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
}
.badge {
    font-family: var(--pixel);
    font-size: 17px;
    line-height: 1;
    padding: 6px 12px 5px;
    background: #191919;
    border: 2px solid var(--accent, var(--muted));
    color: var(--accent, var(--muted));
    letter-spacing: 2px;
    flex: 0 0 auto;
}
.accent-java { --accent: var(--green); }
.accent-bedrock { --accent: var(--gold); }
.accent-proxy { --accent: var(--aqua); }
.meta-row {
    margin-top: 10px;
    font-size: 30px;
    color: var(--muted);
    display: flex;
    align-items: center;
    gap: 14px;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
}
.via-tag {
    font-size: 26px;
    color: var(--gold);
    background: rgba(255,170,0,0.12);
    border: 1px solid rgba(255,170,0,0.4);
    padding: 3px 10px;
    flex: 0 0 auto;
}
.head-right {
    flex: 0 0 auto;
    text-align: right;
}
.latency-num {
    font-family: var(--pixel);
    font-size: 40px;
    line-height: 1;
    letter-spacing: 2px;
    color: var(--green);
    text-shadow: 2px 2px 0 #000;
}
.latency-num.lat-mid { color: var(--gold); }
.latency-num.lat-bad { color: var(--red); }
.latency-label {
    font-size: 22px;
    color: var(--muted);
    letter-spacing: 2px;
    margin-top: 6px;
}

/* ── 聊天框样式 MOTD：半透明黑底 ── */
.motd-chat {
    background: rgba(0, 0, 0, 0.55);
    border: 2px solid #151515;
    box-shadow: inset 0 0 0 1px #000;
    padding: 20px 26px;
    font-size: 34px;
    line-height: 1.6;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 4;
    -webkit-box-orient: vertical;
    word-break: break-all;
}

/* ── XP 条样式玩家进度条 ── */
.players-block {
    margin-top: 24px;
}
.xp-row {
    display: flex;
    align-items: center;
    gap: 18px;
}
.xp-nums {
    font-family: var(--pixel);
    font-size: 42px;
    line-height: 1;
    letter-spacing: 2px;
    color: var(--green-xp);
    text-shadow: 2px 2px 0 #000;
    flex: 0 0 auto;
}
.xp-nums .fraction {
    font-size: 20px;
    color: var(--muted);
}
.xp-track {
    flex: 1;
    height: 26px;
    background: #131313;
    border: 2px solid #050505;
    box-shadow: inset 0 2px 0 rgba(255,255,255,0.08);
    box-sizing: border-box;
    min-width: 0;
}
.xp-fill {
    height: 100%;
    background: repeating-linear-gradient(90deg, #55FF55 0 18px, #43CC43 18px 22px);
    box-shadow: inset 0 3px 0 rgba(255,255,255,0.45), inset 0 -2px 0 rgba(0,0,0,0.3);
}
.xp-pct {
    font-family: var(--pixel);
    font-size: 20px;
    color: var(--green-xp);
    text-shadow: 2px 2px 0 #000;
    flex: 0 0 auto;
    min-width: 70px;
    text-align: right;
}

/* ── 在线玩家头像行（MC Tab 列表风格） ── */
.avatars {
    margin-top: 20px;
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
}
.p-chip {
    display: flex;
    align-items: center;
    gap: 9px;
    background: rgba(0,0,0,0.42);
    border: 2px solid #262626;
    padding: 5px 13px 5px 5px;
    min-width: 0;
}
.p-head {
    width: 44px;
    height: 44px;
    image-rendering: pixelated;
    flex: 0 0 auto;
}
.p-fallback {
    width: 44px;
    height: 44px;
    box-sizing: border-box;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: var(--pixel);
    font-size: 18px;
    flex: 0 0 auto;
}
.p-name {
    font-size: 25px;
    color: #DDD;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 160px;
}
.p-more {
    font-family: var(--pixel);
    font-size: 18px;
    color: var(--muted);
    padding: 6px 10px;
}

/* ── 错误卡：MC 断开连接界面风格 ── */
.err-body {
    padding: 46px 30px 40px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    flex: 1;
    gap: 26px;
    text-align: center;
}
.err-icon {
    font-size: 66px;
    line-height: 1;
    color: var(--red);
    text-shadow: 3px 3px 0 #000;
}
.err-title {
    font-size: 54px;
    font-weight: 700;
    color: #fff;
    text-shadow: 3px 3px 0 #000;
}
.err-msg {
    background: rgba(255,85,85,0.08);
    border: 2px solid rgba(255,85,85,0.35);
    padding: 18px 30px;
    font-size: 32px;
    color: #FF9A9A;
    max-width: 760px;
    word-break: break-all;
}
.err-addr {
    font-size: 27px;
    color: var(--muted);
}

/* ── 页脚：一行等宽小字 ── */
.foot {
    margin-top: 20px;
    text-align: center;
    font-family: var(--pixel);
    font-size: 15px;
    letter-spacing: 1px;
    color: rgba(255,255,255,0.42);
}
</style>

<div class="card">
{% set card_accent = 'accent-proxy' if badge == 'PROXY' else ('accent-bedrock' if badge == 'BEDROCK' else 'accent-java') %}
<div class="panel {{ card_accent }}">

  {% if is_error %}
  <div class="err-body">
    <div class="err-icon">✖</div>
    <div class="err-title">无法连接到服务器</div>
    <div class="err-msg">{{ error_msg }}</div>
    <div class="err-addr">{{ server_address }} · {{ edition_label }}</div>
  </div>

  {% else %}
  <div class="head">
    {% if show_server_icon %}
    <div class="slot icon-slot">
      {% if icon %}
      <img src="{{ icon }}" alt="" onerror="this.style.display='none';this.nextElementSibling.style.display='block'">
      <div class="icon-letter" style="display:none">{{ server_address[0]|upper }}</div>
      {% else %}
      <div class="icon-letter">{{ server_address[0]|upper }}</div>
      {% endif %}
    </div>
    {% endif %}
    <div class="head-main">
      <div class="addr-row">
        <span class="addr">{{ server_address }}</span>
        <span class="badge">{{ badge }}</span>
      </div>
      <div class="meta-row">
        <span>版本 {{ server_version }}</span>
        {% if client_version and client_version != server_version %}<span>支持 {{ client_version }}</span>{% endif %}
        {% if via_hint %}<span class="via-tag">{{ via_hint }}</span>{% endif %}
      </div>
    </div>
    {% if show_latency and latency_ms is not none %}
    <div class="head-right">
      <div class="latency-num {{ latency_class }}">{{ latency_ms }}ms</div>
      <div class="latency-label">查询延迟</div>
    </div>
    {% endif %}
  </div>

  <div class="motd-chat">{{ motd_html }}</div>

  <div class="players-block">
    <div class="xp-row">
      <div class="xp-nums">{{ online_str }}<span class="fraction"> / {{ max_str }}</span></div>
      <div class="xp-track"><div class="xp-fill" style="width: {{ percent }}%"></div></div>
      <div class="xp-pct">{{ percent }}%</div>
    </div>
    {% if show_player_list and (player_list or extra_count > 0) %}
    <div class="avatars">
      {% for p in player_list %}
      <div class="p-chip">
        {% if p.avatar %}
        <img class="p-head" src="{{ p.avatar }}" alt="">
        {% elif p.uuid %}
        <img class="p-head" src="https://mc-heads.net/avatar/{{ p.uuid }}/32" alt=""
             onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
        <div class="p-fallback" style="display:none; background: rgba(0,0,0,0.5); border: 2px solid {{ p.color }}; color: {{ p.color }}">{{ (p.name or '?')[0]|upper }}</div>
        {% else %}
        <div class="p-fallback" style="background: rgba(0,0,0,0.5); border: 2px solid {{ p.color }}; color: {{ p.color }}">{{ (p.name or '?')[0]|upper }}</div>
        {% endif %}
        <span class="p-name">{{ p.name }}</span>
      </div>
      {% endfor %}
      {% if extra_count > 0 %}<div class="p-chip p-more">+{{ extra_count }}</div>{% endif %}
    </div>
    {% endif %}
  </div>
  {% endif %}

</div>
<div class="foot">{{ footer_text }}</div>
</div>
'''

MOTD_HTML_TEMPLATE = _MOTD_TEMPLATE_SRC.replace("__DIRT_TILE__", _DIRT_TILE)


# ============================================================
# HTML 模板：代理服务器状态卡片（母服 + 子服列表）
# 与主卡片共用同一套设计 token / 泥土背景 / 浮雕面板
# ============================================================

_PROXY_TEMPLATE_SRC = '''
<!-- astrbot-t2i-shiki-runtime: 同主卡片, 携带标记 ID 跳过 1.2MB Shiki 运行时注入, 减小上传体积 -->
<meta name="viewport" content="width=1280; height=1">
<style>
@import url('https://cdn.jsdelivr.net/npm/@fontsource/press-start-2p@5/index.min.css');
html, body {
    margin: 0; padding: 0;
}
body {
    /* ── 设计 token：与主卡片保持一致 ── */
    --green: #55FF55; --green-xp: #7EFC20; --gold: #FFAA00;
    --red: #FF5555; --aqua: #55FFFF;
    --panel: #3F3F3F; --panel-hi: #757575; --panel-lo: #191919;
    --slot: #2B2B2B; --slot-hi: #141414; --slot-lo: #4E4E4E;
    --ink: #EDEDED; --muted: #A6A6A6;
    --pixel: 'Press Start 2P', 'Microsoft YaHei', monospace;
    --sans: 'Microsoft YaHei', 'PingFang SC', 'Noto Sans SC', sans-serif;
    font-family: var(--sans);
    color: var(--ink);
    width: 1280px;
    box-sizing: border-box;
    padding: 30px;
    background-color: #5A3E24;
    background-image: url("__DIRT_TILE__");
    background-size: 96px 96px;
    image-rendering: pixelated;
    /* 卡片高度: 同主模板, 由 body_min_height 控制(auto=100vh 自适应 / fixed=固定高度) */
    min-height: {{ body_min_height }};
    display: flex;
    flex-direction: column;
}

/* 卡片容器: 拉伸填满 body, 面板再填满卡片 */
.card {
    display: flex;
    flex-direction: column;
    flex: 1 0 auto;
}
.panel {
    background: var(--panel);
    border-style: solid;
    border-width: 4px;
    border-color: var(--panel-hi) var(--panel-lo) var(--panel-lo) var(--panel-hi);
    padding: 30px 34px 34px;
    box-sizing: border-box;
    flex: 1 0 auto;
}
.slot {
    background: var(--slot);
    border-style: solid;
    border-width: 4px;
    border-color: var(--slot-hi) var(--slot-lo) var(--slot-lo) var(--slot-hi);
    box-sizing: border-box;
    display: flex;
    align-items: center;
    justify-content: center;
}
.accent-proxy { --accent: var(--aqua); }
.accent-java { --accent: var(--green); }
.accent-bedrock { --accent: var(--gold); }

.head {
    display: flex;
    align-items: center;
    gap: 22px;
    margin-bottom: 22px;
    min-width: 0;
}
.icon-slot {
    width: 104px;
    height: 104px;
    flex: 0 0 auto;
}
.icon-slot img {
    width: 84px;
    height: 84px;
    image-rendering: pixelated;
}
.icon-letter {
    font-family: var(--pixel);
    font-size: 34px;
    color: var(--muted);
    text-shadow: 3px 3px 0 #000;
}
.head-main {
    flex: 1;
    min-width: 0;
}
.addr-row {
    display: flex;
    align-items: center;
    gap: 14px;
    min-width: 0;
}
.addr {
    font-size: 54px;
    font-weight: 700;
    color: #fff;
    text-shadow: 3px 3px 0 #000;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
}
.badge {
    font-family: var(--pixel);
    font-size: 16px;
    line-height: 1;
    padding: 6px 11px 5px;
    background: #191919;
    border: 2px solid var(--accent, var(--muted));
    color: var(--accent, var(--muted));
    letter-spacing: 2px;
    flex: 0 0 auto;
}
.meta-row {
    margin-top: 8px;
    font-size: 28px;
    color: var(--muted);
    display: flex;
    align-items: center;
    gap: 14px;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
}
.via-tag {
    font-size: 24px;
    color: var(--gold);
    background: rgba(255,170,0,0.12);
    border: 1px solid rgba(255,170,0,0.4);
    padding: 3px 10px;
    flex: 0 0 auto;
}
.head-right {
    flex: 0 0 auto;
    text-align: right;
}
.latency-num {
    font-family: var(--pixel);
    font-size: 38px;
    line-height: 1;
    letter-spacing: 2px;
    color: var(--green);
    text-shadow: 2px 2px 0 #000;
}
.latency-num.lat-mid { color: var(--gold); }
.latency-num.lat-bad { color: var(--red); }
.latency-label {
    font-size: 22px;
    color: var(--muted);
    letter-spacing: 2px;
    margin-top: 6px;
}

/* 母服 MOTD：聊天框样式，限 2 行 */
.motd-chat {
    background: rgba(0, 0, 0, 0.55);
    border: 2px solid #151515;
    box-shadow: inset 0 0 0 1px #000;
    padding: 16px 24px;
    font-size: 32px;
    line-height: 1.55;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    word-break: break-all;
}

.xp-row {
    display: flex;
    align-items: center;
    gap: 18px;
    margin-top: 22px;
}
.xp-nums {
    font-family: var(--pixel);
    font-size: 40px;
    line-height: 1;
    letter-spacing: 2px;
    color: var(--green-xp);
    text-shadow: 2px 2px 0 #000;
    flex: 0 0 auto;
}
.xp-nums .fraction {
    font-size: 19px;
    color: var(--muted);
}
.xp-track {
    flex: 1;
    height: 24px;
    background: #131313;
    border: 2px solid #050505;
    box-shadow: inset 0 2px 0 rgba(255,255,255,0.08);
    box-sizing: border-box;
    min-width: 0;
}
.xp-fill {
    height: 100%;
    background: repeating-linear-gradient(90deg, #55FF55 0 18px, #43CC43 18px 22px);
    box-shadow: inset 0 3px 0 rgba(255,255,255,0.45), inset 0 -2px 0 rgba(0,0,0,0.3);
}
.xp-pct {
    font-family: var(--pixel);
    font-size: 19px;
    color: var(--green-xp);
    text-shadow: 2px 2px 0 #000;
    flex: 0 0 auto;
    min-width: 68px;
    text-align: right;
}

/* 子服列表 */
.sub-section {
    margin-top: 26px;
}
.sub-title {
    font-size: 28px;
    color: var(--muted);
    letter-spacing: 3px;
    padding-bottom: 10px;
    border-bottom: 2px solid #2A2A2A;
    margin-bottom: 14px;
}
.sub-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
}
.sub-cell {
    background: rgba(0,0,0,0.38);
    border: 2px solid #262626;
    padding: 14px 16px 15px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-width: 0;
    box-sizing: border-box;
}
.sub-cell.offline {
    opacity: 0.78;
    border-color: #4A3A1A;
}
.sub-cell.error {
    opacity: 0.82;
    border-color: #4A2020;
}
.sub-head {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
}
.dot {
    width: 12px;
    height: 12px;
    flex: 0 0 auto;
    box-shadow: 2px 2px 0 rgba(0,0,0,0.6);
}
.dot-online { background: var(--green); box-shadow: 0 0 6px rgba(85,255,85,0.7), 2px 2px 0 rgba(0,0,0,0.6); }
.dot-offline { background: var(--gold); }
.dot-error { background: var(--red); box-shadow: 0 0 6px rgba(255,85,85,0.7), 2px 2px 0 rgba(0,0,0,0.6); }
.sub-name {
    font-size: 29px;
    font-weight: 700;
    color: #fff;
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
}
.sub-players {
    font-family: var(--pixel);
    font-size: 18px;
    line-height: 1;
    letter-spacing: 1px;
    color: var(--green-xp);
    flex: 0 0 auto;
}
.sub-players .fraction {
    font-size: 11px;
    color: var(--muted);
}
.mini-track {
    height: 12px;
    background: #131313;
    border: 2px solid #050505;
    box-sizing: border-box;
}
.mini-fill {
    height: 100%;
    background: repeating-linear-gradient(90deg, #55FF55 0 9px, #43CC43 9px 12px);
}
.sub-motd {
    font-size: 23px;
    color: #999;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
}
.sub-offline-text {
    font-size: 23px;
    color: var(--gold);
}
.sub-error-text {
    font-size: 23px;
    color: #FF6B6B;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
}
.sub-more {
    margin-top: 14px;
    text-align: center;
    font-family: var(--sans);
    font-size: 28px;
    color: var(--muted);
}

/* 母服查询失败时的错误块 */
.err-body {
    padding: 26px 10px 10px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    flex: 1;
    gap: 18px;
    text-align: center;
}
.err-title {
    font-size: 46px;
    font-weight: 700;
    color: #fff;
    text-shadow: 3px 3px 0 #000;
}
.err-msg {
    background: rgba(255,85,85,0.08);
    border: 2px solid rgba(255,85,85,0.35);
    padding: 14px 24px;
    font-size: 28px;
    color: #FF9A9A;
    max-width: 720px;
    word-break: break-all;
}
.err-addr {
    font-size: 25px;
    color: var(--muted);
}

.foot {
    margin-top: 20px;
    text-align: center;
    font-family: var(--pixel);
    font-size: 15px;
    letter-spacing: 1px;
    color: rgba(255,255,255,0.42);
}
</style>

<div class="card">
<div class="panel accent-proxy">

  {% if proxy.is_error %}
  <div class="head">
    <div class="head-main">
      <div class="addr-row">
        <span class="addr">{{ proxy.address }}</span>
        <span class="badge">PROXY</span>
      </div>
    </div>
  </div>
  <div class="err-body">
    <div class="err-title">无法连接到代理服务器</div>
    <div class="err-msg">{{ proxy.error_msg }}</div>
    <div class="err-addr">{{ proxy.address }}</div>
  </div>

  {% else %}
  <div class="head">
    {% if show_server_icon %}
    <div class="slot icon-slot">
      {% if proxy.icon %}
      <img src="{{ proxy.icon }}" alt="" onerror="this.style.display='none';this.nextElementSibling.style.display='block'">
      <div class="icon-letter" style="display:none">P</div>
      {% else %}
      <div class="icon-letter">P</div>
      {% endif %}
    </div>
    {% endif %}
    <div class="head-main">
      <div class="addr-row">
        <span class="addr">{{ proxy.address }}</span>
        <span class="badge">PROXY</span>
      </div>
      <div class="meta-row">
        <span>版本 {{ proxy.server_version }}</span>
        {% if proxy.via_hint %}<span class="via-tag">{{ proxy.via_hint }}</span>{% endif %}
      </div>
    </div>
    {% if show_latency and proxy.latency_ms is not none %}
    <div class="head-right">
      <div class="latency-num {{ proxy.latency_class }}">{{ proxy.latency_ms }}ms</div>
      <div class="latency-label">查询延迟</div>
    </div>
    {% endif %}
  </div>

  <div class="motd-chat">{{ proxy.motd_html }}</div>

  <div class="xp-row">
    <div class="xp-nums">{{ proxy.online_str }}<span class="fraction"> / {{ proxy.max_str }}</span></div>
    <div class="xp-track"><div class="xp-fill" style="width: {{ proxy.percent }}%"></div></div>
    <div class="xp-pct">{{ proxy.percent }}%</div>
  </div>
  {% endif %}

  {% if has_sub_servers %}
  <div class="sub-section">
    <div class="sub-title">子服列表 · {{ sub_servers|length }}</div>
    <div class="sub-grid">
    {% for sub in sub_servers %}
    {% if loop.index <= 9 %}
    <div class="sub-cell {% if sub.is_error %}error{% elif sub.is_offline %}offline{% endif %}">
      <div class="sub-head">
        <span class="dot {% if sub.is_error %}dot-error{% elif sub.is_offline %}dot-offline{% else %}dot-online{% endif %}"></span>
        <span class="sub-name">{{ sub.name }}</span>
        {% if not sub.is_error and not sub.is_offline %}
        <span class="sub-players">{{ sub.online_str }}<span class="fraction">/{{ sub.max_str }}</span></span>
        {% endif %}
      </div>
      {% if sub.is_error %}
      <div class="sub-error-text">{{ sub.error_msg }}</div>
      {% elif sub.is_offline %}
      <div class="mini-track"><div class="mini-fill" style="width: 0%"></div></div>
      <div class="sub-offline-text">未启动</div>
      {% else %}
      <div class="mini-track"><div class="mini-fill" style="width: {{ sub.percent }}%"></div></div>
      <div class="sub-motd">{{ sub.motd_html }}</div>
      {% endif %}
    </div>
    {% endif %}
    {% endfor %}
    </div>
    {% if sub_servers|length > 9 %}
    <div class="sub-more">+{{ sub_servers|length - 9 }} 个子服未显示</div>
    {% endif %}
  </div>
  {% endif %}

</div>
<div class="foot">{{ footer_text }}</div>
</div>
'''

PROXY_HTML_TEMPLATE = _PROXY_TEMPLATE_SRC.replace("__DIRT_TILE__", _DIRT_TILE)


@register("astrbot_plugin_minecraft_motd", "MOTD查询", "查询 Minecraft 服务器状态的 AstrBot 插件，支持 ViaVersion/Velocity/BungeeCord 多版本兼容", "2.3.0")
class MOTDPlugin(Star):
    """MOTD 查询插件主类"""

    # 配置缺省兜底: 防止任何时序下 _base_card_context/_send_card_with_fallback 先于 _load_config 访问
    output_mode = "image"
    card_height_mode = "auto"
    
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        # 发送闸门: 串行化「渲染+发送」段, 群聊多人同时查询时不再叠加渲染/上传开销(渲染失败有文本回退, 不会永久占用)
        self._send_semaphore = asyncio.Semaphore(1)
        self._load_config()
        logger.info(f"[MOTD] 插件初始化完成，版本 2.3.0")
    
    def _load_config(self):
        """加载插件配置"""
        self.default_server = self.config.get("default_server", "")
        self.default_port = self.config.get("default_port", JAVA_DEFAULT_PORT)
        self.enabled_sessions = self.config.get("enabled_sessions", [])
        self.enable_all_sessions = self.config.get("enable_all_sessions", True)
        self.admin_only_config = self.config.get("admin_only_config", True)
        self.query_timeout = self.config.get("query_timeout", 5)
        self.use_api = self.config.get("use_api", True)

        # 头像/图标预取与磁盘缓存
        self.prefetch_avatars = self.config.get("prefetch_avatars", True)
        self.avatar_cache_ttl = self.config.get("avatar_cache_ttl", AVATAR_TTL_HOURS_DEFAULT)
        # 头像下载失败负缓存（分钟）: 钳位 0~1440, 0=关闭负缓存（每次查询都重试）
        raw_neg = self.config.get("avatar_neg_cache_ttl")
        if raw_neg is None:
            raw_neg = NEG_CACHE_TTL_MINUTES_DEFAULT
        try:
            self.avatar_neg_cache_ttl = max(0, min(int(raw_neg), 24 * 60))
        except (TypeError, ValueError):
            self.avatar_neg_cache_ttl = NEG_CACHE_TTL_MINUTES_DEFAULT

        # 卡片显示配置
        self.show_player_list = self.config.get("show_player_list", True)
        self.show_server_icon = self.config.get("show_server_icon", True)
        self.show_latency = self.config.get("show_latency", True)

        # 输出模式: image=渲染像素风图片卡片; text=纯文本(跳过渲染与头像预取, 几乎零开销, 适合 1核1G 低配设备)
        self.output_mode = self.config.get("output_mode", "image")

        # 卡片高度模式: auto=高度贴内容自适应(v2.3.0 起云端视口 height=1 真正生效后的行为);
        # fixed=固定高度(矮内容补白, 观感与 v2.2.0 及以前一致, 不依赖云端视口默认值, 显式 CSS 兜底)
        self.card_height_mode = self.config.get("card_height_mode", "auto")

        # 代理服务器查询配置
        self.query_type = self.config.get("query_type", "normal")
        self.proxy_query_method = self.config.get("proxy_query_method", "velostat")
        self.velostat_api_url = self.config.get("velostat_api_url", "")
        self.sub_servers_config = self.config.get("sub_servers", "")

        logger.info(f"[MOTD] 配置加载: default_server='{self.default_server}', port={self.default_port}")
        logger.info(f"[MOTD] 查询类型: {self.query_type}, 代理查询方式: {self.proxy_query_method}")
        logger.info(f"[MOTD] 使用 API 查询: {self.use_api}")
    
    def _is_admin(self, event: AstrMessageEvent) -> bool:
        """检查用户是否为管理员"""
        try:
            astrbot_config = self.context.get_config()
            if astrbot_config:
                admins = astrbot_config.get("admins_id", [])
                sender_id = event.get_sender_id()
                return sender_id in admins
        except Exception as e:
            logger.error(f"[MOTD] 管理员检查失败: {e}")
        return False
    
    def _check_session_allowed(self, event: AstrMessageEvent) -> bool:
        """检查会话是否允许使用插件"""
        if self.enable_all_sessions:
            return True
        session_id = event.unified_msg_origin
        return session_id in self.enabled_sessions
    
    def _parse_server_address(self, address: str, is_java: bool = True) -> tuple:
        """
        解析服务器地址和端口
        如果用户指定了地址但不带端口，使用标准端口（Java 25565 / 基岩 19132）
        """
        if ':' in address:
            host, port_str = address.rsplit(':', 1)
            try:
                port = int(port_str)
            except ValueError:
                port = JAVA_DEFAULT_PORT if is_java else BEDROCK_DEFAULT_PORT
            host = host.strip('[]')
        else:
            host = address
            port = JAVA_DEFAULT_PORT if is_java else BEDROCK_DEFAULT_PORT
        return host, port
    
    def _format_motd(self, motd_data: Any) -> str:
        """格式化 MOTD 文本"""
        if isinstance(motd_data, str):
            return motd_data
        elif isinstance(motd_data, dict):
            text = motd_data.get("text", "")
            extra = motd_data.get("extra", [])
            for item in extra:
                if isinstance(item, dict):
                    text += item.get("text", "")
                elif isinstance(item, str):
                    text += item
            return text
        elif isinstance(motd_data, list):
            text = ""
            for item in motd_data:
                if isinstance(item, dict):
                    text += item.get("text", "")
                elif isinstance(item, str):
                    text += item
            return text
        return str(motd_data)
    
    def _parse_version(self, version_info: Dict[str, Any]) -> Tuple[str, str, str]:
        """
        解析版本信息，支持 ViaVersion/Velocity/BungeeCord 等多版本兼容模式
        返回: (服务器版本, 支持的客户端版本, 代理/多版本提示)
        """
        version_name = (version_info.get("name") or "").strip()

        # 确保 protocol 是整数
        protocol_raw = version_info.get("protocol", 0)
        try:
            protocol = int(protocol_raw) if protocol_raw is not None else 0
        except (ValueError, TypeError):
            protocol = 0

        logger.info(f"[MOTD] 版本解析输入: name='{version_name}', protocol_raw={protocol_raw}, protocol={protocol}")

        # ── 1. 从版本名提取版本号 ──
        version_in_name = None
        if version_name:
            m = _VERSION_RE.search(version_name)
            if m:
                version_in_name = m.group(1)
                logger.info(f"[MOTD] 从版本名提取版本号: '{version_in_name}'")

        # ── 1.5 协议号无效时，从版本名反查 ──
        if protocol <= 0 and version_name:
            looked_up = _lookup_protocol_from_name(version_name)
            if looked_up is not None:
                logger.info(f"[MOTD] 协议号无效({protocol})，从版本名 '{version_name}' 反查到协议 {looked_up}")
                protocol = looked_up
            else:
                logger.info(f"[MOTD] 协议号无效({protocol})，从版本名 '{version_name}' 反查失败")

        # ── 2. 用协议号查服务器实际版本 ──
        proto_ver_display, proto_major = PROTOCOL_VERSION_MAP.get(protocol, ("", ""))
        if protocol > 0:
            logger.info(f"[MOTD] 协议号映射: {protocol} -> display='{proto_ver_display}', major='{proto_major}'")

        # ── 3. 代理/多版本检测 ──
        proxy_name = ""
        is_multi_version = False
        detect_reason = ""

        name_lower = version_name.lower()

        # 3a. 版本名包含已知代理软件名
        for kw, display_name in _PROXY_KEYWORDS.items():
            if kw in name_lower:
                proxy_name = display_name
                is_multi_version = True
                detect_reason = f"关键词匹配: '{kw}'"
                logger.info(f"[MOTD] 代理检测命中: '{kw}' -> {display_name}")
                break

        # 3b. 版本名包含范围格式（如 "1.7.2-1.21.11"、"1.8 - 26.1"、"1.8 / 1.21"）
        if not is_multi_version and version_name:
            range_match = re.search(r'(\d+\.\d+[\w.]*)\s*[-~–/]\s*(\d+\.\d+)', version_name)
            if range_match:
                is_multi_version = True
                detect_reason = f"范围格式: '{range_match.group(0)}'"
                logger.info(f"[MOTD] 多版本检测命中范围格式: '{range_match.group(0)}'")

        # 3c. 版本名列出多个版本（如 "1.7.x, 1.8.x, ..., 1.21.x"）
        if not is_multi_version and version_name:
            version_matches = _VERSION_RE.findall(version_name)
            if len(version_matches) >= 4:
                is_multi_version = True
                detect_reason = f"多版本列举: {len(version_matches)}个版本"
                logger.info(f"[MOTD] 多版本检测命中列举: {version_matches}")

        # 3d. 协议号 47 + 版本名提及高版本 → BungeeCord/Velocity
        if not is_multi_version and protocol == 47 and version_in_name:
            try:
                ver_parts = [int(x) for x in version_in_name.split('.')]
                if len(ver_parts) >= 2 and (ver_parts[0] > 1 or (ver_parts[0] == 1 and ver_parts[1] > 8)):
                    is_multi_version = True
                    detect_reason = f"协议47+高版本名: '{version_in_name}'"
                    logger.info(f"[MOTD] 多版本检测命中协议47+高版本: proto=47, version='{version_in_name}'")
            except (ValueError, IndexError):
                pass

        if not is_multi_version:
            logger.info(f"[MOTD] 未检测到多版本/代理")

        # ── 4. 从版本名解析支持范围 ──
        min_supported_version = ""
        max_supported_version = ""
        if is_multi_version and version_name:
            all_versions = _VERSION_RE.findall(version_name)
            # 过滤掉明显不是 Minecraft 版本的数字（如代理版本号 3.4.0）
            mc_versions = []
            for v in all_versions:
                parts = v.split('.')
                if len(parts) >= 2 and parts[0] == '1' and parts[1].isdigit():
                    mc_versions.append(v)
                elif len(parts) >= 2:
                    # Minecraft 新版本命名（26.x 起改用年份.版本格式）
                    try:
                        major = int(parts[0])
                        if major >= 26:
                            mc_versions.append(v)
                    except ValueError:
                        pass
            logger.info(f"[MOTD] 版本范围解析: all_versions={all_versions}, mc_versions={mc_versions}")
            if mc_versions:
                max_supported_version = max(mc_versions, key=lambda v: [int(x) for x in v.split('.') if x.isdigit()])
                min_supported_version = min(mc_versions, key=lambda v: [int(x) for x in v.split('.') if x.isdigit()])

        # ── 5. 构建显示结果 ──
        if is_multi_version:
            # 多版本兼容服务器：服务器版本用协议号映射，客户端版本显示支持范围
            server_version = proto_ver_display or version_in_name or "未知"
            if min_supported_version and max_supported_version and min_supported_version != max_supported_version:
                client_version = f"{min_supported_version} ~ {max_supported_version}"
            elif max_supported_version:
                client_version = f"≤ {max_supported_version}"
            else:
                client_version = version_name if version_name else "未知"
        elif version_name and version_name not in ("", "未知", "Unknown"):
            # 普通服务器，有版本名
            server_version = version_name
            client_version = version_name
        elif protocol > 0:
            # 用协议号推断
            server_version = proto_ver_display or "未知"
            client_version = server_version
        else:
            server_version = "未知"
            client_version = "未知"

        # ── 6. 代理/多版本提示 ──
        if is_multi_version:
            if proxy_name:
                via_hint = f"检测到: {proxy_name} 代理"
            else:
                via_hint = "支持多版本客户端连接"
        else:
            via_hint = ""

        logger.info(f"[MOTD] 版本解析输出: server='{server_version}', client='{client_version}', "
                     f"via_hint='{via_hint}', is_multi_version={is_multi_version}, detect_reason='{detect_reason}'")

        return server_version, client_version, via_hint

    def _motd_to_html(self, motd_data: Any, max_length: int = 0) -> str:
        """将 MOTD 数据转换为带颜色/格式的 HTML（段式解析）
        支持: §0-§f 颜色码、§l/§o/§n/§m 格式码、§r 重置、JSON 组件树（含 extra 递归）
        max_length > 0 时，超过该字符数的纯文本会被截断（丢弃样式信息）
        """
        # 长度预检：提取纯文本，超长则降级为截断后的纯字符串
        if max_length > 0:
            if isinstance(motd_data, (dict, list)):
                plain = self._format_motd(motd_data)
            else:
                plain = str(motd_data)
            # 视觉长度按剔除 § 码后的文本计算，截断后丢弃样式
            plain_visible = _MOTD_SECTION_RE.sub('', plain)
            if len(plain_visible) > max_length:
                motd_data = plain_visible[:max_length] + '…'

        segments = []
        _parse_motd_segments(motd_data, _default_motd_state(), segments)
        html = _render_motd_segments(segments)
        if html:
            return html
        # 空结果兜底：输出转义后的纯文本
        fallback = self._format_motd(motd_data) if isinstance(motd_data, (dict, list)) else str(motd_data)
        return _html_escape(fallback or "")

    def _base_card_context(self) -> Dict[str, Any]:
        """构建卡片模板公共上下文（三个分支共用：主卡 / 错误卡 / 代理卡）"""
        return {
            "icon": None,
            "latency_ms": None, "latency_class": "",
            "source_label": "",
            "query_time": time.strftime("%Y-%m-%d %H:%M"),
            "show_player_list": self.show_player_list,
            "show_server_icon": self.show_server_icon,
            "show_latency": self.show_latency,
            # 卡片高度: auto→100vh(云端视口 height=1 生效, 高度贴内容); fixed→720px 显式固定
            # (固定值不依赖云端视口默认值; 矮内容补白, 超出自然撑开, 与 v2.2.0 及以前观感一致)
            "body_min_height": "720px" if self.card_height_mode == "fixed" else "100vh",
        }

    @staticmethod
    def _players_percent(online: int, max_players: int) -> int:
        """计算玩家占用百分比（0-100，上限 100，无人数上限时为 0）"""
        try:
            online, max_players = int(online), int(max_players)
        except (ValueError, TypeError):
            return 0
        if max_players <= 0:
            return 0
        return max(0, min(100, round(online / max_players * 100)))

    @staticmethod
    def _latency_class(latency_ms: Optional[int]) -> str:
        """延迟分级样式：<1000ms 绿 / <3000ms 金 / 其余红"""
        if latency_ms is None:
            return ""
        if latency_ms < 1000:
            return "lat-good"
        if latency_ms < 3000:
            return "lat-mid"
        return "lat-bad"

    def _build_footer_text(self, result: Dict[str, Any], ctx: Dict[str, Any]) -> str:
        """构建页脚文本：查询延迟 · 数据源 · 时间（按配置开关与数据可用性裁剪）"""
        # 结果中的延迟尚未写入上下文时补写（错误分支等场景）
        if ctx.get("latency_ms") is None and result.get("latency_ms") is not None:
            ctx["latency_ms"] = result.get("latency_ms")
        ctx["latency_class"] = self._latency_class(ctx.get("latency_ms"))
        parts = []
        if self.show_latency and ctx.get("latency_ms") is not None:
            parts.append(f"{ctx['latency_ms']}ms")
        source = result.get("source", "")
        if source:
            ctx["source_label"] = _SOURCE_LABELS.get(source, source)
            parts.append(ctx["source_label"])
        parts.append(ctx["query_time"])
        return " · ".join(parts)

    @staticmethod
    def _emoji(event: AstrMessageEvent, key: str) -> str:
        """按场景返回文本前缀 emoji。

        全平台统一使用 Unicode emoji（含 QQ 官方平台）：实测 QQ 官方各消息通道
        （markdown/content）均不渲染 <emoji:id> 内嵌格式（前者剥离、后者透传字面量），
        统一 Unicode 方案保证所有平台显示稳定。event 参数保留以备未来按平台定制。
        """
        return EMOJI_MAP.get(key, "")

    @staticmethod
    def _plain_chain(event: AstrMessageEvent, text: str):
        """构建强制纯文本通道的消息链。

        AstrBot 默认把文本走 markdown(msg_type=2) 通道发送：无 markdown 权限的
        机器人会发送失败，有权限的也会丢失纯文本排版 → 这里强制 use_markdown(False)
        走 content 纯文本通道，Unicode emoji 在该通道显示最稳定。
        其他平台: plain_result 本就是纯文本, use_markdown(False) 无副作用;
        旧版 AstrBot 若无该 API 则原样返回(行为与之前一致)。
        """
        chain = event.plain_result(text)
        use_md = getattr(chain, "use_markdown", None)
        if callable(use_md):
            try:
                chain = use_md(False)
            except Exception:
                pass
        return chain

    async def _send_card_with_fallback(self, event: AstrMessageEvent, template: str,
                                       context: Dict[str, Any], build_text) -> bool:
        """统一降级发送层：
        0. output_mode == "text"（低配设备）→ 跳过渲染，直接发文本；
        1. 渲染模板并发送图片（发送闸门串行 + 60 秒渲染超时，云端渲染不可达时不再无限等待）；
        2. 失败 → 发送文本回退（Unicode emoji，强制 content 纯文本通道）；
        3. 仍失败 → 仅记日志，不抛出（绝不阻塞主流程）。
        build_text: callable(context) -> str，构建回退文本
        """
        if self.output_mode == "text":
            try:
                await event.send(self._plain_chain(event, build_text(context)))
                return True
            except Exception as e:
                logger.error(f"[MOTD] 文本发送失败（放弃）: {e}")
            return False
        try:
            async with self._send_semaphore:
                # type=png: 官方 t2i 服务默认 jpeg q40 会涂抹像素风细节; PNG 无损(服务端会忽略 png 的 quality)
                # 60s 超时: AstrBot 云端渲染的 POST 无超时, 云端拥堵/不可达时最长可挂数分钟, 这里兜底回退文本, 也避免长时间占住发送闸门
                url = await asyncio.wait_for(
                    self.html_render(template, context, options={"full_page": True, "type": "png"}),
                    timeout=60,
                )
                await event.send(event.image_result(url))
            return True
        except Exception as e:
            logger.error(f"[MOTD] 图片渲染/发送失败，回退到文本: {e}")
        text = build_text(context)
        try:
            await event.send(self._plain_chain(event, text))
            return True
        except Exception as e:
            logger.error(f"[MOTD] 文本回退发送失败（放弃）: {e}")
        return False

    def _resolve_icon(self, result: Dict[str, Any], server_address: str) -> Optional[str]:
        """服务器图标缓存策略：
        本次查询带图标 → 写入/刷新磁盘缓存并返回；
        未带图标 → 回退显示 TTL 内的上一次缓存图标（无则 None，渲染为首字母占位块）
        """
        icon = result.get("icon")
        if icon:
            cache_server_icon(server_address, icon)
            return icon
        cached = get_cached_server_icon(server_address)
        if cached:
            logger.info(f"[MOTD] 本次查询未返回图标，使用磁盘缓存图标: {server_address}")
        return cached

    def _format_response(self, result: Dict[str, Any], server_address: str, is_java: bool = True,
                         avatars: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """格式化查询结果为 HTML 模板上下文字典

        avatars: 预取的玩家头像映射（缓存键 -> data URI），由 _do_motd_query 在查询后预取；
                为空时玩家列表仅携带 UUID，由渲染端在线拉取（旧行为）
        """
        if "error" in result:
            logger.info(f"[MOTD] 格式化错误结果: server='{server_address}', error='{result['error']}'")
            ctx = self._base_card_context()
            ctx.update({
                "is_error": True, "is_java": is_java,
                "server_address": server_address,
                "error_msg": result["error"],
                "edition_label": "Java" if is_java else "Bedrock",
                "badge": "JAVA" if is_java else "BEDROCK",
                "footer_text": ctx["query_time"],
            })
            return ctx

        if is_java:
            version_info = result.get("version", {})
            players_info = result.get("players", {})
            description = result.get("description", "无描述")

            # 弱机友好: 人数多的服务器样例可能极长, 只记前 8 个, 避免格式化超大字符串白白消耗 CPU/日志体积
            _sample_preview = (players_info.get("sample") or [])[:8]
            logger.info(f"[MOTD] Java 版原始数据: version={version_info}, "
                        f"players={players_info.get('online', 0)}/{players_info.get('max', 0)}, 样例(前8)={_sample_preview}")

            server_version, client_version, via_hint = self._parse_version(version_info)
            motd_html = self._motd_to_html(description, max_length=100)
            online = players_info.get("online", 0)
            max_players = players_info.get("max", 0)
            sample = players_info.get("sample", []) or []
            # 玩家样例列表：最多显示 8 个，其余计入 +N
            player_list = []
            for p in sample[:8]:
                if isinstance(p, dict):
                    name = p.get("name") or "未知"
                    uuid = p.get("uuid") or p.get("id") or ""
                else:
                    name, uuid = str(p), ""
                entry = {"name": name, "uuid": uuid, "color": _player_color(name)}
                if avatars:
                    avatar_uri = avatars.get(_avatar_cache_key(uuid, name))
                    if avatar_uri:
                        entry["avatar"] = avatar_uri
                player_list.append(entry)
            extra_count = len(sample) - 8 if len(sample) > 8 else 0

            logger.info(f"[MOTD] 格式化结果: server_version='{server_version}', client_version='{client_version}', "
                        f"players={online}/{max_players}, via_hint='{via_hint}'")

            ctx = self._base_card_context()
            ctx.update({
                "is_error": False, "is_java": True,
                "server_address": server_address,
                "edition_label": "Java", "badge": "JAVA", "icon": self._resolve_icon(result, server_address),
                "server_version": server_version,
                "client_version": client_version,
                "via_hint": via_hint,
                "online": online, "max_players": max_players,
                "online_str": f"{online:,}", "max_str": f"{max_players:,}",
                "percent": self._players_percent(online, max_players),
                "player_list": player_list, "extra_count": extra_count,
                "motd_html": motd_html,
            })
            ctx["footer_text"] = self._build_footer_text(result, ctx)
            return ctx
        else:
            motd_html = self._motd_to_html(result.get("motd", "无描述"), max_length=100)
            server_version = result.get("version", "未知")
            online = result.get("online_players", 0)
            max_players = result.get("max_players", 0)

            logger.info(f"[MOTD] 基岩版原始数据: {result}")
            logger.info(f"[MOTD] 基岩版格式化结果: version='{server_version}', players={online}/{max_players}")

            ctx = self._base_card_context()
            ctx.update({
                "is_error": False, "is_java": False,
                "server_address": server_address,
                "edition_label": "Bedrock", "badge": "BEDROCK", "icon": result.get("icon"),
                "server_version": server_version,
                "client_version": server_version,
                "online": online, "max_players": max_players,
                "online_str": f"{online:,}", "max_str": f"{max_players:,}",
                "percent": self._players_percent(online, max_players),
                "player_list": [], "extra_count": 0,
                "motd_html": motd_html,
            })
            ctx["footer_text"] = self._build_footer_text(result, ctx)
            return ctx

    async def _do_motd_query(self, event: AstrMessageEvent, server: str = "", is_java: bool = True):
        """执行 MOTD 查询的核心逻辑"""
        logger.info(f"[MOTD] 开始查询: server='{server}', is_java={is_java}")

        # 检查会话权限
        if not self._check_session_allowed(event):
            logger.info("[MOTD] 会话不在白名单中")
            return

        # 代理服务器查询模式
        if self.query_type == "proxy" and is_java:
            await self._do_proxy_query(event, server)
            return

        # 确定查询的服务器
        if not server or server.strip() == "":
            # 使用默认服务器
            if not self.default_server:
                await event.send(self._plain_chain(event,
                    f"{self._emoji(event, 'fail')} 未设置默认服务器\n"
                    "请使用: motd <服务器地址:端口> 查询指定服务器\n"
                    "或联系管理员使用 /motdconfig default <地址:端口> 设置"
                ))
                return
            server = self.default_server
            port = self.default_port
            logger.info(f"[MOTD] 使用默认服务器: {server}:{port}")
        else:
            # 用户指定了服务器，解析地址和端口
            server, port = self._parse_server_address(server.strip(), is_java=is_java)
            logger.info(f"[MOTD] 使用指定服务器: {server}:{port}")

        server_address = f"{server}:{port}"

        # 发送查询中提示（best-effort：失败不阻塞主查询流程）
        try:
            await event.send(self._plain_chain(event,
                f"{self._emoji(event, 'searching')} 正在查询..."))
        except Exception as e:
            logger.warning(f"[MOTD] 查询中提示发送失败（已忽略）: {e}")

        # 执行查询
        logger.info(f"[MOTD] 开始执行查询，超时={self.query_timeout}秒")
        try:
            if is_java:
                result = await asyncio.wait_for(
                    query_java_server(server, port, self.query_timeout, self.use_api),
                    timeout=self.query_timeout + 5
                )
            else:
                # 基岩版为同步 socket, 移入线程执行: 超时等待期间不再阻塞事件循环(单核弱机上尤为明显)
                result = await asyncio.wait_for(
                    asyncio.to_thread(query_bedrock_server, server, port, self.query_timeout),
                    timeout=self.query_timeout + 5
                )
            # 弱机友好: 只记关键字段, 不再格式化完整查询结果(样例可极长且含 base64 图标)
            if "error" in result:
                logger.info(f"[MOTD] 查询完成(失败): {result.get('error')}")
            else:
                _ver = result.get("version")
                _ver_name = _ver.get("name", "?") if isinstance(_ver, dict) else (_ver or "?")
                _players = result.get("players") if isinstance(result.get("players"), dict) else {}
                _online = _players.get("online", result.get("online_players", "?"))
                _max_p = _players.get("max", result.get("max_players", "?"))
                logger.info(f"[MOTD] 查询完成: source={result.get('source')}, 版本={_ver_name}, "
                            f"玩家={_online}/{_max_p}, 图标={'有' if result.get('icon') else '无'}, 耗时={result.get('latency_ms')}ms")
        except asyncio.TimeoutError:
            logger.error("[MOTD] 查询超时")
            result = {"error": "查询超时，服务器响应时间过长"}
        except Exception as e:
            logger.error(f"[MOTD] 查询异常: {e}")
            result = {"error": f"查询异常: {str(e)}"}

        # 预取玩家头像（磁盘缓存命中则零开销），渲染时内嵌 data URI，
        # 避免渲染服务器的浏览器临时拉取 mc-heads 失败/限流导致头像缺失
        avatar_map: Dict[str, str] = {}
        if (self.prefetch_avatars and self.show_player_list and is_java
                and self.output_mode == "image" and "error" not in result):
            try:
                _sample = result.get("players", {}).get("sample", []) or []
                avatar_map = await get_player_avatars(_sample[:8], self.avatar_cache_ttl, self.avatar_neg_cache_ttl)
                logger.info(f"[MOTD] 头像预取完成: {len(avatar_map)}/{min(len(_sample), 8)} 个")
            except Exception as e:
                logger.warning(f"[MOTD] 玩家头像预取失败（不影响查询结果）: {e}")

        # 格式化并通过统一降级发送层发送
        context = self._format_response(result, server_address, is_java=is_java, avatars=avatar_map)

        def build_text(ctx: Dict[str, Any]) -> str:
            if ctx.get("is_error"):
                return (
                    f"{self._emoji(event, 'fail')} 查询失败\n"
                    f"服务器: {ctx.get('server_address')}\n"
                    f"错误: {ctx.get('error_msg', '未知')}"
                )
            motd_plain = self._format_motd(result.get("description", result.get("motd", "")))
            motd_line = (motd_plain or "无描述")[:80]
            lines = [
                f"{self._emoji(event, 'success')} {ctx.get('server_address')}",
                f"{self._emoji(event, 'online')} 玩家: {ctx.get('online', 0)}/{ctx.get('max_players', 0)}",
                f"版本: {ctx.get('server_version', '?')}",
                f"MOTD: {motd_line}",
            ]
            if self.show_latency and ctx.get("latency_ms") is not None:
                lines.append(f"延迟: {ctx['latency_ms']}ms")
            return "\n".join(lines)

        await self._send_card_with_fallback(event, MOTD_HTML_TEMPLATE, context, build_text)
        logger.info("[MOTD] 查询流程完成")
    async def _do_proxy_query(self, event: AstrMessageEvent, server: str = ""):
        """执行代理服务器查询"""
        logger.info(f"[MOTD] 开始代理查询: method={self.proxy_query_method}, server='{server}'")

        # 确定代理地址（用于显示）
        if not server or server.strip() == "":
            if not self.default_server:
                await event.send(self._plain_chain(event,
                    f"{self._emoji(event, 'fail')} 未设置默认服务器\n"
                    "请使用: motd <服务器地址:端口> 查询代理服务器\n"
                    "或联系管理员使用 /motdconfig default <地址:端口> 设置"
                ))
                return
            proxy_host = self.default_server
            proxy_port = self.default_port
        else:
            proxy_host, proxy_port = self._parse_server_address(server.strip(), is_java=True)

        proxy_address = f"{proxy_host}:{proxy_port}"

        # 发送查询中提示（best-effort：失败不阻塞主查询流程）
        try:
            await event.send(self._plain_chain(event,
                f"{self._emoji(event, 'proxy')} 正在查询..."))
        except Exception as e:
            logger.warning(f"[MOTD] 查询中提示发送失败（已忽略）: {e}")

        # 先查询代理服务器本身
        try:
            proxy_result = await asyncio.wait_for(
                query_java_server(proxy_host, proxy_port, self.query_timeout, self.use_api),
                timeout=self.query_timeout + 5
            )
        except (asyncio.TimeoutError, Exception) as e:
            proxy_result = {"error": f"代理服务器查询失败: {str(e)}"}

        # 查询子服
        sub_servers_data = {}
        errors = []

        if self.proxy_query_method == "velostat":
            if not self.velostat_api_url:
                errors.append("未配置 velostat API 地址，请在插件配置中设置")
            else:
                result = await query_velostat_servers(self.velostat_api_url, self.query_timeout + 5)
                if result["error"]:
                    errors.append(result["error"])
                else:
                    sub_servers_data = result["servers"]
        else:  # direct
            sub_servers = parse_sub_servers_config(self.sub_servers_config)
            if not sub_servers:
                errors.append("未配置子服地址，请在插件配置中设置子服列表")
            else:
                result = await query_sub_servers_direct(sub_servers, self.query_timeout, self.use_api)
                sub_servers_data = result["servers"]
                errors.extend(result["errors"])

        # 构建模板上下文并通过统一降级发送层发送
        context = self._build_proxy_context(proxy_result, proxy_address, sub_servers_data, errors)
        await self._send_card_with_fallback(
            event, PROXY_HTML_TEMPLATE, context,
            lambda ctx: self._build_proxy_text_response(ctx, proxy_address, event)
        )
        logger.info("[MOTD] 代理查询流程完成")

    def _build_proxy_context(self, proxy_result: Dict, proxy_address: str,
                             sub_servers: Dict, errors: list) -> Dict[str, Any]:
        """构建代理查询模板上下文"""
        ctx = self._base_card_context()
        # 处理代理服务器信息
        if "error" in proxy_result:
            proxy_info = {
                "is_error": True,
                "address": proxy_address,
                "error_msg": proxy_result["error"]
            }
            footer_text = ctx["query_time"]
        else:
            version_info = proxy_result.get("version", {})
            players_info = proxy_result.get("players", {})
            description = proxy_result.get("description", "无描述")
            server_version, client_version, via_hint = self._parse_version(version_info)
            online = players_info.get("online", 0)
            max_players = players_info.get("max", 0)
            motd_plain = self._format_motd(description) or "无描述"
            resolved_icon = self._resolve_icon(proxy_result, proxy_address)

            proxy_info = {
                "is_error": False,
                "address": proxy_address,
                "server_version": server_version,
                "client_version": client_version,
                "via_hint": via_hint,
                "online": online,
                "max_players": max_players,
                "online_str": f"{online:,}", "max_str": f"{max_players:,}",
                "percent": self._players_percent(online, max_players),
                "motd_html": self._motd_to_html(description, max_length=80),
                "motd_plain": motd_plain[:100],
                "icon": resolved_icon,
                "latency_ms": proxy_result.get("latency_ms"),
                "latency_class": self._latency_class(proxy_result.get("latency_ms")),
            }
            ctx["latency_ms"] = proxy_result.get("latency_ms")
            ctx["latency_class"] = self._latency_class(ctx["latency_ms"])
            ctx["icon"] = resolved_icon
            footer_parts = []
            if self.show_latency and ctx["latency_ms"] is not None:
                footer_parts.append(f"{ctx['latency_ms']}ms")
            source = proxy_result.get("source", "")
            if source:
                footer_parts.append(_SOURCE_LABELS.get(source, source))
            footer_parts.append(ctx["query_time"])
            footer_text = " · ".join(footer_parts)

        # 处理子服信息
        sub_servers_list = []
        for name, data in sub_servers.items():
            if "error" in data:
                sub_servers_list.append({
                    "name": name,
                    "is_error": True,
                    "is_offline": False,
                    "error_msg": str(data["error"])[:40]
                })
            elif data.get("online") is False:
                # velostat 返回 online=false，表示子服未启动/已关服
                sub_servers_list.append({
                    "name": name,
                    "is_error": False,
                    "is_offline": True,
                    "online": 0,
                    "max_players": 0,
                    "online_str": "0", "max_str": "0",
                    "percent": 0,
                    "server_version": "未知",
                    "motd_html": ""
                })
            else:
                version_info = data.get("version", {})
                players_info = data.get("players", {})
                description = data.get("motd") or data.get("description") or "无描述"
                server_version, client_version, via_hint = self._parse_version(version_info)
                online = players_info.get("online", 0)
                max_players = players_info.get("max", 0)

                sub_servers_list.append({
                    "name": name,
                    "is_error": False,
                    "is_offline": False,
                    "server_version": server_version,
                    "online": online,
                    "max_players": max_players,
                    "online_str": f"{online:,}", "max_str": f"{max_players:,}",
                    "percent": self._players_percent(online, max_players),
                    "motd_html": self._motd_to_html(description, max_length=60)
                })

        ctx.update({
            "proxy": proxy_info,
            "sub_servers": sub_servers_list,
            "errors": errors,
            "has_sub_servers": len(sub_servers_list) > 0,
            "footer_text": footer_text,
        })
        return ctx

    def _build_proxy_text_response(self, context: Dict, proxy_address: str, event: AstrMessageEvent) -> str:
        """构建代理查询纯文本响应（回退用）"""
        lines = [f"{self._emoji(event, 'proxy')} 代理服务器: {proxy_address}"]

        proxy = context.get("proxy", {})
        if proxy.get("is_error"):
            lines.append(f"{self._emoji(event, 'fail')} 代理查询失败: {proxy.get('error_msg', '未知')}")
        else:
            lines.append(f"{self._emoji(event, 'online')} 玩家: {proxy.get('online', 0)}/{proxy.get('max_players', 0)}")
            lines.append(f"版本: {proxy.get('server_version', '?')}")
            if proxy.get("motd_plain"):
                lines.append(f"MOTD: {proxy['motd_plain']}")
            if self.show_latency and proxy.get("latency_ms") is not None:
                lines.append(f"延迟: {proxy['latency_ms']}ms")

        sub_servers = context.get("sub_servers", [])
        if sub_servers:
            lines.append("")
            lines.append(f"{self._emoji(event, 'proxy')} 子服列表:")
            for sub in sub_servers:
                if sub.get("is_error"):
                    lines.append(f"  {self._emoji(event, 'fail')} {sub['name']}: {sub.get('error_msg', '查询失败')}")
                elif sub.get("is_offline"):
                    lines.append(f"  {self._emoji(event, 'offline')} {sub['name']}: 未启动")
                else:
                    lines.append(f"  {self._emoji(event, 'online')} {sub['name']}: {sub.get('online', 0)}/{sub.get('max_players', 0)} ({sub.get('server_version', '?')})")

        errors = context.get("errors", [])
        if errors:
            lines.append("")
            lines.append("⚠️ 错误:")
            for error in errors:
                lines.append(f"  - {error}")

        return "\n".join(lines)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """监听所有消息，处理无斜杠前缀的 motd 指令"""
        message = event.message_str.strip()
        
        # 获取原始消息链，检查第一个消息段
        try:
            message_chain = event.message_obj.message
            if message_chain and len(message_chain) > 0:
                first_seg = message_chain[0]
                # 如果第一个消息段是 Plain 且以 / 开头，跳过（这是指令消息）
                if hasattr(first_seg, 'text') and first_seg.text.startswith('/'):
                    return
        except:
            pass
        
        # 简单文本检查：如果以 / 开头，跳过
        if message.startswith('/'):
            return
        
        # 检查消息是否以 motd 开头（不区分大小写）
        if not re.match(r'^motd', message, re.IGNORECASE):
            return
        
        # 匹配 motd 指令模式
        motd_pattern = r'^(motd)(?:-bedrock)?(?:\s+(.+))?$'
        match = re.match(motd_pattern, message, re.IGNORECASE)
        
        if match:
            logger.info(f"[MOTD] 匹配到 motd 指令: {message}")
            is_bedrock = '-bedrock' in message.lower()
            server = match.group(2).strip() if match.group(2) else ""
            
            await self._do_motd_query(event, server, is_java=not is_bedrock)

    @filter.command("motd")
    async def motd_query_cmd(self, event: AstrMessageEvent, server: str = ""):
        """MOTD 查询指令（带斜杠前缀）"""
        # 获取原始消息，检查是否以 / 开头
        message_str = event.message_str.strip()
        if not message_str.startswith('/'):
            logger.info(f"[MOTD] /motd 指令被跳过（消息不以 / 开头）")
            return
        
        logger.info(f"[MOTD] 收到 /motd 指令: server='{server}'")
        await self._do_motd_query(event, server, is_java=True)

    @filter.command("motd-bedrock")
    async def motd_bedrock_query_cmd(self, event: AstrMessageEvent, server: str = ""):
        """基岩版 MOTD 查询指令（带斜杠前缀）"""
        # 获取原始消息，检查是否以 / 开头
        message_str = event.message_str.strip()
        if not message_str.startswith('/'):
            logger.info(f"[MOTD] /motd-bedrock 指令被跳过（消息不以 / 开头）")
            return
        
        logger.info(f"[MOTD] 收到 /motd-bedrock 指令: server='{server}'")
        await self._do_motd_query(event, server, is_java=False)

    @filter.command("motdr")
    async def motd_refresh_cmd(self, event: AstrMessageEvent):
        """清空头像/图标缓存指令（/motdconfig refresh 的简写）"""
        # 获取原始消息，检查是否以 / 开头
        message_str = event.message_str.strip()
        if not message_str.startswith('/'):
            logger.info(f"[MOTD] /motdr 指令被跳过（消息不以 / 开头）")
            return
        
        logger.info(f"[MOTD] 收到 /motdr 指令")
        
        # 检查管理员权限
        if not self._is_admin(event):
            yield self._plain_chain(event, f"{self._emoji(event, 'fail')} 只有管理员才能使用此指令")
            return
        
        # 立即刷新：清空头像/图标磁盘缓存，下次查询重新下载
        avatar_count, icon_count = clear_disk_cache()
        yield self._plain_chain(event,
            f"{self._emoji(event, 'success')} 缓存已清空，下次查询将重新下载\n"
            f"👤 玩家头像: {avatar_count} 个\n"
            f"🖼️ 服务器图标: {icon_count} 个"
        )

    @filter.command("motdconfig")
    async def motd_config_cmd(self, event: AstrMessageEvent, action: str = "", value: str = ""):
        """MOTD 插件配置指令"""
        # 获取原始消息，检查是否以 / 开头
        message_str = event.message_str.strip()
        if not message_str.startswith('/'):
            logger.info(f"[MOTD] /motdconfig 指令被跳过（消息不以 / 开头）")
            return
        
        logger.info(f"[MOTD] 收到 /motdconfig 指令: action={action}, value={value}")
        
        # 检查管理员权限
        if not self._is_admin(event):
            yield self._plain_chain(event,f"{self._emoji(event, 'fail')} 只有管理员才能使用此指令")
            return
        
        action = action.lower().strip()
        
        if action == "default":
            if not value:
                yield self._plain_chain(event,f"{self._emoji(event, 'fail')} 请提供服务器地址\n用法: /motdconfig default <服务器地址:端口>")
                return
            
            server, port = self._parse_server_address(value, is_java=True)
            
            # 验证服务器是否可连接
            yield self._plain_chain(event, f"{self._emoji(event, 'searching')} 正在验证...")
            
            try:
                result = await asyncio.wait_for(
                    query_java_server(server, port, self.query_timeout, self.use_api),
                    timeout=self.query_timeout + 5
                )
            except asyncio.TimeoutError:
                result = {"error": "验证超时"}
            except Exception as e:
                result = {"error": str(e)}
            
            if "error" in result:
                yield self._plain_chain(event,
                    f"{self._emoji(event, 'fail')} 无法连接到服务器\n"
                    f"地址: {server}:{port}\n"
                    f"错误: {result['error']}\n"
                    f"请检查地址是否正确，或服务器是否在线"
                )
                return
            
            # 更新配置
            self.default_server = server
            self.default_port = port
            self.config["default_server"] = server
            self.config["default_port"] = port
            
            # 保存配置
            try:
                self.config.save_config()
                logger.info(f"[MOTD] 配置已保存: {server}:{port}")
            except Exception as e:
                logger.error(f"[MOTD] 保存配置失败: {e}")
            
            yield self._plain_chain(event,
                f"{self._emoji(event, 'success')} 默认服务器设置成功\n"
                f"地址: {server}:{port}\n"
                f"MOTD: {self._format_motd(result.get('description', '无描述'))}"
            )
        
        elif action == "get":
            default = f"{self.default_server}:{self.default_port}" if self.default_server else "未设置"
            sessions = "所有会话" if self.enable_all_sessions else f"{len(self.enabled_sessions)} 个会话"
            
            yield self._plain_chain(event,
                f"📋 MOTD 插件配置\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🖥️ 默认服务器: {default}\n"
                f"💬 生效范围: {sessions}\n"
                f"🔒 仅管理员配置: {'是' if self.admin_only_config else '否'}\n"
                f"⏱️ 查询超时: {self.query_timeout}秒\n"
                f"📤 输出模式: {'图片卡片' if self.output_mode == 'image' else '纯文本(低配设备)'}\n"
                f"📐 卡片高度: {'随内容自适应' if self.card_height_mode == 'auto' else '固定(720px)'}\n"
                f"🌐 使用 API 竞速查询: {'是' if self.use_api else '否'}\n"
                f"👤 头像预取: {'开启' if self.prefetch_avatars else '关闭'}(刷新周期 {self.avatar_cache_ttl} 小时, 失败负缓存 {'关闭' if self.avatar_neg_cache_ttl <= 0 else f'{self.avatar_neg_cache_ttl} 分钟'})\n"
                f"🖼️ 图标缓存: 保留最后一次成功获取(/motdr 清空)"
            )
        
        else:
            yield self._plain_chain(event,
                "❓ 未知操作\n"
                "可用操作:\n"
                "  default <地址:端口> - 设置默认服务器\n"
                "  get - 查看当前配置\n"
                "  缓存刷新请使用 /motdr (清空头像/图标缓存, 立即刷新)"
            )

    @filter.on_astrbot_loaded()
    async def on_astrbot_loaded(self):
        """Bot 初始化完成时"""
        logger.info("=" * 50)
        logger.info("[MOTD] 插件已加载 v2.3.0")
        logger.info("[MOTD] 支持 ViaVersion/Velocity/BungeeCord 多版本兼容")
        logger.info(f"[MOTD] 默认服务器: {self.default_server}:{self.default_port if self.default_server else '未设置'}")
        logger.info(f"[MOTD] 查询类型: {self.query_type}")
        if self.query_type == "proxy":
            logger.info(f"[MOTD] 代理查询方式: {self.proxy_query_method}")
            if self.proxy_query_method == "velostat":
                logger.info(f"[MOTD] velostat API: {self.velostat_api_url or '未配置'}")
            else:
                logger.info(f"[MOTD] 子服列表: {self.sub_servers_config or '未配置'}")
        logger.info(f"[MOTD] 对所有会话生效: {self.enable_all_sessions}")
        logger.info(f"[MOTD] 使用 API 查询: {self.use_api}")
        logger.info(f"[MOTD] 头像预取: {'开启' if self.prefetch_avatars else '关闭'}, 头像刷新周期 {self.avatar_cache_ttl} 小时, 下载失败负缓存 {'关闭' if self.avatar_neg_cache_ttl <= 0 else f'{self.avatar_neg_cache_ttl} 分钟'}, 图标缓存保留最后一次成功获取")

        logger.info("=" * 50)

    async def terminate(self):
        """插件被禁用/重载时释放资源：关闭共享 HTTP 会话"""
        await _close_http_session()
        logger.info("[MOTD] 插件已卸载，共享 HTTP 会话已关闭")
