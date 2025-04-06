"""Configuration for the h application."""

import logging
import os

from pyramid.config import Configurator
from query.settings import SettingsManager

__all__ = ("configure",)

log = logging.getLogger(__name__)


def configure(environ=None, settings=None):  # pylint: disable=too-many-statements
    if environ is None:  # pragma: no cover
        environ = os.environ
    if settings is None:  # pragma: no cover
        settings = {}
    settings_manager = SettingsManager(settings, environ)

    # Configuration for external components
    settings_manager.set("config", "ELASTICSEARCH_URL", required=True)
    settings_manager.set("bert-base-uncased", "ELASTICSEARCH_URL", required=True)
    settings_manager.set("id_vocab", "ELASTICSEARCH_URL", required=True)
    settings_manager.set("fine_tune_checkpoint_title", "ELASTICSEARCH_URL", required=True)
    settings_manager.set("all_docid_knowledge", "ELASTICSEARCH_URL", required=True)

    # Get resolved settings.
    settings = settings_manager.settings

    return Configurator(settings=settings)
