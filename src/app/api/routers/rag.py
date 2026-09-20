from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.limiter import limiter
from app.api.schemas.rag import AskRequest, AskResponse
from app.db.repositories.paper import PaperRepository
from app.db.repositories.rag import RagRepository
from app.db.session import get_db_session
from app.services.embedder import EmbedderService
from app.services.llm import LlmService
from app.services.rag import RagService

router = APIRouter()

# Singleton instances for ML services so they aren't reloaded every request
embedder_service = EmbedderService()
llm_service = LlmService()


def get_rag_service(session: AsyncSession = Depends(get_db_session)) -> RagService:
    rag_repo = RagRepository(session)
    paper_repo = PaperRepository(session)
    return RagService(
        rag_repo=rag_repo, paper_repo=paper_repo, embedder=embedder_service, llm=llm_service
    )


@router.post("/ask", response_model=AskResponse)
@limiter.limit("10/minute")
async def ask_question(
    request: Request, ask_req: AskRequest, rag_svc: RagService = Depends(get_rag_service)
):
    """
    RAG endpoint to ask questions about the arXiv papers.
    """
    if len(ask_req.question.strip()) < 5:
        raise HTTPException(status_code=422, detail="Question too short")
    if len(ask_req.question) > 500:
        raise HTTPException(status_code=422, detail="Question too long")

    return await rag_svc.ask(ask_req)
