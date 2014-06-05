#!/usr/bin/python

#import os
import json
import os
import sys
#import time
import pdb
import smtplib
import ConfigParser
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.MIMEBase import MIMEBase
from email import Encoders
from optparse import OptionParser
import jira_utils

class PrdReport:
    def __init__(self):
        self.config = "" # for ConfigParser
        self.jql = ""
        self.prds = [] 
        self.prd_issue_list = [] # List of PRD issues we get from the jql query
        self.new_feature_issue_list = [] # List of New Feature issues we get from the jql query
        self.output_file = "prd_report.csv"

    def build_dictionaries(self):
        """ Gets issues from prd_issues_list[] and new_feature_issue_list[]. 
            Create hierarchical dictionaries of PRD and New Features.
            New Features have subtask info so no need to get subtask issues.
            
            self.prds['issue_id']
                     ['status']
                     ['summary']           
                     ['new_features'] # List of New feature issues which contain subtask info
                                                
         """
        
        # Start with PRDs at highest level, each item is an issue
        # Put information from issues list into local dictionaries
        for prd_item in self.prd_issue_list:
            prd = {} # Make dictionaries to add to the self.prds[] list
            prd['new_features_list'] = [] # list of issues (dictionaries)
            issue_id = str(prd_item['key'])
            prd['issue_id'] = issue_id
            prd['summary'] = prd_item['fields']['summary']
            prd['status'] = prd_item['fields']['status']['name']
            
            # Put New feature issue links info in next
            for issue_link in prd_item['fields']['issuelinks']:
                # Some issue links don't have the field "inwardIssue", skip those and continue
                try:
                    if str(issue_link['inwardIssue']['fields']['issuetype']['name']) == "New Feature": # Must turn unicode to string
                        for nf_issue in self.new_feature_issue_list:
                            if nf_issue['key'] == issue_link['inwardIssue']['key']:
                                prd['new_features_list'].append(nf_issue) # put new feature issues in prd's list
                except KeyError: 
                    continue # Some issue links don't have the key were looking for, skip those and continue.
         
            self.prds.append(prd) # Add prd to our list of prds

    def create_csv_file(self):
        """ Using data from self.prds create csv file of PRDs, New Features, Subtasks and their summaries and status.
        """
        
        print "Creating CSV file"

        with open("prd_report.csv", 'w') as outfile:
        
            # First output the Excel headings
            outfile.write(",".join(["PRD ID", "PRD Title", "PRD State", \
                               "New Feature ID", "New Feature Title", "New Feature State", \
                               "Subtask ID", "Subtask Title", "Subtask State"]) + '\r\n')
            
            # Write out the rest of the Excel rows
            for prd in self.prds:
                for nf in prd['new_features_list']:
                    for st in nf['fields']['subtasks']:
                        outfile.write(",".join([prd['issue_id'], prd['summary'].replace(',', ''), prd['status'], \
                                                nf['key'], nf['fields']['summary'].replace(',', ''), nf['fields']['status']['name'], \
                                                st['key'], st['fields']['summary'].replace(',', ''), st['fields']['status']['name']]) + '\r\n')
         
    def get_issues(self):
        """ Get PRDS, then get their New Feature links, then get the New Features  
            Puts issues in self.prd_issue_list and self.new_feature_issue_list
            Lists of issue dictionaries
        """
        
        # Get prd new feature link ids, then we'll get those issues
#        jql =  '(("FL Project" = "G.1.0") and ((project = "Titan") or (project = "Griffin")) and (issuetype = "PRD"))'
        jql =  '(("FL Project" = \"%s\") and (project = \"%s\") and (issuetype = "PRD"))' % (self.options.fl_project, self.options.project)
        self.jql = jql
        print "Getting PRD issues"
        print "jql: %s" % jql
        self.prd_issue_list = list(jira_utils.get_issues(jql)) 
        
        # Get prd new feature link ids, then we'll get those issues
        nf_link_ids = []

        for item in self.prd_issue_list:
            for issue_link in item['fields']['issuelinks']:
                try:
                    if issue_link['inwardIssue']['fields']['issuetype']['name'] == "New Feature":
                        nf_link_ids.append(issue_link['inwardIssue']['key']) # Add New feature id to list
                except KeyError: 
                    continue # Some issue links don't have the field "inwardIssue", skip those and continue
                
        nf_link_ids_string = ",".join(sorted(nf_link_ids))
        jql = 'key in (' + nf_link_ids_string + ')' # Like: key in ("Titan-1234", "Titan-5678")
        
        print "Getting PRDs New Feature link issues"
        print "jql: %s" % jql
        self.new_feature_issue_list = list(jira_utils.get_issues(jql)) 
                
    def send_email(self, files=[]):
        """ Send email to recipients in prd_report.ini
            Files, if any, are attached
        
        """

        msg = MIMEMultipart('alternative')

        msg['From'] = ', '.join(self.config.get("email_from", "emails").split("\n")) # [email_from] section in .ini file
        msg['To'] = ', '.join(self.config.get("email_to", "emails").split("\n")) # [email_to] section in .ini file
        msg['Cc'] = ', '.join(self.config.get("email_cc", "emails").split("\n")) # [email_cc] section in .ini file
        msg['Subject'] = "Jira PRD Report"

        part=MIMEBase('application','octet-stream')
        part.set_payload(open(self.output_file,'r').read())
        Encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(self.output_file))

        jql_text = "jql = %s" % self.jql # The email body text, the jql query used to get the issues, can be copied and pasted into Jira issue search box.
        msg.attach( MIMEText(jql_text))
        msg.attach(part)
        
        # Send the message via our own local SMTP server.
        s = smtplib.SMTP('localhost')
        s.set_debuglevel(1)
        
        # Send email to the "To"s and the "Cc"s in the prd_report.ini config file
        email_addresses = ', '.join(self.config.get("email_to", "emails").split("\n")) + ", " + ','.join(self.config.get("email_cc", "emails").split("\n"))
        s.sendmail(', '.join(self.config.get("email_from", "emails").split("\n")), email_addresses, msg.as_string())
        s.quit()
                       
def main(argv=None):
    if argv is None:
        argv = sys.argv
        
    usage = "usage: %prog --fl_project=<fl project name> --project=<project name>\n   ex. %prog --fl_project=\"G.1.0\" --project=\"Griffin SW\""

    pr = PrdReport() # The one and only PrdReport object

    pr.parser = OptionParser()
    pr.parser.add_option("--fl_project", action="store", type="string", dest="fl_project", help="FL project to get issues for", metavar="FL_PROJECT")
    pr.parser.add_option("--project", action="store", type="string", dest="project", help="Project to get issues for", metavar="PROJECT")
    pr.parser.set_usage(usage)
    (options, args) = pr.parser.parse_args()

    if options.fl_project == None:
        pr.parser.error("incorrect number of arguments")
        pr.parser.print_usage()
    else:
        pr.options = options

    pr.config = ConfigParser.SafeConfigParser() # Make a config parser to parse the prd_report.ini file
    pr.config.optionxform=str # To preserve case of values
    
    try:
        if pr.config.read('prd_report.ini') != []:
            pass
        else:
            raise IOError('Cannot open configuration file')
    except ConfigParser.ParsingError, error:
        print 'Error,', error
    
    pr.get_issues() # Get PRD and New Features.
    pr.build_dictionaries() # Create hierarchical dictionary of PRD, New Feature and Subtasks.
    pr.create_csv_file() # Csv file of PRDs, New Features, Subtasks and their summaries and status
    pr.send_email() # Attaching the csv file

#    temp_issue = jira_utils.get_issue("TEST-528")
#    print json.dumps(temp_issue, indent=4)

if __name__ == "__main__":
    sys.exit(main())

