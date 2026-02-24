from django.db import connection
from django.conf import settings
from django.http import HttpResponse

def where_am_i(request):
    schema = getattr(connection, "schema_name", "?")
    urlconf = getattr(request, "urlconf", settings.ROOT_URLCONF)
    host = request.get_host()
    return HttpResponse(f"schema={schema} host={host} urlconf={urlconf}")