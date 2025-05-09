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
    if string.isnumeric():
        return string

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

def performSearch(search_term: str, search_type="contains", limit_state=False):
    """perform a search using the API

    Args:
        search_term (str): the term to search for (numbers or letters, 3-10 digits)
        search_type (str, optional): the type of search to perform, contains, starts or ends. Defaults to "contains".
        limit_state (optional): whether to limit the state (if so, this should be set to the full state name or the state acronym). Defaults to False.

    Returns:
        _type_: _description_
    """
    if search_term.isalpha():
        search_string = strToT9(search_term)
    else: 
        search_string = search_term

    api_action_args = {
        "type": search_type,
        "query": search_string,

    }
    if limit_state:
        api_action_args.update({
            "state": limit_state
        })
    search_response: dict[str,str|list[dict[str,str|int]]] = api_action("searchDIDsUSA", **api_action_args)
    resp = search_response.get("dids")

    if resp is None:
        # no results
        return []
    else:
        for r in resp:
            r["searchterm"] = search_term
        return resp

def term_check_bad(x):
    return not x.isalnum() and len(x) < 10 and len(x) > 3

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("--search-type", choices=["contains", "starts", "ends"], default="contains", help="the type of search to perform")
    parser.add_argument("--limit-state", type=str, help="limit search to one state")
    parser.add_argument("--longest-substring", action="store_true", help="iteratively reduce the search string size until matches are found")
    parser.add_argument("searchterm",nargs=argparse.REMAINDER, help="one or more terms to search for")

    args = parser.parse_args()

    console = Console()
    states = []
    results = []
    searchterms = args.searchterm or []

    for t in searchterms:
        if term_check_bad(t):
            console.print(f"Invalid search term {t}, must be 3-10 alphanumeric characters")
            del searchterms[searchterms.index(t)]

    search_term = None

    if len(searchterms) == 0:
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

    
    limit_state = False
    if args.limit_state is not None:
        state_codes = [s['state'] for s in states]
        state_names = [s['description'] for s in states]
        if args.limit_state.upper() in state_codes:
            limit_state = args.limit_state.upper()
        elif args.limit_state.upper() in state_names:
            idx = state_names.index(args.limit_state.upper())
            limit_state = state_codes[idx]

    for search_term in searchterms:
        console.print(f"Searching for'[b]{search_term.upper()}[/b]'")
        res = performSearch(search_term, args.search_type, limit_state)

        while len(res) == 0 and args.longest_substring and len(search_term) > 3:
            if args.search_type != "startswith":
                search_term = search_term[1:]
            else:
                search_term = search_term[:-1]
            console.print(f"Searching for'[b]{search_term.upper()}[/b]'")
            res = performSearch(search_term, args.search_type, limit_state)

        results.extend(res)



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

                add_row(table,did,strToT9(search_term),search_term)
        console.print(table)
        console.print(f"Wrote results to [b]{filename}[/b]")
    else:
        console.print("Did not find any results.")

if __name__ == "__main__":
    main()