import logging

from query.config import configure

log = logging.getLogger(__name__)


def create_app(_global_config, **settings):
    config = configure(settings=settings)

    config.include("query.dsi")

    config.add_route('hello', '/')
    config.add_route("query", "query")

    config.scan("query.views")
    log.info("service is ready!")
    return config.make_wsgi_app()
