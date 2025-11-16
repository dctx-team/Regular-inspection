"""
CI 环境配置和辅助函数
"""
import os
from typing import List

class CIConfig:
    """CI 环境配置"""
    
    @staticmethod
    def is_ci_environment() -> bool:
        """检测是否在 CI 环境中"""
        return (
            os.getenv("CI", "false").lower() == "true" or
            os.getenv("GITHUB_ACTIONS", "false").lower() == "true" or
            os.getenv("GITLAB_CI", "false").lower() == "true" or
            os.getenv("CIRCLECI", "false").lower() == "true"
        )
    
    @staticmethod
    def get_disabled_auth_methods() -> List[str]:
        """获取在 CI 环境中禁用的认证方式
        
        可通过环境变量 CI_DISABLED_AUTH_METHODS 配置，多个方法用逗号分隔
        例如：CI_DISABLED_AUTH_METHODS="linux.do,github"
        """
        disabled = os.getenv("CI_DISABLED_AUTH_METHODS", "")
        if disabled:
            return [method.strip().lower() for method in disabled.split(",")]
        return []
    
    @staticmethod
    def should_skip_auth_method(auth_method: str) -> bool:
        """判断是否应该跳过某个认证方式
        
        Args:
            auth_method: 认证方式名称（如 "linux.do", "github", "email"）
        
        Returns:
            bool: 是否应该跳过
        """
        if not CIConfig.is_ci_environment():
            return False
        
        disabled_methods = CIConfig.get_disabled_auth_methods()
        return auth_method.lower() in disabled_methods
    
    @staticmethod
    def get_ci_timeout_multiplier() -> float:
        """获取 CI 环境的超时时间倍数
        
        可通过环境变量 CI_TIMEOUT_MULTIPLIER 配置
        默认为 2.0（超时时间翻倍）
        """
        try:
            multiplier = float(os.getenv("CI_TIMEOUT_MULTIPLIER", "2.0"))
            return max(1.0, multiplier)  # 至少为 1.0
        except ValueError:
            return 2.0
    
    @staticmethod
    def should_use_extended_wait() -> bool:
        """是否在 CI 环境中使用延长的等待时间"""
        return CIConfig.is_ci_environment() and os.getenv("CI_EXTENDED_WAIT", "true").lower() == "true"
    
    @staticmethod
    def get_retry_count() -> int:
        """获取 CI 环境的重试次数

        可通过环境变量 CI_RETRY_COUNT 配置
        默认为 3
        """
        try:
            return int(os.getenv("CI_RETRY_COUNT", "3"))
        except ValueError:
            return 3

    @staticmethod
    def should_enable_behavior_simulation() -> bool:
        """判断是否在 CI 环境中启用人类行为模拟

        人类行为模拟包括：
        - 鼠标移动
        - 页面滚动
        - 逐字符打字
        - 自然的点击行为

        可通过环境变量 CI_ENABLE_BEHAVIOR_SIMULATION 配置
        默认在 CI 环境下启用（true）

        Returns:
            bool: 是否启用行为模拟
        """
        if not CIConfig.is_ci_environment():
            return False

        # 默认在 CI 环境下启用行为模拟
        return os.getenv("CI_ENABLE_BEHAVIOR_SIMULATION", "true").lower() == "true"

    @staticmethod
    def get_behavior_simulation_intensity() -> str:
        """获取行为模拟的强度级别

        可通过环境变量 CI_BEHAVIOR_INTENSITY 配置
        可选值：
        - "light": 轻度模拟（仅基本行为）
        - "medium": 中度模拟（默认）
        - "heavy": 重度模拟（更多行为，更长延迟）

        Returns:
            str: 强度级别
        """
        intensity = os.getenv("CI_BEHAVIOR_INTENSITY", "medium").lower()
        if intensity not in ["light", "medium", "heavy"]:
            return "medium"
        return intensity

