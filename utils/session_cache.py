"""
会话缓存模块 - 保存和恢复认证会话（支持加密）
"""

import json
import os
import base64
from pathlib import Path
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
from cryptography.fernet import Fernet, InvalidToken
from utils.logger import setup_logger

logger = setup_logger(__name__)


class SessionCache:
    """会话缓存管理器（支持敏感数据加密）"""

    def __init__(self, cache_dir: str = ".cache/sessions"):
        """初始化缓存管理器

        Args:
            cache_dir: 缓存目录路径
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 尝试加载加密密钥
        self.encryption_key = os.getenv("SESSION_CACHE_KEY")
        self.cipher = None

        if self.encryption_key:
            try:
                # 密钥强度检查
                if len(self.encryption_key) < 16:
                    logger.warning(
                        f"⚠️ SESSION_CACHE_KEY 长度不足（当前 {len(self.encryption_key)} 字符，建议至少 16 字符）"
                    )

                # 密钥熵检查（过低的唯一字符数意味着弱密钥）
                unique_chars = len(set(self.encryption_key))
                if unique_chars < 4:
                    logger.warning(
                        f"⚠️ SESSION_CACHE_KEY 熵值过低（仅 {unique_chars} 种不同字符），建议使用更复杂的密钥"
                    )

                # 确保密钥是有效的 Fernet 密钥（44字符 base64 编码）
                if len(self.encryption_key) == 44 and self.encryption_key.endswith("="):
                    # 已经是 Fernet 格式的密钥
                    self.cipher = Fernet(self.encryption_key.encode())
                    logger.info("✅ 会话缓存加密已启用（Fernet AES-128）")
                else:
                    # 从旧的密钥生成 Fernet 密钥（向后兼容）
                    logger.warning("⚠️ 检测到旧格式密钥，正在转换为 Fernet 格式...")
                    # 使用 SHA256 哈希生成固定长度的密钥，然后转为 Fernet 格式
                    import hashlib

                    key_hash = hashlib.sha256(self.encryption_key.encode()).digest()
                    fernet_key = base64.urlsafe_b64encode(key_hash)
                    self.cipher = Fernet(fernet_key)
                    logger.info("✅ 会话缓存加密已启用（Fernet AES-128，已转换旧密钥）")
            except Exception as e:
                logger.error(f"❌ 初始化加密失败: {e}")
                logger.warning("⚠️ 将使用 Base64 编码（不加密）")
                self.cipher = None
        else:
            logger.warning(
                "⚠️ SESSION_CACHE_KEY 未设置，会话数据将使用Base64编码（建议设置环境变量启用加密）"
            )
            logger.info("💡 提示：运行以下命令生成 Fernet 密钥：")
            logger.info(
                '   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )

    def _encrypt_data(self, data: str) -> str:
        """加密敏感数据（使用 Fernet AES-128）

        Args:
            data: 原始数据

        Returns:
            加密后的数据（Base64编码）
        """
        try:
            if self.cipher:
                # 使用 Fernet (AES-128) 加密
                encrypted = self.cipher.encrypt(data.encode("utf-8"))
                return encrypted.decode("utf-8")
            else:
                # 仅使用Base64编码（不是真正的加密，但至少不是明文）
                return base64.b64encode(data.encode("utf-8")).decode("utf-8")
        except Exception as e:
            logger.error(f"❌ 数据加密失败: {e}")
            raise

    def _decrypt_data(self, encrypted_data: str) -> str:
        """解密敏感数据（支持 Fernet 和旧 XOR 格式）

        Args:
            encrypted_data: 加密的数据

        Returns:
            解密后的原始数据
        """
        try:
            if self.cipher:
                try:
                    # 尝试使用 Fernet 解密
                    decrypted = self.cipher.decrypt(encrypted_data.encode("utf-8"))
                    return decrypted.decode("utf-8")
                except InvalidToken:
                    # Fernet 解密失败，尝试旧的 XOR 格式（向后兼容）
                    logger.debug("🔄 Fernet 解密失败，尝试 XOR 格式...")
                    return self._decrypt_data_xor(encrypted_data)
            else:
                # 仅Base64解码
                decoded = base64.b64decode(encrypted_data.encode("utf-8"))
                return decoded.decode("utf-8")
        except Exception as e:
            logger.error(f"❌ 数据解密失败: {e}")
            raise

    def _decrypt_data_xor(self, encrypted_data: str) -> str:
        """解密旧的 XOR 加密数据（向后兼容）

        Args:
            encrypted_data: XOR 加密的数据

        Returns:
            解密后的原始数据
        """
        try:
            if not self.encryption_key:
                raise ValueError("No encryption key for XOR decryption")

            decoded = base64.b64decode(encrypted_data.encode("utf-8"))
            key_bytes = self.encryption_key.encode("utf-8")

            # XOR解密
            decrypted = bytearray(len(decoded))
            for i in range(len(decoded)):
                decrypted[i] = decoded[i] ^ key_bytes[i % len(key_bytes)]

            result = decrypted.decode("utf-8")
            logger.info(
                "✅ 成功使用 XOR 解密旧格式数据（建议重新登录以使用 Fernet 加密）"
            )
            return result
        except Exception as e:
            logger.error(f"❌ XOR 解密失败: {e}")
            raise

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
        expiry_hours: int = 24,
    ) -> bool:
        """保存会话数据（敏感数据使用 Fernet AES-128 加密）

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

            # 将敏感数据序列化并加密
            sensitive_data = {"cookies": cookies, "user_id": user_id}
            encrypted_data = self._encrypt_data(
                json.dumps(sensitive_data, ensure_ascii=False)
            )

            cache_data = {
                "account_name": account_name,
                "provider": provider,
                "encrypted_data": encrypted_data,  # 加密的敏感数据
                "username": username,  # 用户名可以不加密（用于日志显示）
                "created_at": datetime.now().isoformat(),
                "expires_at": (
                    datetime.now() + timedelta(hours=expiry_hours)
                ).isoformat(),
            }

            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)

            encryption_method = "Fernet AES-128" if self.cipher else "Base64"
            logger.info(
                f"✅ 会话缓存已保存（{encryption_method} 加密）: {account_name} ({provider})"
            )
            return True

        except Exception as e:
            logger.error(f"❌ 保存会话缓存失败: {e}")
            return False

    def load(self, account_name: str, provider: str) -> Optional[Dict[str, Any]]:
        """加载会话数据（自动解密）

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

            with open(cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)

            # 检查是否过期
            expires_at = datetime.fromisoformat(cache_data["expires_at"])
            if datetime.now() > expires_at:
                logger.info(f"⚠️ 会话缓存已过期: {account_name} ({provider})")
                self.delete(account_name, provider)
                return None

            # 解密敏感数据
            if "encrypted_data" in cache_data:
                # 新格式：使用加密
                encrypted_data = cache_data["encrypted_data"]
                decrypted_json = self._decrypt_data(encrypted_data)
                sensitive_data = json.loads(decrypted_json)

                # 合并解密的数据
                cache_data["cookies"] = sensitive_data.get("cookies", [])
                cache_data["user_id"] = sensitive_data.get("user_id")
                logger.info(
                    f"✅ 会话缓存加载成功（已解密）: {account_name} ({provider})"
                )
            else:
                # 旧格式：明文存储（向后兼容）
                logger.warning(
                    f"⚠️ 加载旧格式会话缓存（明文）: {account_name} ({provider})"
                )
                logger.info(f"💡 建议重新登录以使用加密缓存")

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
                    with open(cache_file, "r", encoding="utf-8") as f:
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

    def check_cache_permissions(self) -> bool:
        """检查缓存目录和文件权限是否安全

        确保缓存文件不会被其他用户读取（仅在非 Windows 系统上检查）。

        Returns:
            bool: 权限是否安全
        """
        import platform

        if platform.system() == "Windows":
            # Windows 使用不同的权限模型，跳过检查
            return True

        try:
            import stat

            dir_stat = self.cache_dir.stat()
            dir_mode = dir_stat.st_mode

            # 检查目录是否对其他用户可读
            if dir_mode & stat.S_IROTH or dir_mode & stat.S_IWOTH:
                logger.warning(
                    f"⚠️ 缓存目录 {self.cache_dir} 对其他用户可访问，建议执行: "
                    f"chmod 700 {self.cache_dir}"
                )
                return False

            # 检查每个缓存文件的权限
            for cache_file in self.cache_dir.glob("*.json"):
                file_stat = cache_file.stat()
                file_mode = file_stat.st_mode
                if file_mode & stat.S_IROTH or file_mode & stat.S_IWOTH:
                    logger.warning(
                        f"⚠️ 缓存文件 {cache_file.name} 对其他用户可访问，建议执行: "
                        f"chmod 600 {cache_file}"
                    )
                    return False

            return True
        except Exception as e:
            logger.debug(f"⚠️ 权限检查失败: {e}")
            return True  # 检查失败时不阻塞流程
