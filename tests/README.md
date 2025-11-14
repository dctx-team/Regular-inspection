# 测试指南

## 安装测试依赖

```bash
pip install -r requirements.txt
```

测试相关依赖：
- `pytest` - 测试框架
- `pytest-asyncio` - 异步测试支持
- `pytest-cov` - 代码覆盖率
- `pytest-mock` - Mock 支持

## 运行测试

### 运行所有测试
```bash
pytest
```

### 运行单元测试
```bash
pytest tests/unit/
```

### 运行集成测试
```bash
pytest tests/integration/
```

### 运行特定测试文件
```bash
pytest tests/unit/test_config.py
```

### 运行特定测试类或函数
```bash
pytest tests/unit/test_config.py::TestPasswordValidation::test_valid_password_strong
```

### 运行标记的测试
```bash
# 只运行认证测试
pytest -m auth

# 只运行单元测试
pytest -m unit

# 排除慢速测试
pytest -m "not slow"
```

### 查看代码覆盖率
```bash
pytest --cov=utils --cov=checkin --cov-report=html
```

然后打开 `htmlcov/index.html` 查看详细覆盖率报告。

### 详细输出
```bash
# 显示所有输出
pytest -v -s

# 显示失败测试的完整回溯
pytest --tb=long
```

## 测试结构

```
tests/
├── __init__.py          # 测试包初始化
├── conftest.py          # Pytest 配置和共享 fixtures
├── unit/                # 单元测试
│   ├── test_config.py   # 配置模块测试
│   └── test_auth.py     # 认证模块测试
└── integration/         # 集成测试
    └── test_checkin_flow.py  # 签到流程测试
```

## 编写测试

### 单元测试示例

```python
import pytest
from utils.config import validate_password_strength

class TestPasswordValidation:
    def test_valid_password(self):
        is_valid, error = validate_password_strength("MyP@ssw0rd", "test", 0)
        assert is_valid is True
        assert error is None

    @pytest.mark.parametrize("password,expected", [
        ("123456", False),
        ("password123", True),
        ("MyP@ssw0rd!", True),
    ])
    def test_multiple_passwords(self, password, expected):
        is_valid, _ = validate_password_strength(password, "test", 0)
        assert is_valid is expected
```

### 异步测试示例

```python
import pytest
from utils.auth import CookiesAuthenticator

class TestAuth:
    @pytest.mark.asyncio
    async def test_authenticate(self, mock_page, mock_context):
        # 测试异步认证方法
        result = await authenticator.authenticate(mock_page, mock_context)
        assert result["success"] is True
```

### 使用 Fixtures

```python
def test_with_sample_config(sample_account_config):
    # 使用 conftest.py 中定义的 fixture
    assert sample_account_config.name == "Test Account"
```

## CI/CD 集成

在 GitHub Actions 中运行测试：

```yaml
- name: 运行测试
  run: |
    pytest --cov=utils --cov=checkin --cov-report=xml

- name: 上传覆盖率报告
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

## 注意事项

1. **Mock 外部依赖**：测试中应该 mock Playwright、httpx 等外部依赖，避免实际的网络请求和浏览器操作

2. **隔离测试**：每个测试应该独立运行，不依赖其他测试的状态

3. **环境变量**：测试时使用 `monkeypatch` 或 `mock.patch` 修改环境变量

4. **异步测试**：使用 `@pytest.mark.asyncio` 装饰异步测试函数

5. **慢速测试**：将需要长时间运行的测试标记为 `@pytest.mark.slow`

## TODO

当前测试框架仅包含基础示例，需要补充：

- [ ] 完善所有认证器的单元测试
- [ ] 添加代理管理器测试
- [ ] 添加会话缓存测试
- [ ] 完善集成测试
- [ ] 添加端到端测试
- [ ] 提高代码覆盖率至 80%+
