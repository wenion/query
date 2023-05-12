from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.view import view_config
from pyramid.renderers import JSONP

import json
import random
import sys
sys.path.insert(0, '/home/ubuntu/KMASS-monash/DSI/Neural-Corpus-Indexer-NCI-main/Data_KMASS/all_data')
from main import *


@view_config(route_name='hello', request_method='GET', renderer='tutorial:templates/mytemplate.jinja2')
def hello_world(request):
    return {'Hello':'world'}


@view_config(route_name='query', request_method='GET', renderer='json')
def query(request):
    querying = request.params.get("q")
    topics = []
    status = '200'

    # response = {
    #     'status': status,
    #     'query': querying,
    #     'context': topics,
    # }

    # print('Incoming request', querying)
    if querying is None or len(querying) == 0:
        return response
    
    # kn = request.registry['kn']
    # querying_list = []
    # querying_list.append(querying)
    # try:
    #     response_list = kn.query_retrieval(querying_list)
    # except Exception as e:
    #     status = str(e)
    # print('response_list', response_list)

    # count = 0
    # for topic in response_list:
    #     # print('topic id ', count)
    #     results = []
    #     rcount = 0
    #     for result in topic:
    #         item = {
    #             'id': rcount,
    #             'page_content': result.page_content,
    #             'metadata': result.metadata,
    #         }
    #         results.append(item)
    #         # print('result id ', rcount, result, type(result.metadata), item, '\n')
    #         rcount += 1
    #     topics.append(results)
    #     count += 1
    #     # print('\n\n')
    status = "openai.error.RateLimitError: You exceeded your current quota, please check your plan and billing details."
    status = "200"

    response = {"status": status, "query": "Who was the target of the failed \"Bomb Plot\" of 1944", "context": [[{"page_content": "## The quiz has ended.\n You will not be able to attempt questions. \nYou are working in a team that is developing a World War II-related game.\nThe former leader of the Soviet Union, Joseph Stalin, had multiple political decoys (body double) when he was ruling the Country. These decoys usually pretend to be him to inspect the frontlines, visit the factories, as well as give out speeches to the public for him. However, ONLY Stalin himself had the power to decide important things, such as:\nDispatch the Red Army, \nMeet with the Allies leaders, \nSign treaties with other Countries, and \nDeclare war against the Axis. \nStalin must do these things on his own instead of relying on his body doubles. He can also do everything that his decoys can do. \nYour colleague is responsible for designing the relationship between Stalin and his decoys (Rashid and Dadaev), who presented a UML class diagram during the team meeting. However, you found out that there is something wrong with this design. The UML class diagram is shown below. \nQuestion 1\nConsidering this UML class diagram, explain what SOLID principles have been violated and why? \nQuestion 2\nSuggest improvements that could be made to this design, based on the principles of good design we have discussed in FIT2099, describe one way to improve the design, and also specify the methods to be inherited by or declared in each component.", "metadata": {"url": "https://edstem.org/au/courses/8750/lessons/23025/slides/174823", "heading": "FIT2099 S2 2022 - Class activities (~50 minutes) - Quiz: Design Critique 1"}}, {"page_content": "You are working in a team that is developing a World War II-related game.\nThe former leader of the Soviet Union, Joseph Stalin, had multiple political decoys (body double) when he was ruling the Country. These decoys usually pretend to be him to inspect the frontlines, visit the factories, as well as give out speeches to the public for him. However, ONLY Stalin himself had the power to decide important things, such as:\nDispatch the Red Army, \nMeet with the Allies leaders, \nSign treaties with other Countries, and \nDeclare war against the Axis. \nStalin must do these things on his own instead of relying on his body doubles. He can also do everything that his decoys can do. \nYour colleague is responsible for designing the relationship between Stalin and his decoys (Rashid and Dadaev), who presented a UML class diagram during the team meeting. However, you found out that there is something wrong with this design. The UML class diagram is shown below. \nQuestion 1\nConsidering this UML class diagram, explain what SOLID principles have been violated and why? \nParagraph\nSubmit\nQuestion 2\nSuggest improvements that could be made to this design, based on the principles of good design we have discussed in FIT2099, describe one way to improve the design, and also specify the methods to be inherited by or declared in each component.\nParagraph\nSubmit", "metadata": {"url": "https://edstem.org/au/courses/10098/lessons/27857/slides/196705", "heading": "FIT2099 Nov 2022 - Class activities (~50 minutes) - Quiz: Design Critique 1"}}, {"page_content": "\u25c0\ufe0eWeek 4\nWeek 6\u25b6\ufe0e\nWeek 5\nMid-semester situation update by teams\nHidden from students\nGuest lecture series\nSpeaker: Prof. Mark Andrejevic\nTitle: The Impact of Automated Targeting of News and Media on Democracy\nAbstract: This talk focuses on the ways in which the automated curation of news, information, and culture online helps reinforce social fragmentation. I start by comparing the mass media era with a media system in which customized content is delivered to personal devices. I then consider recent arguments about the relationship between so called \u201cgeneral interest intermediaries\u201d \u2013 such as mass circulation newspapers and broadcasts \u2013 and civic life. These arguments suggest that the micro-targeting of news and information has the potential to undermine the \u201cdisposition\u201d necessary for democratic self-governance. I provide some familiar critiques of the impacts of social media on civic discourse and suggest that the fragmentation of culture more generally should be taken into consideration. I conclude by highlighting some approaches for holding media platforms accountable for the impact of the commercial customization of media content.\nBio: Mark Andrejevic is Professor in the School of Media, Film, and Journalism. He is also a Chief Investigator in the ARC Centre of Execellence for Automated Decision Making and Society. He is the author of numerous articles and four books, including, most recently: Automated Media. His co-authored book on the social impact of facial recognition technology will be published in July.\nLecture recording\nURL\nIntroduction to Agile and Scrum\nAbstract\nThis session will provide a brief overview of working with agility and how to run a project using the scrum framework.\nSpeaker\nPete Woolley, Manager\nDeloitte Digital Agile & Delivery Lead\nMelbourne\npewoolley@deloitte.com.au\nBio\nPete is an experienced delivery lead, specialising in leading teams building digital solutions utilising agile practices over the past 9 years. He is skilled in managing across the delivery team, from design, through build & test, and onto ensuring a smooth transition into deployment. Pete has managed the delivery of digital projects across a range of client industries and geographies.\nPete is currently fulfilling the role of Delivery Director for a Victorian government digital transformation project, managing a large Deloitte team delivering across multiple technologies and platforms.\nHidden from students\nFIT4002 guest speaker - Lawrence Macdonald\nURL\nHidden from students\nWarning: large file download (~775Mb .w4v)\nSeminar recording\nURL\nHidden from students\nPreliminary Teaching Evaluation Feedback form (iSETU)\nHidden from students\n\u25c0\ufe0eWeek 4\nWeek 6\u25b6\ufe0e", "metadata": {"url": "https://lms.monash.edu/course/view.php?id=135538&section=10", "heading": "FIT4002 Software engineering industry experience studio project - FY 2022 - Week 5"}}, {"page_content": "Untitled", "metadata": {"url": "https://edstem.org/au/courses/10696/lessons/31360/slides/235327.mp4", "heading": "FIT9136 S1 2023 - Workshop Activities - Untitled"}}]]}

    # response['status'] = status
    # response['context'] = topics
    # print('response', response)
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


def main(global_config, **settings):
    # kn = Knowledge_Nuggest(['Jira-pdf', 'PolicyBank-pdf', 'TeachHQ-video','Panopto-video', 'Ed-json', 'ExaminerReport-json', 'MEA-json', 'Moodle-json', 'TeachHQ-json'])

    config = Configurator(settings=settings)
    # config.registry["kn"] = kn

    config.include("pyramid_jinja2")
    config.add_route('query', 'query')
    config.add_route('search', 'search')
    config.add_route('hello', '/')
    config.scan()
    return config.make_wsgi_app()
