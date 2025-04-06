"""Helpers for parsing settings from the environment."""

import logging
from pyramid.view import view_config

log = logging.getLogger(__name__)


@view_config(route_name="hello", request_method="GET", renderer="json")
def hello(request):
    return {"result": "hello"}


@view_config(route_name="query", request_method="GET", renderer="json")
def query_dsi(request):
    querying = request.params.get("q")

    print("dsi 1", querying)
    dsi = request.registry["dsi"]
    print("dsi 2")
    dsi_result = dsi.gen_id(querying)
    print("dsi 3")
    return dsi_result