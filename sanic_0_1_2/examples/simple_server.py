from sanic_0_1_2.src import Sanic
from sanic_0_1_2.src.response import json

app = Sanic(__name__)


@app.route("/")
async def test(request):
    return json({"test": True})


app.run(host="0.0.0.0", port=8000)

"""
从最简单的示例出发，一步步地了解Sanic框架的运行机制

- app.route： 
    这是一个装饰器，随着server的启动而启动，可定义参数 uri, methods，目的是为url的path和视图函数对应起来，构建一对映射关系。
    本例中，Sanic.router 类下的 Router.routes = [] 会增加一个名为 Route 的 namedtuple，如下：
        [Route(handler=<function test at 0x10a0f6488>, methods=None, pattern=re.compile('^/$'), parameters=[])]

- app.run(host="0.0.0.0", port=8000)：
    Sanic 下的 run 函数，启动一个 http server，主要是启动 run 里面的 serve 函数，参数如下：
        - host=host,
        - port=port,
        - debug=debug,
        - after_start=after_start,
        - before_stop=before_stop,
        - request_handler=self.handle_request,
        - request_timeout=self.config.REQUEST_TIMEOUT,
        - request_max_size=self.config.REQUEST_MAX_SIZE,
    至此，Sanic 服务启动了
    
- server.py：
    这里才是 Sanic 的核心部分，app.run(host="0.0.0.0", port=8000)： 里面执行了 server.serve 函数，此时创建了一个 TCP 服务的协程。
    然后通过 loop.run_forever() 运行这个事件循环，以便接收客户端请求以及处理相关事件，每当一个新的客户端建立连接 服务 就会创建一个新的 Protocol 实例。
    接受请求与返回响应离不开其中的 HttpProtocol，里面的函数 支持 接受数据、处理数据、执行视图函数、构建响应数据并返回给客户端
    
    具体可看代码里面的注释

"""
