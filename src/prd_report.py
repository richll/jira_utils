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
from email.MIMEBase import MIMEBase
from email import Encoders
from optparse import OptionParser
import jira_utils

class PrdIssue(jira_utils.IssueClass):
    """Class objects to hold PRD issue attributes."""
    def __init__(self):
        self.new_features = [] # List of New Feature issue link issues (dictionaries)

class PrdReport:
    def __init__(self):
        self.config = "" # for ConfigParser
        self.prd_issues = {}
        self.prd_issues_list = []
        self.prd_issue_objs = {} # Dictionary to hold PrdIssue objects, key is issue_id, value is a PrdIssue object
        self.log_offset = 0 # How old in days the last log file is, added to each status days
        self.prds = {} 
        self.output_file = "prd_report.csv"
        self.search_step = 50

    def build_dictionary(self):
        """ Gets issues from prd_issues_list = [] get id and description for PRD, New Feature and Subtasks issue types. 
            Create hierarchical dictionary of PRD, New Feature and Subtasks.
            
            PRD
                New Feature
                    Subtask
                    Subtask
                       .
        """
        
        # Start with PRDs at highest level, each item is an issue
        for item in self.prd_issues_list:
            self.prd_issues['issue_id'] = item['key']
            print "PRD: %s" % self.prd_issues['issue_id']
            self.prd_issues['issue_id'] = {}
            self.prd_issues['issue_id']['summary'] = item['fields']['summary']
            self.prd_issues['issue_id']['status'] = item['fields']['status']['name']
            self.prd_issues['issue_id']['new_features'] = {}
            
            # Put New feature issue links in next
            for issue_link in item['fields']['issuelinks']:
                try:
                    if issue_link['inwardIssue']['fields']['issuetype']['name'] == "New Feature":
                        self.prd_issues['issue_id']['new_features']['issued_id'] = issue_link['inwardIssue']['key']
                        print self.prd_issues['issue_id']['new_features']['issued_id']
                        self.prd_issues['issue_id']['new_features']['issued_id'] = {}
                        self.prd_issues['issue_id']['new_features']['issued_id']['summary'] = issue_link['inwardIssue']['fields']['summary']
                        self.prd_issues['issue_id']['new_features']['issued_id']['status'] = issue_link['inwardIssue']['fields']['status']['name']
                        self.prd_issues['issue_id']['new_features']['issued_id']['subtasks'] = {}
                except KeyError: 
                    continue # Some issue links don't have the field "inwardIssue", skip those and continue
                
                # Now get the New feature issue to see the subtasks info for this New Feature
                temp_issue = jira_utils.get_issue("'" + issue_link['inwardIssue']['key'] + "'") # Get the New Feature issue to see subtasks
                
                for item in temp_issue['issues'][0]['fields']['subtasks']:
                    self.prd_issues['issue_id']['new_features']['issued_id']['subtasks']['issued_id'] = item['key']
                    self.prd_issues['issue_id']['new_features']['issued_id']['subtasks']['issued_id'] = {}
                    self.prd_issues['issue_id']['new_features']['issued_id']['subtasks']['issued_id']['summary'] = item['fields']['summary']                                                                                     
                    self.prd_issues['issue_id']['new_features']['issued_id']['subtasks']['issued_id']['status'] = item['fields']['status']['name']
                                                                                                              
                
        print self.prd_issues    
        
    def create_csv_file(self):
        """ Using data from self.prd_issues create csv file of PRDs, New Features, Subtasks and their summaries and status.
        """
        
        print "Creating CSV file"

        with open("prd_report.csv", 'w') as outfile:
        
            # First output the Excel headings
            outfile.write(",".join(["PRD ID", "PRD Title", "PRD State", \
                               "New Feature ID", "New Feature Title", "New Feature State", \
                               "Subtask ID", "Subtask Title", "Subtask State"]))
            
            # Write out the rest of the Excel rows
            for prd in self.prd_issues.iteritems():
                for new_feature in prd['new_features'].iteritems():
                    for subtask in prd['new_features']['subtasks'].iteritems():
                        outfile.write(",".join([prd['issue_id'], \
                                           prd['issue_id']['summary'], \
                                           prd['issue_id']['status'], \
                                           prd['issue_id']['new_features']['issued_id'], \
                                           prd['issue_id']['new_features']['issued_id']['summary'], \
                                           prd['issue_id']['new_features']['issued_id']['status'],
                                           prd['issue_id']['new_features']['issued_id']['subtasks']['issued_id'], \
                                           prd['issue_id']['new_features']['issued_id']['subtasks']['issued_id']['summary'], \
                                           prd['issue_id']['new_features']['issued_id']['subtasks']['issued_id']['status'], \
                                           ])) # Writes one row in the file
 
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
            
        
    def send_email(self, recipients, files=[]):
        """ Send it to recipients, recipients is a list
            Files, if any, are attached
        
        """

        msg = MIMEMultipart('alternative')
        msg['Subject'] = "Jira PRD Report"
        msg['From'] = 'jira.utils@lsi.com'
        msg['To'] = ', '.join(recipients) 

        part = MIMEBase('application', "octet-stream")
        part.set_payload(open(self.output_file, "r").read())
        Encoders.encode_base64(part)
        
        part.add_header('Content-Disposition', 'attachment', filename="%s") % self.output_file
        
        msg.attach(part)
        
        # Send the message via our own SMTP server.
        s = smtplib.SMTP('localhost')
        s.set_debuglevel(1)
        s.sendmail('jira.utils@lsi.com', recipients, msg.as_string())
        s.quit()
    
    def send_html_email(self, recipients, html_data, assignee=None):
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
               
#    def send_html_table(self, recipients):
    def send_html_table(self):
        """ Just make the email body (html) and pass to send_html_email() 
        """

        print "Sending main email"
        
        # Make an html table to be body of email
        html_table = '<table style="font-size:12px">'

        # Go thru all prd objects getting the PRDs, New Features and Subtasks
#        for prd in sorted(self.prd_issue_objs.values()):
#1        for prd_id in sorted(self.prd_issue_objs.keys()): # Sort PRDs by issue id (key)
        for prd_issue in self.prd_issues:
#1            html_table += '<tr><td nowrap>PRD %s - %s</td></tr>' % (self.prd_issue_objs[prd_id].issue_id, self.prd_issue_objs[prd_id].summary)
            html_table += '<tr><td nowrap>PRD %s - %s</td></tr>' % (prd_issue['key'], prd_issue['fields']['summary'])
            # Get id and summary of PRD issue links (New Features)
#1            sorted_nf_list = sorted(self.prd_issue_objs[prd_id].new_features, key=operator.itemgetter('inwardIssue')) # Sort the New Feature list
#1            for item in sorted_nf_list:
            # Get New Feature issue links, each one is a dictionary
            for issue_link in prd_issue['fields']['issuelinks']:
                try:
                    if issue_link['inwardIssue']['fields']['issuetype']['name'] == "New Feature":
#                        print "issue_link %s" % issue_link['inwardIssue']['key']
                        html_table += '<tr><td nowrap>&nbsp; &nbsp; &nbsp; &nbsp; New Feature %s - %s</td></tr>' % (issue_link['inwardIssue']['key'], issue_link['inwardIssue']['fields']['summary']) #, new_feature['fields']['summary'])
        #                    pdb.set_trace()
                except KeyError: # Some issue links don't have the field "inwardIssue"
                    pass

#1                html_table += '<tr><td nowrap>&nbsp; &nbsp; &nbsp; &nbsp; New Feature %s - %s</td></tr>' % (item['inwardIssue']['key'], item['inwardIssue']['fields']['summary']) #, new_feature['fields']['summary'])
#                for st in nf:
#                    print "st %s" % st
        
        html_table += '</table>' # Closing table tag
        
#        print html_table

        recipients = self.config.get("recipients", "emails").split("\n") # [recipients] section in .ini file
        print recipients
        
        self.send_html_email(recipients, html_table)

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
        
    pr.prd_issues_list = list(jira_utils.get_issues(jql)) # Gets issues using the jgl query (turn returned json into python list)
    print "Number of issues: %s" % len(pr.prd_issues_list)
    pr.build_dictionary() # Create hierarchical dictionary of PRD, New Feature and Subtasks.
    pr.create_csv_file() # Csv file of PRDs, New Features, Subtasks and their summaries and status
    pr.send_email() # Attaching the csv file


#    temp_issue = jira_utils.get_issue("TEST-528")
#    print json.dumps(temp_issue, indent=4)

                
    # Open a file
#    fo = open("foo.json", "w")
#    fo.write(json.dumps(temp_issue, indent=4))


    # Close opend file
#    fo.close()
                
                
                

#    sys.exit()

if __name__ == "__main__":
    sys.exit(main())

