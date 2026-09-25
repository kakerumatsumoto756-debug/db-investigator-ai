from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from uuid import UUID

import structlog
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, status

from app.agent.agent import InvestigationAgent
from app.agent.tools import DatabaseTools, ToolResult
from app.config import Settings, get_settings
from app.database import Database
from app.llm.provider import LLMProvider, LLMProviderError, OpenAICompatibleProvider
from app.models import (
    DatabaseStatus,
    InvestigationRequest,
    InvestigationResponse,
    InvestigationStatus,
)
from app.repository import InvestigationRepository

logger = structlog.get_logger(__name__)
ProviderFactory = Callable[[Settings], LLMProvider]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    database = Database(settings)
    await database.open()
    app.state.settings = settings
    app.state.database = database
    app.state.repository = InvestigationRepository(database)
    app.state.provider_factory = OpenAICompatibleProvider.from_settings
    yield
    await database.close()


app = FastAPI(
    title="DB Investigator AI",
    version="0.1.0",
    description="Evidence-driven PostgreSQL performance investigations.",
    lifespan=lifespan,
)


def repository(request: Request) -> InvestigationRepository:
    return request.app.state.repository


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/database/status", response_model=DatabaseStatus)
async def database_status(request: Request) -> DatabaseStatus:
    tools = DatabaseTools(request.app.state.database)
    try:
        result = await tools.get_database_version()
        version = result.data[0]["version"] if result.data else None
        return DatabaseStatus(connected=True, version=version)
    except Exception as exc:
        logger.warning("database_status_failed", error_type=type(exc).__name__)
        return DatabaseStatus(connected=False, error="Unable to connect to PostgreSQL")


@app.post(
    "/api/investigate",
    response_model=InvestigationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_investigation(
    payload: InvestigationRequest, background_tasks: BackgroundTasks, request: Request
) -> InvestigationResponse:
    created = await repository(request).create(payload)
    background_tasks.add_task(
        run_investigation,
        created.id,
        payload,
        request.app.state.settings,
        request.app.state.database,
        request.app.state.repository,
        request.app.state.provider_factory,
    )
    return created


@app.get("/api/investigations/{investigation_id}", response_model=InvestigationResponse)
async def get_investigation(investigation_id: UUID, request: Request) -> InvestigationResponse:
    investigation = await repository(request).get(investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return investigation


async def run_investigation(
    investigation_id: UUID,
    payload: InvestigationRequest,
    settings: Settings,
    database: Database,
    repo: InvestigationRepository,
    provider_factory: ProviderFactory,
) -> None:
    provider: LLMProvider | None = None
    try:
        await repo.set_status(investigation_id, InvestigationStatus.RUNNING)
        provider = provider_factory(settings)

        async def on_activity(
            kind: str, summary: str, result: ToolResult | None = None
        ) -> None:
            result_data = result.model_dump(mode="json") if result else None
            await repo.append_event(investigation_id, kind, summary, result_data)

        agent = InvestigationAgent(
            provider,
            DatabaseTools(database),
            max_iterations=settings.agent_max_iterations,
            on_activity=on_activity,
        )
        report = await agent.investigate(payload.problem, payload.sql)
        await repo.complete(investigation_id, report)
    except LLMProviderError as exc:
        logger.warning("investigation_provider_failed", investigation_id=str(investigation_id))
        await repo.fail(investigation_id, str(exc))
    except Exception as exc:
        logger.exception(
            "investigation_failed",
            investigation_id=str(investigation_id),
            error_type=type(exc).__name__,
        )
        await repo.fail(investigation_id, "Investigation failed due to an internal error")
    finally:
        if provider is not None:
            await provider.close()
