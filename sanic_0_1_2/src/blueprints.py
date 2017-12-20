class BlueprintSetup:
    """
    这个类的主要作用是：
        - 添加路由
        - 添加exception
        - 添加中间件
    会在Blueprint.make_setup_state中被实例化，以路由为例，会调用Router.add从而添加一个uri与视图函数的映射关系
    """

    def __init__(self, blueprint, app, options):
        self.app = app
        self.blueprint = blueprint
        self.options = options

        url_prefix = self.options.get('url_prefix')
        if url_prefix is None:
            url_prefix = self.blueprint.url_prefix

        #: The prefix that should be used for all URLs defined on the
        #: blueprint.
        self.url_prefix = url_prefix

    def add_route(self, handler, uri, methods):
        """
        A helper method to register a handler to the application url routes.
        """
        if self.url_prefix:
            uri = self.url_prefix + uri

        self.app.router.add(uri, methods, handler)

    def add_exception(self, handler, *args, **kwargs):
        """
        Registers exceptions to sanic
        """
        self.app.exception(*args, **kwargs)(handler)

    def add_middleware(self, middleware, *args, **kwargs):
        """
        Registers middleware to sanic
        """
        if args or kwargs:
            self.app.middleware(*args, **kwargs)(middleware)
        else:
            self.app.middleware(middleware)


class Blueprint:
    def __init__(self, name, url_prefix=None):
        """
        蓝图类
        :param name: 蓝图名称
        :param url_prefix: 该蓝图的url前缀
        """
        self.name = name
        self.url_prefix = url_prefix
        self.deferred_functions = []

    def record(self, func):
        """
        Registers a callback function that is invoked when the blueprint is
        registered on the application.
        """
        self.deferred_functions.append(func)

    def make_setup_state(self, app, options):
        """
        """
        return BlueprintSetup(self, app, options)

    def register(self, app, options):
        """
        """
        state = self.make_setup_state(app, options)
        for deferred in self.deferred_functions:
            deferred(state)

    def route(self, uri, methods=None):
        """
        蓝图路由装饰器
        """
        def decorator(handler):
            self.record(lambda s: s.add_route(handler, uri, methods))
            return handler
        return decorator

    def middleware(self, *args, **kwargs):
        """
        """

        def register_middleware(middleware):
            self.record(lambda s: s.add_middleware(middleware, *args, **kwargs))
            return middleware

        # Detect which way this was called, @middleware or @middleware('AT')
        if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
            args = []
            return register_middleware(args[0])
        else:
            return register_middleware

    def exception(self, *args, **kwargs):
        """
        """
        def decorator(handler):
            self.record(lambda s: s.add_exception(handler, *args, **kwargs))
            return handler
        return decorator
