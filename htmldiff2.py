#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
from collections import OrderedDict
import difflib
import functools
import json
from multiprocessing.dummy import Pool as ThreadPool
import sys

import jsonschema
import lxml.html
from lxml.cssselect import CSSSelector
import requests

CONFIG_SCHEMA_FILE = 'config_schema.json'


class Server(object):

    def __init__(self, base_url, protocol='http', auth=None):
        self.base_url = base_url
        self.protocol = protocol
        self.auth = tuple(auth) if auth else None

    def get_full_url(self, relative_url):
        return "{}://{}{}".format(self.protocol, self.base_url, relative_url)

    def get_text_response(self, relative_url):
        url = self.get_full_url(relative_url)
        r = requests.get(url, auth=self.auth)
        if r.status_code != 200:
            raise Exception("Got status code {} for URL {}".format(r.status_code, url))
        r.encoding = 'utf-8'
        return r.text

    def get_dom_tree(self, relative_url):
        """ Build the DOM Tree """
        return lxml.html.fromstring(self.get_text_response(relative_url))

    def __str__(self):
        return self.get_url()


def get_text_from_tree(tree, selector, strip_whitespace=True):
    # construct a CSS Selector
    sel = CSSSelector(selector)

    # Apply the selector to the DOM tree.
    results = sel(tree)

    # Return an empty string for diffing if we match nothing
    if len(results) < 1:
        return ''

    # get the html out of all the results
    data = [lxml.html.tostring(result) for result in results]

    if strip_whitespace:
        data = [result.strip() for result in data]

    return data[0]


def mismatched_error_message(relative_url, selector_name, selector, trees, results):
    msg = []
    msg.append("-------------------------")
    msg.append("Error: mismatched results")
    for url, _ in trees.iteritems():
        msg.append("  - {}".format(url))
    msg.append("Selector name: {}".format(selector_name))
    msg.append("Selector: {}".format(selector))
    msg.append("")
    msg.append('\n'.join(difflib.ndiff(results[0].splitlines(), results[1].splitlines())))

    return '\n'.join(msg)


def compare_page(relative_url, servers, selectors):
    differences = []

    trees = OrderedDict()
    for server in servers:
        trees[server.get_full_url(relative_url)] = server.get_dom_tree(relative_url)

    for selector_name, selector in selectors.iteritems():
        results = [get_text_from_tree(tree, selector) for _, tree in trees.iteritems()]

        # If all results are equal, if we construct a set from the results,
        # the length of the set should be 1
        if len(set(results)) != 1:
            differences.append(mismatched_error_message(relative_url, selector_name, selector, trees, results))

    return differences


def compare_pages(relative_urls, servers, selectors, threads=1, debug=False):
    """
        relative_urls: list of str URLs
        selectors: dict of selecton_name, str CSS selector
        servers: list of Server objects
    """
    func = functools.partial(compare_page, servers=servers, selectors=selectors)
    if debug:
        differences = map(func, relative_urls)
    else:
        pool = ThreadPool(threads)
        differences = pool.map(func, relative_urls)
        pool.close()
        pool.join()

    # Flatten the list
    return reduce(lambda x, y: x + y, differences)


def parse_args():
    with open(CONFIG_SCHEMA_FILE, 'r') as f:
        config_schema = f.read()

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='''
        Use %(prog)s for diffing HTML served from the same path on different servers.
        This is useful when you want to find differences between production and
        staging environments.''',
        epilog='JSON config file schema:\n' + config_schema)
    parser.add_argument("config", help="JSON config file. See below for config schema.")
    parser.add_argument("--show-config-format", help="show the config format", action="store_true")
    parser.add_argument("-t", "--threads", type=int, default=1, help="set the number of threads")
    parser.add_argument("--debug", help="disable threading for debug purposes", action="store_true")
    return parser.parse_args()


def parse_config_file(filename):
    with open(filename, 'r') as config_f, open(CONFIG_SCHEMA_FILE, 'r') as config_schema_f:
        config_schema = json.load(config_schema_f)
        config = json.load(config_f)
        jsonschema.validate(config, config_schema)
    config['servers'] = [Server(**server_config) for server_config in config['servers']]
    return config


if __name__ == "__main__":
    args = parse_args()
    config = parse_config_file(args.config)
    differences = compare_pages(threads=args.threads, debug=args.debug, **config)

    print "Number of differences: {}".format(len(differences))
    for difference in differences:
        print difference
