
import requests
import datetime
import time
from datetime import date

class E2OpenSession(requests.Session):
    def __init__(self):
        requests.Session.__init__(self)
        self.username = None
        self.password = None
        self.tenant = None 
        self.token = ""
        self.tokenExpires = ""
        self.tokenCounter = 0
        self.reqCounter=0
        self.output = {}
        self.credentialize()
        self.getToken()
        
    def credentialize(self):
        
        #ACCENTURE cred
        self.username = "6170b797-0c3d-478f-925e-f255cd789efb"
        self.password = "75ac67e5-772f-42fa-9de1-3c429afe4ef4"
        self.tenant = "3129a17d-6155-4507-b8ea-6360f6a8948b"
        return
    
    def getToken(self):
        #UAT
        url = "https://api-uat.amberroad.com/oauth/token"
        
        params = {
            "grant_type": "client_credentials",
            "User ID": self.username,
            "Password": self.password,
            "Tenant id": self.tenant
        }
        response = self.get(url, params=params, auth=requests.auth.HTTPBasicAuth(self.username, self.password))
        self.token = response.json()["access_token"]
        self.tokenExpires = datetime.datetime.now() + datetime.timedelta(seconds=response.json()['expires_in'])
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.tokenCounter += 1
        print(f"Token number: {self.tokenCounter}, valid until {self.tokenExpires}")
    
    def getICCv1(self, coo, coi, hs, custUnitP, cur, qnty, ref_date):
        # API endpoint for calculating import cost
        #UAT
        url = "https://api-uat.amberroad.com/icc/v1/calculateImportCost?tId="+self.tenant
        self.reqCounter += 1        
        # Request body dictionary
        request_body = {
            'reqId': 0,
            'coi': coi,
            'coe': coo,
            'coo': coo,
            'imDate': ref_date,
            'exDate': ref_date,
            'line': [
                {
                    'hs': [
                        {
                            'relatedHs': 0,
                            'seq': 0,
                            'hsNum': hs
                        },
                    ],
                    "cur": cur,
                    "custUnitP": str(float(custUnitP) / float(qnty)), #Division of customs value and qnty in order to take qnty as weight 
                    "classCat": "02",
                    "qnty": qnty
                },
            ],
        }
        # Make the POST request
        attempt = 0 
        while True:
            attempt += 1
            try:
                response = self.post(url, headers=self.headers, json=request_body)
                if response.status_code==401:
                    self.getToken()
                    response = self.post(url, headers=self.headers, json=request_body)
                break
            except requests.exceptions.ConnectionError as e:
                print(f"Connection lost. Retry ({attempt})")
                if attempt<3:
                    time.sleep((2 ** attempt))
                    continue 
                # Check for user confirmation before retrying
                user_input = input("Connection lost! Check your internet connection and press any key to retry, or 'n' to exit: ")
                if user_input.lower() == 'n':
                    print("Exiting...")
                    break  # Exit the loop on user confirmation
        return response
    #Only using getICCv1
    def getICCv2(self, coo, coi, hs, ref_date):
        # API endpoint for calculating import cost
        url = "https://api-uat.amberroad.com/icc/v2/calculateImportCost?tId="+self.tenant
        self.reqCounter += 1        
        # Request body dictionary
        request_body = {
            'reqId': 0,
            'coi': coi,
            'coe': coo,
            'coo': coo,
            'imDate': ref_date,
            'exDate': ref_date,
            'line': [
                {
                    'hs': [
                        {
                            'seq': 0,
                            'hsNum': hs
                        },
                    ],
                    "cur": "USD",
                    "custUnitP": 100,
                    "classCat": "02",
                    "qnty": 10
                },
            ],
        }
        
        # Make the POST request
        attempt = 0 
        while True:
            attempt += 1
            try:
                response = self.post(url, headers=self.headers, json=request_body)
                if response.status_code==401:
                    self.getToken()
                    response = self.post(url, headers=self.headers, json=request_body)
                break
            except requests.exceptions.ConnectionError as e:
                print(f"Connection lost. Retry ({attempt})")
                if attempt<3:
                    time.sleep((2 ** attempt))
                    continue 
                # Check for user confirmation before retrying
                user_input = input("Connection lost! Check your internet connection and press any key to retry, or 'n' to exit: ")
                if user_input.lower() == 'n':
                    print("Exiting...")
                    break  # Exit the loop on user confirmation
        return response
            
    def getPDv1(self, coo, coi, hs, fullHS, ref_date):
        # API endpoint for calculating import cost
        #API
        url = "https://api-uat.amberroad.com/icc/v1/partialDuty?tId="+self.tenant
        self.reqCounter += 1        
        # Request body dictionary
        request_body = {
            "reqId": self.reqCounter,
            "coi": coi,
            "coe": coo,
            "coo": coo,
            "imDate": ref_date,
            "mot": "SEA",
            "fullHS":fullHS,
            "hsNumber":hs,
        } 
        # Make the POST request
        attempt = 0 
        while True:
            attempt += 1
            try:
                response = self.post(url, headers=self.headers, json=request_body)
                if response.status_code==401:
                    self.getToken()
                    response = self.post(url, headers=self.headers, json=request_body)
                break
            except requests.exceptions.ConnectionError as e:
                print(f"Connection lost. Retry ({attempt})")
                if attempt<3:
                    time.sleep((2 ** attempt))
                    continue 
                # Check for user confirmation before retrying
                user_input = input("Connection lost! Check your internet connection and press any key to retry, or 'n' to exit: ")
                if user_input.lower() == 'n':
                    print("Exiting...")
                    break  # Exit the loop on user confirmation

        return response
    #only using getPDv1
    def getPDv2(self, coo, coi, hs, fullHS, ref_date):
        # API endpoint for calculating import cost
        url = "https://api-uat.amberroad.com/icc/v2/partialDuty?tId="+self.tenant
        self.reqCounter += 1        
        # Request body dictionary
        request_body = {
            'partialHSList': [
                {
                    'reqId': 0,
                    'coi': coi,
                    'coe': coo,
                    'coo': coo,
                    'imDate': ref_date,
                    'exDate': ref_date,
                    'fullHS': fullHS,
                    'hsNumber': hs,
                    'custUnitP': 100,
                },
            ],
            'reqId': 0,
        }
        # Make the POST request
        attempt = 0 
        while True:
            attempt += 1
            try:
                response = self.post(url, headers=self.headers, json=request_body)
                if response.status_code==401:
                    self.getToken()
                    response = self.post(url, headers=self.headers, json=request_body)
                break
            except requests.exceptions.ConnectionError as e:
                print(f"Connection lost. Retry ({attempt})")
                if attempt<3:
                    time.sleep((2 ** attempt))
                    continue 
                # Check for user confirmation before retrying
                user_input = input("Connection lost! Check your internet connection and press any key to retry, or 'n' to exit: ")
                if user_input.lower() == 'n':
                    print("Exiting...")
                    break  # Exit the loop on user confirmation

        return response
    
    def getFromStorage(self):
        return self.output
        
    def putInStorage(self, coo, coi, hs, custUnitP, cur,qnty, ref_date, status, comment,response):
        dct = {
            'coo': coo,
            'coi': coi,
            'hs': hs,
            'custUnitP' : custUnitP,
            'cur':cur,
            'qnty':qnty,
            'date': ref_date,
            'status': status,
            'comment': comment,
            }
        if not(status==200):
            idx = len(self.output)
            self.output.update({idx:dct})
            return
        # Loop through each line in response
        for line in response.get('line', []):
            # Loop through each rateProg in the line
            for rate_prog in line.get('rateProgram', []):
                # Check if 'rateProgResult' is either an empty string or an empty list
                rate_prog_result = rate_prog.get('rateProgResult', [])
                if rate_prog_result == "" or rate_prog_result == []:              
                    idx = len(self.output)
                    self.output.update({idx:dct})
                    return
                
        for line in response['line']:
            for prog in line['rateProgram']:
                progName = prog['rateProgName']
                progRates = prog['rateProgResult']
                for tax in progRates:
                    dctProg = {**dct, **{'Program': progName}, **tax}
                    idx = len(self.output)
                    self.output.update({idx: dctProg})
        return
       
    def getImportCost(self, coo, coi, hs, custUnitP, cur, qnty, ref_date):
        response = self.getICCv1(coo, coi, hs, custUnitP, cur, qnty, ref_date)

        # Check for response error
        if response.status_code != 200:
            comment = "Error."
            self.putInStorage(coo, coi, hs, custUnitP, cur,qnty,ref_date, response.status_code, comment, response.text)
            return coo, coi, hs,custUnitP, cur,qnty,response.status_code, comment

        output = response.json()

        def has_valid_rateProgResult(output):
            try:
                lines = output.get('line', [])
                for line in lines:
                    rate_programs = line.get('rateProgram', [])
                    for rp in rate_programs:
                        if rp.get('rateProgResult'):
                            return True
                return False
            except Exception:
                return False

        if has_valid_rateProgResult(output):
            comment = "No issues."
            self.putInStorage(coo, coi, hs,custUnitP, cur, qnty, ref_date, response.status_code, comment, output)
            return coo, coi, hs,custUnitP, cur,qnty,response.status_code, comment

        # Try partial HS match
        for i in range(len(hs) - 1, 5, -1):
            response = self.getICCv1(coo, coi, hs[:i], custUnitP, cur, qnty, ref_date)
            output = response.json()
            if has_valid_rateProgResult(output):
                comment = "Partial HS match."
                self.putInStorage(coo, coi, hs,custUnitP, cur, qnty,ref_date, response.status_code, comment, output)
                return coo, coi, hs,custUnitP, cur,qnty,response.status_code, comment
            
        response = self.getPDv1(coo, coi, hs, "N", ref_date)
        output = response.json()
        if not (output['rateProgResult'] == []):
            comment = "E2Open-provided alternative."
            # Extract the needed fields from original input (they're already given)
            used_coo = coo
            used_coi = coi
            try:
                used_hs = output['rateProgResult'][0]['rateProgResult'][0]['lowValueHS']
            except (IndexError, KeyError):
                used_hs = hs  # fallback to original HS if parsing fails
            
            icc_response = self.getICCv1(used_coo, used_coi, used_hs, custUnitP, cur, qnty, ref_date)
            icc_data = icc_response.json()
            # Store using original HS (hs), but store content with alternative HS used
            icc_data['hsNum'] = used_hs
            self.putInStorage(used_coo, used_coi, hs,custUnitP, cur,qnty, ref_date, icc_response.status_code, comment, icc_data)
            return coo, coi, hs,custUnitP, cur,qnty,icc_response.status_code, comment

        comment = "No info can be found."
        self.putInStorage(coo, coi, hs,custUnitP, cur,qnty, ref_date, response.status_code, comment, output)
        return coo, coi, hs,custUnitP, cur,qnty,response.status_code, comment
     
if __name__=='__main__':
    s = E2OpenSession()
    v = s.getICCv1("FR", "US", "8518302000", "100", "USD", "100","2025-11-25").json()
    #v = s.getICCv1("PL", "KZ", "9403208009", "100", "USD", "10").json()
    #v = s.getPDv1("SE", "MX", "85437099", "n").json()
    #v = s.getPDv2("VN", "IN", "61103010", "y").json()
    #v = s.getPartialDuty("EC", "AR", "3905120000")
    #v = s.getImportCost("PL", "KZ", "9403208009", "100", "USD", "10")
    print(v)
    #print(o)



    
    
    


