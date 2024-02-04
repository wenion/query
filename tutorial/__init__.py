from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config
from pyramid.renderers import JSONP

from tutorial.nosql import fetch_user_event, fetch_all_user_event

import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import pickle
import urllib.parse
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.feature_extraction.text import TfidfVectorizer

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

@view_config(route_name="task_classification", request_method="GET", renderer="json")
def task_classification(request):
    invalid_result = {"task_name": "", "certainty": 0, "message": "", "interval": 20000}
    # get current time
    current_time = datetime.now()
    if "userid" not in request.params:
        return invalid_result
    user_id = request.params.get("userid")
    result = fetch_all_user_event(user_id, "timestamp")
    trace = pd.DataFrame(result["table_result"])
    if user_id not in push_status:
        push_status[user_id] = {"Adding Moodle Forum": None, "Adding Moodle Resource": None, "Updating Moodle Information": None}
    basic_info = current_time.strftime('%Y-%m-%d %H:%M:%S') + " " + user_id
    interval = 20000
    if "interval" in request.params:
        interval = request.params.get("interval")

    if interval == 0:
        print(basic_info + ": Invalid interval")
        return invalid_result

    time_delta_in_second = 20

    if trace is None or len(trace) == 0:
        print(basic_info + ": No trace found")
        return invalid_result

    target_events = ['beforeunload', 'click', 'keydown', 'open', 'scroll', 'select', 'server-record', 'submit']
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
    for url in urls:
        if "?" in url:
            parts = url.split("?")
            if len(parts) != 2:
                continue
            first_part, second_part = parts
            main_urls.add(first_part.split("/")[-1])
            # Parse the URL string
            parsed_url = urllib.parse.urlparse(url)
            # Get the query parameters as a dictionary
            query_params = urllib.parse.parse_qs(parsed_url.query)
            for key in query_params.keys():
                param.add(key)
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

    # load vectorizer
    with open("model/context_vectorizer.pkl", "rb") as f:
        vectorizer = pickle.load(f)
    transformed_context_data = vectorizer.transform([updated_context_info])

    combined_data = [data[0] + list(transformed_context_data[0].toarray()[0])]

    # load task model
    with open("model/task_model_with_context.pkl", "rb") as f:
        task_model = pickle.load(f)

    pred = task_model.predict(combined_data)[0]
    prob = task_model.predict_proba(combined_data)[0]
    print(basic_info, ":", pred, max(prob))
    prob_task = {
        "Adding Moodle Forum": 0.5,
        "Adding Moodle Resource": 0.5,
        "Updating Moodle Information": 0.85
    }
    if max(prob) <= prob_task[pred]:
        return invalid_result
    expert_trace_dict = {
        "Adding Moodle Forum": "<ol><li>Click on Turn Editing On</li><li>Scroll down to +Add an activity or resource</li><li>Select <strong>Open Forum</strong> in the Activities</li><li>Fill in the forum details and select the desired forum type (e.g., Q and A Forum)</li><li>Scroll down to save your edits</li></ol>",
        "Adding Moodle Resource": "<ol><li>Click on Turn Editing On</li><li>Scroll down to +Add an activity or resource</li><li>Select <strong>File</strong> (for media resource) or <strong>Label</strong> (for textual resource) in the Resources</li><li>Fill in the resource details</li><li>Scroll down to save your edits</li></ol>",
        "Updating Moodle Information": "<ol><li>Click on Turn Editing On</li><li>Scroll to the element that you want to edit</li><li>Hover on the Edit to toggle the dropdown</li><li>Select <strong>Edit Setting</strong> to make changes or <strong>Remove/Hide</strong> to delete/hide the information</li></ol>",

    }
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
    print("Push message successfully!")
    return {
        "task_name": pred,
        "certainty": max(prob),
        "message": f"You are currently detected to be working on task <strong>{pred}</strong>",
        "interval": 15000
    }


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
    config.scan()
    return config.make_wsgi_app()
