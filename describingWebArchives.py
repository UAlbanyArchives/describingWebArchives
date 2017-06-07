# -*- coding: utf-8 -*-
from archives_tools import aspace as AS
from archives_tools import dacs
import os
import configparser
import requests
from bs4 import BeautifulSoup
import json
from operator import itemgetter
import sys
import traceback
import datetime
import gc

# version dependant imports
if sys.version_info[0] < 3:
	# Python 2
	from urlparse import urlparse
else:
	# Python 3
	from urllib.parse import urlparse

#main try for script notifier
try:

	# get local_settings
	__location__ = os.path.dirname(os.path.abspath(__file__))
	configPath = os.path.join(__location__, "local_settings.cfg")
	config = configparser.ConfigParser()
	config.read(configPath)

	#ASpace
	baseURL = config.get('ArchivesSpace', 'baseURL')
	repo = config.get('ArchivesSpace', 'repository')
	user = config.get('ArchivesSpace', 'user')
	password = config.get('ArchivesSpace', 'password')

	# Set login tuple for ASpace lib
	aspaceLogin = (baseURL, user, password)

	#get ASpace Session
	session = AS.getSession(aspaceLogin)

	#Archive-It
	aitAccount = config.get('Archive-It', 'account')
	aitUser = config.get('Archive-It', 'user')
	aitPassword = config.get('Archive-It', 'password')
	aitSubject = config.get('Archive-It', 'target_subject')
	aitSource = config.get('Archive-It', 'subject_source')
	extentType = config.get('Archive-It', 'extent_type')
	phystechNote = config.get('Archive-It', 'access_requirements')
	acqinfoDefault = config.get('Archive-It', 'acqinfo_note')
	warcNote = config.get('Archive-It', 'warc_restrict_note')
	generalANote = config.get('Archive-It', 'general_internet_archive_note')

	waybackCDX = "https://web.archive.org/cdx/search/cdx?url="
	aitCDX = ["http://wayback.archive-it.org/", "/timemap/cdx?url="]

	#setup Archive-It auth session
	aitSession = requests.Session()
	aitSession.auth = (aitUser, aitPassword)



	#get collection data
	print ("Requesting Collection Data")
	collectionData = aitSession.get("https://partner.archive-it.org/api/collection?format=json&account=" + aitAccount).json()
	#get seed list
	print ("Requesting Seed List")
	seedList = aitSession.get("https://partner.archive-it.org/api/seed?format=json").json()
	print ("Requesting Host Rules")
	hostRules = aitSession.get("https://partner.archive-it.org/api/host_rule?format=json").json()
	print ("Requesting Seed Rules")
	seedRules = aitSession.get("https://partner.archive-it.org/api/scope_rule?format=json").json()

	#resolves collection-level extent issue with multiple web archives records overwriting collection-level extents
	multipleWebExtents = {}

	# find web archives records
	for result in AS.withSubject(session, repo, aitSubject, aitSource, aspaceLogin):
		recordURL = ""
		seedCheck = False
		aitCollections = []
		accessNote = False
		
		print ("Found Web Archives Record: " + result.title)
		
		for note in result.notes:
			if note.type == "phystech":
				if "label" in note.keys():
					if note.label.lower().strip() == "url":
						recordURL = note.subnotes[0].content.strip()
						if not recordURL.lower().strip().startswith("http"):
							recordURL = "http://" + recordURL
					elif note.label.lower().strip() == "access requirements":
						accessNote = True
		if accessNote == False:
			result = AS.makeMultiNote(result, "phystech", phystechNote, "Access Requirements")
		
		if len(recordURL) == 0:
			print ("ERROR: could not find URL for web archives record " + result.uri)
		else:
			for seed in seedList:
				if seed["canonical_url"] == recordURL:
					seedCheck = True
					seedNumber = seed["id"]
					aitCollections.append(seed["collection"])
					
			#if the URL isn't a seed, check to find seeds with the same domains to find possible collections
			if seedCheck == False:
				domain = urlparse(recordURL).netloc
				for seed in seedList:
					if domain in seed["canonical_url"]:
						if seed["collection"] not in aitCollections:
							#check CDX to make sure URL can be found in this collection
							cdxURL = aitCDX[0] + str(seed["collection"]) + aitCDX[1] + recordURL
							cdxTest = requests.get(cdxURL)
							if len(cdxTest.text.split("\n")) > 1:
								aitCollections.append(seed["collection"])
					
			if seedCheck == True:
				#for URLs that are seeds
				for aitCollection in aitCollections:
					for collection in collectionData:
						if collection["id"] == aitCollection:
							acqinfo = acqinfoDefault + "\n\nThis item is a seed within the " + collection["name"] + " collection."
							seedCount = 0
							for seed in seedList:
								if seed["collection"] == collection["id"]:
									if not recordURL.lower().strip() in seed["canonical_url"].lower().strip():
										seedCount += 1
										if seedCount == 1:
											acqinfo = acqinfo + "\n\n<b>Other seeds in this collection include:</b> " + seed["canonical_url"]
										else:
											acqinfo = acqinfo + ", " + seed["canonical_url"]
							acqinfo = acqinfo + "\n\n\n<b>Archive-it Collection Details:</b>"
							acqinfo = acqinfo + "\n\n<b>created_date:</b> " + collection["created_date"]
							acqinfo = acqinfo + "\n\n<b>created_by:</b> " + collection["created_by"]
							acqinfo = acqinfo + "\n\n<b>state:</b> " + collection["state"]
							acqinfo = acqinfo + "\n\n<b>last_updated_date:</b> " + collection["last_updated_date"]
							acqinfo = acqinfo + "\n\n<b>last_updated_by:</b> " + collection["last_updated_by"]	
							#print acqinfo
			else:
				#for URLs that are not seeds
				acqinfo = acqinfoDefault + "\n\nThis item is not a seed within an Archive-it collection, but capures of this page are found within: "
				for aitCollection in aitCollections:
					for collection in collectionData:
						if collection["id"] == aitCollection:
							acqinfo = acqinfo + "\n\n<b>collection:</b> " + collection["name"]
							acqinfo = acqinfo + "\n\n<b>created_date:</b> " + collection["created_date"]
							acqinfo = acqinfo + "\n\n<b>created_by:</b> " + collection["created_by"]
							acqinfo = acqinfo + "\n\n<b>state:</b> " + collection["state"]
							acqinfo = acqinfo + "\n\n<b>last_updated_date:</b> " + collection["last_updated_date"]
							acqinfo = acqinfo + "\n\n<b>last_updated_by:</b> " + collection["last_updated_by"]	
			
			
			#update acqinfo note
			acqinfoCount = 0
			for note in result.notes:
				if "type" in note.keys():
					if note["type"] == "acqinfo":
						acqinfoCount += 1
						note.subnotes[0].content = acqinfo
			if acqinfoCount == 0:
				result = AS.makeMultiNote(result, "acqinfo", acqinfo)
			

			##################################
			#add new capture records
			##################################
			
			# set variables needed
			localHashList = []
			hashList = []
			captureCount = 0
			firstDate = 99999999
			lastDate = 0
			
			#get hashs from existing records
			children = AS.getChildren(session, result, aspaceLogin)
			#if the record has children
			if len(children) > 0:
				if "children" in children.keys():
					if len(children.children) > 0:
						for child in children.children:
							childRecord = AS.getArchObj(session, child.record_uri, aspaceLogin)
							#update extent and dates
							captureCount += 1
							if len(childRecord.dates) > 0:
								if int(childRecord.dates[0].begin.replace("-", "")) < firstDate:
									firstDate = int(childRecord.dates[0].begin.replace("-", ""))
								if "end" in childRecord.dates[0].keys():
									if int(childRecord.dates[0].end.replace("-", "")) < lastDate:
										lastDate = int(childRecord.dates[0].end.replace("-", ""))
								else:
									if int(childRecord.dates[0].begin.replace("-", "")) < lastDate:
										lastDate = int(childRecord.dates[0].begin.replace("-", ""))
							#add hashes, so not duplicates
							for oldDAOLink in childRecord.instances:
								if "digital_object" in oldDAOLink.keys():
									oldDAO = AS.getDAO(session, repo, oldDAOLink.digital_object.ref, aspaceLogin)
									if "checksum" in oldDAO.file_versions[0].keys():
										oldHash = oldDAO.file_versions[0].checksum
										if not oldHash in hashList:
											hashList.append(oldHash)
			
			#get all hashes from archive-it collections, so they take preference over general IA captures
			for aitCollection in aitCollections:
				cdxURL = aitCDX[0] + str(aitCollection) + aitCDX[1] + recordURL
				localCDX = requests.get(cdxURL)
				if len(localCDX.text.split("\n")) > 1:
					for capture in localCDX.text.split("\n"):
						if len(capture) > 0:
							hash = capture.split(" ")[5]
							if not hash in localHashList:
								localHashList.append(hash)
								
			#list of new archival object to later sort chonologically and POST to ASpace
			newObjectList = []
			
			#get captures from general IA collections
			iaURL = waybackCDX + recordURL
			iaCDX = requests.get(iaURL)
			if len(iaCDX.text.split("\n")) > 1:
				for iaCapture in iaCDX.text.split("\n"):
					if len(iaCapture) > 0:
						if len(iaCapture.split(" ")) < 6:
							print ("Invalid CDX? could not find hash for " + str(iaCapture))
						else:
							hash = iaCapture.split(" ")[5]
							if not hash in localHashList:
								if not hash in hashList:
									hashList.append(hash)
									captureCount += 1
									timestamp = int(iaCapture.split(" ")[1][:8])
									if int(str(timestamp)[4:][:2]) > 12 or int(str(timestamp)[6:][:2]) > 31:
										print ("		invalid date in CDX: " + str(timestamp))
									else:
										print ("		found new capture: " + str(timestamp))
										fullTimestamp = int(iaCapture.split(" ")[1])
										if timestamp < firstDate:
											firstDate = timestamp
										if timestamp > lastDate:
											lastDate = timestamp
										#create a new Archival Object record
										newRecord = AS.makeArchObj()
										newRecord.publish = True
										newRecord.level = "item"
										if result.jsonmodel_type == "resource":
											newRecord.resource = {"ref": result.uri}
										else:
											newRecord.parent = {"ref": result.uri}
											newRecord.resource = {"ref": result.resource.ref}
										newRecord = AS.makeDate(newRecord, dacs.stamp2DACS(str(timestamp))[1])
										daoURL = "https://web.archive.org/web/" + str(fullTimestamp) + "/" + recordURL
										#get page <title>
										soup = BeautifulSoup(requests.get(daoURL).text, "html.parser")
										#try to get page <title>
										try:
											pageTitle = soup.title.string
										except:
											pageTitle = "&lt;title&gt; not present"	
										newRecord.title = pageTitle
										#try to get data from meta tags
										try:
											scopeNote = ""
											for tag in soup.find_all("meta"):
												if tag.has_attr("name"):
													if "author" in tag.get("name", None).lower():
														authorNote = tag.get("content", None)
														if len(authorNote) > 0:
															scopeNote = scopeNote + "<p><b>Meta tag for author:</b> " + authorNote + "</p>"
													elif "description" in tag.get("name", None).lower():
														descNote = tag.get("content", None)
														if len(descNote) > 0:
															scopeNote = scopeNote + "<p><b>Meta tag for description:</b> " + descNote + "</p>"		
													elif "keywords" in tag.get("name", None).lower():
														keywordsNote = tag.get("content", None)
														if len(keywordsNote) > 0:
															scopeNote = scopeNote + "<p><b>Meta tag for keywords:</b> " + keywordsNote + "</p>"									
													elif "language" in tag.get("name", None).lower():
														langNote = tag.get("content", None)
														if len(langNote) > 0:
															newRecord = AS.makeSingleNote(newRecord, "langmaterial", langNote)
											if len(scopeNote) > 0:
												newRecord = AS.makeMultiNote(newRecord, "scopecontent", scopeNote)
										except:
											pass
										newRecord = AS.makeMultiNote(newRecord, "acqinfo", generalANote)
										newDAO = AS.makeDAO(pageTitle, daoURL, hash, "sha-1")
										newDAO.publish = True
										#post digital object record
										postDAO = AS.postDAO(session, repo, newDAO, aspaceLogin)
										if postDAO.status_code == 200:
											daoURI = postDAO.json()["uri"]
										newRecord = AS.addDAO(newRecord, daoURI)
										#add this record to the new object list:
										newObjectList.append([int(timestamp), newRecord])
								
							
							
			# get captures from archive-it collections
			for aitCollection in aitCollections:
				cdxURL = aitCDX[0] + str(aitCollection) + aitCDX[1] + recordURL
				localCDX = requests.get(cdxURL)
				if len(localCDX.text.split("\n")) > 1:
					for capture in localCDX.text.split("\n"):
						if len(capture) > 0:
							hash = capture.split(" ")[5]
							if not hash in hashList:
								hashList.append(hash)
								captureCount += 1
								timestamp = int(capture.split(" ")[1][:8])
								if int(str(timestamp)[4:][:2]) > 12 or int(str(timestamp)[6:][:2]) > 31:
									print ("		invalid date in CDX: " + str(timestamp))
								else:
									print ("		found new capture: " + str(timestamp))
									fullTimestamp = int(capture.split(" ")[1])
									if timestamp < firstDate:
										firstDate = timestamp
									if timestamp > lastDate:
										lastDate = timestamp
									#create a new Archival Object record
									newRecord = AS.makeArchObj()
									newRecord.level = "item"
									if result.jsonmodel_type == "resource":
										newRecord.resource = {"ref": result.uri}
									else:
										newRecord.parent = {"ref": result.uri}
										newRecord.resource = {"ref": result.resource.ref}
									newRecord = AS.makeDate(newRecord, dacs.stamp2DACS(str(timestamp))[1])
									#scrape page
									gc.collect()
									try:
										daoURL = "https://wayback.archive-it.org/" + str(aitCollection) + "/" + str(fullTimestamp) + "/" + recordURL
										soup = BeautifulSoup(requests.get(daoURL).text, "html.parser")
									except:
										daoURL = "http://wayback.archive-it.org/" + str(aitCollection) + "/" + str(fullTimestamp) + "/" + recordURL
										soup = BeautifulSoup(requests.get(daoURL).text, "html.parser")
									#try to get page <title>
									try:
										pageTitle = soup.title.string
									except:
										pageTitle = "&lt;title&gt; not present"	
									newRecord.title = pageTitle
									#try to get data from meta tags
									try:
										scopeNote = ""
										for tag in soup.find_all("meta"):
											if tag.has_attr("name"):
												if "author" in tag.get("name", None).lower():
													authorNote = tag.get("content", None)
													if len(authorNote) > 0:
														scopeNote = scopeNote + "<p><b>Meta tag for author:</b> " + authorNote + "</p>"		
												elif "description" in tag.get("name", None).lower():
													descNote = tag.get("content", None)
													if len(descNote) > 0:
														scopeNote = scopeNote + "<p><b>Meta tag for description:</b> " + descNote + "</p>"		
												elif "keywords" in tag.get("name", None).lower():
													keywordsNote = tag.get("content", None)
													if len(keywordsNote) > 0:
														scopeNote = scopeNote + "<p><b>Meta tag for keywords:</b> " + keywordsNote + "</p>"							
												elif "language" in tag.get("name", None).lower():
													langNote = tag.get("content", None)
													if len(langNote) > 0:
														newRecord = AS.makeSingleNote(newRecord, "langmaterial", langNote)
										#close parsed html file to prevent memory errors
										soup.decompose()
										gc.collect()
										if len(scopeNote) > 0:
											newRecord = AS.makeMultiNote(newRecord, "scopecontent", scopeNote)
									except:
										pass
									crawlID = capture.split(" ")[10].split("-")[3]
									if crawlID.lower().startswith("job"):
										crawlID = crawlID[3:]
									
									def addNote(note, object, key, label = None):
										if key in object.keys():
											if label is None:
												note = note + "\n\n" + key + ": " +  str(object[key])
											else:
												note = note + "\n\n" + label + ": " +  str(object[key])
										return note
								
								#ACQINFO section
															
								#crawl rules here
								ruleCheck = False
								for rule in hostRules:
									if rule["collection"] == aitCollection:
										if int(timestamp) > int(rule["created_date"].split("T")[0].replace("-", "")):
											ruleCheck = True
								if ruleCheck == True:
									crawlAcqinfo = "<b>Crawl Rules</b>"
								else:
									crawlAcqinfo = "\n\n This item had no crawl rules."
								for rule in hostRules:
									if rule["collection"] == aitCollection:
										#check if rule existed during crawl
										if int(timestamp) > int(rule["created_date"].split("T")[0].replace("-", "")):
											if rule["ignore_robots"] == True:
												crawlAcqinfo = crawlAcqinfo + "\n\nIgnore Robots.txt for " + rule["host"] + " (last updated " + rule["last_updated_date"].split("T")[0] + ")"
											elif not rule["block"] == None:
												crawlAcqinfo = crawlAcqinfo + "\n\nBlock host " + rule["host"]
											elif not rule["document_limit"] == None:
												#document limit
												crawlAcqinfo = crawlAcqinfo + "\n\nLimit host " + rule["host"] + " to " + str(rule["document_limit"]) + " documents"
											elif not rule["byte_limit"] == None:
												crawlAcqinfo = crawlAcqinfo + "\n\nLimit date for host " + rule["host"] + " to " + str(rule["byte_limit"]) + " bytes"
											elif len(rule["crawl_scope_rules"]) > 0:
												crawlAcqinfo = crawlAcqinfo + "\n\nHost Rule Type " + str(rule["crawl_scope_rules"][0]["rule_type"]) + " " + str(rule["crawl_scope_rules"][0]["format"]) + " " +  str(rule["crawl_scope_rules"][0]["definition"]) + " (last updated " + str(rule["crawl_scope_rules"][0]["last_updated_date"]).split("T")[0] + ")"
										
								if seedCheck == True:
									for seedRule in seedRules:
										if str(seedRule["seed"]) == str(seedNumber):
											if crawlAcqinfo is None:
												crawlAcqinfo = ""
											if seedRule["type"] == True:
												crawlAcqinfo = crawlAcqinfo + "\n\nSeed Rule Type " + str(seedRule["type"]) + " (last updated " + seedRule["last_updated_date"].split("T")[0] + ")"
											else:
												crawlAcqinfo = crawlAcqinfo + "\n\nSeed Rule Type " + str(seedRule["type"]) + ": " + str(seedRule["value"]) + " (last updated " + seedRule["last_updated_date"].split("T")[0] + ")"
											
								
								# crawl acqinfo here
								try:
									crawlResponse = aitSession.get("https://partner.archive-it.org/api/crawl_job/" + crawlID + "?format=json")
								except:
									#try again!
									crawlResponse = aitSession.get("http://partner.archive-it.org/api/crawl_job/" + crawlID + "?format=json")
									
								if crawlResponse.status_code != 200:
									noCrawlNote = "The CDX index for this capture did not contain crawl information."
									if crawlAcqinfo is None:
										crawlAcqinfo = noCrawlNote
									else:
										crawlAcqinfo = crawlAcqinfo + "\n\n" + noCrawlNote
								else:
									crawlData = crawlResponse.json()
									
									#crawl ID
									crawlAcqinfo = "crawl: " + crawlID + "\n\n\n" + crawlAcqinfo
								
									
									#times
									crawlAcqinfo = crawlAcqinfo + "\n\n\n<b>Crawl Times</b>"
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "start_date")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "original_start_date")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "last_resumption")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "processing_end_date")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "end_date")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "elapsed_ms")
									
									#crawl types
									crawlAcqinfo = crawlAcqinfo + "\n\n\n<b>Crawl Types</b>"
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "type")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "recurrence_type")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "pdfs_only")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "test")						
									
									#limits
									crawlAcqinfo = crawlAcqinfo + "\n\n\n<b>Crawl Limits</b>"
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "time_limit")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "document_limit")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "byte_limit")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "crawl_stop_requested")
																	
									#results
									crawlAcqinfo = crawlAcqinfo + "\n\n\n<b>Crawl Results</b>"
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "status")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "discovered_count")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "novel_count")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "duplicate_count")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "resumption_count")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "queued_count")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "downloaded_count")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "download_failures")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "warc_revisit_count")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "warc_url_count")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "total_data_in_kbs")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "duplicate_bytes")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "warc_compressed_bytes")	
									
									
									#technical details
									crawlAcqinfo = crawlAcqinfo + "\n\n\n<b>Crawl Technical Details</b>"
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "doc_rate")
									crawlAcqinfo = addNote(crawlAcqinfo, crawlData, "kb_rate")
									

								newRecord = AS.makeMultiNote(newRecord, "acqinfo", crawlAcqinfo)
								
								#make new digital object
								newDAO = AS.makeDAO(pageTitle, daoURL, hash, "sha-1")
								newDAO.publish = True
								#post digital object record
								postDAO = AS.postDAO(session, repo, newDAO, aspaceLogin)
								if postDAO.status_code == 200:
									daoURI = postDAO.json()["uri"]
								newRecord = AS.addDAO(newRecord, daoURI)
								
								#add this record to the new object list:
								newObjectList.append([int(timestamp), newRecord])
								
								#make new WARC record
								newWARC = AS.makeArchObj()
								newWARC.publish = True
								newWARC.level = "item"
								if result.jsonmodel_type == "resource":
									newWARC.resource = {"ref": result.uri}
								else:
									newWARC.parent = {"ref": result.uri}
									newWARC.resource = {"ref": result.resource.ref}							
								newWARC = AS.makeDate(newWARC, dacs.stamp2DACS(str(timestamp))[1])
								newWARC.title = "WARC file for " + pageTitle
								if len(crawlAcqinfo) > 0:
									newWARC = AS.makeMultiNote(newWARC, "acqinfo", crawlAcqinfo)
								newWARC = AS.makeMultiNote(newWARC, "phystech", warcNote)
								#add this record to the new object dict:
								newObjectList.append([int(timestamp), newWARC])

			
			#post all new objects back to ASpace
			print ("posting new archival object records")
			for sortedRecord in sorted(newObjectList, key=itemgetter(0)):
				postRecord = sortedRecord[1]
				postAO = AS.postArchObj(session, repo, postRecord, aspaceLogin)
				if str(postAO.status_code).strip() == "200":
					try:
						recordDate = postRecord["dates"][0]["expression"]
					except:
						try:
							recordDate = postRecord["dates"][0]["begin"]
						except:
							recordDate = "no date"
					try:
						print ("\t" + str(postAO.status_code).strip() + " --> posted " + postRecord["dates"][0]["begin"] + ", " + postRecord.title)
					except:
						print ("\t" + str(postAO.status_code).strip() + " --> posted " + postRecord["dates"][0]["begin"] + ", (title with unicode)")
				else:
					raise ValueError(str(postAO) + " --> failed to post new archival_object:\n\n" + postRecord)
			
			def updateDate(object, firstDate, lastDate):	
				#Update record date range
				if firstDate == 99999999 or lastDate == 0:
					#no new date records
					pass
				else:
					#make a date object if none exists
					if len(object.dates) == 0:
						if firstDate == lastDate:
							object = AS.makeDate(object, dacs.stamp2DACS(str(firstDate))[1])
						else:
							object = AS.makeDate(object, dacs.stamp2DACS(str(firstDate))[1], dacs.stamp2DACS(str(lastDate))[1])
					#update begin date
					beginCompare = int(object.dates[0]["begin"].replace("-", ""))
					if len(str(beginCompare)) == 6:
						beginCompare = int(str(beginCompare) + "00")
					elif len(str(beginCompare)) == 8:
						beginCompare = int(str(beginCompare) + "0000")
					if beginCompare > firstDate:
						object.dates[0]["begin"] = dacs.stamp2DACS(str(firstDate))[1]
					#make it a single date for one crawl or a range for many
					if firstDate == lastDate:
						if object.dates[0]["date_type"] == "single":
							#update date expression for single date
							object.dates[0]["expression"] = dacs.stamp2DACS(str(firstDate))[0]
						else:
							if "end" in object.dates[0].keys():
								endCompare = int(object.dates[0]["end"].replace("-", ""))
								if len(str(endCompare)) == 6:
									endCompare = int(str(endCompare) + "00")
								elif len(str(endCompare)) == 8:
									endCompare = int(str(endCompare) + "0000")
								if endCompare < lastDate:
									object.dates[0]["end"] = dacs.stamp2DACS(str(lastDate))[1]
							else:
								object.dates[0]["end"] = dacs.stamp2DACS(str(lastDate))[1]	
							#update date expression for range
							object.dates[0]["expression"] = dacs.stamp2DACS(str(firstDate))[0] + " - " +  dacs.stamp2DACS(str(lastDate))[0]
					else:
						object.dates[0]["date_type"] = "inclusive"
						#if theres an end date, update it, if not add it
						if "end" in object.dates[0].keys():
							endCompare = int(object.dates[0]["end"].replace("-", ""))
							if len(str(endCompare)) == 6:
								endCompare = int(str(endCompare) + "00")
							elif len(str(endCompare)) == 8:
								endCompare = int(str(endCompare) + "0000")
							if endCompare < lastDate:
								object.dates[0]["end"] = dacs.stamp2DACS(str(lastDate))[1]
						else:
							object.dates[0]["end"] = dacs.stamp2DACS(str(lastDate))[1]	
						#update date expression for range
						object.dates[0]["expression"] = dacs.stamp2DACS(str(firstDate))[0] + " - " +  dacs.stamp2DACS(str(lastDate))[0]
				return object
						
			
			def updateExtent(object, number, extentType):		
				#update record extents
				if len(object.extents) == 0:
					object = AS.makeExtent(object, str(captureCount), extentType)
				else:
					typeMatch = False
					for extent in object.extents:
						if extent.extent_type.lower().strip() == str(extentType).lower().strip():
							extent.number = str(number).strip()
							typeMatch = True
					if typeMatch == False:
						object = AS.makeExtent(object, str(captureCount), extentType)
				return object
			
			result = updateDate(result, firstDate, lastDate)
			result = updateExtent(result, str(captureCount), extentType)
			
			#post final web archives record back to ASpace
			post = AS.postObject(session, result, aspaceLogin)
			if str(post).strip() == "200":
				print (str(post).strip() + " --> posted updated web archives object:  " + result.title)
			else:
				raise ValueError(str(post.status_code) + " --> failed to post updated web archives object:\n\n" + result)
			
			#update parents
			if result.jsonmodel_type == "archival_object":
				
				#update patent archival object if any
				if "parent" in result.keys():
					parentURI = result.parent.ref
					parent = AS.getArchObj(session, parentURI, aspaceLogin)
					parent = updateDate(parent, firstDate, lastDate)
					parent = updateExtent(parent, str(captureCount), extentType)
					postParent = AS.postArchObj(session, repo, parent, aspaceLogin)
					if str(postParent.status_code).strip() == "200":
						print (str(postParent.status_code).strip() + " --> posted updated patent record: " + parent.title)
					else:
						raise ValueError(str(postParent) + " --> failed to post updated patent record:\n\n" + parent)
						
				#update resource record
				resourceURI = result.resource.ref
				resource = AS.getResource(session, repo, resourceURI.split("/resources/")[1], aspaceLogin)
				resource = updateDate(resource, firstDate, lastDate)
				if resource.id_0 in multipleWebExtents.keys():
					captureCount = captureCount + int(multipleWebExtents[resource.id_0])
					resource = updateExtent(resource, str(captureCount), extentType)
					multipleWebExtents[resource.id_0] = captureCount
				else:
					resource = updateExtent(resource, str(captureCount), extentType)
					multipleWebExtents[resource.id_0] = captureCount
				
				#Local UAlbany Web Archives Subject, replace or comment-out
				subjectCheck = False
				for subject in resource.subjects:
					if subject["ref"] == "/subjects/327":
						subjectCheck = True
				if subjectCheck == False:
					resource = AS.addSubject(resource,  "/subjects/327")
					
				#post resource back to ASpace
				postCollect = AS.postResource(session, repo, resource, aspaceLogin)
				if str(postCollect).strip() == "200":
					print (str(postCollect).strip() + " --> posted updated resource: " + resource.title)
				else:
					raise ValueError(str(postCollect) + " --> failed to post updated resource:\n\n" + resource)
				
except:
	#the main try failed, use scriptNotifier
	exceptMsg = traceback.format_exc()
	print (exceptMsg)
	errorOutput = "\n" + "#############################################################\n" + str(datetime.datetime.now()) + "\n#############################################################\n" + str(exceptMsg) + "\n********************************************************************************"
	file = open("updateWebCollections.log", "a")
	file.write(errorOutput)
	file.close()
	sys.exit(3)