from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Template filter to get dictionary item by key.
    Usage: {{ mydict|get_item:key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def get_item_str(dictionary, key):
    """
    Template filter to get dictionary item by string key.
    Usage: {{ mydict|get_item_str:"key" }}
    """
    if dictionary is None:
        return None
    return dictionary.get(str(key))