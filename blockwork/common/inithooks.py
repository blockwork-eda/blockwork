class InitHooks:
    """
    Provides methods for registering pre and post init hooks that
    will run on subclasses even if the subclasses don't call
    `super().__init__(...)`. For example::

        @InitHooks()
        class MyNumberClass:
            @InitHooks.pre
            def init_numbers(): ...
    """
    PRE_ATTR = "_init_hooks_pre_init"
    POST_ATTR = "_init_hooks_post_init"

    def __call__(self, cls_):
        return InitHooks._wrap_cls(cls_)

    @staticmethod
    def _wrap_cls(cls_):
        # Find the pre and post hooks
        pre_hooks = []
        post_hooks = []
        for name in dir(cls_):
            attr=getattr(cls_, name)
            if hasattr(attr, InitHooks.PRE_ATTR):
                pre_hooks.append(attr)
            if hasattr(attr, InitHooks.POST_ATTR):
                post_hooks.append(attr)

        # Replace the init_subclass method with one that wraps
        # the subclasses init method.
        orig_init_subclass = cls_.__init_subclass__
        def __init_subclass__(subcls_, *args, **kwargs):
            orig_init_subclass(*args, **kwargs)
            InitHooks._wrap_subcls(subcls_, pre_hooks, post_hooks)
        cls_.__init_subclass__ = classmethod(__init_subclass__)

        return cls_

    @staticmethod
    def _wrap_subcls(subcls_, pre_hooks, post_hooks):
        # Wrap the subclasses init method with one that
        # runs our hooks.
        orig_init = subcls_.__init__
        def __init__(self, *args, **kwargs):
            for hook in pre_hooks:
                hook(self)
            orig_init(self, *args, **kwargs)
            for hook in post_hooks:
                hook(self)
        subcls_.__init__ = __init__
        return subcls_

    @staticmethod
    def pre(fn):
        "Run this function before `__init__` (class must be decorated with `InitHooks`)"
        setattr(fn, InitHooks.PRE_ATTR, True)
        return fn
    
    @staticmethod
    def post(fn):
        "Run this function after `__init__` (class must be decorated with `InitHooks`)"
        setattr(fn, InitHooks.POST_ATTR, True)
        return fn
