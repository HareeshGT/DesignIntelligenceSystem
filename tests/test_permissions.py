from app.core.models import ApprovalRequest
from app.core.permissions import PermissionPolicy


def test_read_and_analysis_actions_are_autonomous():
    decision = PermissionPolicy().evaluate(ApprovalRequest(action="analyze_design"))
    assert decision.allowed and not decision.requires_approval


def test_destructive_actions_require_approval():
    decision = PermissionPolicy().evaluate(ApprovalRequest(action="delete", resource="project"))
    assert not decision.allowed and decision.requires_approval


def test_secret_exfiltration_is_prohibited():
    decision = PermissionPolicy().evaluate(ApprovalRequest(action="exfiltrate_secret"))
    assert not decision.allowed and not decision.requires_approval
