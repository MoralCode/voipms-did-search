import re
import csv

from requests import get
from rich.console import Console
from rich.table import Table
from dotenv import load_dotenv
import os
from pathlib import Path
import json
import argparse

load_dotenv()
## App below

api_root = "https://voip.ms/api/v1/rest.php"

def noyes(val:bool):
    return "Y" if bool(val) else 'N'

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
        noyes(did['sms'])
    )

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("--search-type", choices=["contains", "startswith", "endswith"], default="contains", help="the type of search to perform")
    parser.add_argument("--limit-state", type=str, help="limit search to one state")

    args = parser.parse_args()

    console = Console()
    states = []
    results = []
    searchterms = []

    search_term = None
    term_check_bad = lambda x: not x.isalnum() and len(x) < 10 and len(x) > 3

    while search_term != "":
        console.print("Search Terms: " + ",".join(searchterms))

        search_term = console.input("add search term> ")
        search_term = search_term.strip()
        if search_term == "":
            break
        elif term_check_bad(search_term):
            console.print("Invalid search term, must be 3-10 alphanumeric characters")
        else:
            searchterms.append(search_term)


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


    for search_term in searchterms:
        if search_term.isalpha():
            search_string = strToT9(search_term)
        else: 
            search_string = search_term
        console.print(f"Searching for'[b]{search_term.upper()}[/b]' ({search_string})")

        limit_state = False
        if args.limit_state is not None:
            state_codes = [s['state'] for s in states]
            state_names = [s['description'] for s in states]
            if args.limit_state.upper() in state_codes:
                limit_state = args.limit_state.upper()
            elif args.limit_state.upper() in state_names:
                idx = state_names.inx(args.limit_state.upper())
                limit_state = state_codes[idx]

        api_action_args = {
            "type": args.search_type,
            "query": search_string,

        }
        if limit_state:
            api_action_args.update({
                "state": limit_state
            })
        search_response: dict[str,str|list[dict[str,str|int]]] = api_action("searchDIDsUSA", **api_action_args)
        resp = search_response['dids']
        for r in resp:
            r["searchterm"] = search_term
        results.extend(resp)


    console.print(f"     Found [b]{len(results)} numbers")
    if len(results) > 0:
        table = Table(show_header=True,header_style="bold red",show_lines=True)
        for column in ["State","Number","Setup","Monthly","Minute","SMS?", "Searchterm"]:
            table.add_column(column)
        filename = f"all_results.csv"
        file_existed = Path(filename).exists()
        with open(filename,"a") as f:
            columns = ["state","did","sms", "searchterm"]
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
            if not file_existed:
                writer.writeheader()

            for did in results:
                did['sms'] = noyes(did['sms'])
                writer.writerow(did)
                add_row(table,did,did['searchterm'],search_term)

        console.print(table)
        console.print(f"Wrote results to [b]{filename}[/b]")
    else:
        console.print("Did not find any results.")

if __name__ == "__main__":
    main()