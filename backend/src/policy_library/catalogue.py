"""Allowlisted policy documents and safe resource resolution."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from resources import policy_reference_directory


@dataclass(frozen=True, slots=True)
class PolicyDocument:
    """Metadata for one bundled, read-only policy document."""

    document_id: str
    document_type: str
    title: str
    version: str
    effective_date: date
    source_filename: str
    download_filename: str

    @property
    def path(self) -> Path:
        """Resolve this allowlisted document without accepting a client path."""

        root = policy_reference_directory().resolve()
        path = (root / self.source_filename).resolve()
        if path.parent != root:
            raise RuntimeError("Policy document paths must remain inside the reference directory")
        return path


POLICY_DOCUMENTS = (
    PolicyDocument(
        document_id="hr78-v3",
        document_type="Policy",
        title="HR.78 Medical & Dental Staff Annual Leave Policy",
        version="3",
        effective_date=date(2025, 7, 1),
        source_filename="HR78_Medical_Dental_Annual_Leave_Policy_v3_2025-07.pdf",
        download_filename="HR78-Medical-Dental-Annual-Leave-Policy-v3.pdf",
    ),
    PolicyDocument(
        document_id="hrs09-v1",
        document_type="Guidance",
        title="HR.S.09 Annual Leave Guidance for Medical & Dental Staff",
        version="1",
        effective_date=date(2025, 7, 1),
        source_filename="HRS09_Medical_Dental_Annual_Leave_Guidance_v1_2025-07.pdf",
        download_filename="HRS09-Medical-Dental-Annual-Leave-Guidance-v1.pdf",
    ),
)


def policy_document(document_id: str) -> PolicyDocument | None:
    """Return an allowlisted document by its stable public identifier."""

    return next(
        (document for document in POLICY_DOCUMENTS if document.document_id == document_id),
        None,
    )
