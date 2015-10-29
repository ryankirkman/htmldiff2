usage: `htmldiff2.py [-h] [--show-config-format] [-t THREADS] [--debug] config`

        Use htmldiff2.py for diffing HTML served from the same path on different servers.
        This is useful when you want to find differences between production and
        staging environments.

examle usage: `./htmldiff2.py example_configs/reddit_vs_reddit_beta.json`

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

JSON config file schema: see `config_schema.json`