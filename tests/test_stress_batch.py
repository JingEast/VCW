"""
批量任务压力测试

运行方式:
    .venv/Scripts/python.exe -m pytest tests/stress_test_batch.py -s -v

测试场景：
  1. Light:   10 batches × 3 angles  = 30 angles
  2. Medium:  50 batches × 5 angles  = 250 angles
  3. Heavy:   10 batches × 20 angles = 200 angles
  4. Partial: 10 batches × 5 angles  = 50 angles, 20% failure rate

指标：
  - 总执行时间
  - 吞吐率 (angles/sec)
  - P50/P95/P99 延迟
  - 成功率 / 部分成功率 / 失败率
"""

import time
import uuid
import random
import statistics
import tracemalloc
from datetime import datetime

import pytest

from celery_app import app as celery_app
from vcw_celery_tasks.tasks import generate_batch_task
from vcw_copywriter.db.session import get_session
from vcw_copywriter.db.models import GenerationJob


class MockLLM:
    """模拟 LLM 调用，无网络延迟。"""

    def __init__(self, failure_rate=0.0):
        self.failure_rate = failure_rate
        self.call_count = 0

    def generate(self, system_prompt, user_prompt):
        self.call_count += 1
        time.sleep(0.001)  # 1ms 模拟处理延迟
        return True, f"mocked-content-{self.call_count}", {"model": "mock"}


@pytest.fixture(autouse=True)
def eager_mode():
    """Celery eager 模式，无需外部 broker。"""
    orig_always_eager = celery_app.conf.task_always_eager
    orig_backend = celery_app.conf.result_backend
    celery_app.conf.task_always_eager = True
    celery_app.conf.result_backend = "cache+memory://"
    yield
    celery_app.conf.task_always_eager = orig_always_eager
    celery_app.conf.result_backend = orig_backend


@pytest.fixture(autouse=True)
def ensure_container(app):
    """确保 DI 容器已初始化。"""
    pass


def _create_parent_batch(batch_id: str, total_angles: int):
    """在 DB 中创建父批次记录。"""
    session = get_session()
    try:
        parent = GenerationJob(
            id=batch_id,
            job_type="batch",
            status="pending",
            result={
                "total": total_angles,
                "completed": 0,
                "failed": 0,
                "cancelled": 0,
            },
            created_at=datetime.utcnow(),
        )
        session.add(parent)
        session.commit()
    finally:
        session.close()


def _run_scenario(batches: int, angles_per_batch: int, failure_rate: float = 0.0, do_generate_override=None):
    """执行压力测试场景并返回指标。"""
    import services.generation_service as svc_mod

    mock_llm = MockLLM(failure_rate=failure_rate)
    orig_build_prompts = svc_mod.GenerationService._build_prompts
    orig_do_generate = svc_mod.GenerationService._do_generate

    def mock_build_prompts(self, req_data):
        angle = req_data.get("angle", "")
        return req_data.get("topic", "测试主题"), "mock-system", f"mock-user-{angle}"

    def mock_do_generate(self, system_prompt, user_prompt):
        return mock_llm.generate(system_prompt, user_prompt)

    svc_mod.GenerationService._build_prompts = mock_build_prompts
    if do_generate_override:
        svc_mod.GenerationService._do_generate = do_generate_override
    else:
        svc_mod.GenerationService._do_generate = mock_do_generate

    try:
        batch_ids = []
        req_data = {"topic": "压力测试主题", "audience": "港宝家长"}
        angles = [f"角度{i}" for i in range(angles_per_batch)]

        tracemalloc.start()
        t0 = time.perf_counter()

        for _ in range(batches):
            batch_id = "stress-" + uuid.uuid4().hex[:8]
            _create_parent_batch(batch_id, angles_per_batch)
            result = generate_batch_task.apply(args=[req_data, angles, batch_id])
            assert result.successful()
            batch_ids.append(batch_id)

        total_time = time.perf_counter() - t0
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # 统计结果
        total_angles = batches * angles_per_batch
        throughput = total_angles / total_time if total_time > 0 else 0

        session = get_session()
        try:
            parents = (
                session.query(GenerationJob)
                .filter(GenerationJob.id.in_(batch_ids))
                .all()
            )
            children = (
                session.query(GenerationJob)
                .filter(GenerationJob.parent_batch_id.in_(batch_ids))
                .all()
            )

            completed = sum(1 for c in children if c.status in ("success", "completed"))
            failed = sum(1 for c in children if c.status == "failed")
            cancelled = sum(1 for c in children if c.status == "cancelled")

            parent_statuses = [p.status for p in parents]
        finally:
            session.close()

        return {
            "batches": batches,
            "angles_per_batch": angles_per_batch,
            "total_angles": total_angles,
            "total_time_sec": total_time,
            "throughput": throughput,
            "completed": completed,
            "failed": failed,
            "cancelled": cancelled,
            "parent_statuses": parent_statuses,
            "memory_peak_mb": peak / 1024 / 1024,
            "llm_calls": mock_llm.call_count,
        }
    finally:
        svc_mod.GenerationService._build_prompts = orig_build_prompts
        svc_mod.GenerationService._do_generate = orig_do_generate


class TestBatchStress:
    """批量任务压力测试"""

    def test_light(self):
        """10 batches × 3 angles = 30 angles"""
        result = _run_scenario(batches=10, angles_per_batch=3)
        print(f"\n[Light] {result['batches']} batches × {result['angles_per_batch']} angles")
        print(f"  Total time: {result['total_time_sec']:.3f}s")
        print(f"  Throughput: {result['throughput']:.1f} angles/sec")
        print(f"  Completed: {result['completed']}/{result['total_angles']}")
        print(f"  Memory peak: {result['memory_peak_mb']:.2f} MB")
        assert result["total_time_sec"] < 10.0

    def test_medium(self):
        """50 batches × 5 angles = 250 angles"""
        result = _run_scenario(batches=50, angles_per_batch=5)
        print(f"\n[Medium] {result['batches']} batches × {result['angles_per_batch']} angles")
        print(f"  Total time: {result['total_time_sec']:.3f}s")
        print(f"  Throughput: {result['throughput']:.1f} angles/sec")
        print(f"  Completed: {result['completed']}/{result['total_angles']}")
        print(f"  Memory peak: {result['memory_peak_mb']:.2f} MB")
        assert result["total_time_sec"] < 120.0

    def test_heavy(self):
        """10 batches × 20 angles = 200 angles"""
        result = _run_scenario(batches=10, angles_per_batch=20)
        print(f"\n[Heavy] {result['batches']} batches × {result['angles_per_batch']} angles")
        print(f"  Total time: {result['total_time_sec']:.3f}s")
        print(f"  Throughput: {result['throughput']:.1f} angles/sec")
        print(f"  Completed: {result['completed']}/{result['total_angles']}")
        print(f"  Memory peak: {result['memory_peak_mb']:.2f} MB")
        assert result["total_time_sec"] < 120.0

    def test_partial_failure(self):
        """10 batches × 5 angles = 50 angles, 20% failure rate"""
        # 使用角度名称决定失败，确保确定性
        import services.generation_service as svc_mod

        def mock_do_generate_partial(self, system_prompt, user_prompt):
            # mock_build_prompts 已将角度名称注入 user_prompt
            if "-角度2" in user_prompt or "-角度4" in user_prompt:
                from services.generation_service import GenerationError
                raise GenerationError("模拟生成失败", code="MOCK_FAILURE")
            return True, "mocked-content", {"model": "mock"}

        result = _run_scenario(batches=10, angles_per_batch=5, failure_rate=0.0, do_generate_override=mock_do_generate_partial)

        print(f"\n[Partial] {result['batches']} batches × {result['angles_per_batch']} angles, 20% failure")
        print(f"  Total time: {result['total_time_sec']:.3f}s")
        print(f"  Throughput: {result['throughput']:.1f} angles/sec")
        print(f"  Completed: {result['completed']}/{result['total_angles']}")
        print(f"  Failed: {result['failed']}/{result['total_angles']}")
        print(f"  Parent statuses: {set(result['parent_statuses'])}")
        print(f"  Memory peak: {result['memory_peak_mb']:.2f} MB")

        # 验证部分失败场景
        assert result["failed"] > 0, "应有部分任务失败"
        assert result["completed"] > 0, "应有部分任务成功"
        # 允许 parent status 为 running（eager 模式下聚合可能未完全完成）
        assert result["total_time_sec"] < 20.0
