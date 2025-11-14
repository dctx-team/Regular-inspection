"""
全局常量定义
"""

# ==================== User-Agent ====================
# 使用最新真实的Chrome稳定版本号（2024年12月最新版）
# 注意：定期更新以避免被识别为过时浏览器
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

# 浏览器User-Agent（与DEFAULT_USER_AGENT保持一致）
BROWSER_USER_AGENT = DEFAULT_USER_AGENT


# ==================== Cookie管理 ====================
# 关键Cookie名称列表（用于识别认证Cookie）
KEY_COOKIE_NAMES = [
    "session",
    "sessionid",
    "token",
    "auth",
    "jwt",
    "user_id",
    "csrf_token",
]

# WAF相关Cookie名称
WAF_COOKIE_NAMES = [
    "acw_tc",
    "cdn_sec_tc",
    "acw_sc__v2",
]


# ==================== HTTP请求配置 ====================
# HTTP请求超时时间（秒）
HTTP_TIMEOUT = 30.0

# 浏览器操作超时时间（毫秒）
BROWSER_PAGE_LOAD_TIMEOUT = 20000  # 20秒
BROWSER_NETWORK_IDLE_TIMEOUT = 10000  # 10秒
BROWSER_ELEMENT_WAIT_TIMEOUT = 5000  # 5秒


# ==================== 超时配置类 ====================
class TimeoutConfig:
    """统一的超时时间配置（毫秒）"""

    # ===== 短等待（1-3秒） =====
    VERY_SHORT_WAIT = 300       # 300ms - 关闭弹窗等快速操作
    SHORT_WAIT = 1000           # 1秒 - 按钮点击后等待
    SHORT_WAIT_2 = 2000         # 2秒 - 页面元素加载
    SHORT_WAIT_3 = 3000         # 3秒 - 页面内容加载

    # ===== 中等待（5-10秒） =====
    MEDIUM_WAIT = 5000          # 5秒 - OAuth回调等待
    MEDIUM_WAIT_10 = 10000      # 10秒 - 会话cookies设置

    # ===== 长等待（15-30秒） =====
    LONG_WAIT_15 = 15000        # 15秒 - CI环境Cloudflare等待
    LONG_WAIT_20 = 20000        # 20秒 - 页面加载超时
    LONG_WAIT_25 = 25000        # 25秒 - 登录验证等待
    LONG_WAIT_30 = 30000        # 30秒 - OAuth流程超时

    # ===== 超长等待（45-120秒） =====
    EXTRA_LONG_45 = 45000       # 45秒 - 授权按钮等待
    EXTRA_LONG_60 = 60000       # 60秒 - Cloudflare验证基础时间
    EXTRA_LONG_90 = 90000       # 90秒 - 重试等待
    EXTRA_LONG_120 = 120000     # 120秒 - 验证挑战超时

    # ===== 重试等待间隔（毫秒） =====
    RETRY_WAIT_SHORT = 1500     # 1.5秒 - Cloudflare检查间隔
    RETRY_WAIT_MEDIUM = 3000    # 3秒 - 长时间检查间隔
    RETRY_WAIT_LONG = 5000      # 5秒 - 分段检测间隔
    RETRY_WAIT_10S = 10000      # 10秒 - OAuth参数获取重试
    RETRY_WAIT_20S = 20000      # 20秒 - 重试策略等待

    # ===== 特殊场景超时 =====
    CLOUDFLARE_CHECK = 60000    # 60秒 - Cloudflare验证检测
    PAGE_LOAD = 45000           # 45秒 - goto页面加载
    NETWORK_IDLE = 10000        # 10秒 - 网络空闲等待
    ELEMENT_WAIT = 5000         # 5秒 - 元素等待

    @classmethod
    def get_ci_adjusted(cls, base_timeout: int, multiplier: float = 2.0) -> int:
        """
        获取CI环境调整后的超时时间

        Args:
            base_timeout: 基础超时时间（毫秒）
            multiplier: CI环境倍增器（默认2.0）

        Returns:
            int: 调整后的超时时间（毫秒）
        """
        from utils.ci_config import CIConfig
        if CIConfig.is_ci_environment():
            return int(base_timeout * multiplier)
        return base_timeout


# ==================== 重试配置 ====================
# 异步重试装饰器默认配置
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 2  # 秒
DEFAULT_RETRY_BACKOFF = 2  # 指数退避倍数

# 速率限制保护延迟（秒）
RATE_LIMIT_DELAY_MIN = 1  # 最小延迟
RATE_LIMIT_DELAY_MAX = 3  # 最大延迟


# ==================== 余额转换 ====================
# 余额单位转换率（内部单位 -> 美元）
QUOTA_TO_DOLLAR_RATE = 500000


# ==================== 浏览器配置 ====================
# Playwright浏览器参数
# 注意：已移除 --disable-web-security 以确保安全性
BROWSER_LAUNCH_ARGS = [
    # ===== 核心反检测参数 =====
    "--disable-blink-features=AutomationControlled",  # 最关键！隐藏自动化控制特征
    "--exclude-switches=enable-automation",  # 移除自动化标识

    # ===== 基础环境配置 =====
    "--no-sandbox",  # Docker/CI 环境需要
    "--disable-setuid-sandbox",  # Docker/CI 环境需要
    "--disable-dev-shm-usage",  # 避免共享内存问题

    # ===== 性能优化 =====
    "--disable-gpu",  # 无头模式不需要 GPU
    "--disable-software-rasterizer",  # 禁用软件光栅化
    "--disable-extensions",  # 禁用扩展以提高性能

    # ===== 伪装真实浏览器行为 =====
    "--window-size=1920,1080",  # 固定窗口大小
    "--start-maximized",  # 最大化窗口
    "--disable-infobars",  # 隐藏信息栏
    "--disable-notifications",  # 禁用通知

    # ===== 网络与后台优化 =====
    "--disable-background-networking",  # 禁用后台网络活动
    "--disable-background-timer-throttling",  # 禁用后台定时器节流
    "--disable-backgrounding-occluded-windows",  # 禁用被遮挡窗口的后台处理
    "--disable-renderer-backgrounding",  # 禁用渲染器后台处理

    # ===== 功能禁用（减少检测特征） =====
    "--disable-breakpad",  # 禁用崩溃报告
    "--disable-component-extensions-with-background-pages",  # 禁用带后台页面的组件扩展
    "--disable-features=TranslateUI,BlinkGenPropertyTrees",  # 禁用翻译UI等功能
    "--disable-ipc-flooding-protection",  # 禁用IPC洪水保护
    "--disable-hang-monitor",  # 禁用挂起监控
    "--disable-client-side-phishing-detection",  # 禁用钓鱼检测
    "--disable-component-update",  # 禁用组件更新
    "--disable-default-apps",  # 禁用默认应用
    "--disable-popup-blocking",  # 禁用弹窗阻止
    "--disable-prompt-on-repost",  # 禁用重新提交提示
    "--disable-sync",  # 禁用同步

    # ===== 视觉与显示 =====
    "--force-color-profile=srgb",  # 强制使用sRGB颜色配置
    "--hide-scrollbars",  # 隐藏滚动条

    # ===== 其他优化 =====
    "--metrics-recording-only",  # 仅记录指标
    "--mute-audio",  # 静音
    "--no-first-run",  # 跳过首次运行欢迎页
    "--password-store=basic",  # 使用基本密码存储
    "--use-mock-keychain",  # 使用模拟钥匙串
    "--safebrowsing-disable-auto-update",  # 禁用安全浏览自动更新

    # ===== 网络服务 =====
    "--enable-features=NetworkService,NetworkServiceInProcess",  # 启用网络服务
]

# 浏览器视口大小
BROWSER_VIEWPORT = {
    "width": 1920,
    "height": 1080,
}


# ==================== 认证选择器 ====================
# 邮箱输入框选择器列表
EMAIL_INPUT_SELECTORS = [
    'input[type="email"]',
    'input[name="email"]',
    'input[name="username"]',
    'input[name="account"]',
    'input[id*="email" i]',
    'input[placeholder*="邮箱" i]',
    'input[placeholder*="Email" i]',
    'input[placeholder*="用户名" i]',
    'input[autocomplete="username"]',
]

# 密码输入框选择器
PASSWORD_INPUT_SELECTORS = [
    'input[type="password"]',
    'input[name="password"]',
    'input[autocomplete="current-password"]',
]

# 登录按钮选择器列表
LOGIN_BUTTON_SELECTORS = [
    'button[type="submit"]',
    'button:has-text("登录")',
    'button:has-text("Login")',
    'button:has-text("Sign in")',
    'button:has-text("Sign In")',
    'button.semi-button:has-text("登录")',
]

# 弹窗关闭按钮选择器
POPUP_CLOSE_SELECTORS = [
    '.semi-modal .semi-modal-close',
    '[aria-label="Close"]',
    'button:has-text("关闭")',
    'button:has-text("我知道了")',
    'button:has-text("取消")',
]


# ==================== OAuth配置 ====================
# GitHub登录按钮选择器
GITHUB_BUTTON_SELECTORS = [
    'button:has-text("GitHub")',
    'a:has-text("GitHub")',
    'text=使用 GitHub',
    'a[href*="github.com"]',
]

# Linux.do登录按钮选择器
LINUXDO_BUTTON_SELECTORS = [
    # 精确匹配
    'button:has-text("LinuxDO")',
    'a:has-text("LinuxDO")',
    'button:has-text("Linux.do")',
    'button:has-text("LinuxDO 登录")',
    'a:has-text("使用 LinuxDO")',
    'text=使用 LinuxDO',
    'button:has-text("LinuxDO 账号登录")',
    # 模糊匹配
    'button:has-text("Linux")',
    'a:has-text("Linux")',
    # 链接匹配
    'a[href*="linux.do"]',
    'a[href*="linuxdo"]',
    '[data-provider*="linux"]',
    # 通配符匹配（处理各种变体）
    'button:text-is("LinuxDO")',
    'a:text-is("LinuxDO")',
    # 图标+文本组合
    'button:has(svg) >> :has-text("Linux")',
    'a:has(svg) >> :has-text("Linux")',
    # class或id包含linux关键词
    'button[class*="linux" i]',
    'a[class*="linux" i]',
    'button[id*="linux" i]',
    'a[id*="linux" i]',
]
