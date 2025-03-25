from django import template

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