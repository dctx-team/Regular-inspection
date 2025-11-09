"""
会话缓存模块 - 保存和恢复认证会话
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from utils.logger import setup_logger

logger = setup_logger(__name__)


class SessionCache:
    """会话缓存管理器"""

    def __init__(self, cache_dir: str = ".cache/sessions"):
        """初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录路径
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_file_path(self, account_name: str, provider: str) -> Path:
        """获取缓存文件路径
        
        Args:
            account_name: 账号名称
            provider: 提供商名称
            
        Returns:
            缓存文件路径
        """
        safe_filename = f"{provider}_{account_name}.json"
        return self.cache_dir / safe_filename

    def save(
        self,
        account_name: str,
        provider: str,
        cookies: List[Dict],
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        expiry_hours: int = 24
    ) -> bool:
        """保存会话数据
        
        Args:
            account_name: 账号名称
            provider: 提供商名称
            cookies: cookies列表
            user_id: 用户ID
            username: 用户名
            expiry_hours: 过期时间（小时）
            
        Returns:
            是否保存成功
        """
        try:
            cache_file = self._get_cache_file_path(account_name, provider)
            
            cache_data = {
                "account_name": account_name,
                "provider": provider,
                "cookies": cookies,
                "user_id": user_id,
                "username": username,
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(hours=expiry_hours)).isoformat()
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ 会话缓存已保存: {account_name} ({provider})")
            return True
            
        except Exception as e:
            logger.error(f"❌ 保存会话缓存失败: {e}")
            return False

    def load(self, account_name: str, provider: str) -> Optional[Dict]:
        """加载会话数据
        
        Args:
            account_name: 账号名称
            provider: 提供商名称
            
        Returns:
            会话数据字典，如果不存在或已过期则返回None
        """
        try:
            cache_file = self._get_cache_file_path(account_name, provider)
            
            if not cache_file.exists():
                logger.info(f"ℹ️ 未找到会话缓存: {account_name} ({provider})")
                return None
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 检查是否过期
            expires_at = datetime.fromisoformat(cache_data["expires_at"])
            if datetime.now() > expires_at:
                logger.info(f"⚠️ 会话缓存已过期: {account_name} ({provider})")
                self.delete(account_name, provider)
                return None
            
            logger.info(f"✅ 会话缓存加载成功: {account_name} ({provider})")
            return cache_data
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ 缓存文件JSON格式错误: {e}")
            self.delete(account_name, provider)
            return None
        except Exception as e:
            logger.error(f"❌ 加载会话缓存失败: {e}")
            return None

    def delete(self, account_name: str, provider: str) -> bool:
        """删除会话缓存
        
        Args:
            account_name: 账号名称
            provider: 提供商名称
            
        Returns:
            是否删除成功
        """
        try:
            cache_file = self._get_cache_file_path(account_name, provider)
            
            if cache_file.exists():
                cache_file.unlink()
                logger.info(f"🗑️ 会话缓存已删除: {account_name} ({provider})")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ 删除会话缓存失败: {e}")
            return False

    def clear_all(self) -> int:
        """清空所有缓存
        
        Returns:
            删除的缓存文件数量
        """
        try:
            count = 0
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
                count += 1
            
            logger.info(f"🗑️ 已清空所有缓存，共删除 {count} 个文件")
            return count
            
        except Exception as e:
            logger.error(f"❌ 清空缓存失败: {e}")
            return 0

    def cleanup_expired(self) -> int:
        """清理已过期的缓存
        
        Returns:
            删除的缓存文件数量
        """
        try:
            count = 0
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    
                    expires_at = datetime.fromisoformat(cache_data["expires_at"])
                    if datetime.now() > expires_at:
                        cache_file.unlink()
                        count += 1
                        logger.info(f"🗑️ 已删除过期缓存: {cache_file.name}")
                        
                except Exception:
                    # 如果读取失败，也删除该缓存文件
                    cache_file.unlink()
                    count += 1
            
            if count > 0:
                logger.info(f"🗑️ 已清理 {count} 个过期缓存")
            
            return count
            
        except Exception as e:
            logger.error(f"❌ 清理过期缓存失败: {e}")
            return 0

