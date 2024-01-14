from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config
from pyramid.renderers import JSONP

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

import random
import sys
# sys.path.insert(0, '/home/ubuntu/KMASS-monash/DSI/Neural-Corpus-Indexer-NCI-main/NCI_model')
# from infer import *
# print('\n'.join(sys.path))

# def parsers_parser_web(settings):
#     parser = pre_parsers_parser()

#     parser_args = parser.parse_args([
#         '--decode_embedding', settings['--decode_embedding'],
#         '--n_gpu', settings['--n_gpu'],
#         '--mode', settings['--mode'],
#         '--query_type', settings['--query_type'],
#         '--adaptor_layer_num', settings['--adaptor_layer_num'],
#         '--infer_ckpt', settings['--infer_ckpt'],
#         '--num_return_sequences', settings['--num_return_sequences'],
#         '--tree', settings['--tree'],

#         '--model_info', settings['--model_info'],
#         '--train_batch_size', settings['--train_batch_size'],
#         '--eval_batch_size', settings['--eval_batch_size'],
#         '--test1000', settings['--test1000'],
#         '--dropout_rate', settings['--dropout_rate'],
#         '--Rdrop', settings['--Rdrop'],
#         '--adaptor_decode', settings['--adaptor_decode'],
#         '--adaptor_efficient', settings['--adaptor_efficient'],
#         '--aug_query', settings['--aug_query'],
#         '--aug_query_type', settings['--aug_query_type'],

#         '--input_dropout', settings['--input_dropout'],
#         '--id_class', settings['--id_class'],
#         '--kary', settings['--kary'],
#         '--output_vocab_size', settings['--output_vocab_size'],
#         '--doc_length', settings['--doc_length'],

#         '--denoising', settings['--denoising'],
#         '--max_output_length', settings['--max_output_length'],
#         '--trivia', settings['--trivia'],
#         '--nq', settings['--nq']
#     ])

#     return post_parsers_parser(parser_args)

@view_config(route_name='hello', request_method='GET', renderer='tutorial:templates/mytemplate.jinja2')
def hello_world(request):
    return {'Hello':'world'}

@view_config(route_name='query', request_method='GET', renderer='json')
def query(request):
    return {'Hello':'query'}
#     querying = request.params.get("q")
#     # print('Incoming request', querying)
#     # results = inference(querying, tokenizer, model, kid_content_dict, args)
#     if querying is None or len(querying) == 0:
#         return {
#             'querying': "",
#             'results': [],
#             'content': {},
#         }
#     results, content = inference(
#         querying,
#         request.registry['tokenizer'],
#         request.registry['model'],
#         request.registry['kid_content_dict'],
#         request.registry['args'])

#     test_result = []
#     links = [
#         'https://en.wikipedia.org/wiki/Zerelda_Mimms',
#         'https://en.wikipedia.org/wiki/Ally_McBeal',
#         'https://en.wikipedia.org/wiki/%C5%9Av%C4%93t%C4%81mbara'
#         ]

#     for item in content:
#         random.shuffle(links)
#         test_result.append({
#                 "data_type": 'html',
#                 "title": content[item].split(' ')[0],
#                 "context": content[item][0:200] + '...',
#                 "author": '',
#                 "url": links[1]
#             })

#     return {
#         'total': len(results),
#         "query": querying,
#         "rows": test_result,
#         'querying': querying,
#         'results': results,
#         'content': content,
#     }

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

@view_config(route_name="task_classification", request_method="POST", renderer="json")
def task_classification(request):
    if "trace_data" in request.POST:
        csv_file = request.POST["trace_data"].file
        trace = pd.read_csv(csv_file)
    if "time_delta_in_minute" in request.POST:
        time_delta_in_minute = request.POST["time_delta_in_minute"]
    else:
        time_delta_in_minute = 1
    print(trace.head(2))
    print(time_delta_in_minute)
    if trace is None or len(trace) == 0:
        return {
            "task_name": "",
            "certainty": 0
        }
    print('Incoming request', trace)
    target_events = ['open', 'scroll', 'beforeunload', 'click-submit', 'submit-text', 'submit-checkbox', 'click-button', 'click-href', 'submit-textArea', 'submit-select', 'select', 'click-input', 'sever-record']
    stop_words = set(stopwords.words('english'))
    print(type(trace))
    # converting timestamp
    trace["timestamp"] = pd.to_datetime(trace["timestamp"], unit="ms")
    # get current time
    current_time = datetime.now()
    # Convert current time to a timestamp
    current_timestamp = current_time.timestamp()
    # get [time_delta_in_minute] ago
    ago = current_time - timedelta(minutes=time_delta_in_minute)
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
            "certainty": 0
        }
    data = [dt]
    # contextual features
    context_info = records[
        (records["tag_name"].isin(["INPUT", "BUTTON"])) & (records["text_content"].str.isdigit() == False) & (
                    records["text_content"] != "")]
    context_data = []
    if context_info.empty:
        context_data.append("Unavailable")
    else:
        context_data.append(context_info["text_content"].str.cat(sep=".").replace("\n", "").strip())

    updated_context_data = []
    for val in context_data:
        tokens = word_tokenize(val)
        tokens = [t for t in tokens if t not in stop_words]
        updated_context_data.append(" ".join(tokens))

    # load vectorizer
    with open("model/context_vectorizer.pkl", "rb") as f:
        vectorizer = pickle.load(f)
    transformed_context_data = vectorizer.transform(updated_context_data)

    combined_data = [data[0] + list(transformed_context_data[0].toarray()[0])]

    # load task model
    with open("model/task_model.pkl", "rb") as f:
        task_model = pickle.load(f)

    pred = task_model.predict(combined_data)[0]
    prob = task_model.predict_proba(combined_data)[0]
    return {"task_name": pred, "certainty": max(prob)}


def main(global_config, **settings):
    # args = parsers_parser_web(settings)
    # set_seed(args.seed)
    # # print(torch.cuda.is_available())
    # # print(torch.cuda.device_count())
    # # print(dir_path)
    # # print(parent_path)
    # args.logs_dir = dir_path + '/logs/'
    
    # # this is model pkl save dir
    # args.output_dir = dir_path + '/logs/'

    # time_str = time.strftime("%Y%m%d-%H%M%S")
    # # Note -- you can put important info into here, then it will appear to the name of saved ckpt
    # important_info_list = ['nq:', str(args.nq), 'trivia:', str(args.trivia), "kary:", str(args.kary), args.query_type, args.model_info, args.id_class,
    #                        args.test_set, args.ckpt_monitor, 'dem:',
    #                        str(args.decode_embedding), 'ada:', str(args.adaptor_decode), 'adaeff:',
    #                        str(args.adaptor_efficient), 'adanum:', str(args.adaptor_layer_num), 'RDrop:', str(args.dropout_rate), str(args.Rdrop), str(args.Rdrop_only_decoder)]

    # # nq:_0_trivia:_1_kary:_30_gtq_doc_aug_qg_base_bert_k30_c30_1_dev_recall_dem:_2_ada:_1_adaeff:_1_adanum:_4_RDrop:_0.1_0.15_0_lre2.0d1.0_epoch=0-recall1=0.972320.ckpt'

    # args.query_info = '_'.join(important_info_list)

    # tokenizer, model, kid_content_dict = init(args)

    config = Configurator(settings=settings)
    # config.registry["args"] = args
    # config.registry["tokenizer"] = tokenizer
    # config.registry["model"] = model
    # config.registry["kid_content_dict"] = kid_content_dict

    config.include("pyramid_jinja2")
    config.add_route('query', 'query')
    config.add_route('search', 'search')
    config.add_route('hello', '/')
    config.add_route("task_classification", "task_classification")
    config.scan()
    return config.make_wsgi_app()
