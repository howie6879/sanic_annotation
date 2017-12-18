from sanic_0_1_2.src import Sanic
from sanic_0_1_2.src.response import json

app = Sanic(__name__)


@app.route("/")
async def test(request):
    return json({"test": True})


app.run(host="0.0.0.0", port=8000)

"""
从最简单的示例出发，一步步地了解Sanic框架的运行机制

- app.route： 这是一个装饰器，目的是为url的path和视图函数对应起来，构建一对映射关系


"""
