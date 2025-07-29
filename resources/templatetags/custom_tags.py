from django import template
from django.urls import reverse
register = template.Library()

@register.filter
def get_attr(obj, attr_name):
    # Primero probamos con get_<field>_display (para campos con choices)
    display_method = f'get_{attr_name}_display'
    if hasattr(obj, display_method):
        return getattr(obj, display_method)()
    
    # Luego probamos el atributo directo
    value = getattr(obj, attr_name, '')

    # Si es un objeto relacionado (FK), devolvemos su __str__
    if hasattr(value, '__str__') and not isinstance(value, (str, int, float, bool)):
        return str(value)
    
    return value

@register.simple_tag
def evaluated_object_url(evaluation):
    ct = evaluation.evaluated_type
    model_name = ct.model
    obj_id = evaluation.evaluated_id

    try:
        return reverse(f'{model_name}-detail', args=[obj_id])
    except:
        return '#'
    

@register.filter
def dict_get(dict_data, key):
    return dict_data.get(key, [])