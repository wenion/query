from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config
from pyramid.renderers import JSONP

from tutorial.nosql import fetch_user_event, fetch_all_user_event, fetch_all_events_by_task_name, fetch_all_user_events_by_session, fetch_all_user_event_within_time, create_process_model, delete_process_model_by_session_creator, fetch_all_process_model
from tutorial.nosql import add_task_page, delete_task_page, delete_task_page_name_id, fetch_user_event_record_by_session_id, delete_process_model, fetch_all_user_event_record, fetch_user_event_record_by_session

import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import urllib.parse
from urllib.parse import urlparse, parse_qs
import string
from pm4py.objects.conversion.log import converter as log_converter
from pm4py.algo.conformance.tokenreplay.variants import token_replay
import pm4py
import os
import time
from pm4py.objects.petri_net.importer import importer as pnml_importer
from pm4py.util.constants import DEFAULT_ENCODING
from pm4py.visualization.petri_net import visualizer
import io
import logging
from logging.handlers import RotatingFileHandler
import pytz
import random


logger = logging.getLogger("TAD")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler("task_classification.log", maxBytes=1024000, backupCount=1000)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.Formatter.converter = lambda *args: datetime.now(tz=pytz.timezone('Australia/Melbourne')).timetuple()
#formatter.converter = time.localtime
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.info("Service Started...")

push_status = {}
translation_table = str.maketrans(string.punctuation, '_'*len(string.punctuation))
all_process_models = {}


def load_all_process_models():
    process_models = fetch_all_process_model()
    if process_models:
        for pm in process_models:
            record = fetch_user_event_record_by_session_id(session_id=pm.session_id, userid=pm.creator)
            if not record:
                # if Shareflow doesn't exist, delete the PM
                delete_process_model(pm.pk)
                print(f"{pm.pm_name} {pm.session_id} {pm.creator} NOT FOUND UPON CHECKING AND DELETED")
                continue
            pm_string = pm.pm_content
            net, im, fm = pnml_importer.deserialize(pm_string, parameters={"auto_guess_final_marking": False, "encoding": DEFAULT_ENCODING})
            all_process_models[f"{pm.pm_name}_[SEP]_{pm.session_id}"] = (net, im, fm)
            logger.info(f"Process Model for {pm.pm_name}_{pm.session_id} loaded.")


def convert_log_to_formatted(event_log):
    activity = []
    event_log["event_type"] = event_log["event_type"].replace("recording", "open")
    event_log.sort_values(by=["timestamp"], ascending=[True], inplace=True)
    event_log["time"] = pd.to_datetime(event_log["timestamp"], unit="ms")
    event_log = event_log.reset_index()
    for index, row in event_log.iterrows():
        text_content = ""
        if not pd.isna(row["text_content"]) and row["event_type"] == "click" and row["tag_name"].lower() in ["button", "a", "span"]:
            text_content = " " + str(row["text_content"])
        url = ""
        if type(row["base_url"]) == str:
            url = row["base_url"]
            if "#" in url:
                url, _ = url.split("#") # remove the fragment
            prefix = "https://"
            if "https://" in url:
                _, url = url.split("https://", 1)
                url, last_part = url.rsplit("/", 1)  # exclude the last part of the URL as it tends to mean nothing but being too specific
                url = prefix + url
            if "?" in last_part:
                parsed_url = urlparse(row["base_url"])
                params = parse_qs(parsed_url.query)
                new_params = "?"
                for key, value in params.items():
                    new_params += f"{key.translate(translation_table)}&"
                    # if key in ["id", "course", "update", "courseid"]:
                    #     new_params += f"{key.translate(translation_table)}&"
                    # else:
                    #     new_params += f"{key.translate(translation_table)}_{value[0].translate(translation_table)}&"
                # if parsed_url.fragment:
                #     fragment = parsed_url.fragment
                #     fragment = fragment.translate(translation_table)
                #     new_params += fragment
                if new_params != "?":
                    if new_params[-1] == "&":
                        new_params = new_params[:-1]
                    url = url + new_params
                url = " in " + url
            else:
                url = " in " + url
        # previous_event = "N/A"
        # if index-1 >= 0 and event_log.at[index-1, "tag_name"]:
        #     previous_event = event_log.at[index-1, "tag_name"]
        act = f"{row['event_type']}: {row['tag_name']}{text_content}{url}"
        activity.append(act)
    event_log["activity"] = activity
    # if event_log["time"].dtype == "O":
    #     event_log["time"] = event_log["time"].str.replace(r"\s+(AEDT|ASDT)", "", regex=True)
    #     event_log["time"] = pd.to_datetime(event_log["time"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    if "case_id" not in event_log.columns:
        case_session = {}
        for cid, sid in enumerate(event_log["session_id"].unique()):
            case_session[sid] = cid + 1
        case_ids = []
        for index, row in event_log.iterrows():
            case_ids.append(case_session[row["session_id"]])
        event_log["case_id"] = case_ids
    formatted_event_log = pm4py.format_dataframe(event_log, case_id="case_id", activity_key="activity", timestamp_key="time")
    return formatted_event_log


def create_process_model_from_log(event_log):
    if event_log is None or event_log.empty:
        logger.warning("Empty or invalid event log")
        return None, None, None
    formatted_event_log = convert_log_to_formatted(event_log)
    net, im, fm = pm4py.discover_petri_net_heuristics(formatted_event_log, activity_key="concept:name", case_id_key="case:concept:name", timestamp_key="time:timestamp")
    return net, im, fm


@view_config(route_name='hello', request_method='GET', renderer='tutorial:templates/mytemplate.jinja2')
def hello_world(request):
    return {'Hello': 'world'}


@view_config(route_name='query', request_method='GET', renderer='json')
def query(request):
    return {'Hello': 'query'}


@view_config(route_name="create_process_model", request_method="POST", renderer="json")
def create_pm(request):
    if not request.json_body:
        return {
            "message": "Invalid data",
            "created": False
        }
    if "user_id" not in request.json_body:
        return {
            "message": "User ID missing. Cannot create process model",
            "created": False
        }
    if "shareflow_name" not in request.json_body:
        return {
            "message": "ShareFlow name missing. Cannot create process model",
            "created": False
        }
    if "group_id" not in request.json_body:
        return {
            "message": "Group information not found for the ShareFlow.",
            "created": False
        }
    if "session_id" not in request.json_body:
        return {
            "message": "Session ID not found. Cannot create process model",
            "created": False
        }
    user_id = request.json_body["user_id"]
    shareflow_name = request.json_body["shareflow_name"]
    session_id = request.json_body["session_id"]
    group_id = request.json_body["group_id"]
    result = fetch_all_user_events_by_session(user_id, session_id)
    if not result or not result["table_result"] or result["total"] == 0:
        return {
            "message": "Invalid User ID or ShareFlow name. Cannot create process model",
            "created": False
        }
    trace = pd.DataFrame(result["table_result"])
    trace = trace[(trace["tag_name"] != "RECORD") & (~trace["tag_name"].str.startswith("HYPOTHESIS"))] # filter out RECORD events
    net, im, fm = create_process_model_from_log(trace)
    if not net:
        return {
            "message": "Fail to create process model",
            "created": False
        }
    sf_name = shareflow_name.translate(translation_table)
    current_timestamp = int(datetime.now().timestamp() * 1000)
    file_path = f"process_models/{sf_name}_{current_timestamp}.pnml"
    pm4py.write_pnml(net, im, fm, file_path)
    try:
        with open(file_path, 'r') as file:
            pnml_data = file.read()
            status = create_process_model(creator=user_id,
                                          create_time=current_timestamp,
                                          group=group_id,
                                          pm_name=shareflow_name,
                                          pm_content=pnml_data,
                                          session_id=session_id)
            if not status:
                logger.error("Error occurred during the creation of process model.")
                return {
                    "message": "Error occurred during the creation of process model.",
                    "created": False
                }
    except FileNotFoundError:
        logger.error("File not found. Please check the file path.")
        return {
            "message": "File not found during creation of process model. Please retry!",
            "created": False
        }
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return {
            "message": f"An error occurred: {e}",
            "created": False
        }
    os.remove(file_path)
    all_process_models[f"{shareflow_name}_[SEP]_{session_id}"] = (net, im, fm)
    parameters = {"format": "png"}
    gviz = visualizer.apply(net, im, fm, parameters=parameters)
    visualizer.save(gviz, f"process_models/{sf_name}_{current_timestamp}.png")
    logger.info(f"PM {shareflow_name}_{session_id} created by {user_id}")
    # store all task pages
    all_urls = set(trace["base_url"].unique().tolist())
    all_domains = set()
    for url in all_urls:
        parsed_url = urlparse(url)
        if parsed_url:
            domain = parsed_url.netloc
            if domain:
                all_domains.add(domain)
    for domain in all_domains:
        add_task_page(url=domain, pm_name=shareflow_name, session_id=session_id)
    return {
        "message": "Process model created",
        "created": True
    }


@view_config(route_name="delete_process_model", request_method="POST", renderer="json")
def delete_pm(request):
    if not request.json_body:
        return {
            "message": "Invalid data",
            "created": False
        }
    if "user_id" not in request.json_body:
        return {
            "message": "User ID missing. Cannot delete process model",
            "removed": False
        }
    if "session_id" not in request.json_body:
        return {
            "message": "Session ID missing. Cannot delete process model",
            "removed": False
        }
    if "shareflow_name" not in request.json_body:
        return {
            "message": "Shareflow name not found. Cannot delete process model",
            "removed": False
        }
    user_id = request.json_body["user_id"]
    session_id = request.json_body["session_id"]
    shareflow_name = request.json_body["shareflow_name"]
    result = fetch_all_user_events_by_session(user_id, session_id)
    if not result or not result["table_result"] or result["total"] == 0:
        return {
            "message": "Invalid User ID or Session ID. Cannot delete process model",
            "removed": False
        }
    if f"{shareflow_name}_[SEP]_{session_id}" in all_process_models:
        del all_process_models[f"{shareflow_name}_[SEP]_{session_id}"]
    else:
        logger.warning(f"Process model not found in session, {user_id}, {session_id}")
    status = delete_process_model_by_session_creator(session_id, user_id)
    if not status:
        logger.error(f"Error deleting process model from database, {user_id}, {session_id}")
        return {
            "message": "Error deleting process model from database",
            "removed": False
        }
    deleted = delete_task_page_name_id(shareflow_name, session_id)
    if not deleted:
        logger.error(f"Error deleting task page info from database, {user_id}, {session_id}")
    logger.info(f"PM {shareflow_name}_{session_id} deleted by {user_id}")
    return {
        "message": "Process model deleted",
        "removed": True
    }


@view_config(route_name="task_classification", request_method="GET", renderer="json")
def task_classification(request):
    invalid_result = {"task_name": "", "certainty": 0, "message": "", "interval": 5000, "task_ids": []}
    # get current time
    current_time = datetime.now()
    if "userid" not in request.params:
        return invalid_result
    user_id = request.params.get("userid")
    interval = 10000
    if "interval" in request.params:
        interval = request.params.get("interval")
        interval = int(interval)
    if interval == 0:
        logger.warning(user_id + ": Invalid interval")
        return invalid_result
    current_time = datetime.now()
    time_ago = current_time - timedelta(seconds=10)
    time_ago = int(time_ago.timestamp() * 1000)
    result = fetch_all_user_event_within_time(user_id, time_ago)
    trace = pd.DataFrame(result["table_result"])
    if trace is None or len(trace) < 2:
        logger.warning(f"{user_id}: Not enough trace found - {len(trace)}")
        return invalid_result
    formatted_trace = convert_log_to_formatted(trace)
    # print(formatted_trace["concept:name"].tolist())
    # print(formatted_trace["time:timestamp"].tolist())
    match_scores = {}
    for k, v in all_process_models.items():
        net, im, fm = v
        replay_result = pm4py.conformance.fitness_token_based_replay(formatted_trace, net, im, fm, activity_key="concept:name", case_id_key="case:concept:name", timestamp_key="time:timestamp")
        fitness = replay_result['average_trace_fitness']
        match_scores[k] = fitness

    match_scores = dict(sorted(match_scores.items(), key=lambda item: item[1], reverse=True))
    task = list(match_scores.keys())[0]
    match_score = match_scores[task]
    # not pushing if all match scores below threshold
    if match_score < 0.34:
        logger.warning(user_id + ": No task matching")
        return invalid_result

    # in the process model dictionary storing all PMs in the current session, the keys are <PM_name>_[SEP]_<session_id>
    # "_[SEP]_" is added as a separator, when displaying, it is important to exclude the session ID
    count = 0
    matched_tasks = []
    tids = []
    for key, value in match_scores.items():
        if value == match_score:
            count += 1
            t_name, t_id = key.split("_[SEP]_")
            matched_tasks.append(t_name)
            shareflow = fetch_user_event_record_by_session(t_id)
            if shareflow:
                tids.append(shareflow.pk)
    # if match_score > 0.9:
    # # same highest scores; TODO: should we show all when we have multiple same highest > 0.9?
    #     logger.info(f"Tasks identified for {user_id}: {'; '.join(matched_tasks)} with score {match_score}")
    #     return {
    #         "task_name": "; ".join(matched_tasks),
    #         "certainty": match_score,
    #         "message": "The following tasks may be relevant: " + "; ".join(matched_tasks),
    #         "interval": 7000,
    #         "task_ids": tids
    #     }
    if match_score <= 0.9:
        # if match score <= 0.9, get top n (max 3) whose score <= 0.9 but >= 0.34
        matched_tasks = []
        tids = []
        count = 0
        for key, value in match_scores.items():
            if count == 3 or value < 0.34:
                break
            t_name, t_id = key.split("_[SEP]_")
            matched_tasks.append(t_name)
            shareflow = fetch_user_event_record_by_session(t_id)
            if shareflow:
                tids.append(shareflow.pk)
            count += 1

    # logger.info(f"Tasks identified for {user_id}: {'; '.join(matched_tasks)} with score {match_score}")
    # return {
    #     "task_name": "; ".join(matched_tasks),
    #     "certainty": match_score,
    #     "message": "The following tasks may be relevant: " + "; ".join(matched_tasks),
    #     "interval": 7000,
    #     "task_ids": tids
    # }

    # randomly select one highest Shareflow if there are multiple matching
    matched_task_idx = random.choice(list(range(len(matched_tasks))))
    logger.info(f"Tasks identified for {user_id}: {matched_tasks[matched_task_idx]} with score {match_score}")
    return {
        "task_name": matched_tasks[matched_task_idx],
        "certainty": match_score,
        "message": "The following tasks may be relevant: " + matched_tasks[matched_task_idx],
        "interval": 7000,
        "task_ids": tids[matched_task_idx]
    }


@view_config(route_name="compare_against_pms", request_method="POST", renderer="json")
def compare_against_pms(request):
    if not request.json_body:
        return {
            "message": "Invalid data",
            "result": None
        }
    if "user_id" not in request.json_body:
        return {
            "message": "User ID missing. Cannot compare.",
            "result": None
        }
    if "session_id" not in request.json_body:
        return {
            "message": "Session ID missing. Cannot compare.",
            "result": None
        }
    user_id = request.json_body["user_id"]
    session_id = request.json_body["session_id"]
    result = fetch_all_user_events_by_session(user_id, session_id)
    if not result or not result["table_result"] or result["total"] == 0:
        return {
            "message": "Invalid User ID or Session ID. Cannot delete process model",
            "result": None
        }
    trace = pd.DataFrame(result["table_result"])
    formatted_trace = convert_log_to_formatted(trace)
    match_scores = {}
    for k, v in all_process_models.items():
        net, im, fm = v
        replay_result = pm4py.conformance.fitness_token_based_replay(formatted_trace, net, im, fm,
                                                                     activity_key="concept:name",
                                                                     case_id_key="case:concept:name",
                                                                     timestamp_key="time:timestamp")
        fitness = replay_result['average_trace_fitness']
        match_scores[k] = fitness
    return {
        "message": f"{user_id}'s session {session_id} successfully compared with all existing PMs",
        "result": match_scores
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
    config.add_route("create_process_model", "create_process_model")
    config.add_route("delete_process_model", "delete_process_model")
    config.add_route("task_classification", "task_classification")
    config.add_route("compare_against_pms", "compare_against_pms")
    load_all_process_models()
    #config.add_route("get_all_message", "get_all_message")
    config.scan()
    return config.make_wsgi_app()
