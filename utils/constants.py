"""
全局常量定义
"""

# ==================== User-Agent ====================
# 使用真实的Chrome稳定版本号（避免被识别为机器人）
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

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


# ==================== 重试配置 ====================
# 异步重试装饰器默认配置
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 2  # 秒
DEFAULT_RETRY_BACKOFF = 2  # 指数退避倍数


# ==================== 余额转换 ====================
# 余额单位转换率（内部单位 -> 美元）
QUOTA_TO_DOLLAR_RATE = 500000


# ==================== 浏览器配置 ====================
# Playwright浏览器参数
BROWSER_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--disable-web-security",
    "--no-sandbox",
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
]
