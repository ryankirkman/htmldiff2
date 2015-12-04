#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
from collections import OrderedDict
import difflib
import functools
import json
from multiprocessing.dummy import Pool as ThreadPool

import jsonschema
import lxml.html
from lxml.cssselect import CSSSelector
import requests

CONFIG_SCHEMA_FILE = 'config_schema.json'


class Server(object):
    def __init__(self, base_url, ignore_non_200=False, protocol='http', auth=None, headers=None):
        self.base_url = base_url
        self.ignore_non_200 = ignore_non_200
        self.protocol = protocol
        self.auth = tuple(auth) if auth else None
        self.headers = headers

    def __str__(self):
        return self.get_url()

    @staticmethod
    def compare_pages(
            relative_urls,
            servers,
            html,
            json,
            ignore_non_200=False,
            threads=1,
            debug=False,
            **kwargs):
        """
            relative_urls: list of str URLs
            servers: list of Server objects
            html: Boolean for HTML response type
            json: Boolean for JSON response type
        """
        _servers = [
            Server.factory(html=html, json=json, ignore_non_200=ignore_non_200, **server_config)
            for server_config in servers]
        func = functools.partial(_servers[0].compare_page, servers=_servers, **kwargs)
        if debug:
            differences = map(func, relative_urls)
        else:
            pool = ThreadPool(threads)
            differences = pool.map(func, relative_urls)
            pool.close()
            pool.join()

        # Flatten the list
        return reduce(lambda x, y: x + y, differences)

    @staticmethod
    def factory(html=None, json=None, **config):
        if html:
            return HtmlServer(**config)
        elif json:
            return JsonServer(**config)

        raise Exception('Factory failed to create class')

    def get_full_url(self, relative_url):
        return "{}://{}{}".format(self.protocol, self.base_url, relative_url)

    def get_base_response(self, relative_url):
        url = self.get_full_url(relative_url)
        r = requests.get(url, auth=self.auth, headers=self.headers)
        if r.status_code != 200:
            if self.ignore_non_200:
                return None
            else:
                raise Exception("Got status code {} for URL {}".format(r.status_code, url))
        return r


class HtmlServer(Server):
    def __init__(*args, **kwargs):
        Server.__init__(*args, **kwargs)

    @staticmethod
    def compare_page(relative_url, servers, selectors):
        differences = []

        trees = OrderedDict()
        for server in servers:
            response = server.get_dom_tree(relative_url)
            if not response:
                # Early out for None server response
                url = server.get_full_url(relative_url)
                return ['Failed to retreive URL: {}'.format(url)]
                # return []
            trees[server.get_full_url(relative_url)] = response

        for selector_name, selector in selectors.iteritems():
            results = [
                HtmlServer.get_text_from_tree(tree, selector) for _, tree in trees.iteritems()]

            # If all results are equal, if we construct a set from the results,
            # the length of the set should be 1
            if len(set(results)) != 1:
                differences.append(
                    HtmlServer.mismatched_error_message(
                        relative_url, selector_name, selector, trees, results))

        return differences

    @staticmethod
    def mismatched_error_message(relative_url, selector_name, selector, trees, results):
        msg = []
        msg.append("-------------------------")
        msg.append("Error - mismatched results for: {}".format(relative_url))
        for url, _ in trees.iteritems():
            msg.append("  - {}".format(url))
        msg.append("Selector name: {}".format(selector_name))
        msg.append("Selector: {}".format(selector))
        msg.append("")
        msg.append('\n'.join(difflib.ndiff(results[0].splitlines(), results[1].splitlines())))

        return '\n'.join(msg)

    @staticmethod
    def get_text_from_tree(tree, selector, strip_whitespace=True):
        # construct a CSS Selector
        sel = CSSSelector(selector)

        # Apply the selector to the DOM tree.
        results = sel(tree)

        # Return an empty string for diffing if we match nothing
        if len(results) < 1:
            return ''

        # get the html out of all the results
        data = [result.text for result in results]

        if strip_whitespace:
            data = [result.strip() if isinstance(result, basestring) else None for result in data]

        return data[0]

    def get_dom_tree(self, relative_url):
        """ Build the DOM Tree """
        response = self.get_response(relative_url)
        return lxml.html.fromstring(response) if response else None

    def get_response(self, relative_url):
        r = Server.get_base_response(self, relative_url)
        if not r:
            return None
        r.encoding = 'utf-8'
        return r.text


class JsonServer(Server):
    def __init__(*args, **kwargs):
        Server.__init__(*args, **kwargs)

    @staticmethod
    def compare_page(relative_url, servers, ignore_keys=None, include_keys=None):
        differences = []

        server_responses = OrderedDict()
        for server in servers:
            response = server.get_response(relative_url)
            if not response:
                # Early out for None server response
                url = server.get_full_url(relative_url)
                return ['Failed to retreive URL: {}'.format(url)]
                # return []
            server_responses[server.get_full_url(relative_url)] = response

        results = []
        for _, response in server_responses.iteritems():
            results.append(json.dumps(
                JsonServer.pluck(response, ignore_keys, include_keys),
                sort_keys=True,
                indent=4))

        # If all results are equal, if we construct a set from the results,
        # the length of the set should be 1
        if len(set(results)) != 1:
            differences.append(
                JsonServer.mismatched_error_message(relative_url, results))

        return differences

    @staticmethod
    def pluck(json_obj, ignore_keys=None, include_keys=None):
        if not ignore_keys and not include_keys:
            return json_obj
        elif ignore_keys:
            for key in ignore_keys:
                split = key.split('.')
                temp_obj = json_obj
                for i in xrange(len(split) - 1):
                    temp_obj = temp_obj.get(split[i])
                del temp_obj[split[-1]]
        elif include_keys:
            plucked = {}
            for key in include_keys:
                split = key.split('.')
                temp_obj = json_obj
                for i in xrange(len(split)):
                    temp = temp_obj.get(split[i])
                    if temp:
                        temp_obj = temp
                    else:
                        break
                plucked[key] = temp_obj

            return plucked

        return json_obj

    @staticmethod
    def mismatched_error_message(relative_url, results):
        msg = []
        msg.append("-------------------------")
        msg.append("Error - mismatched results for url: {}".format(relative_url))
        msg.append("")
        msg.append('\n'.join(difflib.ndiff(results[0].splitlines(), results[1].splitlines())))
        return '\n'.join(msg)

    def get_response(self, relative_url):
        r = Server.get_base_response(self, relative_url)
        if not r:
            return None
        return r.json()


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
    parser.add_argument(
        "--ignore-non-200", help="ignore responses that aren't 200 OK", action="store_true")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--html", help="Parse responses as HTML", action="store_true")
    group.add_argument("--json", help="Parse responses as JSON", action="store_true")
    return parser.parse_args()


def parse_config_file(filename):
    with open(filename, 'r') as config_f, open(CONFIG_SCHEMA_FILE, 'r') as config_schema_f:
        config_schema = json.load(config_schema_f)
        config = json.load(config_f)
        jsonschema.validate(config, config_schema)
    return config


if __name__ == "__main__":
    args = parse_args()
    config = parse_config_file(args.config)
    differences = Server.compare_pages(
        threads=args.threads,
        debug=args.debug,
        html=args.html,
        json=args.json,
        ignore_non_200=args.ignore_non_200,
        **config)

    print "Number of differences: {}".format(len(differences))
    for difference in differences:
        print difference.encode('utf-8')
