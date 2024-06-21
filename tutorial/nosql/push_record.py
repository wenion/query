from datetime import datetime, timezone
import math
import pytz
from redis_om import Migrator
from redis_om import Field, JsonModel, EmbeddedJsonModel
from urllib.parse import urlparse
from typing import Optional


class PushRecord(JsonModel):
    class Meta:
        global_key_prefix = 'h'
        model_key_prefix = 'PushRecord'
    timestamp: int = Field(index=True, sortable=True)
    push_type: str = Field(full_text_search=True, sortable=True)
    push_to: str = Field(index=True) #user_id
    push_content: str = Field(full_text_search=True)
    additional_info: tuple = Field()


def add_push_record(timestamp, push_type, push_to, push_content, additional_info):
    pr = PushRecord(timestamp=timestamp, push_type=push_type, push_to=push_to, push_content=push_content, additional_info=additional_info)
    pr.save()
    return pr


def fetch_push_record(pk):
    query = PushRecord.find(PushRecord.pk == pk)
    result = query.all()
    return result[0] if len(result) > 0 else None


def delete_push_record(pk):
    try:
        PushRecord.delete(pk)
        return True
    except:
        return False

