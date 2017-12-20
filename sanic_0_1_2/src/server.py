import asyncio
from inspect import isawaitable
from signal import SIGINT, SIGTERM

import httptools

try:
    import uvloop as async_loop
except:
    async_loop = asyncio

from .log import log
from .request import Request


class Signal:
    stopped = False


class HttpProtocol(asyncio.Protocol):
    """
    用来处理与客户端通信
    https://pymotw.com/3/asyncio/io_protocol.html
    """
    __slots__ = ('loop', 'transport', 'connections', 'signal',  # event loop, connection
                 'parser', 'request', 'url', 'headers',  # request params
                 'request_handler', 'request_timeout', 'request_max_size',  # request config
                 '_total_request_size', '_timeout_handler')  # connection management

    def __init__(self, *, loop, request_handler, signal=Signal(), connections={}, request_timeout=60,
                 request_max_size=None):
        self.loop = loop
        self.transport = None
        self.request = None
        self.parser = None
        self.url = None
        self.headers = None
        self.signal = signal
        self.connections = connections
        self.request_handler = request_handler
        self.request_timeout = request_timeout
        self.request_max_size = request_max_size
        self._total_request_size = 0
        self._timeout_handler = None

        # -------------------------------------------- #

    # Connection
    # -------------------------------------------- #

    def connection_made(self, transport):
        """
        注释：每当有一个新的客户端连接，该方法就会被触发
        :param transport:  transport 参数是一个 asyncio.Transport 实例对象
        :return:
        """
        self.connections[self] = True
        # 超时时间后执行 connection_timeout 并且关闭 self.transport 对象
        self._timeout_handler = self.loop.call_later(self.request_timeout, self.connection_timeout)
        self.transport = transport

    def connection_lost(self, exc):
        """
        当一个连接被关闭的时候
        :param exc:
        :return:
        """
        del self.connections[self]
        self._timeout_handler.cancel()
        self.cleanup()

    def connection_timeout(self):
        self.bail_out("Request timed out, connection closed")

        # -------------------------------------------- #

    # Parsing
    # -------------------------------------------- #

    def data_received(self, data):
        """
        当有数据从客户端发到服务端的时候会使用传输过来的数据调用此方法
        :param data: 传输过来的数据
        :return:
        """
        # Check for the request itself getting too large and exceeding memory limits
        self._total_request_size += len(data)
        if self._total_request_size > self.request_max_size:
            return self.bail_out("Request too large ({}), connection closed".format(self._total_request_size))

        # Create parser if this is the first time we're receiving data
        if self.parser is None:
            assert self.request is None
            self.headers = []
            self.parser = httptools.HttpRequestParser(self)

        # Parse request chunk or close connection
        try:
            self.parser.feed_data(data)
        except httptools.parser.errors.HttpParserError as e:
            self.bail_out("Invalid request data, connection closed ({})".format(e))

    def on_url(self, url):
        self.url = url

    def on_header(self, name, value):
        # 继 on_url 后被循环调用 生成self.headers
        if name == b'Content-Length' and int(value) > self.request_max_size:
            return self.bail_out("Request body too large ({}), connection closed".format(value))

        self.headers.append((name.decode(), value.decode('utf-8')))

    def on_headers_complete(self):
        # 继 on_header 后被调用 实例化 Request 类
        self.request = Request(
            url_bytes=self.url,
            headers=dict(self.headers),
            version=self.parser.get_http_version(),
            method=self.parser.get_method().decode()
        )

    def on_body(self, body):
        self.request.body = body

    def on_message_complete(self):
        # 继 on_headers_complete 后被调用 执行 self.request_handler 最后回调给 self.write_response
        self.loop.create_task(self.request_handler(self.request, self.write_response))

    # -------------------------------------------- #
    # Responding
    # -------------------------------------------- #

    def write_response(self, response):
        # on_message_complete 回调 write_response 返回响应值
        # response 为 HTTPResponse 响应对象 包含 content_type body headers status
        try:
            keep_alive = self.parser.should_keep_alive() and not self.signal.stopped
            self.transport.write(response.output(self.request.version, keep_alive, self.request_timeout))
            if not keep_alive:
                self.transport.close()
            else:
                self.cleanup()
        except Exception as e:
            self.bail_out("Writing request failed, connection closed {}".format(e))

    def bail_out(self, message):
        log.error(message)
        # 关闭连接 此时 connection_lost 会被执行
        self.transport.close()

    def cleanup(self):
        self.parser = None
        self.request = None
        self.url = None
        self.headers = None
        self._total_request_size = 0

    def close_if_idle(self):
        """
        Close the connection if a request is not being sent or received
        :return: boolean - True if closed, false if staying open
        """
        if not self.parser:
            self.transport.close()
            return True
        return False


def serve(host, port, request_handler, after_start=None, before_stop=None, debug=False, request_timeout=60,
          request_max_size=None):
    # Create Event Loop
    # 注释：
    # 创建一个新的时间循环并返回
    loop = async_loop.new_event_loop()
    # 注释：
    # 为当前上下文设置事件循环
    asyncio.set_event_loop(loop)
    # I don't think we take advantage of this
    # And it slows everything waaayyy down
    # loop.set_debug(debug)

    connections = {}
    signal = Signal()
    # 一个可以创建 TCP 服务的协程
    # 每当一个新的客户端建立连接 服务 就会创建一个新的 Protocol 实例
    server_coroutine = loop.create_server(lambda: HttpProtocol(
        loop=loop,
        connections=connections,
        signal=signal,
        request_handler=request_handler,
        request_timeout=request_timeout,
        request_max_size=request_max_size,
    ), host, port)
    try:
        # <Server sockets=[<socket.socket fd=14, family=AddressFamily.AF_INET, type=SocketKind.SOCK_STREAM, proto=0, laddr=('0.0.0.0', 8000)>]>
        http_server = loop.run_until_complete(server_coroutine)
    except OSError as e:
        log.error("Unable to start server: {}".format(e))
        return
    except:
        log.exception("Unable to start server")
        return

    # Run the on_start function if provided
    # 注释：
    # 服务启动后若after_start满足条件将被执行
    if after_start:
        result = after_start(loop)
        if isawaitable(result):
            loop.run_until_complete(result)

    # Register signals for graceful termination
    # 注释：
    # 调用AbstractEventLoop.add_signal_handler()方法 https://docs.python.org/3/library/asyncio-eventloop.html
    # 例：当接受到如Ctrl-c发送的SIGINT会自动调用此时的callback函数loop.stop
    for _signal in (SIGINT, SIGTERM):
        loop.add_signal_handler(_signal, loop.stop)

    try:
        # 注释：
        # 运行这个事件循环，以便接收客户端请求以及处理相关事件
        # 一直运行，直到loop.close()
        loop.run_forever()
    finally:
        log.info("Stop requested, draining connections...")

        # Run the on_stop function if provided
        if before_stop:
            result = before_stop(loop)
            if isawaitable(result):
                loop.run_until_complete(result)

        # Wait for event loop to finish and all connections to drain
        http_server.close()
        loop.run_until_complete(http_server.wait_closed())

        # Complete all tasks on the loop
        signal.stopped = True
        for connection in connections.keys():
            connection.close_if_idle()

        while connections:
            loop.run_until_complete(asyncio.sleep(0.1))

        loop.close()
        log.info("Server Stopped")
