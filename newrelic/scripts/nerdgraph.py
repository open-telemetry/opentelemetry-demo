# Standard library imports
import logging
import json
from typing import List, Any, cast
from urllib.request import Request, urlopen, HTTPError


# Get a logger instance
logger = logging.getLogger(__name__)


# The GraphQL endpoints
GRAPHQL_US_URL = 'https://api.newrelic.com/graphql'
GRAPHQL_EU_URL = 'https://api.eu.newrelic.com/graphql'


# -----------------------------------------------------------------------------
# Error classes
# -----------------------------------------------------------------------------


class GraphQLApiError(Exception):
    """Exception raised for GraphQL errors.
    """

    def __init__(
        self,
        message: str,
        status: int | None = None,
        reason: str | None = None
    ):
        """The constructor method.

        :param message: A message describing the error that occurred
        :type message: str
        :param status: The HTTP status code returned on the API call
        :type status: int | None
        :param reason: The HTTP reason returned on the API call
        :type reason: str | None
        """

        super().__init__(message)
        self.status = status
        self.reason = reason


# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------


def _get_nested_helper(
    val: Any,
    arr: List[str] = [],
    index: int = 0,
) -> Any | bool:
    """Recursive helper used by get_nested to safely get nested attributes by
    path.

    :param val: A value
    :type val: Any
    :param arr: The list of "path" segments, defaults to the empty list
    :type arr: list[str]
    :param index: The index of the current segment to examine, defaults to 0
    :type index: int
    :returns: False if we pass the last segment or the current value is not a
              dictionary, otherwise the value at index.
    :rtype: Any | bool
    """

    if index == len(arr):
        return False
    elif isinstance(val, dict):
        key = arr[index]
        if index == len(arr) - 1:
            data = cast(dict[str, Any], val)
            return data[key] if key in data else None
        return _get_nested_helper(val[key], arr, index + 1) if key in val else None
    return False


def get_nested(d: dict[str, Any], path: str) -> Any | bool:
    """Safely get a value by "path" nested within dictionaries in d.

    :param d: A dictionary of string keys to values
    :type d: dict
    :param path: A "path" of attribute names separated by "."
    :type path: str
    :returns: False if we pass the last segment or the current value is not a
              dictionary, otherwise the value at index.
    :rtype: Any | bool
    """

    return _get_nested_helper(d, path.split('.'))


# -----------------------------------------------------------------------------
# GraphQL functions
# -----------------------------------------------------------------------------


def build_graphql_headers(
    api_key: str,
    headers: dict[str, str] = {},
) -> dict[str, str]:
    """Return a dictionary containing HTTP headers for a Nerdgraph call.

    If specified, the additional headers will be merged into the default
    headers.

    :param api_key: The New Relic User API key to use
    :type api_key: str
    :param headers: Additional headers to send, defaults to {}
    :type headers: dict[str, str]
    :returns: A dictionary containing HTTP headers for a Nerdgraph call.
    :rtype: dict[str, str]
    """

    all_headers = {
        'Accept': 'application/json',
        'Api-Key': api_key,
        'Content-Type': 'application/json'
    }

    all_headers.update(headers)

    return all_headers


def post_graphql(
    api_key: str,
    payload: dict[str, Any],
    headers: dict[str, str] = {},
    region: str = 'US'
) -> dict[str, Any]:
    """Make the actual GraphQL POST call using the given payload.

    :param api_key: The New Relic User API key to use
    :type api_key: str
    :param payload: The payload to send, as a dict of string keys to values
    :type payload: dict[str, Any]
    :param headers: Additional headers to send, defaults to {}
    :type headers: dict[str, str]
    :param region: The region to use for the GraphQL API call, defaults to 'US'
    :type region: str
    :raises GraphQLApiError: if the response code of the POST call is not
            a 2XX code or if an HTTPError is raised or if the `errors` property
            of the parsed GraphQL response is present.
    :returns: The `data` property of the parsed GraphQL response as a dict.
    :rtype: dict[str, Any]
    """

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(json.dumps(payload, indent=2))

    request = Request(
        GRAPHQL_EU_URL if region == 'EU' else GRAPHQL_US_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers=build_graphql_headers(api_key, headers),
    )

    try:
        with urlopen(
            request,
            timeout=30,
        ) as response:
            status = response.status
            reason = response.reason

            if status != 200:
                logger.error(
                    f'GraphQL request failed with status: {status}, reason: {reason}',
                )
                raise GraphQLApiError(
                    f'GraphQL request failed with status: {status}, reason: {reason}',
                    status,
                    reason,
                )

            try:
                text = response.read().decode('utf-8')
            except OSError as e:
                logger.error(f'error reading GraphQL response: {e}')
                raise GraphQLApiError(
                    f'error reading GraphQL response: {e}',
                    status,
                    reason,
                )

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(json.loads(text))

            response_json = json.loads(text)
            if 'errors' in response_json:
                for error in response_json['errors']:
                    logger.error(
                        f'GraphQL post error: {error.get("message")}'
                    )

                errs = ','.join([
                    error.get('message') for error in response_json['errors']
                ])

                raise GraphQLApiError(
                    f'GraphQL post error: {errs}',
                    status,
                    reason,
                )

            return response_json['data']
    except HTTPError as e:
        logger.error(
            f'HTTP error occurred with status: {e.code}, reason: {e.reason}',
        )
        raise GraphQLApiError(
            f'HTTP error occurred with status: {e.code}, reason: {e.reason}',
            e.code,
            e.reason,
        )


def build_graphql_payload(
    query: str,
    variables: dict[str, tuple[str, Any]] = {},
    mutation: bool = False,
) -> dict[str, Any]:
    """Build the GraphQL payload from the given query and variables.

    If `mutation` is True, a mutation query is generated. Otherwise,
    a regular query is generated.

    :param query: The GraphQL query (or mutation) to run
    :type query: str
    :param variables: A dictionary of query variables used in the query
    :type variables: dict[str, tuple[str, Any]]
    :param mutation: True if this is a mutation, defaults to False
    :type mutation: bool
    :returns: The GraphQL payload to send, as a dict of string keys to values.
    :rtype: dict[str, Any]
    """

    var_spec = ''
    vars: dict[str, Any] = {}

    for idx, key in enumerate(variables):
        type, value = variables[key]
        if idx > 0:
            var_spec += ','
        var_spec += "$%s: %s" % (key, type)
        vars[key] = value

    if len(vars) > 0:
        var_spec = '(' + var_spec + ')'

    return {
        'query': "%s%s%s" % (
            'mutation' if mutation else 'query',
            var_spec,
            query
        ),
        'variables': vars
    }


def query_graphql(
    api_key: str,
    query: str,
    variables: dict[str, tuple[str, Any]],
    next_cursor_path: str | None = None,
    mutation: bool = False,
    headers: dict[str, str] = {},
    region: str = 'US',
) -> List[dict[str, Any]]:
    """Make generic GQL queries with built-in pagination support.

    :param api_key: The New Relic User API key to use
    :type api_key: str
    :param query: The GraphQL query (or mutation) to run
    :type query: str
    :param variables: A dictionary of query variables used in the query
    :type variables: dict[str, tuple[str, Any]]
    :param next_cursor_path: The "path" to a property within a GraphQL
           response that holds the value of the pagination cursor, defaults to
           None
    :type next_cursor_path: str | None
    :param mutation: True if this is a mutation, defaults to False
    :type mutation: bool
    :param headers: Additional headers to send, defaults to {}
    :type headers: dict[str, str]
    :param region: The region to use for the GraphQL API call, defaults to 'US'
    :type region: str
    :raises GraphQLApiError: if the response code of the GraphQL API call is not
            a 2XX code or if an HTTPError is raised or if the `errors` property
            of the parsed GraphQL response is present.
    :returns: A list of result objects, one for each page. Contains a single
              result for unpaged queries.
    :rtype: list[dict[str, Any]]
    """

    done = False
    next_cursor = None
    results: List[dict[str, Any]] = []

    while not done:
        if next_cursor_path:
            variables['cursor'] = ('String', next_cursor)

        gql_result = post_graphql(
            api_key,
            build_graphql_payload(query, variables, mutation),
            headers,
            region,
        )
        results.append(gql_result)

        if next_cursor_path:
            next_cursor = get_nested(gql_result, next_cursor_path)
            if next_cursor == False:
                raise GraphQLApiError(
                    f'expected value at path {next_cursor_path} but found none',
                )

        if not next_cursor:
            done = True

    return results


def run_nrql(
    api_key: str,
    account_ids: List[int],
    nrql: str,
    headers: dict[str, str] = {},
    region: str = 'US',
) -> List[dict[str, Any]]:
    """Run a NRQL query using Nerdgraph.

    :param api_key: The User API key to use
    :type api_key: str
    :param account_ids: The list of account IDs to query
    :type account_ids: List[int]
    :param nrql: The NRQL query string
    :type nrql: str
    :param headers: Additional headers to send, defaults to {}
    :type headers: dict[str, str]
    :param region: The region to use for the GraphQL API call, defaults to 'US'
    :type region: str
    :raises GraphQLApiError: if the response code of the GraphQL API call is not
            a 2XX code or if an HTTPError is raised or if the `errors` property
            of the parsed GraphQL response is present or if there is more than
            one result returned or if the results property is missing or
            not a valid list.
    :return: The results of the NRQL query.
    :rtype: List[dict[str, Any]]
    """

    query = """
{
  actor {
    nrql(query: $nrql, accounts: $accounts) {
      results
    }
  }
}"""
    variables: dict[str, tuple[str, Any]] = {
        'nrql': ('Nrql!', nrql),
        'accounts': ('[Int!]!', account_ids),
    }

    results = query_graphql(
        api_key,
        query,
        variables,
        headers=headers,
        region=region,
    )
    if len(results) != 1:
        logger.error(
            f'unexpected number of results for query {query}: {len(results)}',
        )
        raise GraphQLApiError(
            f'unexpected number of results for query {query}: {len(results)}',
        )

    # Get the NRQL results
    result = get_nested(results[0], 'actor.nrql.results')
    if not isinstance(result, list):
        logger.error(
            f'missing or invalid query results for query {query}',
        )
        raise GraphQLApiError(
            f'missing or invalid query results for query {query}',
        )

    results = cast(List[dict[str, Any]], result)

    return results
