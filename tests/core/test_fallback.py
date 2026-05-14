"""fallback 模块单元测试。"""

import pytest

from src.multi_agent_system.core.fallback import FallbackRegistry


class TestFallbackRegistryRegister:
    """注册功能测试。"""

    def test_register_single_function(self) -> None:
        """注册单个降级函数。"""
        registry = FallbackRegistry()
        fn = lambda: "result"  # noqa: E731
        registry.register("test", fn)

        fallbacks = registry.get("test")
        assert len(fallbacks) == 1
        assert fallbacks[0] is fn

    def test_register_multiple_functions_same_name(self) -> None:
        """同一名称注册多个降级函数（多级降级链）。"""
        registry = FallbackRegistry()
        fn1 = lambda: "level1"  # noqa: E731
        fn2 = lambda: "level2"  # noqa: E731
        fn3 = lambda: "level3"  # noqa: E731

        registry.register("test", fn1)
        registry.register("test", fn2)
        registry.register("test", fn3)

        fallbacks = registry.get("test")
        assert len(fallbacks) == 3
        assert fallbacks == [fn1, fn2, fn3]

    def test_register_different_names(self) -> None:
        """不同名称的注册互不影响。"""
        registry = FallbackRegistry()
        fn_a = lambda: "a"  # noqa: E731
        fn_b = lambda: "b"  # noqa: E731

        registry.register("service_a", fn_a)
        registry.register("service_b", fn_b)

        assert len(registry.get("service_a")) == 1
        assert len(registry.get("service_b")) == 1


class TestFallbackRegistryGet:
    """查找功能测试。"""

    def test_get_nonexistent_returns_empty_list(self) -> None:
        """查找未注册的名称返回空列表。"""
        registry = FallbackRegistry()
        result = registry.get("nonexistent")
        assert result == []

    def test_get_returns_copy_or_reference(self) -> None:
        """get 返回注册的函数列表。"""
        registry = FallbackRegistry()
        fn = lambda: "result"  # noqa: E731
        registry.register("test", fn)

        result = registry.get("test")
        assert result[0] is fn


class TestFallbackRegistryExecute:
    """执行功能测试。"""

    @pytest.mark.asyncio
    async def test_execute_single_fallback_success(self) -> None:
        """执行单个降级函数成功。"""
        registry = FallbackRegistry()
        registry.register("test", lambda x: {"data": x})

        result = await registry.execute("test", 42)
        assert result == {"data": 42, "fallback": True}

    @pytest.mark.asyncio
    async def test_execute_async_fallback(self) -> None:
        """执行异步降级函数。"""
        registry = FallbackRegistry()

        async def async_fb(x: int) -> dict:
            return {"data": x}

        registry.register("test", async_fb)

        result = await registry.execute("test", 42)
        assert result == {"data": 42, "fallback": True}

    @pytest.mark.asyncio
    async def test_execute_multi_level_chain_first_success(self) -> None:
        """多级降级链中首个函数成功。"""
        registry = FallbackRegistry()
        registry.register("test", lambda: {"level": 1})
        registry.register("test", lambda: {"level": 2})

        result = await registry.execute("test")
        assert result == {"level": 1, "fallback": True}

    @pytest.mark.asyncio
    async def test_execute_multi_level_chain_fallback(self) -> None:
        """多级降级链中首个失败、次级成功。"""
        registry = FallbackRegistry()

        def fail_fn() -> dict:
            raise RuntimeError("降级1失败")

        registry.register("test", fail_fn)
        registry.register("test", lambda: {"level": 2})

        result = await registry.execute("test")
        assert result == {"level": 2, "fallback": True}

    @pytest.mark.asyncio
    async def test_execute_all_fallbacks_fail(self) -> None:
        """所有降级函数均失败时返回通用错误字典。"""
        registry = FallbackRegistry()

        def fail1() -> dict:
            raise RuntimeError("失败1")

        def fail2() -> dict:
            raise RuntimeError("失败2")

        registry.register("test", fail1)
        registry.register("test", fail2)

        result = await registry.execute("test")
        assert result == {"error": "no fallback available", "fallback": True}

    @pytest.mark.asyncio
    async def test_execute_no_registered_fallback(self) -> None:
        """无注册降级函数时返回通用错误字典。"""
        registry = FallbackRegistry()
        result = await registry.execute("nonexistent")
        assert result == {"error": "no fallback available", "fallback": True}

    @pytest.mark.asyncio
    async def test_execute_non_dict_result_gets_marker(self) -> None:
        """非字典类型的降级结果直接返回（无法附加 fallback 标记）。"""
        registry = FallbackRegistry()
        registry.register("test", lambda: "string_result")

        result = await registry.execute("test")
        assert result == "string_result"

    @pytest.mark.asyncio
    async def test_execute_with_kwargs(self) -> None:
        """支持关键字参数传递。"""
        registry = FallbackRegistry()
        registry.register("test", lambda item_name, item_value: {"name": item_name, "value": item_value})

        result = await registry.execute("test", item_name="test_item", item_value=100)
        assert result == {"name": "test_item", "value": 100, "fallback": True}


class TestFallbackRegistryIsolated:
    """不同实例之间的隔离性测试。"""

    def test_different_instances_are_isolated(self) -> None:
        """不同注册表实例互不影响。"""
        registry_a = FallbackRegistry()
        registry_b = FallbackRegistry()

        registry_a.register("test", lambda: "a")

        assert len(registry_a.get("test")) == 1
        assert len(registry_b.get("test")) == 0
