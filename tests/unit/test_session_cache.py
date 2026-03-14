"""
会话缓存模块单元测试
"""
import json
import os
import pytest
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from cryptography.fernet import Fernet

from utils.session_cache import SessionCache


@pytest.fixture
def temp_cache_dir():
    """创建临时缓存目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def fernet_key():
    """生成一个有效的 Fernet 密钥"""
    return Fernet.generate_key().decode()


@pytest.fixture
def cache_with_fernet(temp_cache_dir, fernet_key):
    """使用 Fernet 加密的 SessionCache"""
    with patch.dict(os.environ, {"SESSION_CACHE_KEY": fernet_key}):
        return SessionCache(cache_dir=temp_cache_dir)


@pytest.fixture
def cache_without_key(temp_cache_dir):
    """无加密密钥的 SessionCache（Base64 fallback）"""
    with patch.dict(os.environ, {}, clear=True):
        env = os.environ.copy()
        env.pop("SESSION_CACHE_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            return SessionCache(cache_dir=temp_cache_dir)


class TestEncryptionDecryption:
    """加密/解密测试"""

    def test_fernet_encrypt_decrypt(self, cache_with_fernet):
        """测试 Fernet 加密和解密"""
        original = '{"cookies": [{"name": "session", "value": "abc"}]}'
        encrypted = cache_with_fernet._encrypt_data(original)
        decrypted = cache_with_fernet._decrypt_data(encrypted)

        assert decrypted == original
        assert encrypted != original  # 确保确实加密了

    def test_base64_fallback(self, cache_without_key):
        """测试 Base64 fallback 编码和解码"""
        original = '{"test": "data"}'
        encoded = cache_without_key._encrypt_data(original)
        decoded = cache_without_key._decrypt_data(encoded)

        assert decoded == original


class TestSaveLoadDelete:
    """保存/加载/删除测试"""

    def test_save_and_load(self, cache_with_fernet):
        """测试保存和加载"""
        cookies = [{"name": "session", "value": "test123"}]
        cache_with_fernet.save("test_account", "anyrouter", cookies, user_id="42", username="tester")

        loaded = cache_with_fernet.load("test_account", "anyrouter")
        assert loaded is not None
        assert loaded["account_name"] == "test_account"
        assert loaded["provider"] == "anyrouter"
        assert loaded["cookies"] == cookies
        assert loaded["user_id"] == "42"
        assert loaded["username"] == "tester"

    def test_load_nonexistent(self, cache_with_fernet):
        """测试加载不存在的缓存"""
        result = cache_with_fernet.load("nonexistent", "provider")
        assert result is None

    def test_delete(self, cache_with_fernet):
        """测试删除缓存"""
        cookies = [{"name": "session", "value": "test"}]
        cache_with_fernet.save("to_delete", "provider", cookies)

        assert cache_with_fernet.delete("to_delete", "provider") is True
        assert cache_with_fernet.load("to_delete", "provider") is None

    def test_delete_nonexistent(self, cache_with_fernet):
        """测试删除不存在的缓存"""
        assert cache_with_fernet.delete("nonexistent", "provider") is False


class TestExpiry:
    """过期清理测试"""

    def test_load_expired(self, cache_with_fernet):
        """测试加载过期缓存"""
        cookies = [{"name": "session", "value": "expired"}]
        cache_with_fernet.save("expired_account", "provider", cookies, expiry_hours=0)

        # 手动修改过期时间为过去
        cache_file = cache_with_fernet._get_cache_file_path("expired_account", "provider")
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["expires_at"] = (datetime.now() - timedelta(hours=1)).isoformat()
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        result = cache_with_fernet.load("expired_account", "provider")
        assert result is None

    def test_cleanup_expired(self, cache_with_fernet):
        """测试清理过期缓存"""
        # 保存一个正常缓存和一个过期缓存
        cache_with_fernet.save("fresh", "provider", [{"name": "s", "value": "v"}], expiry_hours=24)
        cache_with_fernet.save("stale", "provider2", [{"name": "s", "value": "v"}], expiry_hours=24)

        # 手动设置过期
        cache_file = cache_with_fernet._get_cache_file_path("stale", "provider2")
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["expires_at"] = (datetime.now() - timedelta(hours=1)).isoformat()
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        deleted = cache_with_fernet.cleanup_expired()
        assert deleted == 1

        # fresh 应该还在
        assert cache_with_fernet.load("fresh", "provider") is not None

    def test_clear_all(self, cache_with_fernet):
        """测试清空所有缓存"""
        cache_with_fernet.save("a1", "p1", [{"name": "s", "value": "v"}])
        cache_with_fernet.save("a2", "p2", [{"name": "s", "value": "v"}])

        count = cache_with_fernet.clear_all()
        assert count == 2
        assert cache_with_fernet.load("a1", "p1") is None
        assert cache_with_fernet.load("a2", "p2") is None


class TestKeyValidation:
    """密钥验证测试"""

    def test_weak_key_warning(self, temp_cache_dir):
        """测试弱密钥警告"""
        with patch.dict(os.environ, {"SESSION_CACHE_KEY": "short"}):
            # 不应崩溃，只是警告
            cache = SessionCache(cache_dir=temp_cache_dir)
            assert cache is not None

    def test_low_entropy_key_warning(self, temp_cache_dir):
        """测试低熵密钥警告"""
        with patch.dict(os.environ, {"SESSION_CACHE_KEY": "aaaaaaaaaaaaaaaa"}):
            cache = SessionCache(cache_dir=temp_cache_dir)
            assert cache is not None
