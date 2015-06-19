usage: `htmldiff2.py [-h] [--show-config-format] [-t THREADS] [--debug] config`

        Use htmldiff2.py for diffing HTML served from the same path on different servers.
        This is useful when you want to find differences between production and
        staging environments.

positional arguments:
```
  config                JSON config file. See below for config schema.
```

optional arguments:
```
  -h, --help            show this help message and exit
  --show-config-format  show the config format
  -t THREADS, --threads THREADS
                        set the number of threads
  --debug               disable threading for debug purposes
```

JSON config file schema:
```JSON
{
    "title": "htmldiff config",
    "type": "object",
    "properties": {
        "servers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "base_url": {"type": "string"},
                    "auth": {
                        "type": "array",
                        "items": { "type": "string" }
                    },
                    "protocol": {"type" : "string"}
                },
                "required": ["base_url"]
            }
        },
        "relative_urls": {
            "type": "array",
            "minItems": 1,
            "items": { "type": "string" },
            "uniqueItems": true
        },
        "selectors": { "type": "object" }
    },
    "required": ["servers", "relative_urls", "selectors"]
}
```
