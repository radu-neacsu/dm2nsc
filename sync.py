import requests, json, arrow, hashlib, datetime
from decimal import Decimal, ROUND_HALF_UP
from secret import USERNAME, PASSWORD, NS_URL, NS_SECRET

# this is the enteredBy field saved to Nightscout
NS_AUTHOR = "Diabetes-M"

DO_MYSUGR_PROCESSING = (USERNAME == 'jwoglom')


def get_login():
    return requests.post('https://analytics.diabetes-m.com/api/v1/user/authentication/login', json={
        'username': USERNAME,
        'password': PASSWORD,
        'device': ''
    }, headers={
        'origin': 'https://analytics.diabetes-m.com'
    })


def get_entries(login):
    auth_code = login.json()['token']
    fromDate = arrow.now().shift(days=-1)
    print("Loading entries...")
    entries = requests.post('https://analytics.diabetes-m.com/api/v1/diary/entries/list',
                            cookies=login.cookies,
                            headers={
                                'origin': 'https://analytics.diabetes-m.com',
                                'authorization': 'Bearer ' + auth_code
                            }, json={
            'fromDate': -1,
            'toDate': -1,
            'includeCarbs': 'true',
            'isDescOrder': 'true',
            'page_count': 10,
            'page_start_entry_time': 0
        })
    return entries.json()


def to_mgdl(mmol):
    return round(mmol * 18)


def convert_nightscout(entries, start_time=None):
    out = []
    for entry in entries:
        time = arrow.get(int(entry["entry_time"]) / 1000).to(entry["timezone"])
        notes = entry["notes"]
        notes.replace("[Nightscout]", "")
        if start_time and start_time >= time:
            continue

        author = NS_AUTHOR

        dat = {
            "eventType": "Meal Bolus",
            "created_at": time.format(),
            "carbs": entry["carbs"],
            "protein": entry["proteins"],
            "dm_entry_id": entry["entry_id"],
            "dm_extended_bolus": entry["extended_bolus"],
            "dm_extended_bolus_duration": entry["extended_bolus_duration"],
            "dm_carb_ratio_factor": entry["carb_ratio_factor"],
            "fat": entry["fats"],
            "notes": notes,
            "enteredBy": author
        }
        out.append(dat)
        add_slow_carbs_entries(dat, out)

    return out

def add_slow_carbs_entries(entry, out=[]):
    if entry['dm_extended_bolus'] > 0 and entry['dm_extended_bolus_duration'] > 0:
        number_of_ecarb_entries = int(entry['dm_extended_bolus_duration'] / 15)
        total_eCarb = int(round(entry['dm_extended_bolus'] * entry['dm_carb_ratio_factor']))

        time = arrow.get(entry["created_at"])
        i = 0
        while number_of_ecarb_entries > i:
            eCarb = total_eCarb / (number_of_ecarb_entries-i)
            eCarb = int(Decimal(eCarb).to_integral_value(rounding=ROUND_HALF_UP))
            if total_eCarb < eCarb:
                eCarb = total_eCarb
            i += 1
            notes = "eCarb " + str(i) + "/" + str(number_of_ecarb_entries)
            author = NS_AUTHOR+":eCarb:"+str(entry['dm_entry_id'])
            time = time.shift(minutes=15)
            dat = {
                "eventType": "Meal eCarb",
                "created_at": time.format(),
                "carbs": eCarb,
                "notes": notes,
                "enteredBy": author
            }
            total_eCarb -= eCarb
            out.append(dat)

def upload_nightscout(ns_format):
    upload = requests.post(NS_URL + 'api/v1/treatments?api_secret=' + NS_SECRET, json=ns_format, headers={
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'api-secret': hashlib.sha1(NS_SECRET.encode()).hexdigest()
    })
    print("Nightscout upload status:", upload.status_code, upload.text)


def get_last_nightscout():
    last = requests.get(
        NS_URL + 'api/v1/treatments?count=1&find[enteredBy]=Diabetes-M')  # +urllib.parse.quote(NS_AUTHOR))
    if last.status_code == 200:
        js = last.json()
        if len(js) > 0:
            return arrow.get(js[0]['created_at']).datetime


def main():
    print("Logging in to Diabetes-M...", datetime.datetime.now())
    login = get_login()
    if login.status_code == 200:
        entries = get_entries(login)
    else:
        print("Error logging in to Diabetes-M: ", login.status_code, login.text)
        exit(0)

    print("Loaded", len(entries["logEntryList"]), "entries")

    # skip uploading entries past the last entry
    # uploaded to Nightscout by `NS_AUTHOR`
    ns_last = get_last_nightscout()
    ns_format = convert_nightscout(entries["logEntryList"], ns_last)

    print("Converted", len(ns_format), "entries to Nightscout format")

    print("Uploading", len(ns_format), "entries to Nightscout...")
    upload_nightscout(ns_format)


if __name__ == '__main__':
    main()
