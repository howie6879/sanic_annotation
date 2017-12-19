from sanic_0_1_2.src import Sanic
from sanic_0_1_2.src import Blueprint
from sanic_0_1_2.src.response import json, text

app = Sanic(__name__)
blueprint = Blueprint('name', url_prefix='/my_blueprint')
blueprint2 = Blueprint('name2', url_prefix='/my_blueprint2')


@blueprint.route('/foo')
async def foo(request):
    return json({'msg': 'hi from blueprint'})


@blueprint2.route('/foo')
async def foo2(request):
    return json({'msg': 'hi from blueprint2'})


app.register_blueprint(blueprint)
app.register_blueprint(blueprint2)

app.run(host="0.0.0.0", port=8000, debug=True)
