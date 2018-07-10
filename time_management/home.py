from django.shortcuts import HttpResponse, render
from django.db import connection
import datetime
from holidays import get_holidays
import calendar
import json
from django.contrib.auth.decorators import login_required
from time_management.decorators import user_is_in_manager_group


@login_required
@user_is_in_manager_group
def home(request):
    # default to first of the month and today
    end_date = datetime.datetime.now().today().strftime('%m/%d/%Y')
    start_date = str(datetime.datetime.now().today().month) + '/' + str(1) + '/' + \
                 str(datetime.datetime.now().today().year)
    return render(request, 'home.html', {'start': start_date, 'end': end_date})


@login_required
@user_is_in_manager_group
def get_entries_home(request):
    """
        Generates the landing page for anyone to come to for them to change/modify
        their hours.  It allows for users to move hours from project to project.
        """
    # target
    target = request.user.username
    if request.user.is_staff and 'target' in request.GET and request.GET['target'] != '':
        target = request.GET['target']

    # what is the month?
    month = request.GET['month']

    # what is the year?
    year = request.GET['year']

    # connect to the database
    cur = connection.cursor()

    # how should we order things? (ascenting/descending)
    order = 'ASC'
    if request.GET['by'] == 'desc':
        order = 'DESC'

    # how do we want to order our entries?
    order_by = ''
    if request.GET['order'] == 'project':
        order_by = 'projects.name ' + order + ', time_entries.spent_on ASC'
    if request.GET['order'] == 'date':
        order_by = 'time_entries.spent_on ' + order + ', projects.name ASC'
    if request.GET['order'] == 'hours':
        order_by = 'time_entries.hours ' + order + ', projects.name ASC, time_entries.spent_on ASC'
    if request.GET['order'] == 'activity':
        order_by = 'enumerations.name ' + order + ', projects.name ASC, time_entries.spent_on ASC'

    # get the records for this user, month, and year
    cur.execute(
        "SELECT time_entries.id, time_entries.project_id, projects.name, time_entries.issue_id, time_entries.hours, "
        "time_entries.comments, enumerations.name, time_entries.spent_on, custom_values.value, enumerations.id, "
        "projects.id FROM time_entries INNER JOIN custom_values ON custom_values.customized_id = time_entries.id "
        "INNER JOIN users ON users.id = time_entries.user_id "
        "INNER JOIN projects ON projects.id = time_entries.project_id "
        "INNER JOIN enumerations ON enumerations.id = time_entries.activity_id WHERE time_entries.tyear = %(year)s "
        "AND custom_values.value != '' and time_entries.tmonth = %(month)s AND users.login = '%(user)s' ORDER BY %(order)s;" % {
            'month': month, 'year': year, 'user': target, 'order': order_by})

    print cur.mogrify( "SELECT time_entries.id, time_entries.project_id, projects.name, time_entries.issue_id, time_entries.hours, "
        "time_entries.comments, enumerations.name, time_entries.spent_on, custom_values.value, enumerations.id, "
        "projects.id FROM time_entries INNER JOIN custom_values ON custom_values.customized_id = time_entries.id "
        "INNER JOIN users ON users.id = time_entries.user_id "
        "INNER JOIN projects ON projects.id = time_entries.project_id "
        "INNER JOIN enumerations ON enumerations.id = time_entries.activity_id WHERE time_entries.tyear = %(year)s "
        "AND custom_values.value != '' and time_entries.tmonth = %(month)s AND users.login = '%(user)s' ORDER BY %(order)s;" % {
            'month': month, 'year': year, 'user': target, 'order': order_by})

    entries = cur.fetchall()
    print entries

    # assemble into a list
    entry_list = []
    entry_number = 1
    total_hours = 0
    support = 0
    for entry in entries:
        new_entry = {}
        entry_number *= -1
        new_entry['id'] = entry[0]
        new_entry['project'] = entry[1]
        new_entry['name'] = entry[2]
        new_entry['issue'] = entry[3]
        new_entry['hours'] = entry[4]
        new_entry['comments'] = entry[5]
        new_entry['activity'] = entry[6]
        new_entry['date'] = entry[7].isoformat()
        new_entry['number'] = entry_number
        new_entry['logas'] = entry[8]
        new_entry['activity_id'] = entry[9]
        new_entry['project_id'] = entry[10]
        entry_list.append(new_entry)

        # update our total hours (if it's billable!)
        if 'non-billable' not in entry[6].lower():
            total_hours += entry[4]
        else:
            support += entry[4]

        # print new_entry

    # round our total hours
    total_hours = round(total_hours, 2)

    # round support hours
    support = round(support, 2)

    # get a list of all projects this user is a member of
    cur.execute(
        "SELECT projects.id, projects.name FROM projects INNER JOIN members ON projects.id = members.project_id "
        "INNER JOIN users ON users.id = members.user_id WHERE users.login = '%(user)s' ORDER BY projects.name;" % {
            'user': target})
    projects = cur.fetchall()

    # loop through the projects, constructiong a dictionary
    project_list = []
    for project in projects:
        new_project = {}
        new_project['id'] = project[0]
        new_project['name'] = project[1]
        # for each project, get a list of activities!
        # first get any that are specific to our project
        cur.execute(
            "SELECT name FROM enumerations WHERE type = 'TimeEntryActivity' and project_id = %(proj)s "
            "and active = FALSE;" % {
                'proj': project[0]})
        exclusions = cur.fetchall()
        exclude_list = []
        for ex in exclusions:
            exclude_list.append(ex[0])

        # now get the defaults
        cur.execute(
            "SELECT id, name FROM enumerations WHERE type = 'TimeEntryActivity' and active = TRUE "
            "and project_id is NULL;")
        activity = cur.fetchall()

        activity_list = []
        for act in activity:
            if act[1] in exclude_list:
                continue
            active = {}
            active['id'] = act[0]
            active['name'] = act[1]
            activity_list.append(active)
        new_project['activities'] = activity_list

        project_list.append(new_project)

    # get a list of activities
    cur.execute(
        "SELECT min(id), name FROM enumerations where type = 'TimeEntryActivity' "
        "AND active = TRUE GROUP BY name ORDER BY name;")
    activities = cur.fetchall()
    # loop through the activities, constructing a dictionary
    activity_list = []
    for activity in activities:
        new_act = {}
        new_act['id'] = activity[0]
        new_act['name'] = activity[1]
        activity_list.append(new_act)

    # get a list of "log as" options
    cur.execute("SELECT possible_values FROM custom_fields WHERE lower(name) = lower('Log As');")
    logas = cur.fetchall()
    # loop through, constructing a dictionary
    logas = logas[0][0].split('\n')[1:-1]
    logas_list = []
    for l in logas:
        new_logas = {}
        new_logas['name'] = l[2:]
        logas_list.append(new_logas)

    # get a list of users who have time logged for this month/year
    # cur.execute(
    #     "SELECT firstname, lastname, login, max(CASE WHEN (time_entries.tmonth = %(month)s "
    #     "and time_entries.tyear = %(year)s) THEN 2 ELSE 1 end) AS t FROM users "
    #     "INNER JOIN time_entries ON time_entries.user_id = users.id "
    #     "GROUP BY firstname, lastname, login "
    #     "ORDER BY t DESC, firstname, lastname;" % {
    #         'month': month, 'year': year})

    # get a list of users who have time logged for this month/year
    cur.execute(
        "SELECT firstname, lastname, login FROM users "
        "ORDER BY login DESC, firstname, lastname;" % {
            'month': month, 'year': year})
    users = cur.fetchall()
    # loop through the users, constructing a dictionary
    user_list = []
    for u in users:
        new_user = {}
        new_user['name'] = u[0] + ' ' + u[1]
        new_user['login'] = u[2]
        user_list.append(new_user)

    # if the month passed in is NOT this month, then "today" should be the last day of the month
    today = datetime.date.today()
    if int(month) != datetime.date.today().month:
        today = datetime.date(int(year), int(month), int(calendar.monthrange(int(year), int(month))[1]))

    # get a list of holidays for this year
    holiday_list = get_holidays(int(year))

    # setup a count for all weekdays
    # (Monday = [0], Tuesday = [1], etc...)
    weekdays = [0, 0, 0, 0, 0, 0, 0]

    # loop through from the first day to today
    day = 1
    while day < today.day:
        # get the new date
        next_day = datetime.date(today.year, today.month, day)
        # add one day to this weekday IF it is not a holiday
        if next_day not in holiday_list:
            weekdays[next_day.weekday()] += 1
        day += 1

    # Add up how many weekdays ([0] => [4])
    total = weekdays[0] + weekdays[1] + weekdays[2] + weekdays[3] + weekdays[4]

    # which rate do we use? (0.9 or 0.7?)
    billable = 1.0

    if request.user.is_staff:
        billable = 0.55

    # what to expect:
    total = round((total * 8) * billable, 1)

    h_list = []
    for holiday in holiday_list:
        h = {}
        h['date'] = holiday['date'].isoformat()
        h['name'] = holiday['name']
        h_list.append(h)

    context = {'entries': entry_list,
               'projects': project_list,
               'activities': activity_list,
               'total': total_hours,
               'weekdays': total,
               'user_list': user_list,
               'user': request.user.username,
               'holidays': h_list,
               'logas': logas_list,
               'support': support,
               'billable': (billable * 8)}

    return HttpResponse(json.dumps(context))


@login_required
@user_is_in_manager_group
def get_entries_home_page(request):
    """
        Generates the landing page for anyone to come to for them to change/modify
        their hours.  It allows for users to move hours from project to project.
        """
    print "HEY"
    # target
    target = request.user.username
    if request.user.is_staff and 'target' in request.GET and request.GET['target'] != '':
        target = request.GET['target']

    # what is the starting month?
    month_start = request.GET['start'].split('/')[0]

    # what is the starting year?
    year_start = request.GET['start'].split('/')[2]

    # what is the ending month?
    month_end = request.GET['end'].split('/')[0]

    # what is the ending year?
    year_end = request.GET['end'].split('/')[2]

    # connect to the database
    cur = connection.cursor()

    # how should we order things? (ascenting/descending)
    order = 'ASC'
    if request.GET['by'] == 'desc':
        order = 'DESC'

    # how do we want to order our entries?
    order_by = ''
    if request.GET['order'] == 'project':
        order_by = 'projects.name ' + order + ', time_entries.spent_on ASC'
    if request.GET['order'] == 'date':
        order_by = 'time_entries.spent_on ' + order + ', projects.name ASC'
    if request.GET['order'] == 'hours':
        order_by = 'time_entries.hours ' + order + ', projects.name ASC, time_entries.spent_on ASC'
    if request.GET['order'] == 'activity':
        order_by = 'enumerations.name ' + order + ', projects.name ASC, time_entries.spent_on ASC'

    # get the records for this user, month, and year
    cur.execute(
        "SELECT time_entries.id, time_entries.project_id, projects.name, time_entries.issue_id, time_entries.hours, "
        "time_entries.comments, enumerations.name, time_entries.spent_on, custom_values.value, enumerations.id, "
        "projects.id FROM time_entries INNER JOIN custom_values ON custom_values.customized_id = time_entries.id "
        "INNER JOIN projects ON projects.id = time_entries.project_id "
        "INNER JOIN enumerations ON enumerations.id = time_entries.activity_id WHERE "
        "time_entries.spent_on >= '%(start)s'::date AND time_entries.spent_on <= '%(end)s'::date "
        "AND custom_values.value != '' ORDER BY %(order)s;" % {
            'start': request.GET['start'], 'end': request.GET['end'],
            'user': target, 'order': order_by})

    entries = cur.fetchall()

    # assemble into a list
    entry_list = []
    entry_number = 1
    total_hours = 0
    support = 0
    for entry in entries:
        new_entry = {}
        entry_number *= -1
        new_entry['id'] = entry[0]
        new_entry['project'] = entry[1]
        new_entry['name'] = entry[2]
        new_entry['issue'] = entry[3]
        new_entry['hours'] = entry[4]
        new_entry['comments'] = entry[5]
        new_entry['activity'] = entry[6]
        new_entry['date'] = entry[7].isoformat()
        new_entry['number'] = entry_number
        new_entry['logas'] = entry[8]
        new_entry['activity_id'] = entry[9]
        new_entry['project_id'] = entry[10]
        entry_list.append(new_entry)

        # update our total hours (if it's billable!)
        if 'non-billable' not in entry[6].lower():
            total_hours += entry[4]
        else:
            support += entry[4]

    # round our total hours
    total_hours = round(total_hours, 2)

    # round support hours
    support = round(support, 2)

    # get a list of all projects this user is a member of
    cur.execute(
        "SELECT projects.id, projects.name FROM projects INNER JOIN members ON projects.id = members.project_id "
        "INNER JOIN users ON users.id = members.user_id ORDER BY projects.name;")
    projects = cur.fetchall()

    # loop through the projects, constructiong a dictionary
    project_list = []
    for project in projects:
        new_project = {}
        new_project['id'] = project[0]
        new_project['name'] = project[1]
        # for each project, get a list of activities!
        # first get any that are specific to our project
        cur.execute(
            "SELECT name FROM enumerations WHERE type = 'TimeEntryActivity' and project_id = %(proj)s "
            "and active = FALSE;" % {
                'proj': project[0]})
        exclusions = cur.fetchall()
        exclude_list = []
        for ex in exclusions:
            exclude_list.append(ex[0])

        # now get the defaults
        cur.execute(
            "SELECT id, name FROM enumerations WHERE type = 'TimeEntryActivity' and active = TRUE "
            "and project_id is NULL;")
        activity = cur.fetchall()

        activity_list = []
        for act in activity:
            if act[1] in exclude_list:
                continue
            active = {}
            active['id'] = act[0]
            active['name'] = act[1]
            activity_list.append(active)
        new_project['activities'] = activity_list

        project_list.append(new_project)

    # get a list of activities
    cur.execute(
        "SELECT min(id), name FROM enumerations where type = 'TimeEntryActivity' "
        "AND active = TRUE GROUP BY name ORDER BY name;")
    activities = cur.fetchall()
    # loop through the activities, constructing a dictionary
    activity_list = []
    for activity in activities:
        new_act = {}
        new_act['id'] = activity[0]
        new_act['name'] = activity[1]
        activity_list.append(new_act)

    # get a list of "log as" options
    cur.execute("SELECT possible_values FROM custom_fields WHERE lower(name) = lower('Log As');")
    logas = cur.fetchall()
    # loop through, constructing a dictionary
    logas = logas[0][0].split('\n')[1:-1]
    logas_list = []
    for l in logas:
        new_logas = {}
        new_logas['name'] = l[2:]
        logas_list.append(new_logas)

    # get a list of users who have time logged for this month/year
    # cur.execute(
    #     "SELECT firstname, lastname, login, max(CASE WHEN (time_entries.tmonth = %(month)s "
    #     "and time_entries.tyear = %(year)s) THEN 2 ELSE 1 end) AS t FROM users "
    #     "INNER JOIN time_entries ON time_entries.user_id = users.id "
    #     "GROUP BY firstname, lastname, login "
    #     "ORDER BY t DESC, firstname, lastname;" % {
    #         'month': month, 'year': year})

    # get a list of users who have time logged for this month/year
    cur.execute(
        "SELECT firstname, lastname, login FROM users "
        "ORDER BY login DESC, firstname, lastname;")
    users = cur.fetchall()
    # loop through the users, constructing a dictionary
    user_list = []
    for u in users:
        new_user = {}
        new_user['name'] = u[0] + ' ' + u[1]
        new_user['login'] = u[2]
        user_list.append(new_user)

    # if the month passed in is NOT this month, then "today" should be the last day of the month
    today = datetime.date.today()
    # if int(month) != datetime.date.today().month:
    #     today = datetime.date(int(year), int(month), int(calendar.monthrange(int(year), int(month))[1]))

    # get a list of holidays for this year
    holiday_list = [] #get_holidays(int(year))

    # setup a count for all weekdays
    # (Monday = [0], Tuesday = [1], etc...)
    weekdays = [0, 0, 0, 0, 0, 0, 0]

    # loop through from the first day to today
    day = 1
    while day < today.day:
        # get the new date
        next_day = datetime.date(today.year, today.month, day)
        # add one day to this weekday IF it is not a holiday
        if next_day not in holiday_list:
            weekdays[next_day.weekday()] += 1
        day += 1

    # Add up how many weekdays ([0] => [4])
    total = weekdays[0] + weekdays[1] + weekdays[2] + weekdays[3] + weekdays[4]

    # which rate do we use? (0.9 or 0.7?)
    billable = 1.0

    if request.user.is_staff:
        billable = 0.55

    # what to expect:
    total = round((total * 8) * billable, 1)

    h_list = []
    for holiday in holiday_list:
        h = {}
        h['date'] = holiday['date'].isoformat()
        h['name'] = holiday['name']
        h_list.append(h)

    context = {'entries': entry_list,
               'projects': project_list,
               'activities': activity_list,
               'total': total_hours,
               'weekdays': total,
               'user_list': user_list,
               'user': request.user.username,
               'holidays': h_list,
               'logas': logas_list,
               'support': support,
               'billable': (billable * 8)}

    return HttpResponse(json.dumps(context))



@login_required
@user_is_in_manager_group
def get_distribution(request):
    # connect to the database
    cur = connection.cursor()

    # are we a manager?
    cur.execute("select id from users where login = '%(username)s';" % {'username': request.user.username})
    id = cur.fetchone()[0]
    if 'id' in request.GET:
        id = request.GET['id']

    # first check to make sure we have all we need
    # do we have a date range?
    if 'start_date' not in request.GET or request.GET['start_date'] == '':
        return HttpResponse('No Start Date Found')
    if 'end_date' not in request.GET or request.GET['end_date'] == '':
        return HttpResponse('No End Date Found')

    # do we have a type?
    type = 'programmer'
    if 'type' in request.GET:
        type = request.GET['type']

    # now that we have everything, let's get what we need!
    if type == 'project':
        # get user and their total hours
        query = "select distinct(user_id), users.firstname, users.lastname, SUM(hours) FROM time_entries " \
                "INNER JOIN users ON time_entries.user_id = users.id WHERE project_id = %(id)s " \
                "and spent_on >= '%(start)s'::date and spent_on <= '%(end)s'::date " \
                "group by user_id, users.firstname, users.lastname;" % {
                    'id': id, 'start': request.GET['start_date'], 'end': request.GET['end_date']}
        cur.execute(query)

        records = cur.fetchall()

        # get the total hours
        query = "select SUM(hours) FROM time_entries WHERE project_id = %(id)s and spent_on >= '%(start)s' " \
                "and spent_on <= '%(end)s';" % {
                    'id': id, 'start': request.GET['start_date'], 'end': request.GET['end_date']}
        cur.execute(query)
        total = cur.fetchone()
        if total is not None:
            total = total[0]
        else:
            total = 0

        # loop through all records
        entry_list = []

        for rec in records:
            new_entry = {}
            new_entry['id'] = rec[0]
            new_entry['name'] = rec[1] + ' ' + rec[2]
            new_entry['hours'] = rec[3]
            entry_list.append(new_entry)

        # get the budget for this project
        query = "select value from custom_values where customized_id = %(project)s " \
                "and custom_field_id = 12 and customized_type = 'Project';" % {
                    'project': id}
        cur.execute(query)
        budget = cur.fetchone()
        if budget is not None:
            budget = budget[0]
        else:
            budget = 0

        # get the accumulative (if it exists)
        query = "select value from custom_values where customized_id = %(project)s " \
                "and custom_field_id = 13 and customized_type = 'Project';" % {
                    'project': id}
        cur.execute(query)
        accumulative = cur.fetchone()
        if accumulative is not None:
            accumulative = accumulative[0]
        else:
            accumulative = 0

        context = {'entries': entry_list, 'total': total, 'budget': budget, 'accumulative': accumulative}
        return HttpResponse(json.dumps(context))

    if type == 'programmer':
        cur.execute("select login from users where id = %(id)s;" % {'id': id})
        username = cur.fetchone()[0]
        # get user and their total hours
        query = "select distinct(project_id), projects.name, SUM(hours) FROM time_entries " \
                "INNER JOIN projects ON time_entries.project_id = projects.id " \
                "INNER JOIN users ON time_entries.user_id = users.id WHERE login = '%(id)s' " \
                "and spent_on >= '%(start)s' and spent_on <= '%(end)s' group by project_id, projects.name;" % {
                    'id': username, 'start': request.GET['start_date'], 'end': request.GET['end_date']}
        cur.execute(query)

        records = cur.fetchall()

        # get the total hours
        query = "select SUM(hours) FROM time_entries INNER JOIN users ON time_entries.user_id = users.id " \
                "WHERE login = '%(id)s' and spent_on >= '%(start)s' and spent_on <= '%(end)s';" % {
                    'id': username, 'start': request.GET['start_date'], 'end': request.GET['end_date']}
        cur.execute(query)
        total = cur.fetchone()[0]

        # loop through all records
        entry_list = []

        for rec in records:
            new_entry = {}
            new_entry['id'] = rec[0]
            new_entry['name'] = rec[1]
            new_entry['hours'] = rec[2]
            entry_list.append(new_entry)

        context = {'entries': entry_list, 'total': total}
        return HttpResponse(json.dumps(context))


@login_required
@user_is_in_manager_group
def get_all_distribution(request):
    # connect to the database
    cur = connection.cursor()

    # first check to make sure we have all we need
    # do we have a date range?
    if 'start_date' not in request.GET or request.GET['start_date'] == '':
        return HttpResponse('No Start Date Found')
    if 'end_date' not in request.GET or request.GET['end_date'] == '':
        return HttpResponse('No End Date Found')


    # get user and their total hours
    # query = "select distinct(project_id), projects.name, SUM(hours) FROM time_entries " \
    #         "INNER JOIN projects ON time_entries.project_id = projects.id " \
    #         "WHERE " \
    #         "spent_on >= '%(start)s' and spent_on <= '%(end)s' group by project_id, projects.name;" % {
    #         'start': request.GET['start_date'], 'end': request.GET['end_date']}
    # cur.execute(query)
    cur.execute("SELECT id, name FROM projects WHERE "
                "parent_id is NULL;")

    parents = cur.fetchall()
    total_hours = 0.0

    parent_list = []

    for parent_project in parents:
        parent_obj = {
            'id': parent_project[0],
            'name': parent_project[1],
            'subprojects': [],
            'total_hours': 0.0,
            'percent': 0.0
        }
        # get a list of all sub-projects
        cur.execute("SELECT id, name FROM projects WHERE parent_id = %(parent)s or id = %(parent)s;" % {
            'parent': parent_project[0]
        })

        sub_projects = cur.fetchall()
        for sub_project in sub_projects:
            s_obj = {
                'id': sub_project[0],
                'name': sub_project[1],
                'total_hours': 0.0,
                'percent': 0.0
            }

            cur.execute("SELECT sum(hours) FROM time_entries WHERE project_id = %(project)s AND "
                        "spent_on >= '%(start)s' and spent_on <= '%(end)s';" % {
                'start': request.GET['start_date'],
                'end': request.GET['end_date'],
                'project': sub_project[0]
            })
            hours = cur.fetchone()
            if hours[0] is not None or hours[0] > 0:
                s_obj['total_hours'] = hours[0]
                parent_obj['total_hours'] += hours[0]
                total_hours += hours[0]

            parent_obj['subprojects'].append(s_obj)

        parent_list.append(parent_obj)

    # now run through and calculate percentages
    for parent in parent_list:
        # set the parent's percentage
        parent['percent'] = (float(parent['total_hours']) / float(total_hours) * 100.0)

        # for each sub-project
        for sub_project in parent['subprojects']:
            sub_project['percent'] = (float(sub_project['total_hours']) / float(total_hours) * 100.0)

        print parent['name'], parent['percent']


    # # get the total hours
    # query = "select SUM(hours) FROM time_entries INNER JOIN users ON time_entries.user_id = users.id " \
    #         "WHERE spent_on >= '%(start)s' and spent_on <= '%(end)s';" % {
    #             'start': request.GET['start_date'], 'end': request.GET['end_date']}
    # cur.execute(query)
    # total = cur.fetchone()[0]
    #
    # # loop through all records
    # entry_list = []
    #
    # for rec in records:
    #     new_entry = {}
    #     new_entry['id'] = rec[0]
    #     new_entry['name'] = rec[1]
    #     new_entry['hours'] = rec[2]
    #     entry_list.append(new_entry)

    context = {'entries': parent_list, 'total': total_hours}
    return HttpResponse(json.dumps(context))
