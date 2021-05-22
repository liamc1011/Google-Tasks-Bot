from __future__ import print_function
from os import write
import os.path
from socket import EAI_SERVICE
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
import google.auth.transport.requests
import requests
import json
from google.oauth2.credentials import Credentials
import datetime as Datetime
from requests.sessions import Request

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/tasks']

# https://github.com/googleapis/google-api-python-client/blob/master/docs/start.md#building-and-calling-a-service
# the service object, which is an API-specific object that allows access to resources
service = None

def oauth2():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            with open('token.json', 'r') as read_file:
                token_file = json.load(read_file)

            print('creds expired, refreshing')
            request = google.auth.transport.requests.Request()
            creds.refresh(request)         

        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0, access_type='offline', prompt='consent')
        
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    global service
    service = build('tasks', 'v1', credentials=creds)

# I made this to manually refresh the access token because the automatic one 
# by Google's boilerplate code wasn't working, but that turned out not to be the issue
def refresh_access_token():
    with open('token.json', 'r') as read_file:
        token_file = json.load(read_file)
    
    payload = {
        'client_id': token_file['client_id'],
        'client_secret': token_file['client_secret'],
        'grant_type': 'refresh_token',
        'refresh_token': token_file['refresh_token'],
    }
    
    response = requests.post('https://oauth2.googleapis.com/token', data=payload).json()
    print(response)

    token_file['token'] = response['access_token']
    with open('token.json', 'w') as write_file:
        json.dump(token_file, write_file, indent=4)

# Takes a Datetime.date object and returns a formatted tasklist title    
def date_to_title(date):
    if not isinstance(date, Datetime.date):
        raise TypeError('Invalid type: data must be a date object')

    months = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
    
    title = months[date.month] + ' ' + str(date.day) + ' ' + str(date.year)
    return title

# Takes a tasklist title and attempts to construct and return a Datetime.date object
def title_to_date(title):
    words = title.split(" ")
    month = words[0]
    try:
        day = int(words[1])
        year = int(words[2])
    except ValueError:
        return None
    except IndexError:
        return None

    # Day and year given must be in valid ranges for the Datetime module
    if day not in range(0, 32):
        return None
    if year not in range(Datetime.MINYEAR, Datetime.MAXYEAR+1):
        return None

    if month.casefold() == 'jan' or month.casefold() == 'january':
        month = 1
    elif month.casefold() == 'feb' or month.casefold() == 'february':
        month = 2
    elif month.casefold() == 'mar' or month.casefold() == 'march':
        month = 3
    elif month.casefold() == 'apr' or month.casefold() == 'april':
        month = 4
    elif month.casefold() == 'may':
        month = 5    
    elif month.casefold() == 'jun' or month.casefold() == 'june':
        month = 6
    elif month.casefold() == 'jul' or month.casefold() == 'july':
        month = 7
    elif month.casefold() == 'aug' or month.casefold() == 'august':
        month = 8
    elif month.casefold() == 'sep' or month.casefold() == 'september':
        month = 9
    elif month.casefold() == 'oct' or month.casefold() == 'october':
        month = 10
    elif month.casefold() == 'nov' or month.casefold() == 'november':
        month = 11
    elif month.casefold() == 'dec' or month.casefold() == 'december':
        month = 12
    else:
        # Insert proper error handling here lol
        return None
    
    date = Datetime.date(year, month, day)
    return date

# Returns whether the given title follows valid formatting for a date
def is_date(title):
    if title_to_date(title) is not None:
        return True
    else:
        return False

# Creates a new daily tasklist to represent today's todo list.
# All incomplete tasks from the most recent daily todo list are copied over, completed tasks are not.
# Adds it to my taskslists.
def copy_last_tasklist():
    
    # Gets a list of all tasklists.
    # Note that taskslists().list() builds the request for a list of tasklists, and execute() sends the request. 
    # You can't just do taskslists().execute() for some reason, taskslists() isn't really a method it's just a resource. Doing so would just give you the Tasklist object. 
    # The response is a dict with information about all the taskslists, the 'items' key contains the actual list of all tasklists (what we want).
    tasklists = service.tasklists().list().execute()['items']
    
    # Gets the ID of the most recent daily todo list (dubbed "yesterdays" to do list)
    for tasklist in tasklists:
        if is_date(tasklist['title']):
            most_recent_id = tasklist['id']
    
    today = {'title': date_to_title(Datetime.date.today())}     # Creates todays todo list
    service.tasklists().insert(body=today).execute()    # Inserts todays todo list
    today_id = service.tasklists().list().execute()['items'][-1]['id']  # Gets the ID of todays todo list

    # Gets all the incomplete tasks in "yesterdays" todo list.
    most_recent_tasks = service.tasks().list(tasklist=most_recent_id).execute()
    # If "yesterdays" todo list has no incomplete tasks, it will not have the 'items' key
    if 'items' in most_recent_tasks:
        most_recent_tasks = most_recent_tasks['items']
    else:
        # if "yesterdays" todo list has no incomplete tasks, we are done!
        print('Success')
        return

    # Goes through all incomplete tasks from yesterday, for each one makes a copy and adds it to today's list
    for task in most_recent_tasks:
        task_copy = {'title': task['title']}
        service.tasks().insert(tasklist=today_id, body=task_copy).execute()

    print('Success')

def main():
    oauth2()
    copy_last_tasklist()


if __name__ == '__main__':
    main()