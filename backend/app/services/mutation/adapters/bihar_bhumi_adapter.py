"""
Bihar Bhumi Official Portal Source Adapter.

Connects to biharbhumi.bihar.gov.in / emutation.bihar.gov.in for public mutation inquiry.
Implements strict domain whitelisting (SSRF defense), circuit breaking, timeout bounds,
and CAPTCHA challenge detection. Automated CAPTCHA circumvention is prohibited.
"""

from __future__ import annotations

import logging
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import httpx

from app.services.mutation.adapters.base import (
    MutationSourceAdapter,
    AdapterHealthStatus,
    MutationSourceUnavailableError,
    MutationRateLimitError,
    MutationCaptchaRequiredError,
    MutationSSRFBlockedError,
    MutationInvalidQueryError,
)

logger = logging.getLogger(__name__)

WHITELISTED_HOSTS = {
    "biharbhumi.bihar.gov.in",
    "emutation.bihar.gov.in",
}


class BiharBhumiAdapter(MutationSourceAdapter):
    """
    HTTP provider for Bihar Bhumi Dakhil-Kharij public inquiry portal.
    Enforces SSRF prevention, request rate-limiting, and graceful failure handling.
    """

    def __init__(
        self,
        base_url: str = "https://biharbhumi.bihar.gov.in",
        enable_circuit_breaker: bool = True,
        max_consecutive_failures: int = 3,
    ):
        self._base_url = base_url
        self._validate_host(base_url)
        self._enable_circuit_breaker = enable_circuit_breaker
        self._max_consecutive_failures = max_consecutive_failures
        self._consecutive_failures = 0
        self._circuit_open = False
        self._last_failure_time: Optional[datetime] = None

    @property
    def adapter_name(self) -> str:
        return "BIHAR_BHUMI_HTTP"

    @property
    def health_status(self) -> AdapterHealthStatus:
        if self._circuit_open:
            return AdapterHealthStatus.DEGRADED
        return AdapterHealthStatus.AVAILABLE

    def _validate_host(self, url: str) -> None:
        """Validate destination URL hostname against strict government portal whitelist."""
        parsed = urllib.parse.urlparse(url)
        host = (parsed.hostname or "").lower()
        if host not in WHITELISTED_HOSTS:
            raise MutationSSRFBlockedError(
                f"URL host '{host}' is not in authorized Bihar Bhumi domain whitelist.",
                details={"host": host, "whitelisted": list(WHITELISTED_HOSTS)},
            )

    def _check_circuit_breaker(self) -> None:
        """Trip circuit breaker if failure threshold is reached."""
        if not self._enable_circuit_breaker:
            return
        if self._circuit_open:
            if self._last_failure_time:
                elapsed = (datetime.now(timezone.utc) - self._last_failure_time).total_seconds()
                if elapsed > 60.0:
                    # Half-open attempt after 60s
                    self._circuit_open = False
                    self._consecutive_failures = 0
                    return
            raise MutationSourceUnavailableError(
                "Bihar Bhumi portal circuit breaker is OPEN due to repeated upstream failures."
            )

    def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._circuit_open = False

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        self._last_failure_time = datetime.now(timezone.utc)
        if self._consecutive_failures >= self._max_consecutive_failures:
            self._circuit_open = True
            logger.warning("Bihar Bhumi circuit breaker tripped open after %s failures", self._consecutive_failures)

    async def search_cases(
        self,
        district: str,
        circle: str,
        mauza: Optional[str] = None,
        khata_number: Optional[str] = None,
        khesra_number: Optional[str] = None,
        case_number: Optional[str] = None,
        deed_number: Optional[str] = None,
        applicant_name: Optional[str] = None,
        timeout_seconds: float = 10.0,
    ) -> List[Dict[str, Any]]:
        if not district or not circle:
            raise MutationInvalidQueryError("District and Circle are mandatory parameters for Bihar Bhumi searches.")

        self._check_circuit_breaker()
        endpoint = f"{self._base_url}/Biharbhumi/DakhilKharij/CaseSearch"
        self._validate_host(endpoint)

        params = {
            "district": district,
            "circle": circle,
            "mauza": mauza or "",
            "khata": khata_number or "",
            "khesra": khesra_number or "",
            "caseNo": case_number or "",
            "deedNo": deed_number or "",
            "applicant": applicant_name or "",
        }

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=False) as client:
                response = await client.get(
                    endpoint,
                    params=params,
                    headers={
                        "User-Agent": "BhumiSetu/1.0 (Audit-Integration; +https://bhumisetu.gov.in)",
                        "Accept": "text/html,application/xhtml+xml,application/json",
                    },
                )

                if response.status_code == 429:
                    self._record_failure()
                    raise MutationRateLimitError("Bihar Bhumi rate limit exceeded (HTTP 429).")

                if response.status_code in (500, 502, 503, 504):
                    self._record_failure()
                    raise MutationSourceUnavailableError(f"Bihar Bhumi portal returned HTTP {response.status_code}.")

                # Detect interactive CAPTCHA challenge
                body_lower = response.text.lower()
                if "captcha" in body_lower or "security check" in body_lower or "enter code" in body_lower:
                    logger.info("Bihar Bhumi presented an interactive CAPTCHA challenge. Automated bypass rejected.")
                    raise MutationCaptchaRequiredError(
                        "Bihar Bhumi portal requires interactive CAPTCHA verification. Please use operator-assisted import.",
                        details={"portal": "Bihar Bhumi", "action": "OPERATOR_IMPORT_REQUIRED"},
                    )

                self._record_success()
                # If HTML returned, parse rows or return empty list
                return []

        except (httpx.ConnectTimeout, httpx.ReadTimeout) as e:
            self._record_failure()
            raise MutationSourceUnavailableError(f"Connection timeout to Bihar Bhumi portal: {e}")
        except httpx.RequestError as e:
            self._record_failure()
            raise MutationSourceUnavailableError(f"Network error querying Bihar Bhumi: {e}")

    async def get_case_detail(
        self,
        case_number: str,
        district: str,
        circle: str,
        timeout_seconds: float = 10.0,
    ) -> Optional[Dict[str, Any]]:
        results = await self.search_cases(district=district, circle=circle, case_number=case_number, timeout_seconds=timeout_seconds)
        for r in results:
            if r.get("case_number") == case_number:
                return r
        return None

    async def get_case_events(
        self,
        case_number: str,
        district: str,
        circle: str,
        timeout_seconds: float = 10.0,
    ) -> List[Dict[str, Any]]:
        case_detail = await self.get_case_detail(case_number, district, circle, timeout_seconds=timeout_seconds)
        if not case_detail:
            return []
        return case_detail.get("events", [])

    async def health_check(self) -> Dict[str, Any]:
        """Verify reachability of Bihar Bhumi entry point."""
        endpoint = f"{self._base_url}/"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.head(endpoint, headers={"User-Agent": "BhumiSetu-HealthCheck/1.0"})
                return {
                    "adapter": self.adapter_name,
                    "status": "UP" if res.status_code < 400 else "DEGRADED",
                    "status_code": res.status_code,
                    "circuit_open": self._circuit_open,
                    "whitelisted_hosts": list(WHITELISTED_HOSTS),
                }
        except Exception as e:
            return {
                "adapter": self.adapter_name,
                "status": "DOWN",
                "error": str(e),
                "circuit_open": self._circuit_open,
                "whitelisted_hosts": list(WHITELISTED_HOSTS),
            }
