#!/usr/bin/env python3
"""
订阅解析模块 - 支持多种代理订阅格式
支持 Clash、V2Ray、通用订阅等格式
"""

import asyncio
import base64
import json
import random
import time
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse, parse_qs, unquote
import re

import httpx
import yaml

from utils.logger import setup_logger

logger = setup_logger(__name__)


class ProxyNode:
    """代理节点数据类"""

    def __init__(
        self,
        name: str,
        type: str,
        server: str,
        port: int,
        username: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs
    ):
        self.name = name
        self.type = type.lower()  # http, https, socks5
        self.server = server
        self.port = port
        self.username = username
        self.password = password
        self.extra = kwargs
        self.latency = None  # 延迟（毫秒）
        self.last_test_time = None  # 最后测试时间

    def to_playwright_proxy(self) -> Dict[str, str]:
        """转换为 Playwright 代理格式"""
        proxy_url = f"{self.type}://{self.server}:{self.port}"

        proxy_config = {"server": proxy_url}

        if self.username and self.password:
            proxy_config["username"] = self.username
            proxy_config["password"] = self.password

        return proxy_config

    def __repr__(self):
        latency_str = f"{self.latency}ms" if self.latency else "未测速"
        return f"<ProxyNode {self.name} [{self.type}] {self.server}:{self.port} {latency_str}>"


class SubscriptionParser:
    """订阅解析器 - 支持多种格式"""

    def __init__(self):
        self.timeout = 10  # HTTP请求超时

    async def fetch_subscription(self, url: str) -> str:
        """获取订阅内容"""
        try:
            logger.info(f"📡 正在获取订阅: {url[:50]}...")

            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()

            content = response.text
            logger.info(f"✅ 订阅获取成功，内容长度: {len(content)} 字符")
            return content

        except Exception as e:
            logger.error(f"❌ 获取订阅失败: {e}")
            raise

    async def parse(self, subscription_url: str) -> List[ProxyNode]:
        """
        解析订阅链接，自动识别格式

        Returns:
            List[ProxyNode]: 解析出的代理节点列表（仅HTTP/SOCKS5）
        """
        content = await self.fetch_subscription(subscription_url)

        # 添加诊断日志：显示订阅内容前200字符
        logger.debug(f"📄 订阅内容预览: {content[:200]}")

        # 尝试不同的解析方法
        parsers = [
            ("Clash YAML", self._parse_clash),
            ("V2Ray Base64", self._parse_v2ray_base64),
            ("SIP002 URI", self._parse_sip002_uri),
        ]

        for parser_name, parser_func in parsers:
            try:
                nodes = parser_func(content)
                if nodes:
                    logger.info(f"✅ 使用 {parser_name} 格式解析成功，找到 {len(nodes)} 个可用节点")
                    return nodes
                else:
                    logger.warning(f"⚠️ {parser_name} 解析成功但未找到HTTP/SOCKS5节点")
            except Exception as e:
                logger.warning(f"⚠️ {parser_name} 解析失败: {e}")
                continue

        logger.warning("⚠️ 所有解析方法均失败，返回空列表")
        return []

    def _parse_clash(self, content: str) -> List[ProxyNode]:
        """解析 Clash YAML 格式"""
        try:
            config = yaml.safe_load(content)

            if not config:
                logger.warning("❌ YAML解析结果为空")
                return []

            if "proxies" not in config:
                logger.warning(f"❌ YAML中没有proxies字段，实际字段: {list(config.keys())[:10]}")
                return []

            total_proxies = len(config["proxies"])
            logger.info(f"📊 订阅解析成功，找到 {total_proxies} 个代理节点")

            nodes = []
            type_counts = {}
            for proxy in config["proxies"]:
                # 统计节点类型
                proxy_type = proxy.get("type", "").lower()
                type_counts[proxy_type] = type_counts.get(proxy_type, 0) + 1

                # 只提取 HTTP 和 SOCKS5 节点
                if proxy_type in ["http", "https", "socks5"]:
                    node = ProxyNode(
                        name=proxy.get("name", "Unknown"),
                        type=proxy_type,
                        server=proxy.get("server"),
                        port=proxy.get("port"),
                        username=proxy.get("username"),
                        password=proxy.get("password"),
                        tls=proxy.get("tls", False),
                        skip_cert_verify=proxy.get("skip-cert-verify", False)
                    )
                    nodes.append(node)
                    logger.debug(f"  ✅ 解析节点: {node.name} ({node.type})")

            # 显示节点类型统计（使用 WARNING 级别以便在日志中可见）
            logger.warning(f"📊 节点类型分布: {type_counts}")

            if not nodes:
                unsupported_types = ', '.join(type_counts.keys())
                logger.error(f"❌ 订阅中没有 HTTP/SOCKS5 类型节点")
                logger.error(f"📋 实际节点类型: {unsupported_types}")
                logger.error(f"💡 Playwright 仅支持 HTTP/HTTPS/SOCKS5 代理")
                logger.error(f"💡 建议：")
                logger.error(f"   1. 使用本地 Clash/V2Ray 提供 HTTP 混合端口")
                logger.error(f"   2. 或使用 PROXY_SERVER 环境变量配置本地代理")
                logger.error(f"   3. 或禁用代理功能（删除 USE_PROXY 环境变量）")

            return nodes

        except yaml.YAMLError as e:
            logger.warning(f"❌ YAML 解析失败: {e}")
            return []

    def _parse_v2ray_base64(self, content: str) -> List[ProxyNode]:
        """解析 V2Ray Base64 格式（通用订阅）"""
        try:
            # 尝试 Base64 解码
            decoded = base64.b64decode(content).decode('utf-8')
            lines = decoded.strip().split('\n')

            nodes = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # 尝试解析各种 URI 格式
                node = self._parse_single_uri(line)
                if node:
                    nodes.append(node)

            return nodes

        except Exception as e:
            logger.debug(f"V2Ray Base64 解析失败: {e}")
            return []

    def _parse_sip002_uri(self, content: str) -> List[ProxyNode]:
        """解析 SIP002 URI 格式（单行或多行）"""
        lines = content.strip().split('\n')
        nodes = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            node = self._parse_single_uri(line)
            if node:
                nodes.append(node)

        return nodes

    def _parse_single_uri(self, uri: str) -> Optional[ProxyNode]:
        """
        解析单个代理 URI
        支持格式：
        - http://user:pass@host:port
        - https://user:pass@host:port
        - socks5://user:pass@host:port
        """
        try:
            # 匹配 HTTP/HTTPS/SOCKS5 URI
            if not any(uri.startswith(prefix) for prefix in ["http://", "https://", "socks5://"]):
                return None

            parsed = urlparse(uri)

            # 提取节点名称（从 fragment 或生成默认名称）
            name = unquote(parsed.fragment) if parsed.fragment else f"{parsed.hostname}:{parsed.port}"

            node = ProxyNode(
                name=name,
                type=parsed.scheme,
                server=parsed.hostname,
                port=parsed.port,
                username=unquote(parsed.username) if parsed.username else None,
                password=unquote(parsed.password) if parsed.password else None,
            )

            logger.debug(f"  ✅ 解析 URI: {node.name}")
            return node

        except Exception as e:
            logger.debug(f"URI 解析失败 ({uri[:50]}...): {e}")
            return None


class NodeSpeedTester:
    """节点测速器"""

    def __init__(self, test_url: str = "http://www.gstatic.com/generate_204", timeout: int = 5):
        """
        Args:
            test_url: 测速使用的URL（建议使用延迟低的测试地址）
            timeout: 单个节点测速超时时间（秒）
        """
        self.test_url = test_url
        self.timeout = timeout

    async def test_node(self, node: ProxyNode) -> bool:
        """
        测试单个节点延迟

        Returns:
            bool: 测试是否成功
        """
        try:
            proxy_config = node.to_playwright_proxy()
            proxy_url = proxy_config["server"]

            # 构建代理认证 URL
            if node.username and node.password:
                parsed = urlparse(proxy_url)
                proxy_url = f"{parsed.scheme}://{node.username}:{node.password}@{parsed.netloc}"

            start_time = time.time()

            async with httpx.AsyncClient(
                proxies={"http://": proxy_url, "https://": proxy_url},
                timeout=self.timeout,
                follow_redirects=True
            ) as client:
                response = await client.get(self.test_url)
                response.raise_for_status()

            latency = int((time.time() - start_time) * 1000)  # 转换为毫秒
            node.latency = latency
            node.last_test_time = time.time()

            logger.debug(f"  ✅ {node.name}: {latency}ms")
            return True

        except asyncio.TimeoutError:
            logger.debug(f"  ⏱️ {node.name}: 超时")
            node.latency = 9999  # 设置一个很大的值表示超时
            return False
        except Exception as e:
            logger.debug(f"  ❌ {node.name}: {str(e)[:50]}")
            node.latency = 9999
            return False

    async def test_all_nodes(self, nodes: List[ProxyNode], max_concurrent: int = 5) -> List[ProxyNode]:
        """
        并发测试所有节点

        Args:
            nodes: 待测试的节点列表
            max_concurrent: 最大并发数

        Returns:
            List[ProxyNode]: 测试完成的节点列表（按延迟排序）
        """
        logger.info(f"🔍 开始测速 {len(nodes)} 个节点（并发数: {max_concurrent}）...")

        semaphore = asyncio.Semaphore(max_concurrent)

        async def test_with_semaphore(node):
            async with semaphore:
                return await self.test_node(node)

        # 并发测试
        await asyncio.gather(*[test_with_semaphore(node) for node in nodes])

        # 按延迟排序（超时的节点排在最后）
        nodes.sort(key=lambda n: n.latency if n.latency else 9999)

        # 统计可用节点
        available_nodes = [n for n in nodes if n.latency and n.latency < 9999]
        logger.info(f"✅ 测速完成，可用节点: {len(available_nodes)}/{len(nodes)}")

        # 显示前5个最快节点
        if available_nodes:
            logger.info("📊 最快的节点：")
            for i, node in enumerate(available_nodes[:5], 1):
                logger.info(f"   {i}. {node.name}: {node.latency}ms")

        return nodes


class NodeSelector:
    """节点选择器 - 支持多种选择策略"""

    # 港澳台地区关键词（优先级地区）
    PREFERRED_REGIONS = [
        # 香港
        r'香港|hong\s*kong|hongkong|\bhk\b',
        # 澳门
        r'澳[门門]|macau|macao|\bmo\b',
        # 台湾
        r'台[湾灣]|taiwan|\btw\b'
    ]

    @staticmethod
    def is_preferred_region(node_name: str) -> bool:
        """
        判断节点是否属于港澳台地区（优先地区）

        Args:
            node_name: 节点名称

        Returns:
            bool: 是否属于港澳台地区
        """
        node_name_lower = node_name.lower()
        for pattern in NodeSelector.PREFERRED_REGIONS:
            if re.search(pattern, node_name_lower):
                return True
        return False

    @staticmethod
    def select_fastest(nodes: List[ProxyNode], top_n: int = 1) -> Optional[ProxyNode]:
        """
        选择最快的节点（优先港澳台地区）

        优先级策略：
        1. 港澳台节点延迟 - 50ms bonus（虚拟降低延迟排序）
        2. 从调整后最快的 top_n 个节点中随机选择

        Args:
            nodes: 节点列表（应该已测速）
            top_n: 从前N个节点中随机选择（增加随机性，避免单点压力）

        Returns:
            ProxyNode or None
        """
        available = [n for n in nodes if n.latency and n.latency < 9999]

        if not available:
            logger.warning("⚠️ 没有可用节点")
            return None

        # 为港澳台节点计算优先级排序分数（延迟 - 50ms bonus）
        def get_sort_score(node: ProxyNode) -> int:
            base_latency = node.latency or 9999
            # 港澳台节点给予50ms的优先级bonus
            if NodeSelector.is_preferred_region(node.name):
                return max(0, base_latency - 50)
            return base_latency

        # 按优先级分数排序
        available_sorted = sorted(available, key=get_sort_score)

        # 统计港澳台节点数量
        preferred_count = sum(1 for n in available_sorted[:top_n] if NodeSelector.is_preferred_region(n.name))
        if preferred_count > 0:
            logger.info(f"🌏 前{top_n}个候选节点中包含 {preferred_count} 个港澳台节点")

        # 从最快的 top_n 个节点中随机选择
        candidates = available_sorted[:min(top_n, len(available_sorted))]
        selected = random.choice(candidates)

        region_tag = "🌏 港澳台" if NodeSelector.is_preferred_region(selected.name) else ""
        logger.info(f"✅ 自动选择节点: {selected.name} ({selected.latency}ms) {region_tag}")
        return selected

    @staticmethod
    def select_by_name(nodes: List[ProxyNode], name_pattern: str) -> Optional[ProxyNode]:
        """
        根据名称模糊匹配选择节点

        Args:
            nodes: 节点列表
            name_pattern: 节点名称匹配模式（支持正则表达式）

        Returns:
            ProxyNode or None
        """
        try:
            pattern = re.compile(name_pattern, re.IGNORECASE)

            for node in nodes:
                if pattern.search(node.name):
                    logger.info(f"✅ 手动选择节点: {node.name}")
                    return node

            logger.warning(f"⚠️ 未找到匹配的节点: {name_pattern}")
            return None

        except re.error as e:
            logger.error(f"❌ 节点名称正则表达式错误: {e}")
            return None

    @staticmethod
    def select_random(nodes: List[ProxyNode], only_available: bool = True) -> Optional[ProxyNode]:
        """
        随机选择节点（港澳台节点权重加倍）

        加权策略：
        - 港澳台节点权重：2.0
        - 其他节点权重：1.0

        Args:
            nodes: 节点列表
            only_available: 仅从可用节点中选择（需要先测速）

        Returns:
            ProxyNode or None
        """
        if only_available:
            available = [n for n in nodes if n.latency and n.latency < 9999]
            if not available:
                logger.warning("⚠️ 没有可用节点，从所有节点中随机选择")
                available = nodes
        else:
            available = nodes

        if not available:
            logger.warning("⚠️ 节点列表为空")
            return None

        # 计算每个节点的权重
        weights = []
        preferred_count = 0
        for node in available:
            if NodeSelector.is_preferred_region(node.name):
                weights.append(2.0)  # 港澳台节点权重加倍
                preferred_count += 1
            else:
                weights.append(1.0)  # 其他节点基础权重

        # 统计信息
        if preferred_count > 0:
            logger.info(f"🌏 候选节点中包含 {preferred_count}/{len(available)} 个港澳台节点（权重2倍）")

        # 使用 random.choices 进行加权随机选择
        selected = random.choices(available, weights=weights, k=1)[0]

        region_tag = "🌏 港澳台" if NodeSelector.is_preferred_region(selected.name) else ""
        logger.info(f"✅ 随机选择节点: {selected.name} {region_tag}")
        return selected


class SubscriptionProxyManager:
    """订阅代理管理器 - 整合解析、测速、选择功能"""

    def __init__(
        self,
        subscription_url: str,
        selection_mode: str = "auto",  # auto, manual, random
        node_name_pattern: Optional[str] = None,
        test_speed: bool = True,
        cache_duration: int = 3600,  # 缓存时长（秒）
    ):
        """
        Args:
            subscription_url: 订阅链接
            selection_mode: 选择模式（auto/manual/random）
            node_name_pattern: 手动模式下的节点名称匹配模式
            test_speed: 是否进行测速
            cache_duration: 节点缓存时长（秒）
        """
        self.subscription_url = subscription_url
        self.selection_mode = selection_mode.lower()
        self.node_name_pattern = node_name_pattern
        self.test_speed = test_speed
        self.cache_duration = cache_duration

        self.parser = SubscriptionParser()
        self.tester = NodeSpeedTester()
        self.selector = NodeSelector()

        self._cached_nodes: List[ProxyNode] = []
        self._cache_time: Optional[float] = None
        self._selected_node: Optional[ProxyNode] = None

    async def get_proxy_config(self) -> Optional[Dict[str, str]]:
        """
        获取代理配置（主入口）

        Returns:
            Dict: Playwright 格式的代理配置
        """
        try:
            # 1. 获取或使用缓存的节点列表
            nodes = await self._get_nodes()

            if not nodes:
                logger.error("❌ 没有可用的代理节点")
                return None

            # 2. 测速（如果启用且未测速）
            if self.test_speed and not any(n.latency for n in nodes):
                nodes = await self.tester.test_all_nodes(nodes)
                self._cached_nodes = nodes  # 更新缓存

            # 3. 根据选择模式选择节点
            if self.selection_mode == "auto":
                self._selected_node = self.selector.select_fastest(nodes, top_n=3)
            elif self.selection_mode == "manual":
                if not self.node_name_pattern:
                    logger.error("❌ 手动模式需要指定 node_name_pattern")
                    return None
                self._selected_node = self.selector.select_by_name(nodes, self.node_name_pattern)
            elif self.selection_mode == "random":
                self._selected_node = self.selector.select_random(nodes, only_available=self.test_speed)
            else:
                logger.error(f"❌ 未知的选择模式: {self.selection_mode}")
                return None

            if not self._selected_node:
                logger.error("❌ 节点选择失败")
                return None

            # 4. 返回 Playwright 格式的代理配置
            proxy_config = self._selected_node.to_playwright_proxy()
            logger.info(f"🌐 使用代理: {self._selected_node.name} - {proxy_config['server']}")

            return proxy_config

        except Exception as e:
            logger.error(f"❌ 获取代理配置失败: {e}")
            return None

    async def _get_nodes(self) -> List[ProxyNode]:
        """获取节点列表（带缓存）"""
        # 检查缓存是否有效
        if self._cached_nodes and self._cache_time:
            if time.time() - self._cache_time < self.cache_duration:
                logger.debug(f"✅ 使用缓存的节点列表（{len(self._cached_nodes)} 个节点）")
                return self._cached_nodes

        # 重新解析订阅
        logger.info("📡 重新解析订阅...")
        nodes = await self.parser.parse(self.subscription_url)

        self._cached_nodes = nodes
        self._cache_time = time.time()

        return nodes

    def get_selected_node_info(self) -> Optional[Dict[str, Any]]:
        """获取当前选中节点的信息"""
        if not self._selected_node:
            return None

        return {
            "name": self._selected_node.name,
            "type": self._selected_node.type,
            "server": self._selected_node.server,
            "port": self._selected_node.port,
            "latency": self._selected_node.latency,
        }
