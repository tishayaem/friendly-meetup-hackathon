"""Local demonstration only. No messages are sent and no identity is proven."""
from dataclasses import dataclass, field
import secrets
import time


@dataclass
class Session:
    clock: object = time.monotonic
    code_factory: object = lambda: f"{secrets.randbelow(1000000):06d}"
    order_id: str | None = None
    expires: float = 0
    attempts: int = 0
    state: str = "needs_verification"
    _code: str = field(default="", repr=False)
    pending_question: str = ""

    def start(self, order_id: str) -> str:
        self.order_id = order_id.strip().upper()
        self.expires = self.clock() + 300
        self.attempts = 0
        self.state = "verification_pending"
        self._code = self.code_factory()
        return self._code  # Only the demo terminal/test driver sees this.

    def verify(self, code: str) -> bool:
        if self.clock() >= self.expires:
            self.state = "verification_expired"
        if self.state != "verification_pending":
            return False
        self.attempts += 1
        if secrets.compare_digest(str(code), self._code):
            self.state = "verified"
            self._code = ""
            return True
        if self.attempts >= 3:
            self.state = "verification_failed"
            self._code = ""
        return False

    def authorised(self, order_id: str) -> bool:
        if self.state == "verified" and self.clock() >= self.expires:
            self.state = "verification_expired"
        return self.state == "verified" and self.order_id == order_id.strip().upper()
