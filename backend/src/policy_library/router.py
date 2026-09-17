"""Authenticated policy catalogue and PDF download endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from authentication.dependencies import require_authenticated_request
from authentication.service import AuthenticatedUser
from errors import ApiError

from .catalogue import POLICY_DOCUMENTS, policy_document
from .schemas import PolicyDocumentRead

router = APIRouter(prefix="/api/policies", tags=["policies"])


def document_metadata() -> list[PolicyDocumentRead]:
    """Build client metadata without revealing source filesystem paths."""

    return [
        PolicyDocumentRead(
            document_id=document.document_id,
            document_type=document.document_type,
            title=document.title,
            version=document.version,
            effective_date=document.effective_date,
            filename=document.download_filename,
        )
        for document in POLICY_DOCUMENTS
    ]


@router.get("", response_model=list[PolicyDocumentRead])
def list_policy_documents(
    _authenticated: Annotated[AuthenticatedUser, Depends(require_authenticated_request)],
) -> list[PolicyDocumentRead]:
    """List the policy documents available to any signed-in account."""

    return document_metadata()


@router.get("/{document_id}/download", response_class=FileResponse)
def download_policy_document(
    document_id: str,
    _authenticated: Annotated[AuthenticatedUser, Depends(require_authenticated_request)],
) -> FileResponse:
    """Download one allowlisted PDF with a server-controlled filename."""

    document = policy_document(document_id)
    if document is None:
        raise ApiError(
            status_code=404,
            code="policy_document_not_found",
            message="The policy document could not be found.",
        )
    if not document.path.is_file():
        raise ApiError(
            status_code=503,
            code="policy_document_unavailable",
            message="The policy document is temporarily unavailable.",
        )

    return FileResponse(
        document.path,
        media_type="application/pdf",
        filename=document.download_filename,
        content_disposition_type="attachment",
        headers={"Cache-Control": "private, no-store"},
    )
