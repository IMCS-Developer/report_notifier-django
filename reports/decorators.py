"""
Drop-in async-aware replacements for django.views.decorators.http.require_GET/
require_POST/require_http_methods and django.views.decorators.csrf.csrf_exempt.

Root cause: Django 3.2's implementations of these decorators always define a
synchronous `inner`/`wrapped_view` wrapper, even when the view they decorate is
`async def`. Calling a sync wrapper that internally calls an async function
without `await` just returns an un-awaited coroutine object, which Django's
request handler then rejects with:
    ValueError: The view ... didn't return an HttpResponse object.
    It returned an unawaited coroutine instead.
Django 4.1+ fixed this by branching on asyncio.iscoroutinefunction(func) and
defining either a sync or an async wrapper accordingly -- this module
reimplements that same pattern so it works under the pinned Django 3.2.25.
"""
import asyncio
from functools import wraps

from django.http import HttpResponseNotAllowed
from django.utils.log import log_response


def require_http_methods(request_method_list):
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def inner(request, *args, **kwargs):
                if request.method not in request_method_list:
                    response = HttpResponseNotAllowed(request_method_list)
                    log_response(
                        'Method Not Allowed (%s): %s', request.method, request.path,
                        response=response,
                        request=request,
                    )
                    return response
                return await func(request, *args, **kwargs)
        else:
            @wraps(func)
            def inner(request, *args, **kwargs):
                if request.method not in request_method_list:
                    response = HttpResponseNotAllowed(request_method_list)
                    log_response(
                        'Method Not Allowed (%s): %s', request.method, request.path,
                        response=response,
                        request=request,
                    )
                    return response
                return func(request, *args, **kwargs)
        return inner
    return decorator


require_GET = require_http_methods(["GET"])
require_GET.__doc__ = "Decorator to require that a view only accept the GET method."

require_POST = require_http_methods(["POST"])
require_POST.__doc__ = "Decorator to require that a view only accept the POST method."


def csrf_exempt(view_func):
    """Mark a view function as being exempt from CSRF view protection (async-aware)."""
    if asyncio.iscoroutinefunction(view_func):
        async def wrapped_view(*args, **kwargs):
            return await view_func(*args, **kwargs)
    else:
        def wrapped_view(*args, **kwargs):
            return view_func(*args, **kwargs)
    wrapped_view.csrf_exempt = True
    return wraps(view_func)(wrapped_view)
