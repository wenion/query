from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config
from pyramid.renderers import JSONP

import json
import random
import sys
import os
import shutil
import urllib.parse
#from ruamel import yaml
sys.path.insert(0, '/home/ubuntu/KMASS-monash/DSI/Neural-Corpus-Indexer-NCI-main/Data_KMASS/all_data')
from main import *
from gen_retrieval import *
#import gen_retrieval

class Document:
    def __init__(self, page_content, metadata):
        self.page_content = page_content
        self.metadata = metadata


@view_config(route_name='hello', request_method='GET', renderer='tutorial:templates/mytemplate.jinja2')
def hello_world(request):
    return {'Hello':'world'}


@view_config(route_name='query', request_method='GET', renderer='json')
def query(request):
    querying = request.params.get("q")
    topics = []
    status = '200'

    # dsi
    querying = urllib.parse.unquote(querying)
    dsi = request.registry['dsi']
    dsi_results = dsi.gen_id(querying)
    print("dsi", dsi_results)
    # dsi_results = ['Adding activities and resources_default.mp4']+ dsi_results

    response = {
        'status': status,
        'query': querying,
        'context': topics,
    }

    # print('Incoming request', querying)
    if querying is None or len(querying) == 0:
        return response

    kn = request.registry['kn']
    querying_list = []
    querying_list.append(querying)
    try:
        response_list = kn.query_retrieval(querying_list)
    except Exception as e:
        status = str(e)
    # print('response_list', response_list)

    priority_result = []
    count = 0
    for topic in response_list:
        # print('topic id ', count)
        results = []
        rcount = 0
        # for result in topic:
        for item in topic:
            document_tuple = item # document format:
            document = document_tuple[0]
            score = document_tuple[1]

            page_content = document.page_content
            metadata = document.metadata
            metadata["score"] = str(score)
            title = metadata["title"]

            item = {
                'id': rcount,
                # 'page_content': result.page_content,
                'page_content': page_content,
                'metadata': metadata,
            }
            
            # if dsi results overlap with embedding results
            if title in dsi_results:
                priority_result.append(item)
                dsi_results.remove(title)
            else:
                results.append(item)
            # print('result id ', rcount, result, type(result.metadata), item, '\n')
            rcount += 1

        # merge dsi results, embedding results with results
        post_dsi_results = []
        for key, value in enumerate(dsi_results):
            item = {'id':rcount + key, 'page_content': '', 'metadata':{'title': value, }}
            post_dsi_results.append(item)
        results = priority_result + results + post_dsi_results
        print('len', len(results))
        topics.append(results)
        count += 1
        # print('\n\n')
    # status = "openai.error.RateLimitError: You exceeded your current quota, please check your plan and billing details."
    # status = "200"

    response['status'] = status
    response['context'] = topics
    return response

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
#     return {
#         'querying': querying,
#         'results': results,
#         'content': content,
#     }

@view_config(route_name='upload', request_method='POST', renderer='json')
def upload(request):
    kn = request.registry['kn']
    print("start upload request.POST", request.POST)

    try:
        if request.POST['myFile'] is None:
            return {"status": 404, "message": "myFile is empty"}
        filename = request.POST['myFile'].filename
        input_file = request.POST['myFile'].file
        url = request.POST.get("url")
        print("request.POST", url)
    except Exception as e:
        return {"status": 404, "message": repr(e)}

    file_type = "document"

    print("filename", filename, "input_file", input_file, "url", url)

    if filename.endswith(".pdf"):
        target_path = os.path.join(os.getcwd(), "new-pdf")
    elif filename.endswith(".mp4"):
        target_path = os.path.join(os.getcwd(), "new-video")
        file_type = "video"
    else:
        target_path = os.path.join(os.getcwd(), "other")
        file_type = "other"

    file_path = os.path.join(target_path, filename)

    if not os.path.exists(target_path):
        os.mkdir(target_path)

    if os.path.exists(file_path):
        return {"status": 303, "message": "reason:\n" + filename + " already exists in remote"}

    try:
        with open(file_path, 'wb') as output_file:
            shutil.copyfileobj(input_file, output_file)
    except Exception as e:
        return {"status": 404, "message": repr(e)}

    print("file_path", file_path, "url", url, "file_type", file_type)

    if os.path.exists(file_path):
        try:
            ret = kn.nuggest_update(file_list=[file_path,], url_list=[url,], file_type=file_type)
            # ret = 1
        except Exception as e:
            return {"status":304, "message": "[the ingestion failed] reason:\n" + repr(e)}
        else:
            if ret == 1:
                print("succ")
                return {'status':200, "message": filename + ' has been saved in' + target_path}
            else:
                return {"status":304, "message": "[the ingestion failed] reason: return -1"}

    return {"status":404, "message": "file_path "+ file_path + "does not exist"}


@view_config(route_name='delete', request_method='POST', renderer='json')
def delete(request):
    filename = request.POST.get("filename")
    filetype = request.POST.get("filetype")
    print("filename", filename, "filetype", filetype)
    if filetype == ".mp4":
        file_path = os.path.join(os.getcwd(), "new-video")
    elif filetype == ".pdf":
        file_path = os.path.join(os.getcwd(), "new-pdf")
    else:
        file_path = os.path.join(os.getcwd(), "other")
    try:
        file_path = os.path.join(file_path, filename)
        print("file_path", file_path)
        if os.path.exists(file_path):
            print("find file_path:", file_path)
            # os.remove(file_path)
    except Exception as e:
        print("error" + repr(e))
        return {"error", repr(e)}
    return {"succ": "delete "}

def main(global_config, **settings):
    # kn = Knowledge_Nuggest(['PolicyBank-pdf', 'TeachHQ-video', 'ExaminerReport-json'])
    kn = KN()
    dsi_model = DSI()

    config = Configurator(settings=settings)
    config.registry["kn"] = kn
    config.registry["dsi"] = dsi_model

    config.include("pyramid_jinja2")
    config.add_route('query', 'query')
    config.add_route('search', 'search')
    config.add_route('hello', '/')
    config.add_route('upload', '/upload')
    config.add_route('delete', '/delete')
    config.scan()

    # kn.nuggest_update(file_list=["/home/ubuntu/KMASS-monash/DSI/Neural-Corpus-Indexer-NCI-main/Data_KMASS/all_data/new-video/20230611-1626-03.4924826.mp4",], url_list=["https://colam.kmass.cloud.edu.au/video?file=http://localhost:8080/static/admin/20230611-1626-03.4924826.mp4",], file_type="video")
    # kn.nuggest_update(file_list=["/home/ubuntu/KMASS-monash/DSI/Neural-Corpus-Indexer-NCI-main/Data_KMASS/all_data/new-video/2.mp4",], url_list=["https://colam.kmass.cloud.edu.au/video?file=http://localhost:8080/static/admin/20230611-1626-03.4924826.mp4",], file_type="video")
    return config.make_wsgi_app()
