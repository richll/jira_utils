#!/usr/bin/python

#import os
import json
import sys
#import time
from datetime import datetime as dt
from datetime import date, timedelta
import pdb
import smtplib
#from time import strftime
#from types import *
import ConfigParser
import operator
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from optparse import OptionParser
import jira_utils

class PrdIssue(jira_utils.IssueClass):
    """Class objects to hold PRD issue attributes."""
    def __init__(self):
        self.new_features = [] # List of New Feature issue link issues (dictionaries)

class PrdReport:
    def __init__(self):
        self.config = "" # for ConfigParser
        self.prd_issues = []
        self.prd_issue_objs = {} # Dictionary to hold PrdIssue objects, key is issue_id, value is a PrdIssue object
        self.log_offset = 0 # How old in days the last log file is, added to each status days
        self.prds = {} 
        self.output_file = ""
        self.search_step = 50

    def create_prd_issue_objs(self):
        """ Gets issues from self.issues[], make PrdIssue objects, put in self.prd_issue_objs dictionary.
            Populate objects with data from their issue.
        """
        
        print "Creating PrdIssue objects"
        # Create PrdIssue objects, add to prd_issue_objs dictionary
        for issue in self.prd_issues:
            pi = PrdIssue() # Create PrdIssue object for each PRD issue, assign data from issue to object's variables
            pi.issue_id = issue['key']
            pi.issue_type = issue['fields']['issuetype']['name']
            pi.summary = issue['fields']['summary']
            
            # Get New Feature issue links, each one is a dictionary
            for issue_link in issue['fields']['issuelinks']:
                try:
                    if issue_link['inwardIssue']['fields']['issuetype']['name'] == "New Feature":
#                        print "issue_link %s" % issue_link['inwardIssue']['key']
                        pi.new_features.append(issue_link) # Append a dictionary to the list
        #                    pdb.set_trace()
                except KeyError: # Some issue links don't have the field "inwardIssue"
                    pass

                
            self.prd_issue_objs[issue['key']] = pi # Add object to main object dictionary
            
    def send_email(self, recipients, html_data, assignee=None):
        """ Put html_data in the body of an html email and send it to recipients 
            recipients is a list
        """

        msg = MIMEMultipart('alternative')
        msg['Subject'] = "Jira PRD Report"
        msg['From'] = 'jira.utils@lsi.com'
        if assignee:
            msg['To'] = assignee
            msg['Cc'] = ', '.join(recipients) # Assignee emails
        else:
            msg['To'] = ', '.join(recipients) # Main email
        
        html1 = "<!DOCTYPE html><html><head><meta charset=\"utf-8\"/><title>HTML Reference</title></head><body>"
            
        html2 = "</body></html>"
                
        final_message = "%s%s%s" % (html1, html_data, html2)
        html_message = MIMEText(final_message, 'html', _charset='utf-8')
        msg.attach(html_message)
        
        # Send the message via our own SMTP server.
        s = smtplib.SMTP('localhost')
        s.set_debuglevel(1)
#        s.sendmail('richard.leblanc@lsi.com', recipients, msg.as_string())
        s.sendmail('jira.utils@lsi.com', recipients, msg.as_string())
        s.quit()
               
#    def send_main_email(self, recipients):
    def send_main_email(self):
        """ Just make the email body (html) and pass to send_email() 
        """

        print "Sending main email"
        
        # Make an html table to be body of email
        html_table = '<table style="font-size:12px">'

        # Go thru all issues getting the PRDs, New Features and Subtasks
#        for prd in sorted(self.prd_issue_objs.values()):
        for prd_id in sorted(self.prd_issue_objs.keys()):
            html_table += '<tr><td nowrap>PRD %s - %s</td></tr>' % (self.prd_issue_objs[prd_id].issue_id, self.prd_issue_objs[prd_id].summary)
            # Get id and summary of PRD issue links (New Features)
            newlist = sorted(self.prd_issue_objs[prd_id].new_features, key=operator.itemgetter('inwardIssue')) # Sort the list
            for item in newlist:
                html_table += '<tr><td nowrap>&nbsp; &nbsp; &nbsp; &nbsp; New Feature %s - %s</td></tr>' % (item['inwardIssue']['key'], item['inwardIssue']['fields']['summary']) #, new_feature['fields']['summary'])
#                for st in nf:
#                    print "st %s" % st
        
        html_table += '</table>' # Closing table tag
        
#        print html_table

        recipients = self.config.get("recipients", "emails").split("\n") # [recipients] section in .ini file
        print recipients
        
        self.send_email(recipients, html_table)

def main(argv=None):
    if argv is None:
        argv = sys.argv
        
#    usage = "usage: %prog --fl_project=<fl project name>\n   ex. %prog --fl_project=\"Griffin MP1\""

    pr = PrdReport() # The one and only PrdReport object
    pr.config = ConfigParser.SafeConfigParser() # Make a config parser to parse the prd_report.ini file
    pr.config.optionxform=str # To preserve case of values
    
    try:
        if pr.config.read('prd_report.ini') != []:
            pass
        else:
            raise IOError('Cannot open configuration file')
    except ConfigParser.ParsingError, error:
        print 'Error,', error
    
    # The jira query that will get the issues we're interested in.
    jql =  '(("FL Project" = "G.1.0") and ((project = "Titan") or (project = "Griffin")) and (issuetype = "PRD"))'
#            (issuetype = PRD) or (issuetype = "New Feature") or (issuetype = Sub-task))'
          
    print "jql: %s" % jql
        
    pr.prd_issues = list(jira_utils.get_issues(jql)) # Gets issues using the jgl query (turn returned json into python list)
    print "Number of issues: %s" % len(pr.prd_issues)
    pr.create_prd_issue_objs() # Create PrdIssue objects for each prd issue to hold attributes were interested in.
#    pr.create_prd_issue_objs() # Create PrdIssue objects for each prd issue to hold attributes were interested in.
#    pr.create_prd_issue_objs() # Create PrdIssue objects for each prd issue to hold attributes were interested in.
 
#    temp_issue = jira_utils.get_issue("TEST-528")
#    print json.dumps(temp_issue, indent=4)


#    sys.exit()
    pr.send_main_email() 

if __name__ == "__main__":
    sys.exit(main())

