class DellCLIError(Exception):
    """
    Centralized error representing structured CLI operation failures.
    Includes CAUSE, IMPACT, and RECOMMENDED ACTION.
    """

    def __init__(self, title: str, cause: str, impact: str, action: str):
        self.title = title
        self.cause = cause
        self.impact = impact
        self.action = action
        super().__init__(title)
