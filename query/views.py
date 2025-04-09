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

    if not isinstance(querying, str):
        return []

    if len(querying) == 0:
        return []

    dsi = request.registry["dsi"]
    try:
        dsi_result = dsi.gen_id(querying)
    except Exception as e:
        log.error(f"Error in DSI'{str(e)}'")
        return []
    else:
        return dsi_result
