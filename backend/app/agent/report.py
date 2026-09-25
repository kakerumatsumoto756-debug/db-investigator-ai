from app.agent.state import InvestigationState
from app.models import InvestigationReport


def validate_report_evidence(
    report: InvestigationReport, state: InvestigationState
) -> InvestigationReport:
    if not state.evidence:
        raise ValueError("An investigation report requires observed evidence")
    if not report.evidence:
        raise ValueError("The final report must cite evidence")
    return report

