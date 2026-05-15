"""并发执行工具单元测试。"""

import asyncio
import time

import pytest

from src.multi_agent_system.core.concurrent import concurrent_execute, run_with_semaphore


class TestConcurrentExecute:
    """concurrent_execute 函数测试。"""

    @pytest.mark.asyncio
    async def test_all_tasks_complete(self) -> None:
        """所有任务正常完成，返回正确结果。"""

        async def task_a() -> str:
            return "result_a"

        async def task_b() -> str:
            return "result_b"

        results = await concurrent_execute([
            ("a", task_a),
            ("b", task_b),
        ])
        assert results["a"] == "result_a"
        assert results["b"] == "result_b"

    @pytest.mark.asyncio
    async def test_error_isolation(self) -> None:
        """某任务失败不影响其他任务，失败任务返回错误信息。"""

        async def task_success() -> str:
            return "ok"

        async def task_fail() -> None:
            raise ValueError("boom")

        results = await concurrent_execute([
            ("success", task_success),
            ("fail", task_fail),
        ])
        assert results["success"] == "ok"
        assert results["fail"]["error"] == "boom"
        assert results["fail"]["failed"] is True

    @pytest.mark.asyncio
    async def test_concurrent_execution_is_faster(self) -> None:
        """并发执行总耗时接近最慢任务，而非所有任务之和。"""

        async def slow_task() -> str:
            await asyncio.sleep(0.1)
            return "slow"

        async def fast_task() -> str:
            await asyncio.sleep(0.05)
            return "fast"

        start = time.perf_counter()
        results = await concurrent_execute([
            ("slow", slow_task),
            ("fast", fast_task),
        ])
        duration = time.perf_counter() - start

        assert results["slow"] == "slow"
        assert results["fast"] == "fast"
        # 并发执行耗时应接近最慢任务(0.1s)，而非两倍
        assert duration < 0.2

    @pytest.mark.asyncio
    async def test_max_concurrency_limits_parallel(self) -> None:
        """max_concurrency=1 时任务串行执行，总耗时等于各任务之和。"""
        execution_times: list[float] = []

        async def tracked_task() -> None:
            execution_times.append(time.perf_counter())
            await asyncio.sleep(0.05)

        start = time.perf_counter()
        await concurrent_execute(
            [(f"task_{i}", tracked_task) for i in range(3)],
            max_concurrency=1,
        )
        duration = time.perf_counter() - start

        # 串行执行：3 个任务 * 0.05s = 至少 0.15s
        assert duration >= 0.14

    @pytest.mark.asyncio
    async def test_empty_tasks_list(self) -> None:
        """空任务列表返回空字典。"""
        results = await concurrent_execute([])
        assert results == {}

    @pytest.mark.asyncio
    async def test_single_task(self) -> None:
        """单个任务正常执行。"""

        async def task() -> int:
            return 42

        results = await concurrent_execute([("only", task)])
        assert results["only"] == 42

    @pytest.mark.asyncio
    async def test_multiple_failures(self) -> None:
        """多个任务失败时，每个都有独立错误信息。"""

        async def fail_a() -> None:
            raise RuntimeError("error_a")

        async def fail_b() -> None:
            raise TypeError("error_b")

        async def succeed() -> str:
            return "ok"

        results = await concurrent_execute([
            ("a", fail_a),
            ("b", fail_b),
            ("c", succeed),
        ])
        assert results["a"]["failed"] is True
        assert "error_a" in results["a"]["error"]
        assert results["b"]["failed"] is True
        assert "error_b" in results["b"]["error"]
        assert results["c"] == "ok"


class TestRunWithSemaphore:
    """run_with_semaphore 函数测试。"""

    @pytest.mark.asyncio
    async def test_executes_under_semaphore(self) -> None:
        """在信号量控制下正常执行函数并返回结果。"""
        semaphore = asyncio.Semaphore(2)

        async def my_func(x: int) -> int:
            return x * 2

        result = await run_with_semaphore(my_func, semaphore, 5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self) -> None:
        """信号量限制并发数，同一时刻最多 N 个任务执行。"""
        semaphore = asyncio.Semaphore(2)
        active_count = 0
        max_active = 0

        async def tracked() -> None:
            nonlocal active_count, max_active
            async with semaphore:
                active_count += 1
                max_active = max(max_active, active_count)
                await asyncio.sleep(0.05)
                active_count -= 1

        await asyncio.gather(*[tracked() for _ in range(5)])
        assert max_active <= 2
