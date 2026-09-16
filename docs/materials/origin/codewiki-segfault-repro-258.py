
from . import _types as _t
from ._internal_utils import to_native_string, unicode_is_ascii
from .auth import HTTPBasicAuth
from .compat import (
    JSONDecodeError,
    basestring,
    builtin_str,
    chardet,
    cookielib,
    urlencode,
    urlsplit,
    urlunparse,
)
from .compat import json as complexjson
from .cookies import (
    _copy_cookie_jar,
    cookiejar_from_dict,
    get_cookie_header,
)
from .exceptions import (
    ChunkedEncodingError,
    ConnectionError,
    ContentDecodingError,
    HTTPError,
    InvalidJSONError,
    InvalidURL,
    MissingSchema,
    StreamConsumedError,
)
from .exceptions import JSONDecodeError as RequestsJSONDecodeError
from .exceptions import SSLError as RequestsSSLError
from .hooks import default_hooks
from .status_codes import codes
from .structures import CaseInsensitiveDict
from .utils import (
    check_header_validity,
    get_auth_from_url,
    guess_filename,
    guess_json_utf,
    iter_slices,
    parse_header_links,
    requote_uri,
    stream_decode_response_unicode,
    super_len,
    to_key_val_list,
)

if TYPE_CHECKING:
    from http.cookiejar import CookieJar

    from typing_extensions import Self

    from .adapters import HTTPAdapter
    from .cookies import RequestsCookieJar

#: The set of HTTP status codes that indicate an automatically
#: processable redirect.
REDIRECT_STATI: Final[tuple[int, ...]] = (  # type: ignore[assignment]
    codes.moved,  # 301
    codes.found,  # 302
    codes.other,  # 303
    codes.temporary_redirect,  # 307
    codes.permanent_redirect,  # 308
)

DEFAULT_REDIRECT_LIMIT: int = 30
CONTENT_CHUNK_SIZE: int = 10 * 1024
ITER_CHUNK_SIZE: int = 512


class RequestEncodingMixin:
    url: str | None

    @property
    def path_url(self) -> str:
        """Build the path URL to use."""

        url: list[str] = []

        p = urlsplit(cast(str, self.url))

        path = p.path
        if not path:
            path = "/"

        url.append(path)

        query = p.query
        if query:
            url.append("?")
            url.append(query)

        return "".join(url)

    @overload
    @staticmethod
    def _encode_params(data: str) -> str: ...

    @overload
    @staticmethod
    def _encode_params(data: bytes) -> bytes: ...

    @overload
    @staticmethod
    def _encode_params(
        data: _t.SupportsRead[str | bytes],
    ) -> _t.SupportsRead[str | bytes]: ...

    @overload
    @staticmethod
    def _encode_params(data: _t.KVDataType) -> str: ...

    @staticmethod
    def _encode_params(
        data: _t.EncodableDataType,
    ) -> str | bytes | _t.SupportsRead[str | bytes]:
        """Encode parameters in a piece of data.

        Will successfully encode parameters when passed as a dict or a list of
        2-tuples. Order is retained if data is a list of 2-tuples but arbitrary
        if parameters are supplied as a dict.
        """

        if isinstance(data, (str, bytes)):
            return data
        elif _t.has_read(data):
            return data
        elif hasattr(data, "__iter__"):
            result: list[tuple[bytes, bytes]] = []
            for k, vs in to_key_val_list(data):
                if isinstance(vs, basestring) or not hasattr(vs, "__iter__"):
                    vs = [vs]
                for v in vs:
                    if v is not None:
                        result.append(
                            (
                                k.encode("utf-8") if isinstance(k, str) else k,
                                v.encode("utf-8") if isinstance(v, str) else v,
                            )
                        )
            return urlencode(result, doseq=True)
        else:
            return data  # type: ignore[return-value]  # unreachable for valid _t.DataType

    @staticmethod
    def _encode_files(
        files: _t.FilesType, data: _t.RawDataType | None
    ) -> tuple[bytes, str]:
        """Build the body for a multipart/form-data request.

        Will successfully encode files when passed as a dict or a list of
        tuples. Order is retained if data is a list of tuples but arbitrary
        if parameters are supplied as a dict.
        The tuples may be 2-tuples (filename, fileobj), 3-tuples (filename, fileobj, contentype)
        or 4-tuples (filename, fileobj, contentype, custom_headers).
    :param json: json for the body to attach to the request (if files or data is not specified).
    :param params: URL parameters to append to the URL. If a dictionary or
        list of tuples ``[(key, value)]`` is provided, form-encoding will
        take place.
    :param auth: Auth handler or (user, pass) tuple.
    :param cookies: dictionary or CookieJar of cookies to attach to this request.
    :param hooks: dictionary of callback hooks, for internal usage.

    Usage::

      >>> import requests
      >>> req = requests.Request('GET', 'https://httpbin.org/get')
      >>> req.prepare()
      <PreparedRequest [GET]>
    """

    hooks: dict[str, list[_t.HookType]]
    method: str | None
    url: _t.UriType | None
    headers: Mapping[str, str | bytes]
    files: _t.FilesType
    data: _t.DataType
    json: _t.JsonType
    params: _t.ParamsType
    auth: _t.AuthType
    cookies: RequestsCookieJar | CookieJar | dict[str, str] | None

    def __init__(
        self,
        method: str | None = None,
        url: _t.UriType | None = None,
        headers: _t.HeadersType = None,
        files: _t.FilesType = None,
        data: _t.DataType = None,
        params: _t.ParamsType = None,
        auth: _t.AuthType = None,
        cookies: RequestsCookieJar | CookieJar | dict[str, str] | None = None,
        hooks: _t.HooksInputType | None = None,
        json: _t.JsonType = None,
    ) -> None:
        # Default empty dicts for dict params.
        data = [] if data is None else data
        files = [] if files is None else files
        headers = {} if headers is None else headers
        params = {} if params is None else params
        hooks = {} if hooks is None else hooks

        self.hooks = default_hooks()
        for k, v in list(hooks.items()):
            self.register_hook(event=k, hook=v)

        self.method = method
        self.url = url
        self.headers = headers
        self.files = files
        self.data = data
        self.json = json
        self.params = params
        self.auth = auth
        self.cookies = cookies

    def __repr__(self) -> str:
        return f"<Request [{self.method}]>"

    def prepare(self) -> PreparedRequest:
        """Constructs a :class:`PreparedRequest <PreparedRequest>` for transmission and returns it."""
        p = PreparedRequest()
        p.prepare(
            method=self.method,
            url=self.url,
            headers=self.headers,
            files=self.files,
            data=self.data,
            json=self.json,
            params=self.params,
            auth=self.auth,
            cookies=self.cookies,
            hooks=self.hooks,
        )
        return p


class PreparedRequest(RequestEncodingMixin, RequestHooksMixin):
    """The fully mutable :class:`PreparedRequest <PreparedRequest>` object,
    containing the exact bytes that will be sent to the server.

    Instances are generated from a :class:`Request <Request>` object, and
    should not be instantiated manually; doing so may produce undesirable
    effects.

    Usage::

      >>> import requests
      >>> req = requests.Request('GET', 'https://httpbin.org/get')
      >>> r = req.prepare()
      >>> r
      <PreparedRequest [GET]>

      >>> s = requests.Session()
      >>> s.send(r)
      <Response [200]>
    """
