from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config
from pyramid.renderers import JSONP

from tutorial.nosql import fetch_user_event, fetch_all_user_event, fetch_all_events_by_task_name

import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import pickle
import urllib.parse
import string
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.feature_extraction.text import TfidfVectorizer

# load task model
with open("model/six_class_task_model_with_context.pkl", "rb") as f:
    task_model_six = pickle.load(f)
with open("model/three_class_task_model_with_context.pkl", "rb") as f:
    task_model_three = pickle.load(f)
# load vectorizer
with open("model/context_vectorizer.pkl", "rb") as f:
    vectorizer = pickle.load(f)

push_status = {}

@view_config(route_name='hello', request_method='GET', renderer='tutorial:templates/mytemplate.jinja2')
def hello_world(request):
    return {'Hello': 'world'}

@view_config(route_name='query', request_method='GET', renderer='json')
def query(request):
    return {'Hello': 'query'}

# @view_config(route_name='search', request_method='GET', renderer='tutorial:templates/mytemplate.jinja2')
# def search(request):
#     querying = request.params.get("q")
#     if querying is None or len(querying) == 0:
#         return {
#             'querying': "",
#             'results': [],
#             'content': {},
#         }
#     # print('Incoming request', querying)
#     # results = inference(querying, tokenizer, model, kid_content_dict, args)
#     results, content = inference(
#         querying,
#         request.registry['tokenizer'],
#         request.registry['model'],
#         request.registry['kid_content_dict'],
#         request.registry['args'])
#     return {
#         'querying': querying,
#         'results': results,
#         'content': content,
#     }

# @view_config(route_name="get_all_message", request_method="GET", renderer="json")
# def get_all_message(request):
#     task_names = ["Adding Moodle Forum", "Embedding Moodle Media Resource", "Updating Moodle Information"]
#     results = {}
#     for task_name in task_names:
#         expert_trace = fetch_all_events_by_task_name(task_name)
#         expert_trace = expert_trace["table_result"]
#         if len(expert_trace) == 0:
#             return None
#         else:
#             trace_info = expert_trace[list(expert_trace.keys())[0]]
#             trace_message = expert_replay(trace_info)
#             results[task_name] = trace_message
#     return results

@view_config(route_name="task_classification", request_method="GET", renderer="json")
def task_classification(request):
    invalid_result = {"task_name": "", "certainty": 0, "message": "", "interval": 10000}
    # get current time
    current_time = datetime.now()
    if "userid" not in request.params:
        return invalid_result
    user_id = request.params.get("userid")
    result = fetch_all_user_event(user_id, "timestamp")
    trace = pd.DataFrame(result["table_result"])
    if user_id not in push_status:
        push_status[user_id] = {"Adding Moodle Forum": None,
                                "Embedding Moodle Media Resource": None,
                                "Updating Moodle Information": None,
                                "Updating Assessment Information": None,
                                "Embedding Moodle Media Resource in Weekly Content": None,
                                "Updating Unit Information": None,
                                "Updating Consultation Information": None,
                                "Updating Weekly Information": None}
    basic_info = current_time.strftime('%Y-%m-%d %H:%M:%S') + " " + user_id
    interval = 1000
    if "interval" in request.params:
        interval = request.params.get("interval")
        interval = int(interval)

    if interval == 0:
        print(basic_info + ": Invalid interval")
        return invalid_result

    time_delta_in_second = 10

    if trace is None or len(trace) == 0:
        print(basic_info + ": No trace found")
        return invalid_result

    target_events = ['START', 'beforeunload', 'click', 'close', 'keydown', 'onmouseover', 'open', 'scroll', 'select', 'server-record', 'submit']
    stop_words = set(stopwords.words('english'))
    # converting timestamp
    trace["timestamp"] = pd.to_datetime(trace["timestamp"], unit="ms")
    # get current time
    current_time = datetime.now()
    # Convert current time to a timestamp
    current_timestamp = current_time.timestamp()
    # get [time_delta_in_minute] ago
    ago = current_time - timedelta(seconds=time_delta_in_second)
    records = trace[(trace["timestamp"] >= ago) & (trace["timestamp"] <= current_time)]
    if records is None or len(records) == 0:
        print(basic_info + ": No records found")
        return invalid_result
    # records = trace.iloc[24:71] # for testing
    # get the attributes
    no_events = len(records)
    no_unique_events = len(records["event_type"].unique())
    no_unique_tags = len(records["tag_name"].unique())
    avg_time_between_operations = records["timestamp"].diff().dt.total_seconds().dropna()
    counts = records["event_type"].value_counts()
    dt = [no_events, no_unique_events, no_unique_tags]
    if len(avg_time_between_operations) == 0:
        dt += [0, 0]
    elif len(avg_time_between_operations) == 1:
        dt += [avg_time_between_operations.mean(), 0]
    else:
        dt += [avg_time_between_operations.mean(), avg_time_between_operations.std()]
    dt += [counts[val] if val in counts else 0 for val in target_events]
    if np.isnan(dt).any():
        print(basic_info + ": Invalid feature values")
        print(dt)
        return invalid_result
    data = [dt]
    # contextual features
    urls = records["base_url"].unique()
    main_urls = set()
    param = set()
    params = {} # hard code part
    for url in urls:
        if type(url) != str:
            continue
        if "?" in url:
            parts = url.split("?")
            if len(parts) != 2:
                continue
            first, second = parts
            new_url = ''.join(char for char in first if char not in string.punctuation)
            main_urls.add(new_url)
            # Parse the URL string
            parsed_url = urllib.parse.urlparse(url)
            if "#" in url:
                params.add(''.join(char for char in parsed_url.fragment if char not in string.punctuation))
            # Get the query parameters as a dictionary
            query_params = urllib.parse.parse_qs(parsed_url.query)
            for key, value in query_params.items():
                param.add(''.join(char for char in f"{key}{value}" if char not in string.punctuation))
    context_info = ""
    # for i, r in records.iterrows():
    #     if r["tag_name"].upper() != "SUBMIT" and len(r["text_content"]) != 0:
    #         context_info += str(r["text_content"]) + " "
    # context_info = context_info.replace("\n", "").strip()
    # if len(context_info) == 0:
    #     context_info = ""
    for url in main_urls:
        context_info += url + " "
    for p in param:
        context_info += p + " "

    tokens = word_tokenize(context_info)
    tokens = [t for t in tokens if t not in stop_words]
    updated_context_info = " ".join(tokens)

    transformed_context_data = vectorizer.transform([updated_context_info])

    combined_data = [data[0] + list(transformed_context_data[0].toarray()[0])]

    pred = task_model_six.predict(combined_data)[0]
    prob = task_model_six.predict_proba(combined_data)[0]

    if max(prob) <= 0.8:
        pred = task_model_three.predict(combined_data)[0]
        prob = task_model_three.predict_proba(combined_data)[0]

    print(basic_info, ":", pred, max(prob))
    if max(prob) <= 0.8:
        return invalid_result

    trace_message = ""
    expert_trace = fetch_all_events_by_task_name(pred)
    expert_trace = expert_trace["table_result"]
    if len(expert_trace) == 0:
        print(basic_info, ":", "Task identified but no expert trace available")
        return invalid_result
    else:
        trace_info = expert_trace[list(expert_trace.keys())[-1]]
        trace_message = expert_replay(trace_info)

    if not push_status[user_id][pred]:
        push_status[user_id][pred] = datetime.now()
    else:
        time_diff = datetime.now() - push_status[user_id][pred]
        time_delta = timedelta(minutes=8)
        if time_diff < time_delta:
            print(basic_info, ":", "Task Identified within 8 Minutes")
            return invalid_result
        else:
            push_status[user_id][pred] = datetime.now()
    print("Push message successfully!", pred)
    return {
        "task_name": pred,
        "certainty": max(prob),
        "message": f"You are currently detected to be working on task <strong>{pred}</strong>{trace_message}",
        "interval": 60000
    }

### Methods from Ivan
def expert_replay(trace):
    trace_message_list = []
    flag_scroll = False  # is it continuous scrolling event?
    flag_input = False  # is it continuous inputting event?
    text_key_down = ""
    pre_url = None
    for event in trace:
        cur_event = str(event["event_type"])
        if not pre_url:
            pre_url = str(event["base_url"])
        elif pre_url != str(event["base_url"]):
            if flag_input:
                flag_input = False  # user finishes inputting
                event_description = get_text_by_event("keydown", text_key_down, "")
                trace_message_list.append(f"{event_description}<br><small>url: <a href='{pre_url}'>{pre_url}</a><br>position: N/A</small>")
                text_key_down = ""
            if flag_scroll:
                flag_scroll = False
            #trace_message_list.append(f"Navigate to {event['base_url']}")
            pre_url = str(event["base_url"])
        else:
            pre_url = str(event["base_url"])

        if cur_event not in ["OPEN", "visibilitychange", "beforeunload", "open", "server-record", "submit", "START", "close"]:
            if cur_event == "scroll":
                if flag_input:
                    flag_input = False  # user finishes inputting
                    event_description = get_text_by_event("keydown", text_key_down, "")
                    trace_message_list.append(f"{event_description}<br><small>url: <a href='{pre_url}'>{pre_url}</a><br>position: N/A</small>")
                    text_key_down = ""

                if not flag_scroll:
                    flag_scroll = True  # user is currently scrolling
                    event_description = get_text_by_event(cur_event, str(event["text_content"]).split(":")[0], "")
                    trace_message_list.append(f"{event_description}<br><small>url: <a href='{pre_url}'>{pre_url}</a><br>position: N/A</small>")

            elif cur_event == "keydown":
                text_key_down = get_keyboard(text_key_down, str(event["text_content"]))
                if not flag_input:
                    flag_input = True
                if flag_scroll:
                    flag_scroll = False
            else:
                if str(event["text_content"]) != "" and str(event["tag_name"]) != "SIDEBAR-TAB":
                    width = 0 if event["width"] == None else event["width"]
                    height = 0 if event["height"] == None else event["height"]
                    event_position = get_position_viewport(int(width), int(height), int(event["offset_x"]), int(event["offset_y"]))
                    event_description = get_text_by_event(cur_event, str(event["text_content"]), event_position)
                    if event_description != "No description":
                        trace_message_list.append(f"{event_description}<br><small>url: <a href='{pre_url}'>{pre_url}</a><br>position: {event_position}</small>")
    if len(text_key_down) != 0:
        event_description = get_text_by_event("keydown", text_key_down, "")
        trace_message_list.append(f"{event_description}<small>[{pre_url}]</small>")

    trace_message = "<div style='max-height: 500px; overflow-y: auto; overflow-x: hidden; boarder: 1.5px solid grey'><ul><li>" + "</li><li>".join(trace_message_list) + "</li></ul></div>"
    return trace_message

def get_keyboard(text_keydown, content):
    if content == "Backspace":
        return text_keydown[:-1]
    elif content == "Shift" or content == "Enter":
        return text_keydown
    return text_keydown + content

def get_text_by_event(event_type, text_content, event_position):
    if len(text_content) > 20:
        text_content = text_content[0:20] + "..."
    if event_type == "click":
        return 'Click on "' + text_content.replace("  ", " ").replace("\n", " ") + '" at ' + event_position
    elif event_type == "scroll":
        return text_content.lower().capitalize() + " on the web page"
    elif event_type == "select":
        return 'Select  "' + text_content + '" at ' + event_position
    elif event_type == "keydown":
        return 'Type "' + text_content + '"'
    else:
        return "No description"

def get_position_viewport(port_x, port_y, offset_x, offset_y):
    # if port_y / 3 <= offset_y <= port_y * 2 / 3 and port_x / 3 <= offset_x <= port_x * 2 / 3:
    #     return "center"
    height = ""
    width = ""
    if port_y/2 > offset_y:
        height = "top"
    else:
        height = "bottom"
    if port_x/2 > offset_x:
        width = "left"
    else:
        width = "right"
    return f"{height} {width}"

def main(global_config, **settings):
    config = Configurator(settings=settings)
    # config.registry["args"] = args
    # config.registry["tokenizer"] = tokenizer
    # config.registry["model"] = model
    # config.registry["kid_content_dict"] = kid_content_dict

    config.include("pyramid_jinja2")
    # config.include("tutorial.db")
    config.include("tutorial.nosql")


    userid = "acct:admin@localhost"
    print(fetch_user_event(userid, 0, 1, "timestamp"))

    config.add_route('query', 'query')
    config.add_route('search', 'search')
    config.add_route('hello', '/')
    config.add_route("task_classification", "task_classification")
    #config.add_route("get_all_message", "get_all_message")
    config.scan()
    return config.make_wsgi_app()
