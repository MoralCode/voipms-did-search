import re
import csv

from requests import get
from rich.console import Console
from rich.table import Table
from dotenv import load_dotenv
import os
from pathlib import Path
import json

load_dotenv()
## App below

api_root = "https://voip.ms/api/v1/rest.php"

noyes = ["N","Y"]

def api_action(action: str,**kwargs):
    params = {
        "content_type": "json",
        "api_username": os.getenv("VOIPMS_API_USERNAME"),
        "api_password": os.getenv("VOIPMS_API_PASSWORD"),
        "method": action
    }
    if len(kwargs) > 0:
        params.update(kwargs)
    r = get(api_root,params=params)
    if r.status_code == 200:
        return r.json()
    else:
        raise Exception(r.url,r.request.body)

def strToT9(string: str):
    t9_str_list = []
    t9_tuple = ("","","2ABC","3DEF","4GHI","5JKL","6MNO","7PQRS","8TUV","9WXYZ")
    for letter in string:
        for key in t9_tuple[2:]:
            if letter.upper() in key:
                t9_str_list.append(t9_tuple.index(key))
                break
    t9_str = "".join([str(x) for x in t9_str_list])
    if len(t9_str) == len(string):
        return t9_str
    else:
        raise TypeError("Search input must be alphanumeric only")

def add_row(table,did,search_string,search_term):
    start = did['did'].index(search_string)
    end = start + len(search_string)
    highlight_number = f"{did['did'][0:start]}[b green3]{did['did'][start:end]}[/b green3]{did['did'][end:]}"
    highlight_search = f"{did['did'][0:start]}[b green3]{search_term.upper()}[/b green3]{did['did'][end:]}"
    table.add_row(
        did['state'],
        f"{highlight_number}\n{highlight_search}",
        f"${did['perminute_setup']} / ${did['flat_setup']}",
        f"${did['perminute_monthly']} / ${did['flat_monthly']}",
        f"${did['perminute_minute']} / ${did['flat_minute']}",
        noyes[did['sms']]
    )

def main():
    console = Console()
    states = []
    results = []
    search_term = ""
    term_check_bad = lambda x: re.match(r'[^a-zA-Z0-9]',x) or len(x) > 10
    while term_check_bad(search_term) or len(search_term) < 3:
        search_term = console.input("Primary search> ")
        if term_check_bad(search_term):
            console.print("Invalid search term, must be 3-10 alphanumeric characters")

    stateCache = Path("states.json")
    if not stateCache.exists():
        try:
            response = api_action("getStates")
            states.extend(response['states'])
            stateCache.write_text(json.dumps(states))
        except Exception as e:
            console.print_exception()
    else:
        states = json.loads(stateCache.read_text())

    search_string = strToT9(search_term)
    search_response: dict[str,str|list[dict[str,str|int]]] = api_action("searchDIDsUSA",type="contains",query=search_string)
    results.extend(search_response['dids'])
    console.print(f"     Found [b]{len(search_response['dids'])}[/b] numbers")
    if len(results) > 0:
        table = Table(show_header=True,header_style="bold red",show_lines=True)
        for column in ["State","Number","Setup","Monthly","Minute","SMS?", "Searchterm"]:
            table.add_column(column)
        filename = f"all_results.csv"
        with open(filename,"w",newline="") as f:
            csvfile = csv.writer(f)
            columns = ["state","did","sms", "searchterm"]
            csvfile.writerow(columns)
            for did in results:
                csvfile.writerow([did['state'],did['did'],noyes[did['sms']], search_term])
                add_row(table,did,search_string,search_term)

        console.print(table)
        console.print(f"Wrote results to [b]{filename}[/b]")
    else:
        console.print("Did not find any results.")

if __name__ == "__main__":
    main()