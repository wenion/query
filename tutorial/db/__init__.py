from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


Session = sessionmaker()

def _session(request):  # pragma: no cover
    engine = request.registry["sqlalchemy.engine"]
    session = Session(bind=engine)

    # If the request has a transaction manager, associate the session with it.
    try:
        tm = request.tm
    except AttributeError:
        pass
    # else:
    #     zope.sqlalchemy.register(session, transaction_manager=tm)

    # pyramid_tm doesn't always close the database session for us.
    #
    # If anything that executes later in the Pyramid request processing cycle
    # than pyramid_tm tween egress opens a new DB session (for example a tween
    # above the pyramid_tm tween, a response callback, or a NewResponse
    # subscriber) then pyramid_tm won't close that DB session for us.
    #
    # So as a precaution add our own callback here to make sure db sessions are
    # always closed.
    @request.add_finished_callback
    def close_the_sqlalchemy_session(_request):
        # Close any unclosed DB connections.
        # It's okay to call `session.close()` even if the session does not need to
        # be closed, so just call it so that there's no chance
        # of leaking any unclosed DB connections.
        session.close()

    return session


def make_engine(settings):
    return create_engine(settings["sqlalchemy.url"])


def includeme(config):  # pragma: no cover
    # Create the SQLAlchemy engine and save a reference in the app registry.
    print("config", config.registry.settings)
    engine = make_engine(config.registry.settings)
    config.registry["sqlalchemy.engine"] = engine

    # # Add a property to all requests for easy access to the session. This means
    # # that view functions need only refer to `request.db` in order to retrieve
    # # the current database session.
    config.add_request_method(_session, name="db", reify=True)