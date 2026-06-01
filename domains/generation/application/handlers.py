"""Generation domain application handlers."""

from typing import Dict, Iterator, List, Optional, Tuple

from .commands import (
    CancelAsyncBatchCommand,
    CancelAsyncCommand,
    GenerateBatchCommand,
    GenerateCopyCommand,
    SubmitAsyncBatchCommand,
    SubmitAsyncCommand,
)
from .queries import GenerateStreamQuery, GetAsyncBatchStatusQuery, GetAsyncStatusQuery
from services.async_task_service import (
    AsyncBatchSubmitDto,
    AsyncTaskSubmitDto,
)


class GenerationHandler:
    """Orchestrates generation use cases."""

    def __init__(
        self,
        generation_service,
        async_task_service=None,
        history_service=None,
    ):
        self._svc = generation_service
        self._async_svc = async_task_service
        self._history = history_service

    def handle_generate_copy(self, command: GenerateCopyCommand) -> Dict:
        return self._svc.generate_copy(command.req_data)

    def handle_generate_batch(self, command: GenerateBatchCommand) -> List[Dict]:
        return self._svc.generate_batch(command.req_data, command.angles)

    def handle_generate_stream(
        self, query: GenerateStreamQuery
    ) -> Iterator[Tuple[str, str]]:
        return self._svc.generate_stream(query.req_data)

    # ---- Async single ----

    def handle_submit_async(self, command: SubmitAsyncCommand) -> str:
        if self._async_svc is None:
            raise RuntimeError("AsyncTaskService not configured")
        return self._async_svc.submit_async_generate(
            AsyncTaskSubmitDto(req_data=command.req_data)
        )

    def handle_get_async_status(
        self, query: GetAsyncStatusQuery
    ) -> Optional[Dict]:
        if self._async_svc is None:
            raise RuntimeError("AsyncTaskService not configured")
        return self._async_svc.get_async_status(query.task_id).to_dict()

    def handle_cancel_async(self, command: CancelAsyncCommand) -> bool:
        if self._async_svc is None:
            raise RuntimeError("AsyncTaskService not configured")
        return self._async_svc.cancel_async_task(command.task_id)

    # ---- Async batch ----

    def handle_submit_async_batch(self, command: SubmitAsyncBatchCommand) -> str:
        if self._async_svc is None:
            raise RuntimeError("AsyncTaskService not configured")
        return self._async_svc.submit_async_batch(
            AsyncBatchSubmitDto(
                req_data=command.req_data,
                angles=command.angles,
            )
        )

    def handle_get_async_batch_status(
        self, query: GetAsyncBatchStatusQuery
    ) -> Optional[Dict]:
        if self._async_svc is None:
            raise RuntimeError("AsyncTaskService not configured")
        return self._async_svc.get_async_batch_status(query.batch_id)

    def handle_cancel_async_batch(self, command: CancelAsyncBatchCommand) -> bool:
        if self._async_svc is None:
            raise RuntimeError("AsyncTaskService not configured")
        return self._async_svc.cancel_async_batch(command.batch_id)

    # ---- history / dashboard (cross-cutting read models) ----

    def handle_list_recent_files(self, limit: int = 5) -> List[Dict]:
        if self._history is not None:
            return self._history.list_recent_files(limit)
        return []

    def handle_get_dashboard_stats(self) -> Dict:
        if self._history is not None:
            return self._history.get_dashboard_stats()
        return {}
