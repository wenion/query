from datetime import datetime
import pytz
from redis_om import Field, JsonModel, EmbeddedJsonModel, Migrator
from typing import Optional

__all__ = (
    "UserRole",
    "UserEvent",
)

class UserRole(EmbeddedJsonModel):
    class Meta:
        global_key_prefix = 'h'
        model_key_prefix = 'UserRole'
    userid: str = Field(index=True)
    faculty: str = Field(index=True)
    teaching_role: str = Field(index=True)
    teaching_unit: str = Field(index=True)
    campus: Optional[str] = Field(full_text_search=True, sortable=True)
    joined_year: int = Field(index=True)
    years_of_experience: int = Field(index=True)
    expert: int = Field(index=True)


def fetch_user_by_index(index):
    result = UserRole.find().all()
    return result[index]


class UserEvent(JsonModel):
    class Meta:
        global_key_prefix = 'h'
        model_key_prefix = 'UserEvent'
    event_type: str = Field(index=True, full_text_search=True)
    timestamp: int = Field(index=True)
    tag_name: str = Field(index=True)     # Result pk
    text_content: str = Field(index=True)
    base_url: str = Field(index=True)
    userid: str = Field(index=True)
    ip_address: Optional[str] = Field(full_text_search=True, sortable=True)
    interaction_context: Optional[str] = Field(full_text_search=True, sortable=True)
    event_source: Optional[str] = Field(full_text_search=True, sortable=True)
    system_time: Optional[datetime]
    x_path: Optional[str] = Field(full_text_search=True, sortable=True)
    offset_x: Optional[float] = Field(full_text_search=True, sortable=True)
    offset_y: Optional[float] = Field(full_text_search=True, sortable=True)
    doc_id: Optional[str] = Field(full_text_search=True, sortable=True)
    region: Optional[str] = Field(index=True, default="Australia/Sydney")


def add_user_event(
        userid,
        event_type,
        timestamp,
        tag_name,
        text_content,
        base_url,
        ip_address,
        interaction_context,
        event_source,
        x_path,
        offset_x,
        offset_y,
        doc_id,
        region
        ):
    user_event = UserEvent(
        userid=userid,
        event_type=event_type,
        timestamp=timestamp,
        tag_name=tag_name,
        text_content=text_content,
        base_url=base_url,
        ip_address=ip_address,
        interaction_context=interaction_context,
        event_source=event_source,
        x_path=x_path,
        offset_x=offset_x,
        offset_y=offset_y,
        doc_id=doc_id,
        system_time=datetime.utcnow().replace(tzinfo=pytz.utc),
        region=region,
    )
    user_event.save()
    return user_event


def get_user_event(pk):
    user_event = UserEvent.get(pk)
    return {
        'pk': user_event.pk,
        'userid': user_event.userid,
        'event_type': user_event.event_type,
        'timestamp': user_event.timestamp,
        # 'time': datetime.utcfromtimestamp(user_event.timestamp/1000).strftime('%Y-%m-%d %H:%M:%S UTC'),
        'time': datetime.utcfromtimestamp(user_event.timestamp/1000).replace(tzinfo=pytz.utc).astimezone(pytz.timezone("Australia/Sydney")).strftime('%Y-%m-%d %H:%M:%S %Z'),
        'tag_name': user_event.tag_name,
        'text_content': user_event.text_content,
        'base_url': user_event.base_url,
        'ip_address': user_event.ip_address,
        'interaction_context': user_event.interaction_context,
        'event_source': user_event.event_source,
        'x_path': user_event.x_path,
        'offset_x': user_event.offset_x,
        'offset_y': user_event.offset_y,
        'doc_id': user_event.doc_id,
        'system_time': user_event.system_time.replace(tzinfo=pytz.utc).astimezone(pytz.timezone("Australia/Sydney")) if user_event.system_time else None,
        'region': user_event.region,
    }


def fetch_all_user_event(userid, sortby):
    result = UserEvent.find(
        UserEvent.userid == userid
    ).sort_by(sortby).all()
    table_result=[]
    for index, item in enumerate(result):
        json_item = {'id': index, **get_user_event(item.pk)}
        table_result.append(json_item)
    return {
        "table_result": table_result,
        "total": len(result),
        }


def fetch_user_event(userid, offset, limit, sortby):
    query = UserEvent.find(
        UserEvent.userid == userid
        )
    total = len(query.all())

    results = query.copy(offset=offset, limit=limit).sort_by(sortby).execute(exhaust_results=False)

    table_result=[]
    for index, item in enumerate(results):
        json_item = {'id': index, **get_user_event(item.pk)}
        table_result.append(json_item)
    return {
        "table_result": table_result,
        "total": total,
        "offset": offset,
        "limit": limit,
        }


def get_user_event_sortable_fields():
    properties = UserEvent.schema()["properties"]
    sortable_fields = {key: value for key, value in properties.items() if 'format' not in value}
    return sortable_fields


def includeme(config):
    Migrator().run()