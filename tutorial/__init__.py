import json

from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config
from pyramid.renderers import JSONP

from tutorial.nosql import fetch_user_event, fetch_all_user_event, fetch_all_events_by_task_name, \
    fetch_all_user_events_by_session, fetch_all_user_event_within_time, create_process_model, \
    delete_process_model_by_session_creator, fetch_all_process_model, same_as_previous
from tutorial.nosql import add_task_page, delete_task_page, delete_task_page_name_id, fetch_user_event_record_by_session_id, delete_process_model, fetch_all_user_event_record, fetch_user_event_record_by_session, fetch_all_task_pages
from tutorial.nosql import add_push_record, delete_push_record, fetch_push_record, fetch_all_push_record, clean_old_record_from_user
from tutorial.nosql import is_task_page, stop_pushing

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
from redis_om import get_redis_connection


logger = logging.getLogger("TAD")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler("task_classification.log", maxBytes=5120000, backupCount=5000)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.Formatter.converter = lambda *args: datetime.now(tz=pytz.timezone('Australia/Melbourne')).timetuple()
#formatter.converter = time.localtime
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.info("Service Starting...")

idle_status = {}
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
            if "?" in url:
                url, _ = url.split("?") # exclude the query for now
            prefix = "https://"
            if "https://" in url:
                _, url = url.split("https://", 1)
                if url.count("/") > 1:
                    # remove the last parts (if there are multiple levels in the URL) that likely are too context specific
                    url, last_part = url.rsplit("/", 1)

                url = prefix + url

            if "?" in row["base_url"]:
                parsed_url = urlparse(row["base_url"])
                params = parse_qs(parsed_url.query)
                new_params = "?"
                for key, value in params.items():
                    nondigit_values = []
                    for val in value:
                        if not val.isdigit():
                            nondigit_values.append(val.translate(translation_table))
                    new_params += f"{key.translate(translation_table)}_{','.join(nondigit_values)}&"
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


# @view_config(route_name='add', request_method='GET', renderer='json')
# def add(request):
#     pr = add_push_record(timestamp=datetime.now().timestamp(),
#                          push_type="ShareFlow",
#                          push_to="acct:Steve_Li@localhost",
#                          push_content="You are detected to be working on Adding a Forum in Moodle",
#                          additional_info=(("selxbww2kkBRtqx", 0.93), ("selx4j17pcGiIJQ", 0.93)))
#     #redis = get_redis_connection()
#     #redis.expire(pr.pk, 20)
#     pr.expire(20)
#     return {'pk': pr.pk}
#
#
# @view_config(route_name='query', request_method='GET', renderer='json')
# def query(request):
#     if "pk" not in request.params:
#         return {"result": False}
#     pk = request.params.get("pk")
#     result = fetch_push_record(pk)
#     if result:
#         return {"result": True}
#     return {'result': False}
#
#
# @view_config(route_name='delete', request_method='GET', renderer='json')
# def delete(request):
#     if "pk" not in request.params:
#         return {"result": False}
#     outcome = delete_push_record(request.params.get("pk"))
#     return {'result': outcome}

@view_config(route_name='delete_all_pm', request_method='POST', renderer='json')
def delete_all_pm(request):
    if not request.json_body:
        return {
            "message": "Invalid",
            "deleted": False
        }
    if "admin_token" not in request.json_body:
        return {
            "message": "Invalid",
            "deleted": False
        }
    if request.json_body["admin_token"] != "STEVESUPERDOPE":
        return {
            "message": "Invalid",
            "deleted": False
        }
    pms = fetch_all_process_model()
    for pm in pms:
        delete_process_model(pm.pk)
        logging.info(f"PM {pm.pm_name} from session {pm.session_id} by {pm.creator} deleted")
    return {
        "message": "All PM deleted",
        "deleted": True
    }


@view_config(route_name='delete_all_tp', request_method='POST', renderer='json')
def delete_all_tp(request):
    if not request.json_body:
        return {
            "message": "Invalid",
            "deleted": False
        }
    if "admin_token" not in request.json_body:
        return {
            "message": "Invalid",
            "deleted": False
        }
    if request.json_body["admin_token"] != "STEVESUPERDOPE":
        return {
            "message": "Invalid",
            "deleted": False
        }
    tps = fetch_all_task_pages()
    for tp in tps:
        delete_task_page(tp.pk)
    return {
        "message": "All TP deleted",
        "deleted": True
    }


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
    trace = trace[(trace["tag_name"] != "RECORD") & (~trace["tag_name"].str.startswith("HYPOTHESIS"))] # filter out RECORD events and extension events
    trace = trace[~trace["base_url"].str.contains("docs.google.com")] # exclude google related events; to be removed in actual evaluation TODO
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
        logger.info(f"{domain} added as task page.")
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

    invalid_result = {"task_name": "", "certainty": 0, "message": "", "interval": -1, "task_ids": [], "task_details": [], "show_flag": False}
    next_request_result = {"task_name": "", "certainty": 0, "message": "", "interval": 5000, "task_ids": [], "task_details": [], "show_flag": False}
    current_time = datetime.now()
    if "url" not in request.params or not is_task_page(request.params.get("url")):
        # if url information is not provided or if the provided url is not a task page
        logger.warning("Invalid URL information!")
        return invalid_result
    url = request.params.get("url")
    if "userid" not in request.params:
        logger.warning("Invalid user information!")
        return invalid_result
    user_id = request.params.get("userid")
    interval = 5000
    if "interval" in request.params:
        interval = request.params.get("interval")
        interval = int(interval)
    if interval == 0:
        logger.warning(user_id + ": Invalid interval" + " " + current_time)
        return next_request_result


    time_threshold = current_time - timedelta(minutes=6)
    time_threshold = int(time_threshold.timestamp())
    clean_old_record_from_user(time_threshold, user_id)

    if stop_pushing(url, user_id):
        logger.info(user_id + ": Stop pushing criteria matched")
        return {"task_name": "", "certainty": 0, "message": "", "interval": 60000, "task_ids": [], "task_details": [], "show_flag": False}

    time_delta = 11
    interval_in_second = interval / 1000
    if interval_in_second > time_delta:
        time_delta = interval_in_second
    time_ago = current_time - timedelta(seconds=time_delta)
    time_ago = int(time_ago.timestamp() * 1000)
    result = fetch_all_user_event_within_time(user_id, time_ago)
    trace = pd.DataFrame(result["table_result"])

    if trace is None or len(trace) < 2:
        if len(trace) == 0:
            if user_id not in idle_status:
                idle_status[user_id] = 0
            idle_status[user_id] += 1
        logger.warning(f"{user_id}: Not enough trace found - {len(trace)}" + " " + current_time)
        if user_id in idle_status:
            # if an user is idle for more than 5 minutes, gradually increase the request interval
            idle_result = next_request_result.copy()
            multiplier = 1
            if int(idle_status[user_id]/12) >= 5:
                multiplier += int(idle_status[user_id]/12)
                logger.warning(f"{user_id} is detected to be inactive for more than 5 minutes")
            idle_result["interval"] = idle_result["interval"] * multiplier
            return idle_result
        return next_request_result
    if len(trace) > 0 and user_id in idle_status and idle_status[user_id] > 0:
        del idle_status[user_id]
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
        return next_request_result

    # in the process model dictionary storing all PMs in the current session, the keys are <PM_name>_[SEP]_<session_id>
    # "_[SEP]_" is added as a separator, when displaying, it is important to exclude the session ID
    count = 0
    matched_tasks = []
    task_details = []
    tids = []
    for key, value in match_scores.items():
        if value == match_score:
            count += 1
            t_name, t_id = key.split("_[SEP]_")
            matched_tasks.append(t_name)
            shareflow = fetch_user_event_record_by_session(t_id)
            if shareflow:
                task_details.append({"pk": shareflow.pk,
                                     "session_id": shareflow.session_id,
                                     "user_id": shareflow.userid,
                                     "task_name": shareflow.task_name,
                                     "certainty": value})
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
        task_details = []
        tids = []
        count = 0
        for key, value in match_scores.items():
            if count == 3 or value < 0.34:
                break
            t_name, t_id = key.split("_[SEP]_")
            matched_tasks.append(t_name)
            shareflow = fetch_user_event_record_by_session(t_id)
            if shareflow:
                task_details.append({"pk": shareflow.pk,
                                     "session_id": shareflow.session_id,
                                     "user_id": shareflow.userid,
                                     "task_name": shareflow.task_name,
                                     "certainty": value})
                tids.append(shareflow.pk)
            count += 1
    else:
        # randomly select one highest Shareflow if there are multiple matching
        matched_task_idx = random.choice(list(range(len(matched_tasks))))
        logger.info(f"Tasks identified for {user_id}: {matched_tasks[matched_task_idx]} with score {match_score}")
        matched_tasks = [matched_tasks[matched_task_idx]]
        task_details = [task_details[matched_task_idx]]
        tids = [tids[matched_task_idx]]
    push_message = "The following ShareFlows from your colleagues might be useful: "
    same = same_as_previous(user_id=user_id,
                            url=url,
                            push_type="SF",
                            push_content=push_message,
                            additional_info=json.dumps(task_details))
    if same:
        logger.info(user_id + ": Same task identified as in previous Shareflow Push; the current one won't be pushed")
        return next_request_result

    pr = add_push_record(timestamp=datetime.now().timestamp(),
                         push_type="SF",
                         push_to=user_id,
                         push_content=push_message,
                         url=url,
                         additional_info=json.dumps(task_details))
    #pr.expire(360) # the push records are stored for 6 minutes, then expire

    logger.info(f"Tasks identified for {user_id}: {'; '.join(matched_tasks)} with score {match_score}")
    return {
        "task_name": "; ".join(matched_tasks),
        "certainty": match_score,
        "message": push_message,
        "interval": interval * 2,
        "task_ids": tids,
        "task_details": task_details,
        "show_flag": True
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


@view_config(route_name='get_trace_for_session', request_method="POST", renderer='string')
def get_trace_for_session(request):
    if not request.json_body:
        return {
            "message": "Invalid data",
            "result": None
        }
    if "user_id" not in request.json_body:
        return {
            "message": "User ID missing. Cannot produce trace.",
            "result": None
        }
    if "session_id" not in request.json_body:
        return {
            "message": "Session ID missing. Cannot produce trace.",
            "result": None
        }
    user_id = request.json_body["user_id"]
    session_id = request.json_body["session_id"]
    query_response = fetch_all_user_events_by_session(user_id, session_id)
    if query_response["total"] == 0:
        return {
            "message": "No trace found",
            "result": None
        }
    df = pd.DataFrame(query_response["table_result"])
    # Prepare your CSV data
    csv_output = io.StringIO()
    df.to_csv(csv_output, index=False)
    csv_output.seek(0)
    csv_content = csv_output.getvalue()

    # Create response
    response = Response(content_type='text/csv')
    response.content_disposition = 'attachment; filename="data.csv"'
    response.body = csv_content.encode('utf-8')
    return response


@view_config(route_name="view_all_task_pages", request_method="POST", renderer="json")
def view_all_task_pages(request):
    task_pages = []
    query_result = fetch_all_task_pages()
    if not query_result:
        return task_pages
    for index, item in enumerate(query_result):
        json_item = {"id": index, "url": item.url, "pm_name": item.pm_name}
        task_pages.append(json_item)
    return task_pages


@view_config(route_name="view_all_push_records", request_method="POST", renderer="json")
def view_all_push_records(request):
    query_result = fetch_all_push_record()
    return query_result


def main(global_config, **settings):
    config = Configurator(settings=settings)
    # config.registry["args"] = args
    # config.registry["tokenizer"] = tokenizer
    # config.registry["model"] = model
    # config.registry["kid_content_dict"] = kid_content_dict
    logger.info("Connecting to Redis...")
    config.include("pyramid_jinja2")
    # config.include("tutorial.db")
    config.include("tutorial.nosql")


    # userid = "acct:admin@localhost"
    # print(fetch_user_event(userid, 0, 1, "timestamp"))

    # config.add_route('query', 'query')
    # config.add_route('add', 'add')
    # config.add_route("delete", "delete")
    config.add_route("delete_all_pm", "delete_all_pm")
    config.add_route("delete_all_tp", "delete_all_tp")
    config.add_route('hello', '/')
    config.add_route("create_process_model", "create_process_model")
    config.add_route("delete_process_model", "delete_process_model")
    config.add_route("task_classification", "task_classification")
    config.add_route("compare_against_pms", "compare_against_pms")
    config.add_route("get_trace_for_session", "get_trace_for_session")
    config.add_route("view_all_task_pages", "view_all_task_pages")
    config.add_route("view_all_push_records", "view_all_push_records")
    logger.info("Loading Process Models...")
    load_all_process_models()
    #config.add_route("get_all_message", "get_all_message")
    config.scan()
    logger.info("Service started!!")
    return config.make_wsgi_app()
