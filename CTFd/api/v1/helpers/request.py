from functools import wraps

from flask import request
from pydantic import Extra, ValidationError, create_model

ARG_LOCATIONS = {
    "query": lambda: request.args,
    "json": lambda: request.get_json(),
    "formData": lambda: request.form,
    "headers": lambda: request.headers,
    "cookies": lambda: request.cookies,
}


def expects_args(spec, location, allow_extras=False, validate=False):
    """
    A decorator to document an endpoint's expected parameters, with support for optional validation.

    Args:
        spec: The pydantic model to use for validation
        location: The location of the request. One of "query", "json", "form", "headers", "cookies"
        allow_extras: Allow extra parameters in the request
        validate: Perform validation of the request
    """
    if isinstance(spec, dict):
        spec = create_model("", **spec)

    if allow_extras:
        spec.__config__.extra = Extra.allow

    schema = spec.schema()

    defs = schema.pop("definitions", {})
    props = schema.get("properties", {})
    required = schema.get("required", [])

    # Remove all titles and resolve all $refs in properties
    for k in props:
        if "title" in props[k]:
            del props[k]["title"]

        if "$ref" in props[k]:
            definition: dict = defs[props[k].pop("$ref").split("/").pop()]

            # Check if the schema is for enums, if so, we just add in the "enum" key
            # else we add the whole schema into the properties
            if "enum" in definition:
                props[k]["enum"] = definition["enum"]
            else:
                props[k] = definition

    def decorator(func):
        # Inject parameters information into the Flask-Restx apidoc attribute.
        # Not really a good solution. See https://github.com/CTFd/CTFd/issues/1504
        nonlocal location

        apidoc = getattr(func, "__apidoc__", {"params": {}})

        if location == "form":
            location = "formData"

            if any(v["type"] == "file" for v in props.values()):
                apidoc["consumes"] = ["multipart/form-data"]
            else:
                apidoc["consumes"] = [
                    "application/x-www-form-urlencoded",
                    "multipart/form-data",
                ]

        if location == "json":
            title = schema.get("title", "")
            apidoc["consumes"] = ["application/json"]
            apidoc["params"].update({title: {"in": "body", "schema": schema}})
        else:
            for k, v in props.items():
                v["in"] = location

                if k in required:
                    v["required"] = True

                apidoc["params"][k] = v

        func.__apidoc__ = apidoc

        @wraps(func)
        def wrapper(*args, **kwargs):
            data = ARG_LOCATIONS[location]()

            if not validate:
                return func(*args, data, **kwargs)

            try:
                # Try to load data according to pydantic spec
                loaded = spec(**data).dict(exclude_unset=True)
            except ValidationError as e:
                # Handle reporting errors when invalid
                resp = {}
                errors = e.errors()
                for err in errors:
                    loc = err["loc"][0]
                    msg = err["msg"]
                    resp[loc] = msg
                return {"success": False, "errors": resp}, 400
            return func(*args, loaded, **kwargs)

        return wrapper

    return decorator


def validate_args(spec, location, allow_extras=False):
    return expects_args(spec, location, allow_extras, validate=True)
