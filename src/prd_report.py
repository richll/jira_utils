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

class PrdReport:
    def __init__(self):
        self.config = "" # for ConfigParser
        self.issues = []
        self.issues_types = ['New Feature', 'Sub-task'] # Issue types we will check status of (.ini config file sections)
        self.log_offset = 0 # How old in days the last log file is, added to each status days
        self.prds = {} 
        self.output_file = ""
        self.search_step = 50

    def send_email(self, recipients, html_data, assignee=None):
        """ Put html_data in the body of an html email and send it to recipients 
            recipients is a list
        """

        msg = MIMEMultipart('alternative')
#        msg['Subject'] = "Jira Alert - Stagnant Jiras %s" % self.options.fl_project
        msg['Subject'] = "Jira Alert - Stagnant Jiras"
        msg['From'] = 'jira.alert@lsi.com'
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
        s.sendmail('jira.alert@lsi.com', recipients, msg.as_string())
        s.quit()
               
#    def send_main_email(self, recipients):
    def send_main_email(self):
        """ Just make the email body (html) and pass to send_email() 
            This is the main email that contains issues for all assignees.
        """

        print "Sending main email"
        
        # Make an html table to be body of email
        html_table = '<table style="font-size:12px">'

        # Go thru all issues getting the PRDs, New Features and Subtasks
        for issue in self.issues:
            if issue['fields']['issuetype']['name'] == "PRD":
                
                html_table += '<tr><td nowrap>PRD %s - %s</td></tr>' % (issue['key'], issue['fields']['summary'])
    #            for nf in prd['fields']['issuelinks']:
    #                print "nf %s" % nf
    #                html_table += '<tr><td nowrap>PRD %s</td></tr>' % nf
    #                for st in nf:
    #                    print "st %s" % st
        
        html_table += '</table>' # Closing table tag
        
        print html_table

        recipients = self.config.get("recipients", "emails").split("\n") # [recipients] section in .ini file
        print recipients
        sys.exit()
        
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
    jql =  '(("FL Project" = "G.1.0") and ((project = "Titan") or (project = "Griffin")) and (issuetype = PRD))'
#            (issuetype = PRD) or (issuetype = "New Feature") or (issuetype = Sub-task))'
          
    print "jql: %s" % jql
        
    pr.issues = list(jira_utils.get_issues(jql)) # Gets issues using the jgl query (turn returned json into python list)
 
    print "Number of issues: %s" % len(pr.issues)

#    sys.exit()
    pr.send_main_email() 

if __name__ == "__main__":
    sys.exit(main())

