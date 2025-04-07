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
    settings_manager.set("config", "CONFIG", required=True)
    settings_manager.set("bert-base-uncased", "BERT", required=True)
    settings_manager.set("id_vocab", "ID_VOCAB", required=True)
    settings_manager.set("fine_tune_checkpoint_title", "CHECKOPINT_TITLE", required=True)
    settings_manager.set("all_docid_knowledge", "DOCID", required=True)

    # Get resolved settings.
    settings = settings_manager.settings

    return Configurator(settings=settings)
