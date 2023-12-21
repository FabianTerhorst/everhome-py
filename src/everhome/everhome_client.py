"""This is a Sample Python file."""

from __future__ import annotations

import json
import logging
import re
import warnings

import requests
import six
import urllib3

from everhome.exceptions import EverHomeException


__all__ = ["EverHome", "EverHomeException"]

logger = logging.getLogger(__name__)

class EverHome(object):
    """
        Example usage::

            import everhome

            client = everhome.Client(oauth2Token)

            devices = client.getDevices()
            print(devices)
    """

    def __init__(
        self,
        auth=None,
        requests_timeout=5
    ):
        """
        Creates a everHome API client.

        :param auth: An access token (optional)
        """
        self.prefix = "https://everhome.cloud/"
        self._auth = auth
        self._build_session()
        self.requests_timeout = requests_timeout

    def set_auth(self, auth):
        self._auth = auth

    def _build_session(self):
        self._session = requests.Session()
        retry = urllib3.Retry(
            total=3,
            connect=None,
            read=False,
            allowed_methods=frozenset(['GET', 'POST', 'PUT', 'DELETE']),
            status=(429, 500, 502, 503, 504),
            backoff_factor=0.3,
            status_forcelist=None)

        adapter = requests.adapters.HTTPAdapter(max_retries=retry)
        self._session.mount('http://', adapter)
        self._session.mount('https://', adapter)

    def _auth_headers(self):
        return {"Authorization": "Bearer {0}".format(self._auth)}

    def _internal_call(self, method, url, payload, params):
        args = dict(params=params)
        if not url.startswith("http"):
            url = self.prefix + url
        headers = self._auth_headers()

        if "content_type" in args["params"]:
            headers["Content-Type"] = args["params"]["content_type"]
            del args["params"]["content_type"]
            if payload:
                args["data"] = payload
        else:
            headers["Content-Type"] = "application/json"
            if payload:
                args["data"] = json.dumps(payload)

        logger.debug('Sending %s to %s with Params: %s Headers: %s and Body: %r ',
                     method, url, args.get("params"), headers, args.get('data'))

        try:
            response = self._session.request(
                method, url, headers=headers, proxies=None,
                timeout=self.requests_timeout, **args
            )

            response.raise_for_status()
            results = response.json()
        except requests.exceptions.HTTPError as http_error:
            response = http_error.response
            try:
                json_response = response.json()
                error = json_response.get("error", {})
                msg = error.get("message")
                reason = error.get("reason")
            except ValueError:
                # if the response cannot be decoded into JSON (which raises a ValueError),
                # then try to decode it into text

                # if we receive an empty string (which is falsy), then replace it with `None`
                msg = response.text or None
                reason = None

            logger.error(
                'HTTP Error for %s to %s with Params: %s returned %s due to %s',
                method, url, args.get("params"), response.status_code, msg
            )

            raise EverHomeException(
                response.status_code,
                -1,
                "%s:\n %s" % (response.url, msg),
                reason=reason,
                headers=response.headers,
            )
        except requests.exceptions.RetryError as retry_error:
            request = retry_error.request
            logger.error('Max Retries reached')
            try:
                reason = retry_error.args[0].reason
            except (IndexError, AttributeError):
                reason = None
            raise EverHomeException(
                429,
                -1,
                "%s:\n %s" % (request.path_url, "Max Retries"),
                reason=reason
            )
        except ValueError:
            results = None

        logger.debug('RESULTS: %s', results)
        return results

    def _get(self, url, args=None, payload=None, **kwargs):
        if args:
            kwargs.update(args)

        return self._internal_call("GET", url, payload, kwargs)

    def _post(self, url, args=None, payload=None, **kwargs):
        if args:
            kwargs.update(args)
        return self._internal_call("POST", url, payload, kwargs)

    def _delete(self, url, args=None, payload=None, **kwargs):
        if args:
            kwargs.update(args)
        return self._internal_call("DELETE", url, payload, kwargs)

    def _put(self, url, args=None, payload=None, **kwargs):
        if args:
            kwargs.update(args)
        return self._internal_call("PUT", url, payload, kwargs)

    def user(self):
        """ Gets informations about the logged in everHome User
        """
        return self._get("user/current")

    def test(self) -> Any:
        self._get("devices")
        return 42
