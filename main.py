"""
AstrBot MOTD 查询插件
用于查询 Minecraft 服务器状态
"""

import socket
import struct
import json
import time
import re
import asyncio
import aiohttp
from typing import Optional, Dict, Any, Tuple

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
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


async def query_java_server_api(host: str, port: int = JAVA_DEFAULT_PORT) -> Dict[str, Any]:
    """使用第三方 API 查询 Java 版服务器状态"""
    try:
        async with aiohttp.ClientSession() as session:
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

                        return {
                            "version": {"name": version_name_raw, "protocol": protocol_raw if protocol_raw is not None else 0},
                            "players": {"online": data.get("players", {}).get("online", 0), "max": data.get("players", {}).get("max", 0)},
                            "description": data.get("motd", {}).get("clean", "无描述")
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
    """直接查询 Java 版服务器状态"""
    
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
    
    def _unpack_varint(sock: socket.socket) -> int:
        result = 0
        for i in range(5):
            byte = sock.recv(1)
            if not byte:
                raise ConnectionError("连接中断")
            byte = byte[0]
            result |= (byte & 0x7F) << (7 * i)
            if not (byte & 0x80):
                return result
        raise ValueError("变长整数过大")
    
    def _pack_data(data: bytes) -> bytes:
        return _pack_varint(len(data)) + data
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        
        # 发送握手包
        handshake_data = (
            _pack_varint(-1) +  # 协议版本 -1
            _pack_data(host.encode('utf-8')) +
            struct.pack('>H', port) +
            _pack_varint(1)  # 状态请求
        )
        packet = _pack_varint(0) + handshake_data
        sock.sendall(_pack_data(packet))
        
        # 发送状态请求
        sock.sendall(_pack_data(_pack_varint(0)))
        
        # 读取响应长度
        length = _unpack_varint(sock)
        packet_id = _unpack_varint(sock)
        
        # 读取 JSON 长度
        json_length = _unpack_varint(sock)
        
        # 读取 JSON 数据
        json_data = b""
        while len(json_data) < json_length:
            chunk = sock.recv(min(4096, json_length - len(json_data)))
            if not chunk:
                break
            json_data += chunk
        
        sock.close()
        
        response = json.loads(json_data.decode('utf-8'))
        return response
        
    except socket.timeout:
        return {"error": "连接超时，请检查服务器地址和端口是否正确"}
    except socket.gaierror:
        return {"error": "无法解析服务器地址，请检查主机名是否正确"}
    except ConnectionRefusedError:
        return {"error": "连接被拒绝，服务器可能未运行或端口不正确"}
    except Exception as e:
        return {"error": f"查询失败: {str(e)}"}


async def query_java_server(host: str, port: int = JAVA_DEFAULT_PORT, timeout: int = 5, use_api: bool = True) -> Dict[str, Any]:
    """查询 Java 版服务器状态，优先使用 API"""
    if use_api:
        # 先尝试 API
        result = await query_java_server_api(host, port)
        if "error" not in result:
            return result
        logger.info(f"[MOTD] API 查询失败，尝试直接查询: {result.get('error')}")

    # API 失败或禁用 API，使用直接查询
    result = await query_java_server_direct(host, port, timeout)

    # 直连返回协议号 ≤ 0（代理/多版本服务器），补查 API 获取带范围的版本名
    if "error" not in result:
        proto = result.get("version", {}).get("protocol", 0)
        version_name = result.get("version", {}).get("name", "")
        logger.info(f"[MOTD] 直连查询结果: protocol={proto}, name='{version_name}'")
        if proto is not None and proto <= 0:
            logger.info(f"[MOTD] 直连协议号 {proto} ≤ 0，补查 API 获取版本范围")
            api_result = await query_java_server_api(host, port)
            if "error" not in api_result:
                api_name = api_result.get("version", {}).get("name", "")
                if api_name and api_name != version_name:
                    result["version"]["name"] = api_name
                    logger.info(f"[MOTD] API 补全版本名: '{version_name}' -> '{api_name}'")
                else:
                    logger.info(f"[MOTD] API 版本名相同或为空，无需补全")

    return result


async def query_bedrock_server(host: str, port: int = BEDROCK_DEFAULT_PORT, timeout: int = 5) -> Dict[str, Any]:
    """异步查询基岩版服务器状态"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        
        # 发送 Unconnected Ping
        ping_data = b'\x01' + struct.pack('>Q', int(time.time() * 1000)) + b'\x00\x00\x00\x00\x00\x00\x00\x00'
        sock.sendto(ping_data, (host, port))
        
        # 接收响应
        data, addr = sock.recvfrom(2048)
        sock.close()
        
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
                "server_id": server_info[6] if len(server_info) > 6 else "未知"
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
                return name, None, f"{name}: {result['error']}"
            else:
                return name, result, None
        except asyncio.TimeoutError:
            return name, None, f"{name}: 查询超时"
        except Exception as e:
            return name, None, f"{name}: {str(e)}"

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
            if error:
                errors.append(error)

    return {"servers": results, "errors": errors}


# ============================================================
# HTML 模板：MOTD 服务器状态卡片
# Minecraft 游戏内 UI 风格
# ============================================================
MOTD_HTML_TEMPLATE = '''
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap');
html, body {
    margin: 0; padding: 0;
    height: 100%;
}
body {
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif;
    color: #e0e0e0;
    width: 100%;
    height: 100%;
    margin: 0;
    padding: 0;
}
.card {
    padding: 32px;
    background: #2D2D2D;
    width: 100%;
    height: 100%;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    border: 3px solid #555;
    box-shadow: inset 0 0 0 1px #444;
}
.header {
    display: flex;
    align-items: baseline;
    gap: 16px;
    margin-bottom: 32px;
    padding-bottom: 20px;
    border-bottom: 2px solid #444;
}
.server-name {
    font-size: 72px;
    font-weight: 700;
    color: #fff;
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.badge {
    font-family: 'JetBrains Mono', monospace;
    font-size: 28px;
    font-weight: 600;
    padding: 6px 14px;
    background: #3C3C3C;
    color: #aaa;
    border: 1px solid #555;
}
.badge-java {
    color: #55ff55;
    border-color: #55ff55;
}
.badge-bedrock {
    color: #ffaa00;
    border-color: #ffaa00;
}
.stats-row {
    display: flex;
    gap: 24px;
    margin-bottom: 24px;
}
.stat-box {
    flex: 1;
    background: #333;
    padding: 28px 32px;
    border: 2px solid #444;
    position: relative;
}
.stat-box::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: #55ff55;
}
.stat-label {
    font-size: 28px;
    color: #777;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-bottom: 12px;
}
.stat-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 128px;
    font-weight: 700;
    color: #fff;
}
.stat-value.players-num {
    color: #55ff55;
}
.stat-value .fraction {
    font-size: 64px;
    color: #666;
}
.stat-main {
    display: flex;
    align-items: flex-end;
    justify-content: center;
    gap: 80px;
}
.players-section {
    flex: 0 0 auto;
}
.version-section {
    text-align: right;
    flex: 0 0 auto;
}
.version-label {
    font-size: 22px;
    color: #666;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 6px;
}
.version-text {
    font-size: 40px;
    color: #fff;
    font-weight: 600;
}
.version-protocol {
    font-size: 26px;
    color: #666;
    margin-top: 4px;
}
.via-tag {
    display: inline-block;
    font-size: 24px;
    color: #ffaa00;
    background: rgba(255,170,0,0.15);
    padding: 3px 8px;
    margin-top: 6px;
    border: 1px solid rgba(255,170,0,0.3);
}
.motd-section {
    flex: 1;
    background: #1a1a1a;
    border: 2px solid #444;
    padding: 24px;
    position: relative;
}
.motd-content {
    font-size: 22px;
    line-height: 1.7;
    color: #ccc;
    word-break: break-all;
}
.footer {
    margin-top: 24px;
    display: flex;
    justify-content: space-between;
    font-size: 24px;
    color: #555;
}
.footer-line {
    flex: 1;
    height: 1px;
    background: #444;
    align-self: center;
    margin: 0 16px;
}
.title-error { color: #ff5555; }
.error-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    gap: 20px;
}
.error-icon {
    font-size: 48px;
    opacity: 0.8;
}
.error-msg {
    background: rgba(255,85,85,0.1);
    padding: 16px 24px;
    font-size: 16px;
    color: #ff8888;
    text-align: center;
    border: 2px solid rgba(255,85,85,0.3);
    max-width: 400px;
}
</style>

<div class="card">

  {% if is_error %}
  <div class="header">
    <span class="server-name title-error">连接失败</span>
    <span class="badge badge-bedrock">{{ edition_label }}</span>
  </div>
  <div class="error-container">
    <div class="error-icon">✖</div>
    <div class="error-msg">{{ error_msg }}</div>
    <div style="font-size: 13px; color: #666;">{{ server_address }}</div>
  </div>

  {% else %}
  <div class="header">
    <span class="server-name">{{ server_address }}</span>
    <span class="badge {% if is_java %}badge-java{% else %}badge-bedrock{% endif %}">{{ edition_label }}</span>
  </div>

  <div class="stat-box">
    <div class="stat-label">在线玩家</div>
    <div class="stat-main">
      <div class="players-section">
        <div class="stat-value players-num">{{ online }}<span class="fraction">/{{ max_players }}</span></div>
      </div>
      <div class="version-section">
        <div class="version-label">服务器版本</div>
        <div class="version-text">{{ server_version }}</div>
        {% if client_version and client_version != server_version %}
        <div class="version-label" style="margin-top: 12px;">客户端版本</div>
        <div class="version-text" style="font-size: 32px;">{{ client_version }}</div>
        {% endif %}
        {% if via_hint %}<div class="via-tag">{{ via_hint }}</div>{% endif %}
      </div>
    </div>
  </div>

  <div class="motd-section">
    <div class="motd-content">{{ motd_html }}</div>
  </div>

  <div class="footer">
    <span>MOTD 查询</span>
    <div class="footer-line"></div>
    <span>Hayston1001</span>
  </div>
  {% endif %}

</div>
'''


# ============================================================
# HTML 模板：代理服务器状态卡片（母服 + 子服列表）
# ============================================================
PROXY_HTML_TEMPLATE = '''
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap');
html, body {
    margin: 0; padding: 0;
    height: 100%;
}
body {
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif;
    color: #e0e0e0;
    width: 100%;
    height: 100%;
    margin: 0;
    padding: 0;
}
.card {
    padding: 32px;
    background: #2D2D2D;
    width: 100%;
    height: 100%;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    border: 3px solid #555;
    box-shadow: inset 0 0 0 1px #444;
}
.header {
    display: flex;
    align-items: baseline;
    gap: 16px;
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 2px solid #444;
}
.server-name {
    font-size: 48px;
    font-weight: 700;
    color: #fff;
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.badge {
    font-family: 'JetBrains Mono', monospace;
    font-size: 22px;
    font-weight: 600;
    padding: 5px 12px;
    background: #3C3C3C;
    color: #aaa;
    border: 1px solid #555;
}
.badge-proxy {
    color: #55ffff;
    border-color: #55ffff;
}
/* 代理服务器信息 */
.proxy-info {
    background: #333;
    padding: 28px 32px;
    border: 2px solid #444;
    margin-bottom: 20px;
    position: relative;
}
.proxy-info::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: #55ffff;
}
.proxy-label {
    font-size: 24px;
    color: #777;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-bottom: 12px;
}
.proxy-stats {
    display: flex;
    align-items: flex-end;
    justify-content: center;
    gap: 60px;
}
.proxy-players-section {
    flex: 0 0 auto;
}
.proxy-players {
    font-family: 'JetBrains Mono', monospace;
    font-size: 72px;
    font-weight: 700;
    color: #55ff55;
}
.proxy-players .fraction {
    font-size: 36px;
    color: #666;
}
.proxy-version {
    text-align: right;
    flex: 0 0 auto;
}
.proxy-version-label {
    font-size: 20px;
    color: #666;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 6px;
}
.proxy-version-text {
    font-size: 36px;
    color: #fff;
    font-weight: 600;
}
.proxy-via-tag {
    display: inline-block;
    font-size: 16px;
    color: #ffaa00;
    background: rgba(255,170,0,0.15);
    padding: 3px 8px;
    margin-top: 6px;
    border: 1px solid rgba(255,170,0,0.3);
}
.proxy-motd {
    margin-top: 12px;
    font-size: 16px;
    line-height: 1.5;
    color: #ccc;
}
/* 子服列表 */
.sub-servers-section {
    flex: 1;
    min-height: 0;
}
.section-title {
    font-size: 20px;
    color: #aaa;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #444;
}
.sub-servers-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
}
.sub-servers-grid.compact {
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
}
.sub-server-item {
    background: #1a1a1a;
    border: 2px solid #333;
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 6px;
}
.sub-server-item.compact {
    padding: 10px 12px;
    gap: 3px;
}
.sub-server-item.compact .sub-server-name {
    font-size: 16px;
}
.sub-server-item.compact .sub-server-players {
    font-size: 18px;
}
.sub-server-item.compact .sub-server-players .fraction {
    font-size: 12px;
}
.sub-server-item.compact .sub-server-version {
    font-size: 13px;
}
.sub-server-item.compact .sub-server-motd {
    font-size: 12px;
}
.sub-server-item.compact .status-dot {
    width: 6px;
    height: 6px;
}
.sub-servers-more {
    margin-top: 8px;
    font-size: 14px;
    color: #888;
    text-align: center;
}
.sub-server-header {
    display: flex;
    align-items: center;
    gap: 10px;
}
.sub-server-name {
    font-size: 20px;
    font-weight: 700;
    color: #fff;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.sub-server-status {
    display: flex;
    align-items: baseline;
    gap: 8px;
}
.sub-server-players {
    font-family: 'JetBrains Mono', monospace;
    font-size: 22px;
    font-weight: 700;
    color: #55ff55;
}
.sub-server-players .fraction {
    font-size: 14px;
    color: #666;
}
.sub-server-version {
    font-size: 14px;
    color: #aaa;
}
.sub-server-motd {
    font-size: 13px;
    color: #888;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.sub-server-error {
    font-size: 11px;
    color: #ff5555;
}
.status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
}
.status-dot-online {
    background: #55ff55;
    box-shadow: 0 0 3px #55ff55;
}
.status-dot-offline {
    background: #ff5555;
    box-shadow: 0 0 3px #ff5555;
}
/* 错误状态 */
.error-container {
    padding: 16px;
    text-align: center;
}
.error-msg {
    background: rgba(255,85,85,0.1);
    padding: 10px 16px;
    font-size: 13px;
    color: #ff8888;
    border: 2px solid rgba(255,85,85,0.3);
    display: inline-block;
}
/* 底部 */
.footer {
    margin-top: 12px;
    display: flex;
    justify-content: space-between;
    font-size: 14px;
    color: #555;
}
.footer-line {
    flex: 1;
    height: 1px;
    background: #444;
    align-self: center;
    margin: 0 12px;
}

</style>

<div class="card">
  <div class="header">
    <span class="server-name">代理服务器</span>
    <span class="badge badge-proxy">PROXY</span>
  </div>

  {% if proxy.is_error %}
  <div class="proxy-info">
    <div class="error-container">
      <div class="error-msg">{{ proxy.error_msg }}</div>
      <div style="font-size: 13px; color: #666; margin-top: 8px;">{{ proxy.address }}</div>
    </div>
  </div>
  {% else %}
  <div class="proxy-info">
    <div class="proxy-label">在线玩家</div>
    <div class="proxy-stats">
      <div class="proxy-players-section">
        <div class="proxy-players">{{ proxy.online }}<span class="fraction">/{{ proxy.max_players }}</span></div>
      </div>
      <div class="proxy-version">
        <div class="proxy-version-label">代理版本</div>
        <div class="proxy-version-text">{{ proxy.server_version }}</div>
        {% if proxy.via_hint %}<div class="proxy-via-tag">{{ proxy.via_hint }}</div>{% endif %}
      </div>
    </div>
    <div class="proxy-motd">{{ proxy.motd_html }}</div>
  </div>
  {% endif %}

  {% if has_sub_servers %}
  <div class="sub-servers-section">
    <div class="section-title">子服列表 ({{ sub_servers|length }})</div>
    <div class="sub-servers-grid {% if sub_servers|length > 6 %}compact{% endif %}">
    {% for sub in sub_servers %}
    {% if loop.index <= 6 %}
    <div class="sub-server-item {% if sub_servers|length > 6 %}compact{% endif %}">
      <div class="sub-server-header">
        <span class="status-dot {% if sub.is_error %}status-dot-offline{% else %}status-dot-online{% endif %}"></span>
        <span class="sub-server-name">{{ sub.name }}</span>
      </div>
      {% if sub.is_error %}
      <span class="sub-server-error">{{ sub.error_msg }}</span>
      {% else %}
      <div class="sub-server-status">
        <span class="sub-server-players">{{ sub.online }}<span class="fraction">/{{ sub.max_players }}</span></span>
        <span class="sub-server-version">{{ sub.server_version }}</span>
      </div>
      <span class="sub-server-motd">{{ sub.motd_html }}</span>
      {% endif %}
    </div>
    {% endif %}
    {% endfor %}
    </div>
    {% if sub_servers|length > 6 %}
    <div class="sub-servers-more">还有 {{ sub_servers|length - 6 }} 个子服未显示...</div>
    {% endif %}
  </div>
  {% endif %}

  <div class="footer">
    <span>MOTD 查询</span>
    <div class="footer-line"></div>
    <span>Hayston1001</span>
  </div>
</div>
'''


@register("astrbot_plugin_minecraft_motd", "MOTD查询", "查询 Minecraft 服务器状态的 AstrBot 插件，支持 ViaVersion/Velocity/BungeeCord 多版本兼容", "1.6.0")
class MOTDPlugin(Star):
    """MOTD 查询插件主类"""
    
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._load_config()
        logger.info(f"[MOTD] 插件初始化完成，版本 1.6.0")
    
    def _load_config(self):
        """加载插件配置"""
        self.default_server = self.config.get("default_server", "")
        self.default_port = self.config.get("default_port", JAVA_DEFAULT_PORT)
        self.enabled_sessions = self.config.get("enabled_sessions", [])
        self.enable_all_sessions = self.config.get("enable_all_sessions", True)
        self.admin_only_config = self.config.get("admin_only_config", True)
        self.query_timeout = self.config.get("query_timeout", 5)
        self.use_api = self.config.get("use_api", True)

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

    def _motd_to_html(self, motd_data: Any) -> str:
        """将 MOTD 数据转换为带颜色的 HTML，支持 § 颜色码和 JSON 格式"""
        parts = []
        current_color = '#ffffff'

        def _flush(text: str):
            if text:
                escaped = _html_escape(text)
                if current_color != '#ffffff':
                    parts.append(f'<span style="color:{current_color}">{escaped}</span>')
                else:
                    parts.append(escaped)

        def _walk(data, color):
            nonlocal current_color
            if isinstance(data, str):
                # 处理 § 颜色码
                segments = re.split(r'(§[0-9a-fk-or])', data)
                for seg in segments:
                    m = re.match(r'§([0-9a-f])', seg, re.IGNORECASE)
                    if m:
                        code = m.group(1).lower()
                        _flush('')  # 保存当前颜色段
                        current_color = MINECRAFT_COLOR_MAP.get(code, current_color)
                    elif seg:
                        _flush(seg)
            elif isinstance(data, dict):
                c = color
                if 'color' in data:
                    c = data['color']
                if c:
                    current_color = c
                _walk(data.get('text', ''), c)
                for item in data.get('extra', []):
                    _walk(item, c)
            elif isinstance(data, list):
                for item in data:
                    _walk(item, color)

        _walk(motd_data, current_color)
        _flush('')  # flush remaining
        return ''.join(parts) if parts else _html_escape(str(motd_data))

    def _format_response(self, result: Dict[str, Any], server_address: str, is_java: bool = True) -> Dict[str, Any]:
        """格式化查询结果为 HTML 模板上下文字典"""
        if "error" in result:
            logger.info(f"[MOTD] 格式化错误结果: server='{server_address}', error='{result['error']}'")
            return {
                "is_error": True, "is_java": is_java,
                "server_address": server_address,
                "error_msg": result["error"],
                "edition_label": "Java" if is_java else "Bedrock",
            }

        if is_java:
            version_info = result.get("version", {})
            players_info = result.get("players", {})
            description = result.get("description", "无描述")

            logger.info(f"[MOTD] Java 版原始数据: version={version_info}, players={players_info}")

            server_version, client_version, via_hint = self._parse_version(version_info)
            motd_html = self._motd_to_html(description)
            online = players_info.get("online", 0)
            max_players = players_info.get("max", 0)
            sample = players_info.get("sample", [])
            player_list = [p.get("name", "未知") for p in sample[:10]] if sample else []
            extra_count = len(sample) - 10 if len(sample) > 10 else 0

            logger.info(f"[MOTD] 格式化结果: server_version='{server_version}', client_version='{client_version}', "
                        f"players={online}/{max_players}, via_hint='{via_hint}'")

            return {
                "is_error": False, "is_java": True,
                "server_address": server_address,
                "edition_label": "Java",
                "server_version": server_version,
                "client_version": client_version,
                "via_hint": via_hint,
                "online": online, "max_players": max_players,
                "player_list": player_list, "extra_count": extra_count,
                "motd_html": motd_html,
            }
        else:
            motd_html = self._motd_to_html(result.get("motd", "无描述"))
            server_version = result.get("version", "未知")
            online = result.get("online_players", 0)
            max_players = result.get("max_players", 0)

            logger.info(f"[MOTD] 基岩版原始数据: {result}")
            logger.info(f"[MOTD] 基岩版格式化结果: version='{server_version}', players={online}/{max_players}")

            return {
                "is_error": False, "is_java": False,
                "server_address": server_address,
                "edition_label": "Bedrock",
                "server_version": server_version,
                "client_version": server_version,
                "online": online,
                "max_players": max_players,
                "player_list": [], "extra_count": 0,
                "motd_html": motd_html,
            }

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
                await event.send(event.plain_result(
                    "❌ 未设置默认服务器\n"
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

        # 发送查询中提示
        await event.send(event.plain_result(f"🔍 正在查询服务器 {server_address} ..."))

        # 执行查询
        logger.info(f"[MOTD] 开始执行查询，超时={self.query_timeout}秒")
        try:
            if is_java:
                result = await asyncio.wait_for(
                    query_java_server(server, port, self.query_timeout, self.use_api),
                    timeout=self.query_timeout + 5
                )
            else:
                result = await asyncio.wait_for(
                    query_bedrock_server(server, port, self.query_timeout),
                    timeout=self.query_timeout + 5
                )
            logger.info(f"[MOTD] 查询完成，结果: {result}")
        except asyncio.TimeoutError:
            logger.error("[MOTD] 查询超时")
            result = {"error": "查询超时，服务器响应时间过长"}
        except Exception as e:
            logger.error(f"[MOTD] 查询异常: {e}")
            result = {"error": f"查询异常: {str(e)}"}

        # 格式化并渲染为图片
        context = self._format_response(result, server_address, is_java=is_java)
        try:
            url = await self.html_render(MOTD_HTML_TEMPLATE, context, options={"full_page": True})
            await event.send(event.image_result(url))
        except Exception as e:
            logger.error(f"[MOTD] 图片渲染失败，回退到纯文本: {e}")
            # 回退：纯文本输出
            if context.get("is_error"):
                text = f"❌ 查询失败\n服务器: {server_address}\n错误: {context.get('error_msg', '未知')}"
            else:
                text = f"🎮 服务器: {server_address}\n版本: {context.get('server_version', '?')}\n玩家: {context.get('online', 0)}/{context.get('max_players', 0)}"
            await event.send(event.plain_result(text))
        logger.info("[MOTD] 查询流程完成")

    async def _do_proxy_query(self, event: AstrMessageEvent, server: str = ""):
        """执行代理服务器查询"""
        logger.info(f"[MOTD] 开始代理查询: method={self.proxy_query_method}, server='{server}'")

        # 确定代理地址（用于显示）
        if not server or server.strip() == "":
            if not self.default_server:
                await event.send(event.plain_result(
                    "❌ 未设置默认服务器\n"
                    "请使用: motd <服务器地址:端口> 查询代理服务器\n"
                    "或联系管理员使用 /motdconfig default <地址:端口> 设置"
                ))
                return
            proxy_host = self.default_server
            proxy_port = self.default_port
        else:
            proxy_host, proxy_port = self._parse_server_address(server.strip(), is_java=True)

        proxy_address = f"{proxy_host}:{proxy_port}"

        # 发送查询中提示
        await event.send(event.plain_result(f"🔍 正在查询代理服务器 {proxy_address} 及其子服..."))

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

        # 构建模板上下文
        context = self._build_proxy_context(proxy_result, proxy_address, sub_servers_data, errors)

        # 渲染并发送
        try:
            url = await self.html_render(PROXY_HTML_TEMPLATE, context, options={"full_page": True})
            await event.send(event.image_result(url))
        except Exception as e:
            logger.error(f"[MOTD] 代理查询图片渲染失败: {e}")
            # 回退到纯文本
            text = self._build_proxy_text_response(context, proxy_address)
            await event.send(event.plain_result(text))

        logger.info("[MOTD] 代理查询流程完成")

    def _build_proxy_context(self, proxy_result: Dict, proxy_address: str,
                             sub_servers: Dict, errors: list) -> Dict[str, Any]:
        """构建代理查询模板上下文"""
        # 处理代理服务器信息
        if "error" in proxy_result:
            proxy_info = {
                "is_error": True,
                "address": proxy_address,
                "error_msg": proxy_result["error"]
            }
        else:
            version_info = proxy_result.get("version", {})
            players_info = proxy_result.get("players", {})
            description = proxy_result.get("description", "无描述")
            server_version, client_version, via_hint = self._parse_version(version_info)

            proxy_info = {
                "is_error": False,
                "address": proxy_address,
                "server_version": server_version,
                "client_version": client_version,
                "via_hint": via_hint,
                "online": players_info.get("online", 0),
                "max_players": players_info.get("max", 0),
                "motd_html": self._motd_to_html(description)
            }

        # 处理子服信息
        sub_servers_list = []
        for name, data in sub_servers.items():
            if "error" in data:
                sub_servers_list.append({
                    "name": name,
                    "is_error": True,
                    "error_msg": data["error"]
                })
            else:
                version_info = data.get("version", {})
                players_info = data.get("players", {})
                description = data.get("description", "无描述")
                server_version, client_version, via_hint = self._parse_version(version_info)

                sub_servers_list.append({
                    "name": name,
                    "is_error": False,
                    "server_version": server_version,
                    "online": players_info.get("online", 0),
                    "max_players": players_info.get("max", 0),
                    "motd_html": self._motd_to_html(description)
                })

        return {
            "proxy": proxy_info,
            "sub_servers": sub_servers_list,
            "errors": errors,
            "has_sub_servers": len(sub_servers_list) > 0
        }

    def _build_proxy_text_response(self, context: Dict, proxy_address: str) -> str:
        """构建代理查询纯文本响应（回退用）"""
        lines = [f"🖥️ 代理服务器: {proxy_address}"]

        proxy = context.get("proxy", {})
        if proxy.get("is_error"):
            lines.append(f"❌ 代理查询失败: {proxy.get('error_msg', '未知')}")
        else:
            lines.append(f"版本: {proxy.get('server_version', '?')}")
            lines.append(f"玩家: {proxy.get('online', 0)}/{proxy.get('max_players', 0)}")

        sub_servers = context.get("sub_servers", [])
        if sub_servers:
            lines.append("\n📡 子服列表:")
            for sub in sub_servers:
                if sub.get("is_error"):
                    lines.append(f"  ❌ {sub['name']}: {sub.get('error_msg', '查询失败')}")
                else:
                    lines.append(f"  ✅ {sub['name']}: {sub.get('online', 0)}/{sub.get('max_players', 0)} ({sub.get('server_version', '?')})")

        errors = context.get("errors", [])
        if errors:
            lines.append("\n⚠️ 错误:")
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
            yield event.plain_result("❌ 只有管理员才能使用此指令")
            return
        
        action = action.lower().strip()
        
        if action == "default":
            if not value:
                yield event.plain_result("❌ 请提供服务器地址\n用法: /motdconfig default <服务器地址:端口>")
                return
            
            server, port = self._parse_server_address(value, is_java=True)
            
            # 验证服务器是否可连接
            yield event.plain_result(f"🔍 正在验证服务器 {server}:{port} ...")
            
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
                yield event.plain_result(
                    f"❌ 无法连接到服务器\n"
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
            
            yield event.plain_result(
                f"✅ 默认服务器设置成功\n"
                f"地址: {server}:{port}\n"
                f"MOTD: {self._format_motd(result.get('description', '无描述'))}"
            )
        
        elif action == "get":
            default = f"{self.default_server}:{self.default_port}" if self.default_server else "未设置"
            sessions = "所有会话" if self.enable_all_sessions else f"{len(self.enabled_sessions)} 个会话"
            
            yield event.plain_result(
                f"📋 MOTD 插件配置\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🖥️ 默认服务器: {default}\n"
                f"💬 生效范围: {sessions}\n"
                f"🔒 仅管理员配置: {'是' if self.admin_only_config else '否'}\n"
                f"⏱️ 查询超时: {self.query_timeout}秒\n"
                f"🌐 使用 API 查询: {'是' if self.use_api else '否'}"
            )
        
        else:
            yield event.plain_result(
                "❓ 未知操作\n"
                "可用操作:\n"
                "  default <地址:端口> - 设置默认服务器\n"
                "  get - 查看当前配置"
            )

    @filter.on_astrbot_loaded()
    async def on_astrbot_loaded(self):
        """Bot 初始化完成时"""
        logger.info("=" * 50)
        logger.info("[MOTD] 插件已加载 v1.6.0")
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
        logger.info("=" * 50)
