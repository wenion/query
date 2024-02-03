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
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.feature_extraction.text import TfidfVectorizer

@view_config(route_name='hello', request_method='GET', renderer='tutorial:templates/mytemplate.jinja2')
def hello_world(request):
    return {'Hello':'world'}

@view_config(route_name='query', request_method='GET', renderer='json')
def query(request):
    return {'Hello':'query'}

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
    if "userid" not in request.params:
        return {
            "task_name": "",
            "certainty": 0,
            "message": ""
        }
    user_id = request.params.get("userid")
    result = fetch_all_user_event(user_id, "timestamp")
    trace = pd.DataFrame(result["table_result"])

    if "time_delta_in_second" in request.params:
        time_delta_in_second = request.params.get("time_delta_in_second")
    else:
        time_delta_in_second = 30

    if trace is None or len(trace) == 0:
        return {
            "task_name": "",
            "certainty": 0,
            "message": ""
        }
    target_events = ['beforeunload', 'click', 'keydown', 'scroll', 'select', 'submit']
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
    # records = trace.iloc[24:71] # for testing
    # get the attributes
    no_events = len(records)
    no_unique_events = len(records["event_type"].unique())
    no_unique_tags = len(records["tag_name"].unique())
    avg_time_between_operations = records["timestamp"].diff().dt.total_seconds().dropna()
    counts = records["event_type"].value_counts()
    dt = [no_events, no_unique_events, no_unique_tags, avg_time_between_operations.mean(),
          avg_time_between_operations.std()] + [counts[val] if val in counts else 0 for val in target_events]
    if np.isnan(dt).any():
        return {
            "task_name": "",
            "certainty": 0,
            "message": ""
        }
    data = [dt]
    # # contextual features
    # context_info = records[
    #     (records["tag_name"].isin(["INPUT", "BUTTON"])) & (records["text_content"].str.isdigit() == False) & (
    #                 records["text_content"] != "")]
    # context_data = []
    # if context_info.empty:
    #     context_data.append("Unavailable")
    # else:
    #     context_data.append(context_info["text_content"].str.cat(sep=".").replace("\n", "").strip())
    #
    # updated_context_data = []
    # for val in context_data:
    #     tokens = word_tokenize(val)
    #     tokens = [t for t in tokens if t not in stop_words]
    #     updated_context_data.append(" ".join(tokens))
    #
    # # load vectorizer
    # with open("model/context_vectorizer.pkl", "rb") as f:
    #     vectorizer = pickle.load(f)
    # transformed_context_data = vectorizer.transform(updated_context_data)
    #
    # combined_data = [data[0] + list(transformed_context_data[0].toarray()[0])]

    # load task model
    with open("model/task_model_updated.pkl", "rb") as f:
        task_model = pickle.load(f)

    pred = task_model.predict(data)[0]
    prob = task_model.predict_proba(data)[0]
    print(user_id, pred, max(prob))
    if max(prob) <= 0.95:
        return {
            "task_name": "",
            "certainty": 0,
            "message": ""
        }
    expert_trace_dict = {
        "Adding Moodle Forum": "<ol><li>Click on Turn Editing On</li><li>Scroll down to +Add an activity or resource</li><li>Select <strong>Open Forum</strong> in the Activities</li><li>Fill in the forum details and select the desired forum type (e.g., Q and A Forum)</li><li>Scroll down to save your edits</li></ol>",
        "Adding Moodle Resource": "<ol><li>Click on Turn Editing On</li><li>Scroll down to +Add an activity or resource</li><li>Select <strong>File</strong> (for media resource) or <strong>Label</strong> (for textual resource) in the Resources</li><li>Fill in the resource details</li><li>Scroll down to save your edits</li></ol>",
        "Updating Moodle Information": "<ol><li>Click on Turn Editing On</li><li>Scroll to the element that you want to edit</li><li>Hover on the Edit to toggle the dropdown</li><li>Select <strong>Edit Setting</strong> to make changes or <strong>Remove/Hide</strong> to delete/hide the information</li></ol>",

    }
    return {
        "task_name": pred,
        "certainty": max(prob),
        "message": f"You are currently detected to be working on task <strong>{pred}</strong>."
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
