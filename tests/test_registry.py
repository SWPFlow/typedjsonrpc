import json
import pytest
import six

from typedjsonrpc.errors import (InvalidParamsError, InvalidReturnTypeError, InvalidRequestError,
                                 MethodNotFoundError, ParseError)
from typedjsonrpc.registry import Registry


def test_register():
    registry = Registry()

    def foo(x):
        return x
    registry.register("bar", foo)
    assert registry._name_to_method_info["bar"].method == foo


def test_register_class_method():
    registry = Registry()

    class Foo(object):
        def bar(self):
            pass
    baz = Foo()
    with pytest.raises(Exception):
        registry.register("42", baz.bar)


def test_method():
    registry = Registry()

    @registry.method(returns=str, x=str)
    def foo(x):
        return x
    expected_name = "{}.{}".format(foo.__module__, foo.__name__)
    assert registry._name_to_method_info[expected_name].method == foo


def test_method_correct_argtypes():
    registry = Registry()

    @registry.method(returns=str, some_text=str, some_number=int)
    def foo(some_text, some_number):
        return some_text + str(some_number)
    assert foo("Hello", 5) == "Hello5"
    assert foo(some_text="Hello", some_number=5) == "Hello5"
    assert foo("Hello", some_number=5) == "Hello5"
    assert foo(some_number=5, some_text="Hello") == "Hello5"

    @registry.method(returns=str)
    def bar():
        return "Works"
    assert bar() == "Works"

    @registry.method(returns=str, some_text=str, some_number=int)
    def stuff(some_number, some_text):
        return str(some_number) + some_text
    assert stuff(42, "Answer") == "42Answer"


def test_method_args():
    registry = Registry()

    @registry.method(returns=str, some_text=str, some_number=int)
    def foo(some_text, some_number, *args):
        return some_text + str(some_number) + str(args)
    assert foo("Hi", 5, 6, "Test") == "Hi5(6, 'Test')"

    @registry.method(returns=str, some_text=str, some_number=int)
    def bar(some_text, some_number, *args, **kwargs):
        return some_text + str(some_number) + str(args) + str(kwargs)
    assert bar("Hi", 5, "foo", bla=6, stuff="Test") == "Hi5('foo',){'stuff': 'Test', 'bla': 6}"
    with pytest.raises(InvalidParamsError):
        bar("Hi", test=7)


def test_method_defaults():
    registry = Registry()

    @registry.method(returns=str, some_number=int, some_text=str)
    def foo(some_number, some_text="Test"):
        return some_text
    assert foo(5) == "Test"
    assert foo(5, "Hello") == "Hello"


def test_method_wrong_type_declarations():
    registry = Registry()

    with pytest.raises(Exception):
        @registry.method(returns=str, some_text=str, some_number=int)
        def foo(some_text, some_stuff):
            return some_text + some_stuff


def test_method_wrong_argument_order():
    registry = Registry()

    @registry.method(returns=str, some_text=str, some_number=int)
    def foo(some_text, some_number):
        return some_text + str(some_number)
    assert foo("Answer", 42) == "Answer42"
    with pytest.raises(InvalidParamsError):
        foo(42, "Answer")


def test_method_wrong_return_type():
    registry = Registry()

    @registry.method(returns=str, some_number=int)
    def foo(some_number):
        return some_number
    with pytest.raises(InvalidReturnTypeError):
        foo(5)


def test_method_no_return_type():
    registry = Registry()

    with pytest.raises(Exception):
        @registry.method(some_number=int)
        def foo(some_number):
            return some_number


def test_method_return_type_none():
    registry = Registry()

    @registry.method(returns=None)
    def foo():
        pass
    foo()

    @registry.method(returns=type(None))
    def fun():
        pass
    fun()

    @registry.method(returns=type(None), some_text=str)
    def bar(some_text):
        return some_text
    with pytest.raises(InvalidReturnTypeError):
        bar("Hello")

    @registry.method(returns=None, some_number=int)
    def stuff(some_number):
        return 2 * some_number
    with pytest.raises(InvalidReturnTypeError):
        stuff(21)


def test_method_parameter_named_returns():
    registry = Registry()

    with pytest.raises(Exception):
        @registry.method(returns=str, some_number=int)
        def foo(some_number, returns):
            return str(some_number) + returns


class TestDispatch(object):

    @staticmethod
    def assert_error(result, error_id, error_type):
        """
        :type result: str or dict
        :type error_id: int or str
        :type error_type: typedjsonrpc.errors.Error
        """
        if isinstance(result, six.string_types):
            result = json.loads(result)
        assert "jsonrpc" in result and result["jsonrpc"] == "2.0"
        assert "id" in result and result["id"] == error_id
        assert "error" in result and isinstance(result["error"], dict)
        error = result["error"]
        assert "code" in error and error_type.code == error["code"]
        assert "message" in error and error_type.message == error["message"]
        assert "data" in error

    @staticmethod
    def _create_fake_request(data):
        class FakeRequest(object):
            def get_data(self):
                return json.dumps(data)
        return FakeRequest()

    def test_keyword_args(self):
        registry = Registry()

        def add(x, y):
            return x + y
        registry.register("add", add)

        fake_request = self._create_fake_request({
            "jsonrpc": "2.0",
            "method": "add",
            "params": {
                "x": 1,
                "y": 2,
            },
            "id": "bogus",
        })
        response = registry.dispatch(fake_request)
        assert response == json.dumps({
            "jsonrpc": "2.0",
            "id": "bogus",
            "result": 3
        })

    def test_positional_args(self):
        registry = Registry()

        def add(x, y):
            return x + y
        registry.register("add", add)

        fake_request = self._create_fake_request({
            "jsonrpc": "2.0",
            "method": "add",
            "params": [1, 2],
            "id": "bogus",
        })
        response = registry.dispatch(fake_request)
        assert response == json.dumps({
            "jsonrpc": "2.0",
            "id": "bogus",
            "result": 3
        })

    def test_invalid_method(self):
        registry = Registry()

        fake_request = self._create_fake_request({
            "jsonrpc": "2.0",
            "method": "bogus",
            "params": [1, 2],
            "id": "bogus",
        })
        response = registry.dispatch(fake_request)
        TestDispatch.assert_error(response, "bogus", MethodNotFoundError)

    def test_invalid_params(self):
        registry = Registry()

        @registry.method(returns=None)
        def foo():
            pass

        fake_request = self._create_fake_request({
            "jsonrpc": "2.0",
            "method": "test_registry.foo",
            "params": "Hello world",
            "id": 42,
        })
        response = registry.dispatch(fake_request)
        TestDispatch.assert_error(response, 42, InvalidRequestError)

    def test_invalid_request_wrong_jsonrpc(self):
        registry = Registry()

        @registry.method(returns=None)
        def bogus(*args):
            print(args)

        fake_request = self._create_fake_request({
            "jsonrpc": "1.0",
            "method": "test_registry.bogus",
            "params": [1, 2],
            "id": "bogus",
        })
        response = registry.dispatch(fake_request)
        TestDispatch.assert_error(response, "bogus", InvalidRequestError)

    def test_invalid_request_no_method(self):
        registry = Registry()

        fake_request = self._create_fake_request({
            "jsonrpc": "2.0",
            "params": [1, 2],
            "id": "test",
        })
        response = registry.dispatch(fake_request)
        TestDispatch.assert_error(response, "test", InvalidRequestError)

    def test_invalid_request_float_id(self):
        registry = Registry()

        @registry.method(returns=None)
        def bogus(*args):
            print(args)

        fake_request = self._create_fake_request({
            "jsonrpc": "2.0",
            "method": "test_registry.bogus",
            "params": [1, 2],
            "id": 1.0,
        })
        response = registry.dispatch(fake_request)
        TestDispatch.assert_error(response, 1.0, InvalidRequestError)

    def test_invalid_request_no_jsonrpc(self):
        registry = Registry()

        @registry.method(returns=None)
        def bogus(*args):
            print(args)

        fake_request = self._create_fake_request({
            "method": "test_registry.bogus",
            "params": [1, 2],
            "id": "foo",
        })
        response = registry.dispatch(fake_request)
        TestDispatch.assert_error(response, "foo", InvalidRequestError)

    def test_invalid_json(self):
        registry = Registry()

        class FakeRequest(object):
            def get_data(self):
                return '{ "jsonrpc": "2.0", "method":, "id":]'

        fake_request = FakeRequest()
        response = registry.dispatch(fake_request)
        TestDispatch.assert_error(response, None, ParseError)

    def test_id_notification(self):
        registry = Registry()

        @registry.method(returns=int)
        def foo():
            return 42

        fake_request = self._create_fake_request({
            "jsonrpc": "2.0",
            "method": "test_registry.foo",
        })
        assert registry.dispatch(fake_request) is None

    def test_id_int(self):
        registry = Registry()

        @registry.method(returns=int)
        def foo():
            return 42

        fake_request = self._create_fake_request({
            "jsonrpc": "2.0",
            "method": "test_registry.foo",
            "id": 1
        })
        assert json.loads(registry.dispatch(fake_request))["result"] == 42

    def test_id_none(self):
        registry = Registry()

        @registry.method(returns=int)
        def foo():
            return 42

        fake_request = self._create_fake_request({
            "jsonrpc": "2.0",
            "method": "test_registry.foo",
            "id": None
        })
        result = registry.dispatch(fake_request)
        TestDispatch.assert_error(result, None, InvalidRequestError)

    def test_id_list(self):
        registry = Registry()

        @registry.method(returns=int)
        def foo():
            return 42

        fake_request = self._create_fake_request({
            "jsonrpc": "2.0",
            "method": "test_registry.foo",
            "id": [1, 2, 3]
        })
        result = registry.dispatch(fake_request)
        TestDispatch.assert_error(result, [1, 2, 3], InvalidRequestError)

    def test_id_float(self):
        registry = Registry()

        @registry.method(returns=int)
        def foo():
            return 42

        fake_request = self._create_fake_request({
            "jsonrpc": "2.0",
            "method": "test_registry.foo",
            "id": 4.0
        })
        result = registry.dispatch(fake_request)
        TestDispatch.assert_error(result, 4.0, InvalidRequestError)

    def test_error_unknown_id(self):
        registry = Registry()

        @registry.method(returns=int)
        def foo():
            return 42

        fake_request = self._create_fake_request(["foo"])
        result = registry.dispatch(fake_request)
        TestDispatch.assert_error(result, None, InvalidRequestError)

    def test_error_in_function_unknown_id(self):
        registry = Registry()

        @registry.method(returns=int)
        def foo():
            raise Exception()

        fake_request = self._create_fake_request(["foo"])
        result = registry.dispatch(fake_request)
        TestDispatch.assert_error(result, None, InvalidRequestError)

    def test_batched_input(self):
        registry = Registry()

        @registry.method(returns=int, x=int, y=int)
        def add(x, y):
            return x + y

        json_data = [{
            "jsonrpc": "2.0",
            "method": "test_registry.add",
            "params": {
                "x": 1,
                "y": 2,
            },
            "id": 1,
        }, {
            "jsonrpc": "2.0",
            "method": "test_registry.add",
            "params": {
                "x": 2,
                "y": 2,
            },
            "id": 2,
        }]

        fake_request = self._create_fake_request(json_data)
        json_response = registry.dispatch(fake_request)
        response = json.loads(json_response)
        expected_response_by_id = {
            1: {
                "jsonrpc": "2.0",
                "id": 1,
                "result": 3
            },
            2: {
                "jsonrpc": "2.0",
                "id": 2,
                "result": 4
            }
        }
        response_by_id = {msg["id"]: msg for msg in response}
        assert len(response) == len(json_data)
        assert response_by_id == expected_response_by_id

    def test_batched_input_one_failure(self):
        registry = Registry()

        @registry.method(returns=int, x=int, y=int)
        def add(x, y):
            return x + y

        json_data = [{
            "jsonrpc": "2.0",
            "method": "test_registry.add",
            "params": {
                "x": 1,
                "y": 2,
            },
            "id": 1,
        }, {
            "jsonrpc": "2.0",
            "method": "test_registry.add",
            "params": {
                "x": "2",
                "y": 2,
            },
            "id": 2,
        }]

        fake_request = self._create_fake_request(json_data)
        json_response = registry.dispatch(fake_request)
        response = json.loads(json_response)
        expected_response1 = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": 3
        }
        response_by_id = {msg["id"]: msg for msg in response}
        assert len(response) == len(json_data)
        assert response_by_id[1] == expected_response1
        other_response = response_by_id[2]
        assert sorted(other_response.keys()) == ["error", "id", "jsonrpc"]
        TestDispatch.assert_error(other_response, 2, InvalidParamsError)

    def test_batched_input_one_notification(self):
        registry = Registry()

        @registry.method(returns=int, x=int, y=int)
        def add(x, y):
            return x + y

        json_data = [{
            "jsonrpc": "2.0",
            "method": "test_registry.add",
            "params": {
                "x": 1,
                "y": 2,
            },
            "id": 1,
        }, {
            "jsonrpc": "2.0",
            "method": "test_registry.add",
            "params": {
                "x": 2,
                "y": 2,
            },
        }]

        fake_request = self._create_fake_request(json_data)
        json_response = registry.dispatch(fake_request)
        response = json.loads(json_response)
        expected_response_by_id = {
            1: {
                "jsonrpc": "2.0",
                "id": 1,
                "result": 3
            }
        }
        response_by_id = {msg["id"]: msg for msg in response}
        assert len(response) == 1
        assert response_by_id == expected_response_by_id

    def test_batched_input_all_notifications(self):
        registry = Registry()

        @registry.method(returns=int, x=int, y=int)
        def add(x, y):
            return x + y

        json_data = [{
            "jsonrpc": "2.0",
            "method": "test_registry.add",
            "params": {
                "x": 1,
                "y": 2,
            },
        }, {
            "jsonrpc": "2.0",
            "method": "test_registry.add",
            "params": {
                "x": 2,
                "y": 2,
            },
        }]
        fake_request = self._create_fake_request(json_data)
        assert registry.dispatch(fake_request) is None

    def test_batched_input_empty_array(self):
        registry = Registry()

        @registry.method(returns=int, x=int, y=int)
        def add(x, y):
            return x + y

        fake_request = self._create_fake_request([])
        assert registry.dispatch(fake_request) is None


class TestValidateParams(object):
    def test_list(self):
        def foo(a, b, c="baz"):
            pass

        with pytest.raises(InvalidParamsError):
            Registry._validate_params_match(foo, ["foo"])
        Registry._validate_params_match(foo, ["foo", "bar"])

        with pytest.raises(InvalidParamsError):
            Registry._validate_params_match(foo, ["foo", "bar", "bop", 42])

    def test_varargs(self):
        def foo(a, b="foo", *varargs):
            pass

        with pytest.raises(InvalidParamsError):
            Registry._validate_params_match(foo, [])
        Registry._validate_params_match(foo, ["foo", "bar"])
        Registry._validate_params_match(foo, ["foo", "bar", 42])

    def test_dict(self):
        def foo(a, b, c="baz"):
            pass

        with pytest.raises(InvalidParamsError):
            Registry._validate_params_match(foo, {"a": "foo"})
        Registry._validate_params_match(foo, {"a": "foo", "b": "bar"})

        with pytest.raises(InvalidParamsError):
            Registry._validate_params_match(foo, {"a": "foo", "b": "bar", "c": "bop", "d": 42})

        with pytest.raises(InvalidParamsError):
            Registry._validate_params_match(foo, {"a": "foo", "c": "bar"})

    def test_kwargs(self):
        def foo(a, b, c="baz", **kwargs):
            pass

        with pytest.raises(InvalidParamsError):
            Registry._validate_params_match(foo, {"a": "foo"})
        Registry._validate_params_match(foo, {"a": "foo", "b": "bar"})

        Registry._validate_params_match(foo, {"a": "foo", "b": "bar", "d": 42})

        with pytest.raises(InvalidParamsError):
            Registry._validate_params_match(foo, {"a": "foo", "c": "bar"})

    def test_no_defaults(self):
        def foo(a):
            pass
        with pytest.raises(InvalidParamsError):
            Registry._validate_params_match(foo, [])
        Registry._validate_params_match(foo, ["bar"])
        with pytest.raises(InvalidParamsError):
            Registry._validate_params_match(foo, ["bar", "baz"])

        with pytest.raises(InvalidParamsError):
            Registry._validate_params_match(foo, {})
        Registry._validate_params_match(foo, {"a": "bar"})
        with pytest.raises(InvalidParamsError):
            Registry._validate_params_match(foo, {"a": "bar", "b": "baz"})


def test_describe():
    registry = Registry()

    @registry.method(returns=str, x=int, y=str)
    def foo(x, y):
        return str(x) + y
    foo_desc = {'params': [{'type': 'int', 'name': 'x'},
                           {'type': 'str', 'name': 'y'}],
                'name': 'test_registry.foo',
                'returns': 'str',
                'description': None}
    describe_desc = {'params': [],
                     'name': 'rpc.describe',
                     'returns': 'dict',
                     'description': registry.describe.__doc__}
    assert registry.describe()["methods"] == [describe_desc, foo_desc]

    docstring = "This is a test."

    @registry.method(returns=int, a=int, b=int)
    def bar(a, b):
        return a + b
    bar.__doc__ = docstring
    bar_desc = {'params': [{'type': 'int', 'name': 'a'},
                           {'type': 'int', 'name': 'b'}],
                'name': 'test_registry.bar',
                'returns': 'int',
                'description': docstring}
    assert registry.describe()["methods"] == [describe_desc, bar_desc, foo_desc]
