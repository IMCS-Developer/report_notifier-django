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
