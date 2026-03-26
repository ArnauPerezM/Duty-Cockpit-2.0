
import requests
import datetime
import time

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

    def getToken(self):
        url = self._urls["token"]
        params = {
            "grant_type": "client_credentials",
            "User ID": self.username,
            "Password": self.password,
            "Tenant id": self.tenant,
        }
        response = self.get(url, params=params, auth=requests.auth.HTTPBasicAuth(self.username, self.password))
        self.token = response.json()["access_token"]
        self.tokenExpires = datetime.datetime.now() + datetime.timedelta(seconds=response.json()["expires_in"])
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.tokenCounter += 1
        print(f"Token number: {self.tokenCounter}, valid until {self.tokenExpires}")

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
            except requests.exceptions.ConnectionError:
                print(f"Connection lost. Retry ({attempt})")
                if attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise

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

    def getFromStorage(self):
        return self.output

    def putInStorage(self, coo, coi, hs, custUnitP, cur, qnty, ref_date, status, comment, response):
        dct = {
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
        if not (status == 200):
            idx = len(self.output)
            self.output.update({idx: dct})
            return
        for line in response.get("line", []):
            for rate_prog in line.get("rateProgram", []):
                rate_prog_result = rate_prog.get("rateProgResult", [])
                if rate_prog_result == "" or rate_prog_result == []:
                    idx = len(self.output)
                    self.output.update({idx: dct})
                    return
        for line in response["line"]:
            for prog in line["rateProgram"]:
                progName = prog["rateProgName"]
                progRates = prog["rateProgResult"]
                for tax in progRates:
                    dctProg = {**dct, **{"Program": progName}, **tax}
                    idx = len(self.output)
                    self.output.update({idx: dctProg})

    def getImportCost(self, coo, coi, hs, custUnitP, cur, qnty, ref_date):
        response = self.getICCv1(coo, coi, hs, custUnitP, cur, qnty, ref_date)

        if response.status_code != 200:
            comment = "Error."
            self.putInStorage(coo, coi, hs, custUnitP, cur, qnty, ref_date, response.status_code, comment, response.text)
            return coo, coi, hs, custUnitP, cur, qnty, response.status_code, comment

        output = response.json()

        def has_valid_rateProgResult(output):
            try:
                for line in output.get("line", []):
                    for rp in line.get("rateProgram", []):
                        if rp.get("rateProgResult"):
                            return True
                return False
            except Exception:
                return False

        if has_valid_rateProgResult(output):
            comment = "No issues."
            self.putInStorage(coo, coi, hs, custUnitP, cur, qnty, ref_date, response.status_code, comment, output)
            return coo, coi, hs, custUnitP, cur, qnty, response.status_code, comment

        for i in range(len(hs) - 1, 5, -1):
            response = self.getICCv1(coo, coi, hs[:i], custUnitP, cur, qnty, ref_date)
            output = response.json()
            if has_valid_rateProgResult(output):
                comment = "Partial HS match."
                self.putInStorage(coo, coi, hs, custUnitP, cur, qnty, ref_date, response.status_code, comment, output)
                return coo, coi, hs, custUnitP, cur, qnty, response.status_code, comment

        response = self.getPDv1(coo, coi, hs, "N", ref_date)
        output = response.json()
        if not (output["rateProgResult"] == []):
            comment = "E2Open-provided alternative."
            used_coo = coo
            used_coi = coi
            try:
                used_hs = output["rateProgResult"][0]["rateProgResult"][0]["lowValueHS"]
            except (IndexError, KeyError):
                used_hs = hs
            icc_response = self.getICCv1(used_coo, used_coi, used_hs, custUnitP, cur, qnty, ref_date)
            icc_data = icc_response.json()
            icc_data["hsNum"] = used_hs
            self.putInStorage(used_coo, used_coi, hs, custUnitP, cur, qnty, ref_date, icc_response.status_code, comment, icc_data)
            return coo, coi, hs, custUnitP, cur, qnty, icc_response.status_code, comment

        comment = "No info can be found."
        self.putInStorage(coo, coi, hs, custUnitP, cur, qnty, ref_date, response.status_code, comment, output)
        return coo, coi, hs, custUnitP, cur, qnty, response.status_code, comment


if __name__ == "__main__":
    import os
    _user = os.environ.get("E2OPEN_USERNAME", "")
    _pwd  = os.environ.get("E2OPEN_PASSWORD", "")
    _tnt  = os.environ.get("E2OPEN_TENANT", "")
    _env  = os.environ.get("E2OPEN_ENV", "UAT")
    s = E2OpenSession(_user, _pwd, _tnt, _env)
    v = s.getICCv1("FR", "US", "8518302000", "100", "USD", "100", "2025-11-25").json()
    print(v)
