
import logging
import requests
import datetime
import time

_logger = logging.getLogger(__name__)

_ENDPOINTS = {
    "UAT": {
        "token":  "https://api-uat.amberroad.com/oauth/token",
        "icc_v1": "https://api-uat.amberroad.com/icc/v1/calculateImportCost?tId=",
        "icc_v2": "https://api-uat.amberroad.com/icc/v2/calculateImportCost?tId=",
        "pd_v1":  "https://api-uat.amberroad.com/icc/v1/partialDuty?tId=",
        "pd_v2":  "https://api-uat.amberroad.com/icc/v2/partialDuty?tId=",
    },
    "PRO": {
        "token":  "https://api.amberroad.com/oauth/token",
        "icc_v1": "https://api.amberroad.com/icc/v1/calculateImportCost?tId=",
        "icc_v2": "https://api.amberroad.com/icc/v2/calculateImportCost?tId=",
        "pd_v1":  "https://api.amberroad.com/icc/v1/partialDuty?tId=",
        "pd_v2":  "https://api.amberroad.com/icc/v2/partialDuty?tId=",
    },
}


class E2OpenSession(requests.Session):
    # (connect timeout, read timeout) in seconds — prevents hung runs on flaky networks
    _DEFAULT_TIMEOUT = (10, 30)

    def request(self, method, url, **kwargs):
        kwargs.setdefault("timeout", self._DEFAULT_TIMEOUT)
        return super().request(method, url, **kwargs)

    def __init__(self, username: str, password: str, tenant: str, environment: str = "UAT"):
        requests.Session.__init__(self)
        self.username = username
        self.password = password
        self.tenant = tenant
        self.environment = environment.upper()
        self.account_key = f"{self.environment}:{self.username}:{self.tenant}"
        self._urls = _ENDPOINTS.get(self.environment, _ENDPOINTS["UAT"])
        self.token = ""
        self.tokenExpires = ""
        self.tokenCounter = 0
        self.reqCounter = 0
        self.output = {}
        self.getToken()

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _safe_json(response):
        """Return (data: dict, error: str|None). Never raises."""
        try:
            data = response.json()
        except Exception as exc:
            return {}, f"Invalid JSON response: {exc}"
        if not isinstance(data, dict):
            return {}, "Invalid JSON response: root is not an object."
        return data, None

    @staticmethod
    def _as_list(value):
        """None / '' / [] → []; list → value; anything else → [value]."""
        if value is None or value == "" or value == []:
            return []
        if isinstance(value, list):
            return value
        return [value]

    def _has_valid_rate_prog_result(self, output):
        """Return True if any rateProgResult entry has usable data."""
        try:
            for line in self._as_list(output.get("line")):
                if not isinstance(line, dict):
                    continue
                for rp in self._as_list(line.get("rateProgram")):
                    if isinstance(rp, dict) and rp.get("rateProgResult"):
                        return True
        except Exception:
            pass
        return False

    def _extract_pd_alternative_hs(self, output, fallback_hs):
        """Extract lowValueHS from partialDuty output, or return fallback_hs."""
        try:
            for item in self._as_list(output.get("rateProgResult")):
                if not isinstance(item, dict):
                    continue
                for sub in self._as_list(item.get("rateProgResult")):
                    if isinstance(sub, dict) and sub.get("lowValueHS"):
                        return sub["lowValueHS"]
        except Exception:
            pass
        return fallback_hs

    # ── Auth ──────────────────────────────────────────────────────────────────

    def getToken(self):
        url = self._urls["token"]
        params = {
            "grant_type": "client_credentials",
            "User ID": self.username,
            "Password": self.password,
            "Tenant id": self.tenant,
        }
        response = self.get(url, params=params, auth=requests.auth.HTTPBasicAuth(self.username, self.password))
        if response.status_code != 200:
            raise RuntimeError(
                f"E2Open authentication failed (HTTP {response.status_code}): {response.text[:300]}"
            )
        try:
            data = response.json()
            self.token = data["access_token"]
            self.tokenExpires = datetime.datetime.now() + datetime.timedelta(seconds=data["expires_in"])
        except (KeyError, ValueError) as exc:
            raise RuntimeError(
                f"E2Open token response missing expected fields ({exc}). "
                f"Response: {response.text[:300]}"
            ) from exc
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.tokenCounter += 1
        _logger.info("Token %d obtained, valid until %s", self.tokenCounter, self.tokenExpires)

    def _post_with_retry(self, url: str, request_body: dict):
        """POST helper with auto token refresh on 401 and connection retry."""
        attempt = 0
        while True:
            attempt += 1
            try:
                response = self.post(url, headers=self.headers, json=request_body)
                if response.status_code == 401:
                    self.getToken()
                    response = self.post(url, headers=self.headers, json=request_body)
                return response
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                _logger.warning("Connection lost or timed out. Retry (%d)", attempt)
                if attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise

    # ── API calls ─────────────────────────────────────────────────────────────

    def getICCv1(self, coo, coi, hs, custUnitP, cur, qnty, ref_date):
        url = self._urls["icc_v1"] + self.tenant
        self.reqCounter += 1
        request_body = {
            "reqId": 0,
            "coi": coi,
            "coe": coo,
            "coo": coo,
            "imDate": ref_date,
            "exDate": ref_date,
            "line": [
                {
                    "hs": [{"relatedHs": 0, "seq": 0, "hsNum": hs}],
                    "cur": cur,
                    "custUnitP": str(float(custUnitP) / float(qnty)),
                    "classCat": "02",
                    "qnty": qnty,
                }
            ],
        }
        return self._post_with_retry(url, request_body)

    # Only getICCv1 is used in the main flow; v2 kept for compatibility
    def getICCv2(self, coo, coi, hs, ref_date):
        url = self._urls["icc_v2"] + self.tenant
        self.reqCounter += 1
        request_body = {
            "reqId": 0,
            "coi": coi,
            "coe": coo,
            "coo": coo,
            "imDate": ref_date,
            "exDate": ref_date,
            "line": [
                {
                    "hs": [{"seq": 0, "hsNum": hs}],
                    "cur": "USD",
                    "custUnitP": 100,
                    "classCat": "02",
                    "qnty": 10,
                }
            ],
        }
        return self._post_with_retry(url, request_body)

    def getPDv1(self, coo, coi, hs, fullHS, ref_date):
        url = self._urls["pd_v1"] + self.tenant
        self.reqCounter += 1
        request_body = {
            "reqId": self.reqCounter,
            "coi": coi,
            "coe": coo,
            "coo": coo,
            "imDate": ref_date,
            "mot": "SEA",
            "fullHS": fullHS,
            "hsNumber": hs,
        }
        return self._post_with_retry(url, request_body)

    # Only getPDv1 is used in the main flow; v2 kept for compatibility
    def getPDv2(self, coo, coi, hs, fullHS, ref_date):
        url = self._urls["pd_v2"] + self.tenant
        self.reqCounter += 1
        request_body = {
            "partialHSList": [
                {
                    "reqId": 0,
                    "coi": coi,
                    "coe": coo,
                    "coo": coo,
                    "imDate": ref_date,
                    "exDate": ref_date,
                    "fullHS": fullHS,
                    "hsNumber": hs,
                    "custUnitP": 100,
                }
            ],
            "reqId": 0,
        }
        return self._post_with_retry(url, request_body)

    # ── Storage ───────────────────────────────────────────────────────────────

    def getFromStorage(self):
        return self.output

    def putInStorage(self, coo, coi, hs, custUnitP, cur, qnty, ref_date, status, comment, response, tx_id=None):
        base = {
            "coo": coo,
            "coi": coi,
            "hs": hs,
            "custUnitP": custUnitP,
            "cur": cur,
            "qnty": qnty,
            "date": ref_date,
            "status": status,
            "comment": comment,
        }
        if tx_id is not None:
            base["_tx_id"] = str(tx_id)

        # Preserve HS alternative when caller embeds it in the response dict
        if isinstance(response, dict) and response.get("hsNum"):
            base["hsNum"] = response.get("hsNum")

        def _store(row):
            self.output[len(self.output)] = row

        if status != 200:
            if not isinstance(response, dict) and response not in (None, ""):
                base["response_text"] = str(response)[:500]
            _store(base)
            return

        if not isinstance(response, dict):
            if response not in (None, ""):
                base["response_text"] = str(response)[:500]
            _store(base)
            return

        lines = self._as_list(response.get("line"))
        if not lines:
            _store(base)
            return

        stored_tax_rows = 0
        for line in lines:
            if not isinstance(line, dict):
                continue
            for prog in self._as_list(line.get("rateProgram")):
                if not isinstance(prog, dict):
                    continue
                prog_name = prog.get("rateProgName", "")
                for tax in self._as_list(prog.get("rateProgResult")):
                    if not isinstance(tax, dict) or not tax:
                        continue
                    _store({**base, "Program": prog_name, **tax})
                    stored_tax_rows += 1

        if stored_tax_rows == 0:
            _store(base)

    # ── Main cost query ───────────────────────────────────────────────────────

    def getImportCost(self, coo, coi, hs, custUnitP, cur, qnty, ref_date, tx_id=None):
        # ── A) Full HS ──────────────────────────────────────────────────────
        response = self.getICCv1(coo, coi, hs, custUnitP, cur, qnty, ref_date)

        if response.status_code != 200:
            comment = "Error."
            self.putInStorage(coo, coi, hs, custUnitP, cur, qnty, ref_date,
                              response.status_code, comment, response.text, tx_id=tx_id)
            return coo, coi, hs, custUnitP, cur, qnty, response.status_code, comment

        output, json_error = self._safe_json(response)
        if json_error:
            self.putInStorage(coo, coi, hs, custUnitP, cur, qnty, ref_date,
                              "INVALID_JSON", json_error, response.text, tx_id=tx_id)
            return coo, coi, hs, custUnitP, cur, qnty, "INVALID_JSON", json_error

        if self._has_valid_rate_prog_result(output):
            comment = "No issues."
            self.putInStorage(coo, coi, hs, custUnitP, cur, qnty, ref_date,
                              response.status_code, comment, output, tx_id=tx_id)
            return coo, coi, hs, custUnitP, cur, qnty, response.status_code, comment

        # ── B) Partial HS loop ──────────────────────────────────────────────
        for i in range(len(hs) - 1, 5, -1):
            partial_resp = self.getICCv1(coo, coi, hs[:i], custUnitP, cur, qnty, ref_date)
            if partial_resp.status_code != 200:
                _logger.warning("Partial HS %s returned HTTP %d — skipping.", hs[:i], partial_resp.status_code)
                continue
            partial_output, json_error = self._safe_json(partial_resp)
            if json_error:
                _logger.warning("Partial HS %s: %s — skipping.", hs[:i], json_error)
                continue
            if self._has_valid_rate_prog_result(partial_output):
                comment = "Partial HS match."
                self.putInStorage(coo, coi, hs, custUnitP, cur, qnty, ref_date,
                                  partial_resp.status_code, comment, partial_output, tx_id=tx_id)
                return coo, coi, hs, custUnitP, cur, qnty, partial_resp.status_code, comment

        # ── C) Partial Duty fallback ────────────────────────────────────────
        pd_response = self.getPDv1(coo, coi, hs, "N", ref_date)

        if pd_response.status_code != 200:
            comment = "Partial duty fallback failed."
            self.putInStorage(coo, coi, hs, custUnitP, cur, qnty, ref_date,
                              pd_response.status_code, comment, pd_response.text, tx_id=tx_id)
            return coo, coi, hs, custUnitP, cur, qnty, pd_response.status_code, comment

        pd_output, json_error = self._safe_json(pd_response)
        if json_error:
            self.putInStorage(coo, coi, hs, custUnitP, cur, qnty, ref_date,
                              "INVALID_JSON", json_error, pd_response.text, tx_id=tx_id)
            return coo, coi, hs, custUnitP, cur, qnty, "INVALID_JSON", json_error

        if self._as_list(pd_output.get("rateProgResult")):
            comment = "E2Open-provided alternative."
            used_hs = self._extract_pd_alternative_hs(pd_output, hs)
            icc_response = self.getICCv1(coo, coi, used_hs, custUnitP, cur, qnty, ref_date)
            if icc_response.status_code != 200:
                self.putInStorage(coo, coi, hs, custUnitP, cur, qnty, ref_date,
                                  icc_response.status_code, comment, icc_response.text, tx_id=tx_id)
                return coo, coi, hs, custUnitP, cur, qnty, icc_response.status_code, comment
            icc_data, json_error = self._safe_json(icc_response)
            if json_error:
                self.putInStorage(coo, coi, hs, custUnitP, cur, qnty, ref_date,
                                  "INVALID_JSON", json_error, icc_response.text, tx_id=tx_id)
                return coo, coi, hs, custUnitP, cur, qnty, "INVALID_JSON", json_error
            icc_data["hsNum"] = used_hs
            self.putInStorage(coo, coi, hs, custUnitP, cur, qnty, ref_date,
                              icc_response.status_code, comment, icc_data, tx_id=tx_id)
            return coo, coi, hs, custUnitP, cur, qnty, icc_response.status_code, comment

        # ── D) No result ────────────────────────────────────────────────────
        comment = "No info can be found."
        self.putInStorage(coo, coi, hs, custUnitP, cur, qnty, ref_date,
                          pd_response.status_code, comment, pd_output, tx_id=tx_id)
        return coo, coi, hs, custUnitP, cur, qnty, pd_response.status_code, comment


if __name__ == "__main__":
    import os
    _user = os.environ.get("E2OPEN_USERNAME", "")
    _pwd  = os.environ.get("E2OPEN_PASSWORD", "")
    _tnt  = os.environ.get("E2OPEN_TENANT", "")
    _env  = os.environ.get("E2OPEN_ENV", "UAT")
    s = E2OpenSession(_user, _pwd, _tnt, _env)
    v = s.getICCv1("FR", "US", "8518302000", "100", "USD", "100", "2025-11-25").json()
    print(v)
