import pyramid
# from pyramid.config import Configurator
from pyramid.view import view_config

from query.config import configure


def create_app(_global_config, **settings):
    config = configure(settings=settings)

    config.include("query.dsi")

    config.add_route('hello', '/')
    config.add_route("query", "query")

    config.scan("query.views")
    print("service is ready!")
    return config.make_wsgi_app()
