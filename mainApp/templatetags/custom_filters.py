from django import template

register = template.Library()

@register.filter(name='mul')
def mul(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''

@register.filter(name='multiply')
def multiply(value, arg):
    try:
        return float(value) * int(arg)
    except (ValueError, TypeError):
        return 0

@register.filter(name='add_class')
def add_class(field, css_class):
    return field.as_widget(attrs={"class": css_class})
