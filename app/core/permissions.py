from app.core.models import ApprovalDecision, ApprovalRequest


class PermissionPolicy:
    """Conservative action policy: analysis is autonomous; risky mutations need approval."""

    APPROVAL_REQUIRED = {
        "delete", "publish", "deploy", "purchase", "send_external", "overwrite",
        "change_permissions", "merge",
    }
    BLOCKED = {"exfiltrate_secret", "disable_security", "expose_credential"}

    def evaluate(self, request: ApprovalRequest, autonomy: str = "high") -> ApprovalDecision:
        action = request.action.strip().lower()
        if action in self.BLOCKED:
            return ApprovalDecision(
                allowed=False, requires_approval=False,
                explanation="This action is prohibited by the system safety policy.",
            )
        if action in self.APPROVAL_REQUIRED:
            return ApprovalDecision(
                allowed=False, requires_approval=True,
                explanation="Explicit user approval is required before this consequential action.",
            )
        return ApprovalDecision(
            allowed=True, requires_approval=False,
            explanation="This action is permitted within the autonomous design workflow.",
        )
