from blockwork.common.registry import RegisteredClass
from blockwork.common.singleton import Singleton

class Config(RegisteredClass, metaclass=Singleton):
    'This is just used point to the modules which register configuration'
    pass
