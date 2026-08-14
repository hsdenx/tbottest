"""
Unit tests for the _Singleton metaclass in tbottest/initconfig.py.

IniTBotConfig/IniConfig themselves can't be constructed here (their
class bodies resolve a real board environment at import time), so
these tests extract _Singleton's actual, current source out of
initconfig.py (see conftest.load_definition) and exercise it against
small throwaway classes -- which is exactly how IniTBotConfig/
IniConfig use it.
"""

import gc
import os

from conftest import load_definition

INITCONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "tbottest", "initconfig.py"
)

initconfig = load_definition(
    "tbottest_initconfig_singleton_metaclass_only",
    INITCONFIG_PATH,
    "_Singleton",
    extra_src="import typing",
)


class TestSingleton:
    def test_repeated_construction_returns_identical_instance(self):
        class Cfg(metaclass=initconfig._Singleton):
            def __init__(self):
                self.value = object()

        a = Cfg()
        b = Cfg()
        assert a is b

    def test_init_runs_exactly_once(self):
        calls = []

        class Cfg(metaclass=initconfig._Singleton):
            def __init__(self):
                calls.append(1)

        for _ in range(5):
            Cfg()
        assert len(calls) == 1

    def test_different_classes_get_independent_singletons(self):
        class A(metaclass=initconfig._Singleton):
            pass

        class B(metaclass=initconfig._Singleton):
            pass

        assert A() is A()
        assert B() is B()
        assert A() is not B()

    def test_repeated_calls_do_not_leak_instances(self):
        """
        Regression test for the bug that motivated the singleton:
        with the old weakref.finalize(self, self.cleanup) pattern
        (a bound method holding a strong ref back to self), every
        call created a new, never-collected instance. With the
        singleton, repeated calls must not accumulate live objects.
        """

        class Cfg(metaclass=initconfig._Singleton):
            pass

        gc.collect()
        before = sum(1 for o in gc.get_objects() if isinstance(o, Cfg))
        for _ in range(50):
            Cfg()
        gc.collect()
        after = sum(1 for o in gc.get_objects() if isinstance(o, Cfg))
        assert after - before == 1
