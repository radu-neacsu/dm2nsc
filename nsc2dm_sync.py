import arrow
import re
import requests

from secret import USERNAME, PASSWORD, NS_URL

DIABETES_M_CATEGORY = 333283014
DIABETES_M_INSULIN_TYPE = 13  # NovoRapid
NIGHTSCOUT_MM_AUTHOR = 'openaps://medtronic/723'


def get_login():
    return requests.post('https://analytics.diabetes-m.com/api/v1/user/authentication/login', json={
        'username': USERNAME,
        'password': PASSWORD,
        'device': ''
    }, headers={
        'origin': 'https://analytics.diabetes-m.com'
    })


def get_last_diabetes_m(login):
    auth_code = login.json()['token']
    fromDate = arrow.now().shift(days=-1)
    response = requests.post('https://analytics.diabetes-m.com/api/v1/diary/entries/list',
                             cookies=login.cookies,
                             headers={
                                 'origin': 'https://analytics.diabetes-m.com',
                                 'authorization': 'Bearer ' + auth_code
                             }, json={
            'categories': [DIABETES_M_CATEGORY],
            'fromDate': fromDate.timestamp,
            'toDate': -1,
            'isDescOrder': 'true',
            'page_count': 1,
            'page_start_entry_time': 0
        })
    if response.status_code == 200:
        x = response.json()
        entry = response.json()['logEntryList'].pop(0)
        return arrow.get(entry['entry_time'] / 1000)


def get_last_nightscout_treatments(date: arrow):
    entries = []
    allowedEvents = ['Correction Bolus', 'Temp Basal']
    last = requests.get(
        NS_URL + 'api/v1/treatments?find[enteredBy]=/' + re.escape(
            NIGHTSCOUT_MM_AUTHOR) + '/&find[created_at][$gt]=' + date.isoformat())  # +urllib.parse.quote(NS_AUTHOR))
    if last.status_code == 200:
        js = last.json()
        if len(js) > 0:
            for entry in js:
                if entry['eventType'] in allowedEvents:
                    entries.append(entry)
    return entries


def convert_nightscout_to_diabetes_m(entries):
    out = []
    for entry in entries:
        notes = ''
        if 'notes' in entry:
            notes = entry['notes']
        microtimestamp = arrow.get(entry['created_at']).to('utc').timestamp * 1000
        dat = {
            'entry_time': microtimestamp,
            'last_modified': microtimestamp,
            'notes': notes,
            'category': DIABETES_M_CATEGORY,
            'bolus_insulin_type': DIABETES_M_INSULIN_TYPE,
            'basal_insulin_type': DIABETES_M_INSULIN_TYPE
        }
        if entry['eventType'] == 'Correction Bolus':
            dat['carb_bolus'] = entry['insulin']
        elif entry['eventType'] == 'Temp Basal':
            dat['basal'] = entry['absolute']
            dat['basal_is_rate'] = True
            dat['notes'] = 'Temp basal: ' + str(entry['absolute']) + '/h -> ' + str(entry['duration']) + ' min'
        else:
            continue
        out.append(dat)
    return out


def upload_to_dm(entries, login):
    auth_code = login.json()['token']
    out = []
    for entity in entries:

        response = requests.post('https://analytics.diabetes-m.com/api/v1/diary/entries/validate',
                                 cookies=login.cookies,
                                 headers={
                                     'origin': 'https://analytics.diabetes-m.com',
                                     'authorization': 'Bearer ' + auth_code
                                 }, json=entity)
        if response.json()['status'] == "OK":
            response = requests.post('https://analytics.diabetes-m.com/api/v1/diary/entries/save_as_new',
                                     cookies=login.cookies,
                                     headers={
                                         'origin': 'https://analytics.diabetes-m.com',
                                         'authorization': 'Bearer ' + auth_code
                                     }, json=entity)
            out.append(response.json())
    return out


def main():
    login = get_login()
    last_entry = get_last_diabetes_m(login)
    entries = get_last_nightscout_treatments(last_entry)
    new_entries = convert_nightscout_to_diabetes_m(entries)
    uploaded_entities = upload_to_dm(new_entries, login)

    exit(1)


if __name__ == '__main__':
    main()
