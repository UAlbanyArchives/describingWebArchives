from archives_tools import aspace as AS

session = AS.getSession()
repo = 2

count = 0
for dao in AS.getDAOs(session, repo, "all"):
	if len(dao.linked_instances) == 0:
		count += 1
		print (dao.title)
		post = AS.deleteObject(session, dao)
		print (post)
print (str(count) + " deleted")