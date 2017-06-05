import requests
import json
	
#Archive-It creds
aitAccount = ""
aitUser = ""
aitPassword = ""

#setup Archive-It auth session
aitSession = requests.Session()
if len(aitUser) > 0 and len(aitUser) > 0 and len(aitUser) > 0:
	aitSession.auth = (str(aitUser), str(aitPassword))

# URL to request
requestURL = "https://partner.archive-it.org/api/collection?id=3308"

#make actual request
print ("requesting " + requestURL)
requestResult = aitSession.get(requestURL)

#checking for errors
if requestResult.status_code != requests.codes.ok:
	print  ("There was an error with your request, reponse --> " + str(requestResult.status_code))
	requestResult.raise_for_status()
else:
	# pretty print json to console
	print (json.dumps(requestResult.json(), indent=2))