import requests
import json
import configparser
import os
import sys
import argparse

#output functions
def pp(output, format):
	if format == "json":
		print (json.dumps(output, indent=2))
	else:
		print(output)
def serializeOutput(filePath, output, format):
	f = open(filePath, "w")
	if format == "json":
		f.write(json.dumps(output, indent=2))
	else:
		f.write(output)
	f.close

#get command line args
argParse = argparse.ArgumentParser()
argParse.add_argument("-t", help="Request type, accepts collection, seed, crawl, host_rule, scope_rule. Defaults to collection.")
argParse.add_argument("-u", help="Archive-it username. Optional override of local_settings.cfg")
argParse.add_argument("-p", help="Archive-it password. Optional override of local_settings.cfg")
argParse.add_argument("-a", help="Archive-it account number. Optional override of local_settings.cfg")
argParse.add_argument("-l", help="Option URL Params limiters for limiting responses to specific collections.", nargs='*')
argParse.add_argument("-f", help="Format of data, accepts json, xml, csv. Defaults to json.")
argParse.add_argument("-o", help="Path to output file to serialize data to a text file.")
args = argParse.parse_args()
	
# get local_settings
__location__ = os.path.dirname(os.path.abspath(__file__))
configPath = os.path.join(__location__, "local_settings.cfg")
#check for creds in flags
if args.u and args.p and args.a:
	aitAccount = str(args.a).strip()
	aitUser = str(args.u).strip()
	aitPassword = str(args.p).strip()
elif os.path.isfile(configPath):
	#else check for creds in configfile
	config = configparser.ConfigParser()
	config.read(configPath)

	#Archive-It
	aitAccount = config.get('Archive-It', 'account')
	aitUser = config.get('Archive-It', 'user')
	aitPassword = config.get('Archive-It', 'password')
else:
	print ("No Archive-It credentials entered. ")

#setup Archive-It auth session
aitSession = requests.Session()
aitSession.auth = (str(aitUser), str(aitPassword))

# build the url from options
rootURL =  "https://partner.archive-it.org/api/"
if args.t:
	inputType = str(args.t).lower().strip()
	if inputType == "collection":
		requestType = "collection"
	elif inputType == "seed":
		requestType = "seed"
	elif inputType == "host_rule":
		requestType = "host_rule"
	elif inputType == "scope_rule":
		requestType = "scope_rule"
	elif inputType == "crawl":
		requestType = "crawl_job"
	else:
		print ("ERROR: invalid request type " + str(args.t))
		print("Please try again.")
		sys.exit()
else:
	requestType = "collection"

requestURL = rootURL + requestType
requestURL = requestURL + "?account=" +  str(aitAccount)
if args.l:
	for param in args.l:
		if not str(param).lower().strip().startswith("&"):
			requestURL = requestURL + "&" + str(param).strip()
		else:
			requestURL = requestURL + str(param).strip()
if args.f:
	print args.f
	if args.f.lower().strip() == "xml":
		format = "xml"
		requestURL = requestURL + "&format=xml"
	elif args.f.lower().strip() == "csv":
		format = "csv"
		requestURL = requestURL + "&format=csv"
	else:
		format = "json"
else:
	format = "json"
	
#make actual request
print ("requesting " + requestURL)
requestResult = aitSession.get(requestURL)
if requestResult.status_code != requests.codes.ok:
	print  ("There was an error with your request, reponse --> " + str(requestResult.status_code))
	requestResult.raise_for_status()
else:
	#get data response
	if format == "json":
		requestData = requestResult.json()
	else:
		requestData = requestResult.text

	#output to file or print to console
	if args.o:
		serializeOutput(args.o, requestData, format)
	else:
		pp(requestData, format)