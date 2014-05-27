'''
Created on May 16, 2014

@author: rich
'''

import requests
import sys
                               
def get_issues(jql):
    """ Gets all issues from the jgl query into issues[] 
        Returns issues from the jql queie in json.
        
        Example, to list all issue ids in returned issue list:
        
        for item in issues:
            print item['key']
            
        prints:
        TITAN-1234
        TITAN-5678
        .
        .
        .
        
        Example, to see all issues in readable form:
        
         for item in issues:
            print json.dumps(item, indent=4)

   """
    
    commit_data = {'issues': "anything"} # Any text for non-zero start value for while loop
    issues = [] # List of issues (python dictionaries) to return
    start_at_issue = 0
    
    # Get 50 issues at a time (default, can't seem to change) until we don't get anymore issues.
    while len(commit_data['issues']):
        print "startat: %s" % start_at_issue
        r = requests.get('http://jira.sandforce.com/rest/api/2/search?jql=%s&startAt=%s&expand=changelog,transitions,history' % (jql, start_at_issue), auth=('jalert', '123456789')) 
        start_at_issue += 50 
        
        if r.status_code == 200:
            pass
        else:
            print "code %s:" % requests.status_codes.codes.__getitem__('200')
            print "status %s:" % r.status_code
            sys.exit()
        
        commit_data = r.json() # 50 issues, put in json format (like python dictionaries)
        
        for item in commit_data['issues']:
            issues.append(item) # Append all the issues to the issues list

    return issues # list of issue dictionaries

def get_issue(issue_id):
    """ Gets a single issue from the jgl query and returns it in json form.
        
        Example how to use in a script:        
        tempvar = jira_utils.get_issue('TITAN-5969')
        print json.dumps(tempvar, indent=4)
 
    """
        
    jql = "issue = %s" % issue_id # Get issue for passed in issue_id.
    r = requests.get('http://jira.sandforce.com/rest/api/2/search?jql=%s&expand=changelog,transitions,history' % jql, auth=('jalert', '123456789')) 
    
    if r.status_code == 200:
        pass
    else:
        print "code %s:" % requests.status_codes.codes.__getitem__('200')
        print "status %s:" % r.status_code
        sys.exit()
    
    commit_data = r.json() # Return issue in json format (like python dictionary)

    return commit_data 
        

