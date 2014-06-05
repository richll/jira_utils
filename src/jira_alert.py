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

class IssueClass:
    def __init__(self):
        self.assignee = ""
        self.assignee_email = ""
        self.icdt = "" # Issue create date time
        self.issue_id = ""
        self.issue_parent = ""
        self.issue_type = ""
        self.sprint = ""
        self.stalled = False
        self.status = ""
        self.summary = ""
        self.time_in_status = ""
        self.subtasks = {}

class JiraAlert:
    def __init__(self):
        self.config = "" # for ConfigParser
        self.current_status = {} # Dictionary of current status, days_in_status = 0
        self.issues = []
        self.issue_objs = {} # Dictionary to hold IssueClass objects
        self.issues_over_limit = {} # Issues that have been in status too long
        self.issues_types = ['New Feature', 'Sub-task'] # Issue types we will check status of (.ini config file sections)
        self.log_offset = 0 # How old in days the last log file is, added to each status days
        self.nf_objs = {} 
        self.output_file = ""
        self.search_step = 50
        self.stalled_nf_issues = []            
        self.stalled_st_issues = []            
        self.time_in_status = {} # Status times for issues
#        for issue_type in self.issues_types:

    def create_issue_objs(self):
        """ Gets issues from self.issues[], make IssueClass objects, put in self.issue_obj dictionary.
            Populate objects with data from their issue.
            calls get_time_in_status() to get some info.
        """
        
        print "Creating IssueClass objects"
        
        # Create IssueClass objects, add to issue_objs dictionary
        for issue in self.issues: 
#                print json.dumps(issue, indent=4)
            if issue['fields']['issuetype']['name'] == "Sub-task" and issue['fields']['parent']['fields']['issuetype']['name'] != "New Feature":
                continue # Skip sub-tasks whose parents are not New features
            ic = IssueClass() # Create IssueClass object for each issue, assign data from issue to object's variables
            ic.assignee = issue['fields']['assignee']['name']
            ic.assignee_email = issue['fields']['assignee']['emailAddress']
            ic.issue_id = issue['key']
            ic.issue_type = issue['fields']['issuetype']['name']
            ic.summary = issue['fields']['summary']
            ic.status = issue['fields']['status']['name']
            self.issue_objs[issue['key']] = ic # Add object to main object dictionary
            
            if ic.issue_type == "Sub-task":
                ic.issue_parent = issue['fields']['parent']['key'] # Get Sub-task parent
            
            try:
                ic.sprint = issue['fields']['customfield_10264'][0]['value'] # Get current sprint
            except TypeError:
                pass # Some issues have no sprint
            
            # Brand new issues less than change_period with no changes yet are considered a "change of status".
            ic.icdt = dt.strptime(issue['fields']['created'].split('.')[0], "%Y-%m-%dT%H:%M:%S") # Item create datetime
            if (issue['fields']['issuetype']['name'] == "New Feature") and \
                ic.icdt.date() > date.today()-timedelta(days=int(self.config.get('default', 'change_period'))):
                ic.last_sprint = "" # Only objects with a last_sprint or last_status attribute will be checked for changes within change_period
                ic.last_status = "" # Set last_sprint and last_status to null for issues less than change_period old

            # Get time in status for the issues we're interested in, also updates sprint/last_sprint, status/last_status
            self.get_time_in_status(issue, ic.status)
                
    def get_stalled_issues(self):
        """ Goes thru self.issue_objs, applies limits, updates self.stalled_issues """
        
        print "Getting stalled issues"
        
        # Mark issues stalled if over limit 
        for v in self.issue_objs.values():
            if (v.issue_type == "New Feature") and (v.status not in ["Open", "In Progress", "Reopened", "Resolved", "Closed"]):
                if int(v.time_in_status) > int(self.config.get(v.issue_type, v.status)):
                    v.stalled = True
                    for st in v.subtasks.values():
                        if (st.status == "In Progress") and (st.time_in_status > int(self.config.get(v.issue_type, v.status))):
                            st.stalled = True
                        elif (st.status == "In Progress") and (st.time_in_status < int(self.config.get(v.issue_type, v.status))):
                            v.stalled = False
                            st.stalled = False
                            
        # Put stalled issues in list
        self.stalled_nf_issues = sorted([obj for obj in self.issue_objs.values() if ((obj.issue_type == "New Feature") and obj.stalled)], key=operator.attrgetter('status')) # Stalled New Features
        self.stalled_st_issues = sorted([st for obj in self.stalled_nf_issues if len(obj.subtasks) for st in obj.subtasks.values() if st.stalled], key=operator.attrgetter('status')) # Stalled subtasks
        
    def get_time_in_status(self, issue, state):
        """ Calculate the time in status for this issue from the changelog history. 
            Go thru changelog histories looking for this status.
            Return days in status for this issue.
            While we're going thru changelog histories we can also find New Features last sprint and last status.
        """
        
#        current_datetime = str(dt.now()).split('.')[0].replace(' ', 'T') # The current datetime

        if ((issue['fields']['issuetype']['name'] == "Sub-task") and (issue['fields']['status']['name'] == "In Progress")) or \
           ((issue['fields']['issuetype']['name'] == "New Feature") and (issue['fields']['status']['name'] not in ["Open", "In Progress", "Reopened", "Resolved", "Closed"])):
            print "Getting time in status for %s" % issue['fields']['status']['name']
            # At first assume state is first, last and only state in case no changelog, if there's a changelog we'll revise later.
            # First state create time same as issue created datetime 
            cicdt = dt.strptime(issue['fields']['created'].split('.')[0], "%Y-%m-%dT%H:%M:%S") # Current item create datetime
            nicd = dt.strptime(str(dt.now()).split('.')[0].replace(' ', 'T'), "%Y-%m-%dT%H:%M:%S") # Next item create datetime
            diff = nicd - cicdt # Time the issue has been in that state
                         
            # If there's a changelog history go thru it else use issue create date and current date for time in status
            # If there's no changelog/histories then we're still in first state, nothing has changed
            if not len(issue['changelog']['histories']):
                print "no changelog for %s" % issue['key']
                self.issue_objs[issue['key']].time_in_status = diff.days
            else:
                # If there is a changelog look for the value "status", changes may be something other than status
                print "There's a changelog for issue %s" % issue['key']
#                    print json.dumps(issue, indent=4)
                 
                # Go thru changelog histories to see if any of the changes are "status" for this state, also get last status or sprint if New Feature
                status_change_found = False
                for histories_item in issue['changelog']['histories']:
                    if ((histories_item['items'][0]['field'] == 'status') and (histories_item['items'][0]['toString'] == state)):
                        print "There's a status change"
                        status_change_found = True
                        
                    # Get oldest sprint and status within config.change_period days ago for New Features 
                    if (issue['fields']['issuetype']['name'] == "New Feature") and \
                       ((histories_item['items'][0]['field'] == 'Milestone(s)') or (histories_item['items'][0]['field'] == 'status')):
                        hicdt = dt.strptime(histories_item['created'].split('.')[0], "%Y-%m-%dT%H:%M:%S").date() # histories item create datetime
                        if hicdt < date.today()-timedelta(days=int(self.config.get('default', 'change_period'))):
                            print "change too old %s, getting next histories item" % hicdt
                            continue # If older than config.change_period days then we don't care, get next histories item
                        else:
                            print "recent change %s " % hicdt
                            if histories_item['items'][0]['field'] == 'Milestone(s)':
                                self.issue_objs[issue['key']].last_sprint = histories_item['items'][0]['fromString'] # last sprint if issue less that config.change_period old
                                print "last_sprint %s" % self.issue_objs[issue['key']].last_sprint
                                break # Got the oldest change within change_period
                            if histories_item['items'][0]['field'] == 'status':
                                self.issue_objs[issue['key']].last_status = histories_item['items'][0]['fromString'] # last status if issue less that config.change_period old
                                print "last_status %s" % self.issue_objs[issue['key']].last_status
                                break # Got the oldest change within change_period
                                
                # If there was a change in status calculate time in status from changelog
                if(status_change_found):
                    total_days = 0 # Accumulate all the diffs for each time in this state
                    # Go thru changelog histories to see if this issue was in this state before.
                    for i, histories_item in enumerate(issue['changelog']['histories']):
                        # All the different kinds of things that have changed, we're only interested in 'status'
        
                        # Display all the changelog history items
                        if (0):
                            for k, v in histories_item.items():
                                print "issue['changelog']['histories'] key: %s value: %s" % (k, v)
                            print "issue['changelog']['histories']['items'] %s" % histories_item['items']
                            for item in histories_item['items']:
                                print "histories_item['items'] %s" % item
                            print "histories_item['items'][0] %s" %histories_item['items'][0]
                            for item2 in histories_item['items'][0]:
                                print "histories_item['items'][0] %s %s" % (item2, histories_item['items'][0][item2])
                         
                        # If status record we're interested in is found, look for next status change or use current date for end date
                        # If status "Pending" for New Features or "Open" for Sub-tasks there is no change entry for that, it's first state, use created date.
                        if ((histories_item['items'][0]['field'] == 'status') and (histories_item['items'][0]['toString'] == state)):
                            current_status_create_datetime = histories_item['created'].split('.')[0]
    
                            # Go thru future history changes until the next status change
                            status_found = False
                            for j in range(i+1, len(issue['changelog']['histories'])):
                                if (issue['changelog']['histories'][j]['items'][0]['field'] == 'status'):
                                    next_item_create_date = issue['changelog']['histories'][j]['created'].split('.')[0] # Only next status change not any change
                                    print "%s. next histories item  created: %s" % (j, next_item_create_date)
                                    status_found = True
                                    break # Break the for loop, next status found
                                     
                            if not status_found:    
                                next_item_create_date = str(dt.now()).split('.')[0].replace(' ', 'T') # The current datetime  
                                print "No next histories item, using today's date: %s" % (next_item_create_date)
                             
                            cscdt = dt.strptime(current_status_create_datetime, "%Y-%m-%dT%H:%M:%S") # Current status create datetime
                            nicdt = dt.strptime(next_item_create_date, "%Y-%m-%dT%H:%M:%S") # Next item create datetime
                             
                            print "Current status create date for %s: %s" % (issue['key'], cscdt)
                            print "Next item create date for %s: %s" % (issue['key'], nicdt)
                             
                            diff = nicdt - cscdt # The number of days the issue has been in that state
                            total_days += diff.days # Accumulate all the times this issue has been in this state.
                    self.issue_objs[issue['key']].time_in_status = total_days
                else:
                    self.issue_objs[issue['key']].time_in_status = diff.days # No change in status, days in status is issue created date to now
                                     
    def make_nfs_changed_rows(self, info_type):
        """ Make html table for email from a list of IssueClass objects. 
            The table is all the New Features that have changed sprint or status since self.change_period.
        """
                    
        html_table = ""
        
        # Put data in html table rows
        for v in sorted(self.issue_objs.values(), key=operator.attrgetter('issue_id')):
            do_the_rest = False
            
            # New Features only that have changed sprint or status
            if (v.issue_type == "New Feature"):
                if (info_type == 'sprint') and hasattr(v, 'last_sprint') and (v.sprint != v.last_sprint):
                    print "sprint %s not equal to last sprint %s" % (v.sprint, v.last_sprint)
                    html_table += '<tr><td nowrap>New Feature changed from \"%s\" to \"%s\"</td>' % (v.last_sprint, v.sprint)
                    do_the_rest = True
                elif (info_type == 'status') and hasattr(v, 'last_status') and (v.status != v.last_status):        
                    print "status %s not equal to last status %s" % (v.status, v.last_status)
                    html_table += '<tr><td nowrap>New Feature changed from \"%s\" to \"%s\"</td>' % (v.last_status, v.status)
                    do_the_rest = True

                if do_the_rest:        
                    html_table += '<td nowrap>&#124; %s &#124;</td>' % v.assignee # &#124; is vertical bar in html
                    if '&' in v.summary:
                        v.summary = v.summary.replace('&', '&amp;') # Ampersands screw up html, replace with html escaped version
                    html_table += '<td nowrap><a href=\"http://jira.sandforce.com/browse/%s\">%s</a></td>' % (v.issue_id, v.issue_id)
                    html_table += '<td nowrap>%s</td></tr>' % v.summary
            
        if html_table:
            html_table += '<tr><td nowrap>&nbsp;</td></tr>' # blank line at end of table

        return html_table

    def make_time_in_status_rows(self, obj_list):
        """ Make html table for email from a list of IssueClass objects. """
        
        # Make an html table from a list of IssueClass objects
        html_table = ""

        # Put the data in html table rows
        for item in obj_list:
            html_table += '<tr><td nowrap>%s in \"%s\" status for %s days</td>' % (item.issue_type, item.status, item.time_in_status)
            html_table += '<td nowrap>&#124; %s &#124;</td>' % item.assignee # &#124; is vertical bar in html
            if '&' in item.summary:
                item.summary = item.summary.replace('&', '&amp;') # Ampersands screw up html, replace with html escaped version
            html_table += '<td nowrap><a href=\"http://jira.sandforce.com/browse/%s\">%s</a></td>' % (item.issue_id, item.issue_id)
            html_table += '<td nowrap>%s</td></tr>' % item.summary

        html_table += '<tr><td nowrap>&nbsp;</td></tr>' # blank line at end of table

        return html_table
    
    def put_subtask_in_parent(self):
        """ Put subtask objects in their parent object. """
        
        print "Putting subtasks in parents"
        
        for obj in self.issue_objs.values(): 
            if obj.issue_type == "Sub-task":
                try:
                    self.issue_objs[self.issue_objs[obj.issue_id].issue_parent].subtasks[obj.issue_id] = obj
                    del self.issue_objs[obj.issue_id] # Delete subtask object after putting in parent.
                except KeyError:
                    print "Can't find parent issue for subtask %s" % obj.issue_id
                    sys.exit(1)
    
#    def send_assignee_emails(self, recipients):
    def send_assignee_emails(self):
        """ Just make the email body (html table) and pass to send_email()
            This sends a separate email to each assignee with their issues only.
        """

        assignees = list(set([obj.assignee for obj in self.stalled_nf_issues])) # Assignees from New Features
        assignees.extend(list(set([obj.assignee for obj in self.stalled_st_issues]))) # Add assignees from Sub-tasks
        recipients = self.config.get("recipients", "emails").split("\n") # [recipients] section in .ini file

        for assignee in assignees:
            assignee_issues = [] # List of IssueClass objects
            # Get all stalled New feature issues for this assignee
            for item in self.stalled_nf_issues + self.stalled_st_issues:
                if item.assignee == assignee:
#                if item.assignee == "ashih":
                    assignee_issues.append(item)
                    assignee_email = item.assignee_email
                        
            if len(assignee_issues):
                html_table = '<table style="font-size:12px">'
                html_table += self.make_time_in_status_rows(assignee_issues)
                html_table += '</table>' # Closing table tag
                #recipients.append(assignee_email)
                print "Sending email to: %s" % recipients
                self.send_email(recipients, html_table, assignee)
        
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
        html_table += self.make_nfs_changed_rows("sprint") # New features only
        html_table += self.make_nfs_changed_rows("status") # New features only
        html_table += self.make_time_in_status_rows(self.stalled_nf_issues) 
        html_table += self.make_time_in_status_rows(self.stalled_st_issues) # Sub-tasks
        html_table += '</table>' # Closing table tag

        recipients = self.config.get("recipients", "emails").split("\n") # [recipients] section in .ini file
        
#        emails = self.config.items('recipients')
#        for key, email in emails:
#            recipients = ', '.join(self.config.items('recipients'))
        
        print recipients
#        sys.exit()
        self.send_email(recipients, html_table)

def main(argv=None):
    if argv is None:
        argv = sys.argv
        
#    usage = "usage: %prog --fl_project=<fl project name>\n   ex. %prog --fl_project=\"Griffin MP1\""

    ja = JiraAlert() # The one and only JiraAlert object
#    ja.parser = OptionParser()
#    ja.parser.add_option("--fl_project", action="store", type="string", dest="fl_project", help="FL project to get issues for", metavar="FL_PROJECT")
#    ja.parser.set_usage(usage)
#    (options, args) = ja.parser.parse_args()

#    if options.fl_project == None:
#        ja.parser.error("incorrect number of arguments")
#        ja.parser.print_usage()
#    else:
#        ja.options = options

    ja.config = ConfigParser.SafeConfigParser() # Make a config parser to parse the jira_alert.ini file
    ja.config.optionxform=str # To preserve case of values
    
    try:
        if ja.config.read('jira_alert.ini') != []:
            pass
        else:
            raise IOError('Cannot open configuration file')
    except ConfigParser.ParsingError, error:
        print 'Error,', error
    
    # The jira query that will get the issues we're interested in.
    jql = '(("FL Project" = "G.1.0") and ("project" = "TITAN") and \
          (issuetype = "New Feature") and (status != "Open" or status != "In Progress" or status != "Reopened" or status != "Resolved" or status != "Closed") or \
          (issuetype = Sub-task and status = "In Progress"))'
#              (issuetype = Sub-task and status = "In Progress"))' % self.options.fl_project
    print "jql: %s" % jql
        
#    temp_issue = jira_utils.get_issue("TEST-114")
#    print json.dumps(temp_issue, indent=4)
#    sys.exit()
    
    ja.issues = list(jira_utils.get_issues(jql)) # Gets issues using the jgl query (turn returned json into python list)
 
    print "Number of issues: %s" % len(ja.issues)

    ja.create_issue_objs() # Create IssueClass objects for each issue, also gets changes and time in status
    ja.put_subtask_in_parent()
    ja.get_stalled_issues()
    ja.send_main_email() # Email complete list of latest issue status times
#    ja.send_assignee_emails() # Send email to assignees about their issues

if __name__ == "__main__":
    sys.exit(main())

