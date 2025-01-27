# Copyright 2017 Open Source Robotics Foundation, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
from unittest.mock import Mock
import warnings

from rcl_interfaces.msg import FloatingPointRange
from rcl_interfaces.msg import IntegerRange
from rcl_interfaces.msg import ParameterDescriptor
from rcl_interfaces.msg import ParameterType
from rcl_interfaces.msg import ParameterValue
from rcl_interfaces.msg import SetParametersResult
from rcl_interfaces.srv import GetParameters
import rclpy
from rclpy.clock import ClockType
from rclpy.exceptions import InvalidParameterException
from rclpy.exceptions import InvalidParameterValueException
from rclpy.exceptions import InvalidServiceNameException
from rclpy.exceptions import InvalidTopicNameException
from rclpy.exceptions import ParameterAlreadyDeclaredException
from rclpy.exceptions import ParameterImmutableException
from rclpy.exceptions import ParameterNotDeclaredException
from rclpy.executors import SingleThreadedExecutor
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_default
from rclpy.qos import qos_profile_sensor_data
from test_msgs.msg import BasicTypes

TEST_NODE = 'my_node'
TEST_NAMESPACE = '/my_ns'


class TestNodeAllowUndeclaredParameters(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.context = rclpy.context.Context()
        rclpy.init(context=cls.context)
        cls.node = rclpy.create_node(
            TEST_NODE, namespace=TEST_NAMESPACE, context=cls.context,
            allow_undeclared_parameters=True)

    @classmethod
    def tearDownClass(cls):
        cls.node.destroy_node()
        rclpy.shutdown(context=cls.context)

    def test_accessors(self):
        self.assertIsNotNone(self.node.handle)
        with self.assertRaises(AttributeError):
            self.node.handle = 'garbage'
        self.assertEqual(self.node.get_name(), TEST_NODE)
        self.assertEqual(self.node.get_namespace(), TEST_NAMESPACE)
        self.assertEqual(self.node.get_clock().clock_type, ClockType.ROS_TIME)

    def test_create_publisher(self):
        self.node.create_publisher(BasicTypes, 'chatter', 0)
        self.node.create_publisher(BasicTypes, 'chatter', 1)
        self.node.create_publisher(BasicTypes, 'chatter', qos_profile_sensor_data)
        with self.assertRaisesRegex(InvalidTopicNameException, 'must not contain characters'):
            self.node.create_publisher(BasicTypes, 'chatter?', 1)
        with self.assertRaisesRegex(InvalidTopicNameException, 'must not start with a number'):
            self.node.create_publisher(BasicTypes, '/chatter/42_is_the_answer', 1)
        with self.assertRaisesRegex(ValueError, 'unknown substitution'):
            self.node.create_publisher(BasicTypes, 'chatter/{bad_sub}', 1)
        with self.assertRaisesRegex(ValueError, 'must be greater than or equal to zero'):
            self.node.create_publisher(BasicTypes, 'chatter', -1)
        with self.assertRaisesRegex(TypeError, 'Expected QoSProfile or int'):
            self.node.create_publisher(BasicTypes, 'chatter', 'foo')

    def test_create_subscription(self):
        self.node.create_subscription(BasicTypes, 'chatter', lambda msg: print(msg), 0)
        self.node.create_subscription(BasicTypes, 'chatter', lambda msg: print(msg), 1)
        self.node.create_subscription(
            BasicTypes, 'chatter', lambda msg: print(msg), qos_profile_sensor_data)
        with self.assertRaisesRegex(InvalidTopicNameException, 'must not contain characters'):
            self.node.create_subscription(BasicTypes, 'chatter?', lambda msg: print(msg), 1)
        with self.assertRaisesRegex(InvalidTopicNameException, 'must not start with a number'):
            self.node.create_subscription(BasicTypes, '/chatter/42ish', lambda msg: print(msg), 1)
        with self.assertRaisesRegex(ValueError, 'unknown substitution'):
            self.node.create_subscription(BasicTypes, 'foo/{bad_sub}', lambda msg: print(msg), 1)
        with self.assertRaisesRegex(ValueError, 'must be greater than or equal to zero'):
            self.node.create_subscription(BasicTypes, 'chatter', lambda msg: print(msg), -1)
        with self.assertRaisesRegex(TypeError, 'Expected QoSProfile or int'):
            self.node.create_subscription(BasicTypes, 'chatter', lambda msg: print(msg), 'foo')

    def raw_subscription_callback(self, msg):
        print('Raw subscription callback: %s length %d' % (msg, len(msg)))
        self.raw_subscription_msg = msg

    def test_create_raw_subscription(self):
        executor = SingleThreadedExecutor(context=self.context)
        executor.add_node(self.node)
        basic_types_pub = self.node.create_publisher(BasicTypes, 'raw_subscription_test', 1)
        self.raw_subscription_msg = None  # None=No result yet
        self.node.create_subscription(
            BasicTypes,
            'raw_subscription_test',
            self.raw_subscription_callback,
            1,
            raw=True
        )
        basic_types_msg = BasicTypes()
        cycle_count = 0
        while cycle_count < 5 and self.raw_subscription_msg is None:
            basic_types_pub.publish(basic_types_msg)
            cycle_count += 1
            executor.spin_once(timeout_sec=1)
        self.assertIsNotNone(self.raw_subscription_msg, 'raw subscribe timed out')
        self.assertIs(type(self.raw_subscription_msg), bytes, 'raw subscribe did not return bytes')
        # The length might be implementation dependant, but shouldn't be zero
        # There may be a canonical serialization in the future at which point this can be updated
        self.assertNotEqual(len(self.raw_subscription_msg), 0, 'raw subscribe invalid length')

        executor.shutdown()

    def test_create_client(self):
        self.node.create_client(GetParameters, 'get/parameters')
        with self.assertRaisesRegex(InvalidServiceNameException, 'must not contain characters'):
            self.node.create_client(GetParameters, 'get/parameters?')
        with self.assertRaisesRegex(InvalidServiceNameException, 'must not start with a number'):
            self.node.create_client(GetParameters, '/get/42parameters')
        with self.assertRaisesRegex(ValueError, 'unknown substitution'):
            self.node.create_client(GetParameters, 'foo/{bad_sub}')

    def test_create_service(self):
        self.node.create_service(GetParameters, 'get/parameters', lambda req: None)
        with self.assertRaisesRegex(InvalidServiceNameException, 'must not contain characters'):
            self.node.create_service(GetParameters, 'get/parameters?', lambda req: None)
        with self.assertRaisesRegex(InvalidServiceNameException, 'must not start with a number'):
            self.node.create_service(GetParameters, '/get/42parameters', lambda req: None)
        with self.assertRaisesRegex(ValueError, 'unknown substitution'):
            self.node.create_service(GetParameters, 'foo/{bad_sub}', lambda req: None)

    def test_deprecation_warnings(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            self.node.create_publisher(BasicTypes, 'chatter')
            assert len(w) == 1
            assert issubclass(w[0].category, UserWarning)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            self.node.create_publisher(BasicTypes, 'chatter', qos_profile_default)
            assert len(w) == 1
            assert issubclass(w[0].category, UserWarning)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            self.node.create_subscription(BasicTypes, 'chatter', lambda msg: print(msg))
            assert len(w) == 1
            assert issubclass(w[0].category, UserWarning)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            self.node.create_subscription(
                BasicTypes, 'chatter', lambda msg: print(msg), qos_profile_default)
            assert len(w) == 1
            assert issubclass(w[0].category, UserWarning)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            self.node.create_subscription(BasicTypes, 'chatter', lambda msg: print(msg), raw=True)
            assert len(w) == 1
            assert issubclass(w[0].category, UserWarning)

    def test_service_names_and_types(self):
        # test that it doesn't raise
        self.node.get_service_names_and_types()

    def test_service_names_and_types_by_node(self):
        # test that it doesnt raise
        self.node.get_service_names_and_types_by_node(TEST_NODE, TEST_NAMESPACE)

    def test_client_names_and_types_by_node(self):
        # test that it doesnt raise
        self.node.get_client_names_and_types_by_node(TEST_NODE, TEST_NAMESPACE)

    def test_topic_names_and_types(self):
        # test that it doesn't raise
        self.node.get_topic_names_and_types(no_demangle=True)
        self.node.get_topic_names_and_types(no_demangle=False)

    def test_node_names(self):
        # test that it doesn't raise
        self.node.get_node_names()

    def test_node_names_and_namespaces(self):
        # test that it doesn't raise
        self.node.get_node_names_and_namespaces()

    def test_count_publishers_subscribers(self):
        short_topic_name = 'chatter'
        fq_topic_name = '%s/%s' % (TEST_NAMESPACE, short_topic_name)

        self.assertEqual(0, self.node.count_publishers(fq_topic_name))
        self.assertEqual(0, self.node.count_subscribers(fq_topic_name))

        self.node.create_publisher(BasicTypes, short_topic_name, 1)
        self.assertEqual(1, self.node.count_publishers(short_topic_name))
        self.assertEqual(1, self.node.count_publishers(fq_topic_name))

        self.node.create_subscription(BasicTypes, short_topic_name, lambda msg: print(msg), 1)
        self.assertEqual(1, self.node.count_subscribers(short_topic_name))
        self.assertEqual(1, self.node.count_subscribers(fq_topic_name))

        self.node.create_subscription(BasicTypes, short_topic_name, lambda msg: print(msg), 1)
        self.assertEqual(2, self.node.count_subscribers(short_topic_name))
        self.assertEqual(2, self.node.count_subscribers(fq_topic_name))

        # error cases
        with self.assertRaisesRegex(TypeError, 'bad argument type for built-in operation'):
            self.node.count_subscribers(1)
        with self.assertRaisesRegex(ValueError, 'is invalid'):
            self.node.count_subscribers('42')
        with self.assertRaisesRegex(ValueError, 'is invalid'):
            self.node.count_publishers('42')

    def test_node_logger(self):
        node_logger = self.node.get_logger()
        expected_name = '%s.%s' % (TEST_NAMESPACE.replace('/', '.')[1:], TEST_NODE)
        self.assertEqual(node_logger.name, expected_name)
        node_logger.set_level(rclpy.logging.LoggingSeverity.INFO)
        node_logger.debug('test')

    def test_initially_no_executor(self):
        node = rclpy.create_node('my_node', context=self.context)
        try:
            assert node.executor is None
        finally:
            node.destroy_node()

    def test_set_executor_adds_node_to_it(self):
        node = rclpy.create_node('my_node', context=self.context)
        executor = Mock()
        executor.add_node.return_value = True
        try:
            node.executor = executor
            assert id(executor) == id(node.executor)
        finally:
            node.destroy_node()
        executor.add_node.assert_called_once_with(node)

    def test_set_executor_removes_node_from_old_executor(self):
        node = rclpy.create_node('my_node', context=self.context)
        old_executor = Mock()
        old_executor.add_node.return_value = True
        new_executor = Mock()
        new_executor.add_node.return_value = True
        try:
            node.executor = old_executor
            assert id(old_executor) == id(node.executor)
            node.executor = new_executor
            assert id(new_executor) == id(node.executor)
        finally:
            node.destroy_node()
        old_executor.remove_node.assert_called_once_with(node)
        new_executor.remove_node.assert_not_called()

    def test_set_executor_clear_executor(self):
        node = rclpy.create_node('my_node', context=self.context)
        executor = Mock()
        executor.add_node.return_value = True
        try:
            node.executor = executor
            assert id(executor) == id(node.executor)
            node.executor = None
            assert node.executor is None
        finally:
            node.destroy_node()

    def test_node_set_parameters(self):
        results = self.node.set_parameters([
            Parameter('foo', Parameter.Type.INTEGER, 42),
            Parameter('bar', Parameter.Type.STRING, 'hello'),
            Parameter('baz', Parameter.Type.DOUBLE, 2.41)
        ])
        self.assertTrue(all(isinstance(result, SetParametersResult) for result in results))
        self.assertTrue(all(result.successful for result in results))
        self.assertEqual(self.node.get_parameter('foo').value, 42)
        self.assertEqual(self.node.get_parameter('bar').value, 'hello')
        self.assertEqual(self.node.get_parameter('baz').value, 2.41)

    def test_node_cannot_set_invalid_parameters(self):
        with self.assertRaises(TypeError):
            self.node.set_parameters([42])

    def test_node_set_parameters_atomically(self):
        result = self.node.set_parameters_atomically([
            Parameter('foo', Parameter.Type.INTEGER, 42),
            Parameter('bar', Parameter.Type.STRING, 'hello'),
            Parameter('baz', Parameter.Type.DOUBLE, 2.41)
        ])
        self.assertEqual(self.node.get_parameter('foo').value, 42)
        self.assertIsInstance(result, SetParametersResult)
        self.assertTrue(result.successful)

    def test_describe_undeclared_parameter(self):
        self.assertFalse(self.node.has_parameter('foo'))

        descriptor = self.node.describe_parameter('foo')
        self.assertEqual(descriptor, ParameterDescriptor())

    def test_describe_undeclared_parameters(self):
        self.assertFalse(self.node.has_parameter('foo'))
        self.assertFalse(self.node.has_parameter('bar'))

        # Check list.
        descriptor_list = self.node.describe_parameters(['foo', 'bar'])
        self.assertIsInstance(descriptor_list, list)
        self.assertEqual(len(descriptor_list), 2)
        self.assertEqual(descriptor_list[0], ParameterDescriptor())
        self.assertEqual(descriptor_list[1], ParameterDescriptor())

    def test_node_get_parameter(self):
        self.node.set_parameters([Parameter('foo', Parameter.Type.INTEGER, 42)])
        self.assertIsInstance(self.node.get_parameter('foo'), Parameter)
        self.assertEqual(self.node.get_parameter('foo').value, 42)

    def test_node_get_parameter_returns_parameter_not_set(self):
        self.assertIsInstance(self.node.get_parameter('unset'), Parameter)
        self.assertEqual(self.node.get_parameter('unset').type_, Parameter.Type.NOT_SET)

    def test_node_has_parameter_services(self):
        service_names_and_types = self.node.get_service_names_and_types()
        self.assertIn(
            ('/my_ns/my_node/describe_parameters', ['rcl_interfaces/srv/DescribeParameters']),
            service_names_and_types
        )
        self.assertIn(
            ('/my_ns/my_node/get_parameter_types', ['rcl_interfaces/srv/GetParameterTypes']),
            service_names_and_types
        )
        self.assertIn(
            ('/my_ns/my_node/get_parameters', ['rcl_interfaces/srv/GetParameters']),
            service_names_and_types
        )
        self.assertIn(
            ('/my_ns/my_node/list_parameters', ['rcl_interfaces/srv/ListParameters']),
            service_names_and_types
        )
        self.assertIn(
            ('/my_ns/my_node/set_parameters', ['rcl_interfaces/srv/SetParameters']),
            service_names_and_types
        )
        self.assertIn(
            (
                '/my_ns/my_node/set_parameters_atomically',
                ['rcl_interfaces/srv/SetParametersAtomically']
            ), service_names_and_types
        )


class TestNode(unittest.TestCase):

    @classmethod
    def setUp(self):
        self.context = rclpy.context.Context()
        rclpy.init(context=self.context)
        self.node = rclpy.create_node(
            TEST_NODE,
            namespace=TEST_NAMESPACE,
            context=self.context,
            parameter_overrides=[
                Parameter('initial_foo', Parameter.Type.INTEGER, 4321),
                Parameter('initial_bar', Parameter.Type.STRING, 'init_param'),
                Parameter('initial_baz', Parameter.Type.DOUBLE, 3.14)
            ],
            automatically_declare_parameters_from_overrides=False
        )

    @classmethod
    def tearDown(self):
        self.node.destroy_node()
        rclpy.shutdown(context=self.context)

    def test_declare_parameter(self):
        result_initial_foo = self.node.declare_parameter(
            'initial_foo', ParameterValue(), ParameterDescriptor())
        result_foo = self.node.declare_parameter(
            'foo', 42, ParameterDescriptor())
        result_bar = self.node.declare_parameter(
            'bar', 'hello', ParameterDescriptor())
        result_baz = self.node.declare_parameter(
            'baz', 2.41, ParameterDescriptor())
        result_value_not_set = self.node.declare_parameter('value_not_set')

        # OK cases.
        self.assertIsInstance(result_initial_foo, Parameter)
        self.assertIsInstance(result_foo, Parameter)
        self.assertIsInstance(result_bar, Parameter)
        self.assertIsInstance(result_baz, Parameter)
        self.assertIsInstance(result_value_not_set, Parameter)
        self.assertEqual(result_initial_foo.value, 4321)
        self.assertEqual(result_foo.value, 42)
        self.assertEqual(result_bar.value, 'hello')
        self.assertEqual(result_baz.value, 2.41)
        self.assertIsNone(result_value_not_set.value)
        self.assertEqual(self.node.get_parameter('initial_foo').value, 4321)
        self.assertEqual(self.node.get_parameter('foo').value, 42)
        self.assertEqual(self.node.get_parameter('bar').value, 'hello')
        self.assertEqual(self.node.get_parameter('baz').value, 2.41)
        self.assertIsNone(self.node.get_parameter('value_not_set').value)
        self.assertTrue(self.node.has_parameter('value_not_set'))

        # Error cases.
        # TODO(@jubeira): add failing test cases with invalid names once name
        # validation is implemented.
        with self.assertRaises(ParameterAlreadyDeclaredException):
            self.node.declare_parameter(
                'foo', 'raise', ParameterDescriptor())
        with self.assertRaises(InvalidParameterException):
            self.node.declare_parameter(
                '', 'raise', ParameterDescriptor())
        with self.assertRaises(InvalidParameterException):
            self.node.declare_parameter(
                '', 'raise', ParameterDescriptor())

        self.node.set_parameters_callback(self.reject_parameter_callback)
        with self.assertRaises(InvalidParameterValueException):
            self.node.declare_parameter(
                'reject_me', 'raise', ParameterDescriptor())

        with self.assertRaises(TypeError):
            self.node.declare_parameter(
                1,
                'wrong_name_type',
                ParameterDescriptor())

        with self.assertRaises(TypeError):
            self.node.declare_parameter(
                'wrong_parameter_value_type', ParameterValue(), ParameterDescriptor())

        with self.assertRaises(TypeError):
            self.node.declare_parameter(
                'wrong_parameter_descriptor_type', 1, ParameterValue())

    def test_declare_parameters(self):
        parameters = [
            ('foo', 42, ParameterDescriptor()),
            ('bar', 'hello', ParameterDescriptor()),
            ('baz', 2.41),
            ('value_not_set',)
        ]

        result = self.node.declare_parameters('', parameters)

        # OK cases.
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], Parameter)
        self.assertIsInstance(result[1], Parameter)
        self.assertIsInstance(result[2], Parameter)
        self.assertIsInstance(result[3], Parameter)
        self.assertEqual(result[0].value, 42)
        self.assertEqual(result[1].value, 'hello')
        self.assertEqual(result[2].value, 2.41)
        self.assertIsNone(result[3].value)
        self.assertEqual(self.node.get_parameter('foo').value, 42)
        self.assertEqual(self.node.get_parameter('bar').value, 'hello')
        self.assertEqual(self.node.get_parameter('baz').value, 2.41)
        self.assertIsNone(self.node.get_parameter('value_not_set').value)
        self.assertTrue(self.node.has_parameter('value_not_set'))

        result = self.node.declare_parameters('namespace', parameters)

        # OK cases.
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], Parameter)
        self.assertIsInstance(result[1], Parameter)
        self.assertIsInstance(result[2], Parameter)
        self.assertIsInstance(result[3], Parameter)
        self.assertEqual(result[0].value, 42)
        self.assertEqual(result[1].value, 'hello')
        self.assertEqual(result[2].value, 2.41)
        self.assertIsNone(result[3].value)
        self.assertEqual(self.node.get_parameter('namespace.foo').value, 42)
        self.assertEqual(self.node.get_parameter('namespace.bar').value, 'hello')
        self.assertEqual(self.node.get_parameter('namespace.baz').value, 2.41)
        self.assertIsNone(self.node.get_parameter('namespace.value_not_set').value)
        self.assertTrue(self.node.has_parameter('namespace.value_not_set'))

        # Error cases.
        with self.assertRaises(ParameterAlreadyDeclaredException):
            self.node.declare_parameters('', parameters)

        # Declare a new set of parameters; the first one is not already declared,
        # but 2nd and 3rd one are.
        parameters = [
            ('foobar', 43, ParameterDescriptor()),
            ('bar', 'hello', ParameterDescriptor()),
            ('baz', 2.41, ParameterDescriptor()),
        ]
        with self.assertRaises(ParameterAlreadyDeclaredException):
            self.node.declare_parameters('', parameters)

        # Declare a new set; the third one shall fail because of its name.
        parameters = [
            ('foobarbar', 44, ParameterDescriptor()),
            ('barbarbar', 'world', ParameterDescriptor()),
            ('', 2.41, ParameterDescriptor()),
        ]
        with self.assertRaises(InvalidParameterException):
            self.node.declare_parameters('', parameters)

        # Declare a new set; the third one shall be rejected by the callback.
        parameters = [
            ('im_ok', 44, ParameterDescriptor()),
            ('im_also_ok', 'world', ParameterDescriptor()),
            ('reject_me', 2.41, ParameterDescriptor()),
        ]
        self.node.set_parameters_callback(self.reject_parameter_callback)
        with self.assertRaises(InvalidParameterValueException):
            self.node.declare_parameters('', parameters)

        with self.assertRaises(TypeError):
            self.node.declare_parameters(
                '',
                [(
                    1,
                    'wrong_name_type',
                    ParameterDescriptor()
                )]
            )

        with self.assertRaises(TypeError):
            self.node.declare_parameters(
                '',
                [(
                    'wrong_parameter_value_type',
                    ParameterValue(),
                    ParameterDescriptor()
                )]
            )

        with self.assertRaises(TypeError):
            self.node.declare_parameters(
                '',
                [(
                    'wrong_parameter_descriptor_tpye',
                    ParameterValue(),
                    ParameterValue()
                )]
            )

    def reject_parameter_callback(self, parameter_list):
        rejected_parameters = (param for param in parameter_list if 'reject' in param.name)
        return SetParametersResult(successful=(not any(rejected_parameters)))

    def test_node_undeclare_parameter_has_parameter(self):
        # Undeclare unexisting parameter.
        with self.assertRaises(ParameterNotDeclaredException):
            self.node.undeclare_parameter('foo')

        # Verify that it doesn't exist.
        self.assertFalse(self.node.has_parameter('foo'))

        # Declare parameter, verify existance, undeclare, and verify again.
        self.node.declare_parameter(
            'foo',
            'hello',
            ParameterDescriptor()
        )
        self.assertTrue(self.node.has_parameter('foo'))
        self.node.undeclare_parameter('foo')
        self.assertFalse(self.node.has_parameter('foo'))

        # Try with a read only parameter.
        self.assertFalse(self.node.has_parameter('immutable_foo'))
        self.node.declare_parameter(
            'immutable_foo',
            'I am immutable',
            ParameterDescriptor(read_only=True)
        )
        with self.assertRaises(ParameterImmutableException):
            self.node.undeclare_parameter('immutable_foo')

        # Verify that it still exists with the same value.
        self.assertTrue(self.node.has_parameter('immutable_foo'))
        self.assertEqual(self.node.get_parameter('immutable_foo').value, 'I am immutable')

    def test_node_set_undeclared_parameters(self):
        with self.assertRaises(ParameterNotDeclaredException):
            self.node.set_parameters([
                Parameter('foo', Parameter.Type.INTEGER, 42),
                Parameter('bar', Parameter.Type.STRING, 'hello'),
                Parameter('baz', Parameter.Type.DOUBLE, 2.41)
            ])

    def test_node_set_undeclared_parameters_atomically(self):
        with self.assertRaises(ParameterNotDeclaredException):
            self.node.set_parameters_atomically([
                Parameter('foo', Parameter.Type.INTEGER, 42),
                Parameter('bar', Parameter.Type.STRING, 'hello'),
                Parameter('baz', Parameter.Type.DOUBLE, 2.41)
            ])

    def test_node_get_undeclared_parameter(self):
        with self.assertRaises(ParameterNotDeclaredException):
            self.node.get_parameter('initial_foo')

    def test_node_get_undeclared_parameter_or(self):
        result = self.node.get_parameter_or(
            'initial_foo', Parameter('foo', Parameter.Type.INTEGER, 152))
        self.assertEqual(result.name, 'foo')
        self.assertEqual(result.value, 152)

    def test_node_set_parameters(self):
        integer_value = 42
        string_value = 'hello'
        float_value = 2.41
        parameter_tuples = [
            (
                'foo',
                integer_value,
                ParameterDescriptor()
            ),
            (
                'bar',
                string_value,
                ParameterDescriptor()
            ),
            (
                'baz',
                float_value,
                ParameterDescriptor()
            )
        ]

        # Create rclpy.Parameter list from tuples.
        parameters = [
            Parameter(
                name=parameter_tuples[0][0],
                value=integer_value
            ),
            Parameter(
                name=parameter_tuples[1][0],
                value=string_value
            ),
            Parameter(
                name=parameter_tuples[2][0],
                value=float_value
            ),
        ]

        with self.assertRaises(ParameterNotDeclaredException):
            self.node.set_parameters(parameters)

        self.node.declare_parameters('', parameter_tuples)
        result = self.node.set_parameters(parameters)

        # OK cases: check successful result and parameter value for each parameter set.
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], SetParametersResult)
        self.assertIsInstance(result[1], SetParametersResult)
        self.assertIsInstance(result[2], SetParametersResult)
        self.assertTrue(result[0].successful)
        self.assertTrue(result[1].successful)
        self.assertTrue(result[2].successful)
        self.assertEqual(self.node.get_parameter('foo').value, 42)
        self.assertEqual(self.node.get_parameter('bar').value, 'hello')
        self.assertEqual(self.node.get_parameter('baz').value, 2.41)

        # Now we modify the declared parameters, add a new one and set them again.
        integer_value = 24
        string_value = 'bye'
        float_value = 1.42
        extra_value = 2.71
        parameter_tuples.append(
            (
                'foobar',
                extra_value,
                ParameterDescriptor())
            )
        parameters = [
            Parameter(
                name=parameter_tuples[0][0],
                value=integer_value
            ),
            Parameter(
                name=parameter_tuples[1][0],
                value=string_value
            ),
            Parameter(
                name=parameter_tuples[2][0],
                value=float_value
            ),
            Parameter(
                name=parameter_tuples[3][0],
                value=float_value
            ),
        ]
        # The first three parameters should have been set; the fourth one causes the exception.
        with self.assertRaises(ParameterNotDeclaredException):
            self.node.set_parameters(parameters)

        # Validate first three.
        self.assertEqual(self.node.get_parameter('foo').value, 24)
        self.assertEqual(self.node.get_parameter('bar').value, 'bye')
        self.assertEqual(self.node.get_parameter('baz').value, 1.42)

        # Confirm that the fourth one does not exist.
        with self.assertRaises(ParameterNotDeclaredException):
            self.node.get_parameter('foobar')

    def test_node_set_parameters_rejection(self):
        # Declare a new parameter and set a callback so that it's rejected when set.
        reject_parameter_tuple = (
            'reject_me',
            True,
            ParameterDescriptor()
        )

        self.node.declare_parameter(*reject_parameter_tuple)
        self.node.set_parameters_callback(self.reject_parameter_callback)
        result = self.node.set_parameters(
            [
                Parameter(
                    name=reject_parameter_tuple[0],
                    value=reject_parameter_tuple[1]
                )
            ]
        )
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], SetParametersResult)
        self.assertFalse(result[0].successful)

    def test_node_set_parameters_read_only(self):
        integer_value = 42
        string_value = 'hello'
        float_value = 2.41
        parameter_tuples = [
            (
                'immutable_foo',
                integer_value,
                ParameterDescriptor(read_only=True)
            ),
            (
                'bar',
                string_value,
                ParameterDescriptor()
            ),
            (
                'immutable_baz',
                float_value,
                ParameterDescriptor(read_only=True)
            )
        ]

        # Create rclpy.Parameter list from tuples.
        parameters = [
            Parameter(
                name=parameter_tuples[0][0],
                value=integer_value
            ),
            Parameter(
                name=parameter_tuples[1][0],
                value=string_value
            ),
            Parameter(
                name=parameter_tuples[2][0],
                value=float_value
            ),
        ]

        self.node.declare_parameters('', parameter_tuples)

        # Try setting a different value to the declared parameters.
        integer_value = 24
        string_value = 'bye'

        float_value = 1.42

        # Re-create parameters with modified values.
        parameters = [
            Parameter(
                name=parameter_tuples[0][0],
                value=integer_value
            ),
            Parameter(
                name=parameter_tuples[1][0],
                value=string_value
            ),
            Parameter(
                name=parameter_tuples[2][0],
                value=float_value
            ),
        ]

        result = self.node.set_parameters(parameters)

        # Only the parameter that is not read_only should have succeeded.
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], SetParametersResult)
        self.assertIsInstance(result[1], SetParametersResult)
        self.assertIsInstance(result[2], SetParametersResult)
        self.assertFalse(result[0].successful)
        self.assertTrue(result[1].successful)
        self.assertFalse(result[2].successful)
        self.assertEqual(self.node.get_parameter('immutable_foo').value, 42)
        self.assertEqual(self.node.get_parameter('bar').value, 'bye')
        self.assertEqual(self.node.get_parameter('immutable_baz').value, 2.41)

    def test_node_set_parameters_implicit_undeclare(self):
        parameter_tuples = [
            (
                'foo',
                42,
                ParameterDescriptor()
            ),
            (
                'bar',
                'hello',
                ParameterDescriptor()
            ),
            (
                'baz',
                2.41,
                ParameterDescriptor()
            )
        ]

        self.node.declare_parameters('', parameter_tuples)

        # Verify that the parameters are set.
        self.assertEqual(self.node.get_parameter('foo').value, 42)
        self.assertEqual(self.node.get_parameter('bar').value, 'hello')
        self.assertEqual(self.node.get_parameter('baz').value, 2.41)

        # Now undeclare one of them implicitly.
        self.node.set_parameters([Parameter('bar', Parameter.Type.NOT_SET, None)])
        self.assertEqual(self.node.get_parameter('foo').value, 42)
        self.assertFalse(self.node.has_parameter('bar'))
        self.assertEqual(self.node.get_parameter('baz').value, 2.41)

    def test_node_set_parameters_atomically(self):
        integer_value = 42
        string_value = 'hello'
        float_value = 2.41
        parameter_tuples = [
            (
                'foo',
                integer_value,
                ParameterDescriptor()
            ),
            (
                'bar',
                string_value,
                ParameterDescriptor()
            ),
            (
                'baz',
                float_value,
                ParameterDescriptor()
            )
        ]

        # Create rclpy.Parameter list from tuples.
        parameters = [
            Parameter(
                name=parameter_tuples[0][0],
                value=integer_value
            ),
            Parameter(
                name=parameter_tuples[1][0],
                value=string_value
            ),
            Parameter(
                name=parameter_tuples[2][0],
                value=float_value
            ),
        ]

        with self.assertRaises(ParameterNotDeclaredException):
            self.node.set_parameters_atomically(parameters)

        self.node.declare_parameters('', parameter_tuples)
        result = self.node.set_parameters_atomically(parameters)

        # OK case: check successful aggregated result.
        self.assertIsInstance(result, SetParametersResult)
        self.assertTrue(result.successful)
        self.assertEqual(self.node.get_parameter('foo').value, 42)
        self.assertEqual(self.node.get_parameter('bar').value, 'hello')
        self.assertEqual(self.node.get_parameter('baz').value, 2.41)

        # Now we modify the declared parameters, add a new one and set them again.
        integer_value = 24
        string_value = 'bye'
        float_value = 1.42
        extra_value = 2.71
        parameter_tuples.append(
            (
                'foobar',
                extra_value,
                ParameterDescriptor())
            )
        parameters = [
            Parameter(
                name=parameter_tuples[0][0],
                value=integer_value
            ),
            Parameter(
                name=parameter_tuples[1][0],
                value=string_value
            ),
            Parameter(
                name=parameter_tuples[2][0],
                value=float_value
            ),
            Parameter(
                name=parameter_tuples[3][0],
                value=float_value
            ),
        ]

        # The fourth parameter causes the exception, hence none is set.
        with self.assertRaises(ParameterNotDeclaredException):
            self.node.set_parameters_atomically(parameters)

        # Confirm that the first three were not modified.
        self.assertEqual(self.node.get_parameter('foo').value, 42)
        self.assertEqual(self.node.get_parameter('bar').value, 'hello')
        self.assertEqual(self.node.get_parameter('baz').value, 2.41)

        # Confirm that the fourth one does not exist.
        with self.assertRaises(ParameterNotDeclaredException):
            self.node.get_parameter('foobar')

    def test_node_set_parameters_atomically_rejection(self):
        # Declare a new parameter and set a callback so that it's rejected when set.
        reject_parameter_tuple = (
            'reject_me',
            True,
            ParameterDescriptor()
        )

        self.node.declare_parameter(*reject_parameter_tuple)
        self.node.set_parameters_callback(self.reject_parameter_callback)
        result = self.node.set_parameters_atomically(
            [
                Parameter(
                    name=reject_parameter_tuple[0],
                    value=reject_parameter_tuple[1]
                )
            ]
        )
        self.assertIsInstance(result, SetParametersResult)
        self.assertFalse(result.successful)

    def test_node_set_parameters_atomically_read_only(self):
        integer_value = 42
        string_value = 'hello'
        float_value = 2.41
        parameter_tuples = [
            (
                'foo',
                integer_value,
                ParameterDescriptor()
            ),
            (
                'bar',
                string_value,
                ParameterDescriptor()
            ),
            (
                'immutable_baz',
                float_value,
                ParameterDescriptor(read_only=True)
            )
        ]

        # Create rclpy.Parameter list from tuples.
        parameters = [
            Parameter(
                name=parameter_tuples[0][0],
                value=integer_value
            ),
            Parameter(
                name=parameter_tuples[1][0],
                value=string_value
            ),
            Parameter(
                name=parameter_tuples[2][0],
                value=float_value
            ),
        ]

        self.node.declare_parameters('', parameter_tuples)

        # Try setting a different value to the declared parameters.
        integer_value = 24
        string_value = 'bye'
        float_value = 1.42

        parameters = [
            Parameter(
                name=parameter_tuples[0][0],
                value=integer_value
            ),
            Parameter(
                name=parameter_tuples[1][0],
                value=string_value
            ),
            Parameter(
                name=parameter_tuples[2][0],
                value=float_value
            ),
        ]

        result = self.node.set_parameters_atomically(parameters)

        # At least one parameter is read-only, so the overall result should be a failure.
        # All the parameters should have their original value.
        self.assertIsInstance(result, SetParametersResult)
        self.assertFalse(result.successful)
        self.assertEqual(self.node.get_parameter('foo').value, 42)
        self.assertEqual(self.node.get_parameter('bar').value, 'hello')
        self.assertEqual(self.node.get_parameter('immutable_baz').value, 2.41)

    def test_node_set_parameters_atomically_implicit_undeclare(self):
        parameter_tuples = [
            (
                'foo',
                42,
                ParameterDescriptor()
            ),
            (
                'bar',
                'hello',
                ParameterDescriptor()
            ),
            (
                'baz',
                2.41,
                ParameterDescriptor()
            )
        ]

        self.node.declare_parameters('', parameter_tuples)

        # Verify that the parameters are set.
        self.assertEqual(self.node.get_parameter('foo').value, 42)
        self.assertEqual(self.node.get_parameter('bar').value, 'hello')
        self.assertEqual(self.node.get_parameter('baz').value, 2.41)

        # Now undeclare one of them implicitly.
        self.node.set_parameters_atomically([Parameter('bar', Parameter.Type.NOT_SET, None)])
        self.assertEqual(self.node.get_parameter('foo').value, 42)
        self.assertFalse(self.node.has_parameter('bar'))
        self.assertEqual(self.node.get_parameter('baz').value, 2.41)

    def test_describe_parameter(self):
        with self.assertRaises(ParameterNotDeclaredException):
            self.node.describe_parameter('foo')

        # Declare parameter with descriptor.
        self.node.declare_parameter(
            'foo',
            'hello',
            ParameterDescriptor(
                name='foo',
                type=ParameterType.PARAMETER_STRING,
                additional_constraints='some constraints',
                read_only=True,
                floating_point_range=[FloatingPointRange(from_value=-2.0, to_value=2.0, step=0.1)],
                integer_range=[IntegerRange(from_value=-10, to_value=10, step=2)]
            )
        )

        descriptor = self.node.describe_parameter('foo')
        self.assertEqual(descriptor.name, 'foo')
        self.assertEqual(descriptor.type, ParameterType.PARAMETER_STRING)
        self.assertEqual(descriptor.additional_constraints, 'some constraints')
        self.assertEqual(descriptor.read_only, True)
        self.assertEqual(descriptor.floating_point_range[0].from_value, -2.0)
        self.assertEqual(descriptor.floating_point_range[0].to_value, 2.0)
        self.assertEqual(descriptor.floating_point_range[0].step, 0.1)
        self.assertEqual(descriptor.integer_range[0].from_value, -10)
        self.assertEqual(descriptor.integer_range[0].to_value, 10)
        self.assertEqual(descriptor.integer_range[0].step, 2)

    def test_describe_parameters(self):
        with self.assertRaises(ParameterNotDeclaredException):
            self.node.describe_parameter('foo')
        with self.assertRaises(ParameterNotDeclaredException):
            self.node.describe_parameter('bar')

        # Declare parameters with descriptors.
        self.node.declare_parameter(
            'foo',
            'hello',
            ParameterDescriptor(
                name='foo',
                type=ParameterType.PARAMETER_STRING,
                additional_constraints='some constraints',
                read_only=True,
                floating_point_range=[FloatingPointRange(from_value=-2.0, to_value=2.0, step=0.1)],
                integer_range=[IntegerRange(from_value=-10, to_value=10, step=2)]
            )
        )
        self.node.declare_parameter(
            'bar',
            10,
            ParameterDescriptor(
                name='bar',
                type=ParameterType.PARAMETER_DOUBLE,
                additional_constraints='some more constraints',
                read_only=True,
                floating_point_range=[FloatingPointRange(from_value=-3.0, to_value=3.0, step=0.3)],
                integer_range=[IntegerRange(from_value=-20, to_value=20, step=3)]
            )
        )

        # Check list.
        descriptor_list = self.node.describe_parameters(['foo', 'bar'])
        self.assertIsInstance(descriptor_list, list)
        self.assertEqual(len(descriptor_list), 2)

        # Check individual descriptors.
        foo_descriptor = descriptor_list[0]
        self.assertEqual(foo_descriptor.name, 'foo')
        self.assertEqual(foo_descriptor.type, ParameterType.PARAMETER_STRING)
        self.assertEqual(foo_descriptor.additional_constraints, 'some constraints')
        self.assertEqual(foo_descriptor.read_only, True)
        self.assertEqual(foo_descriptor.floating_point_range[0].from_value, -2.0)
        self.assertEqual(foo_descriptor.floating_point_range[0].to_value, 2.0)
        self.assertEqual(foo_descriptor.floating_point_range[0].step, 0.1)
        self.assertEqual(foo_descriptor.integer_range[0].from_value, -10)
        self.assertEqual(foo_descriptor.integer_range[0].to_value, 10)
        self.assertEqual(foo_descriptor.integer_range[0].step, 2)

        # The descriptor gets the type of the parameter.
        bar_descriptor = descriptor_list[1]
        self.assertEqual(bar_descriptor.name, 'bar')
        self.assertEqual(bar_descriptor.type, ParameterType.PARAMETER_INTEGER)
        self.assertEqual(bar_descriptor.additional_constraints, 'some more constraints')
        self.assertEqual(bar_descriptor.read_only, True)
        self.assertEqual(bar_descriptor.floating_point_range[0].from_value, -3.0)
        self.assertEqual(bar_descriptor.floating_point_range[0].to_value, 3.0)
        self.assertEqual(bar_descriptor.floating_point_range[0].step, 0.3)
        self.assertEqual(bar_descriptor.integer_range[0].from_value, -20)
        self.assertEqual(bar_descriptor.integer_range[0].to_value, 20)
        self.assertEqual(bar_descriptor.integer_range[0].step, 3)

    def test_set_descriptor(self):
        with self.assertRaises(ParameterNotDeclaredException):
            self.node.set_descriptor('foo', ParameterDescriptor())

        # Declare parameter with default descriptor.
        # The name and type of the stored descriptor shall match the parameter,
        self.node.declare_parameter(
            'foo',
            'hello',
            ParameterDescriptor()
        )
        self.assertEqual(
            self.node.describe_parameter('foo'),
            ParameterDescriptor(name='foo', type=Parameter.Type.STRING.value)
        )

        # Now modify the descriptor and check again.
        value = self.node.set_descriptor(
            'foo',
            ParameterDescriptor(
                name='this will be ignored',
                type=ParameterType.PARAMETER_INTEGER,  # Type will be ignored too.
                additional_constraints='some constraints',
                read_only=False,
                integer_range=[IntegerRange(from_value=-10, to_value=10, step=2)]
            )
        )
        self.assertEqual(value.type, Parameter.Type.STRING.value)
        self.assertEqual(value.string_value, 'hello')

        # Name and type will match the parameter, not the given descriptor.
        descriptor = self.node.describe_parameter('foo')
        self.assertEqual(descriptor.name, 'foo')
        self.assertEqual(descriptor.type, ParameterType.PARAMETER_STRING)
        self.assertEqual(descriptor.additional_constraints, 'some constraints')
        self.assertEqual(descriptor.read_only, False)
        self.assertEqual(descriptor.integer_range[0].from_value, -10)
        self.assertEqual(descriptor.integer_range[0].to_value, 10)
        self.assertEqual(descriptor.integer_range[0].step, 2)

        # A descriptor that is not read-only can be replaced by a read-only one.
        value = self.node.set_descriptor(
            'foo',
            ParameterDescriptor(
                name='bar',
                type=ParameterType.PARAMETER_STRING,
                additional_constraints='some more constraints',
                read_only=True,
                floating_point_range=[FloatingPointRange(from_value=-2.0, to_value=2.0, step=0.1)],
            )
        )
        self.assertEqual(value.type, Parameter.Type.STRING.value)
        self.assertEqual(value.string_value, 'hello')

        descriptor = self.node.describe_parameter('foo')
        self.assertEqual(descriptor.name, 'foo')
        self.assertEqual(descriptor.type, ParameterType.PARAMETER_STRING)
        self.assertEqual(descriptor.additional_constraints, 'some more constraints')
        self.assertEqual(descriptor.read_only, True)
        self.assertEqual(descriptor.floating_point_range[0].from_value, -2.0)
        self.assertEqual(descriptor.floating_point_range[0].to_value, 2.0)
        self.assertEqual(descriptor.floating_point_range[0].step, 0.1)

    def test_set_descriptor_read_only(self):
        with self.assertRaises(ParameterNotDeclaredException):
            self.node.set_descriptor('foo', ParameterDescriptor())

        # Declare parameter with a read_only descriptor.
        self.node.declare_parameter(
            'foo',
            'hello',
            ParameterDescriptor(read_only=True)
        )
        self.assertEqual(
            self.node.describe_parameter('foo'),
            ParameterDescriptor(name='foo', type=Parameter.Type.STRING.value, read_only=True)
        )

        # Try modifying the descriptor.
        with self.assertRaises(ParameterImmutableException):
            self.node.set_descriptor(
                'foo',
                ParameterDescriptor(
                    name='foo',
                    type=ParameterType.PARAMETER_STRING,
                    additional_constraints='some constraints',
                    read_only=False,
                )
            )

    def test_floating_point_range_descriptor(self):
        # OK cases; non-floats are not affected by the range.
        fp_range = FloatingPointRange(from_value=0.0, to_value=10.0, step=0.5)
        parameters = [
            ('from_value', 0.0, ParameterDescriptor(floating_point_range=[fp_range])),
            ('to_value', 10.0, ParameterDescriptor(floating_point_range=[fp_range])),
            ('in_range', 4.5, ParameterDescriptor(floating_point_range=[fp_range])),
            ('str_value', 'I am no float', ParameterDescriptor(floating_point_range=[fp_range])),
            ('int_value', 123, ParameterDescriptor(floating_point_range=[fp_range]))
        ]

        result = self.node.declare_parameters('', parameters)

        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], Parameter)
        self.assertIsInstance(result[1], Parameter)
        self.assertIsInstance(result[2], Parameter)
        self.assertIsInstance(result[3], Parameter)
        self.assertIsInstance(result[4], Parameter)
        self.assertAlmostEqual(result[0].value, 0.0)
        self.assertAlmostEqual(result[1].value, 10.0)
        self.assertAlmostEqual(result[2].value, 4.5)
        self.assertEqual(result[3].value, 'I am no float')
        self.assertEqual(result[4].value, 123)
        self.assertEqual(self.node.get_parameter('from_value').value, 0.0)
        self.assertEqual(self.node.get_parameter('to_value').value, 10.0)
        self.assertEqual(self.node.get_parameter('in_range').value, 4.5)
        self.assertEqual(self.node.get_parameter('str_value').value, 'I am no float')
        self.assertAlmostEqual(self.node.get_parameter('int_value').value, 123)

        # Try to set a parameter out of range.
        result = self.node.set_parameters([Parameter('in_range', value=12.0)])
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], SetParametersResult)
        self.assertFalse(result[0].successful)
        self.assertEqual(self.node.get_parameter('in_range').value, 4.5)

        # Try to set a parameter out of range (bad step).
        result = self.node.set_parameters([Parameter('in_range', value=4.25)])
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], SetParametersResult)
        self.assertFalse(result[0].successful)
        self.assertEqual(self.node.get_parameter('in_range').value, 4.5)

        # Change in_range parameter to int; ranges will not apply.
        result = self.node.set_parameters([Parameter('in_range', value=12)])
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], SetParametersResult)
        self.assertTrue(result[0].successful)
        self.assertEqual(self.node.get_parameter('in_range').value, 12)

        # From and to are always valid.
        # Parameters that don't comply with the description will raise an exception.
        fp_range = FloatingPointRange(from_value=-10.0, to_value=0.0, step=30.0)
        parameters = [
            ('from_value_2', -10.0, ParameterDescriptor(floating_point_range=[fp_range])),
            ('to_value_2', 0.0, ParameterDescriptor(floating_point_range=[fp_range])),
            ('in_range_bad_step', -4.5, ParameterDescriptor(floating_point_range=[fp_range])),
            ('out_of_range', 30.0, ParameterDescriptor(floating_point_range=[fp_range]))
        ]
        with self.assertRaises(InvalidParameterValueException):
            self.node.declare_parameters('', parameters)

        self.assertAlmostEqual(self.node.get_parameter('from_value_2').value, -10.0)
        self.assertAlmostEqual(self.node.get_parameter('to_value_2').value, 0.0)
        self.assertFalse(self.node.has_parameter('in_range_bad_step'))
        self.assertFalse(self.node.has_parameter('out_of_range'))

        # Try some more parameters with no step.
        fp_range = FloatingPointRange(from_value=-10.0, to_value=10.0, step=0.0)
        parameters = [
            ('from_value_no_step', -10.0, ParameterDescriptor(floating_point_range=[fp_range])),
            ('to_value_no_step', 10.0, ParameterDescriptor(floating_point_range=[fp_range])),
            ('in_range_no_step', 5.37, ParameterDescriptor(floating_point_range=[fp_range])),
        ]

        result = self.node.declare_parameters('', parameters)

        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], Parameter)
        self.assertIsInstance(result[1], Parameter)
        self.assertIsInstance(result[2], Parameter)
        self.assertAlmostEqual(result[0].value, -10.0)
        self.assertAlmostEqual(result[1].value, 10.0)
        self.assertAlmostEqual(result[2].value, 5.37)
        self.assertAlmostEqual(self.node.get_parameter('from_value_no_step').value, -10.0)
        self.assertAlmostEqual(self.node.get_parameter('to_value_no_step').value, 10.0)
        self.assertAlmostEqual(self.node.get_parameter('in_range_no_step').value, 5.37)

    def test_integer_range_descriptor(self):
        # OK cases; non-integers are not affected by the range.
        integer_range = IntegerRange(from_value=0, to_value=10, step=2)
        parameters = [
            ('from_value', 0, ParameterDescriptor(integer_range=[integer_range])),
            ('to_value', 10, ParameterDescriptor(integer_range=[integer_range])),
            ('in_range', 4, ParameterDescriptor(integer_range=[integer_range])),
            ('str_value', 'I am no integer', ParameterDescriptor(integer_range=[integer_range])),
            ('float_value', 123.0, ParameterDescriptor(integer_range=[integer_range]))
        ]

        result = self.node.declare_parameters('', parameters)

        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], Parameter)
        self.assertIsInstance(result[1], Parameter)
        self.assertIsInstance(result[2], Parameter)
        self.assertIsInstance(result[3], Parameter)
        self.assertIsInstance(result[4], Parameter)
        self.assertEqual(result[0].value, 0)
        self.assertEqual(result[1].value, 10)
        self.assertEqual(result[2].value, 4)
        self.assertEqual(result[3].value, 'I am no integer')
        self.assertAlmostEqual(result[4].value, 123.0)
        self.assertEqual(self.node.get_parameter('from_value').value, 0)
        self.assertEqual(self.node.get_parameter('to_value').value, 10)
        self.assertEqual(self.node.get_parameter('in_range').value, 4)
        self.assertEqual(self.node.get_parameter('str_value').value, 'I am no integer')
        self.assertAlmostEqual(self.node.get_parameter('float_value').value, 123.0)

        # Try to set a parameter out of range.
        result = self.node.set_parameters([Parameter('in_range', value=12)])
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], SetParametersResult)
        self.assertFalse(result[0].successful)
        self.assertEqual(self.node.get_parameter('in_range').value, 4)

        # Try to set a parameter out of range (bad step).
        result = self.node.set_parameters([Parameter('in_range', value=5)])
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], SetParametersResult)
        self.assertFalse(result[0].successful)
        self.assertEqual(self.node.get_parameter('in_range').value, 4)

        # Change in_range parameter to a float; ranges will not apply.
        result = self.node.set_parameters([Parameter('in_range', value=12.0)])
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], SetParametersResult)
        self.assertTrue(result[0].successful)
        self.assertAlmostEqual(self.node.get_parameter('in_range').value, 12.0)

        # From and to are always valid.
        # Parameters that don't comply with the description will raise an exception.
        integer_range = IntegerRange(from_value=-10, to_value=0, step=30)
        parameters = [
            ('from_value_2', -10, ParameterDescriptor(integer_range=[integer_range])),
            ('to_value_2', 0, ParameterDescriptor(integer_range=[integer_range])),
            ('in_range_bad_step', -4, ParameterDescriptor(integer_range=[integer_range])),
            ('out_of_range', 30, ParameterDescriptor(integer_range=[integer_range]))
        ]
        with self.assertRaises(InvalidParameterValueException):
            self.node.declare_parameters('', parameters)

        self.assertEqual(self.node.get_parameter('from_value_2').value, -10)
        self.assertEqual(self.node.get_parameter('to_value_2').value, 0)
        self.assertFalse(self.node.has_parameter('in_range_bad_step'))
        self.assertFalse(self.node.has_parameter('out_of_range'))

        # Try some more parameters with no step.
        integer_range = IntegerRange(from_value=-10, to_value=10, step=0)
        parameters = [
            ('from_value_no_step', -10, ParameterDescriptor(integer_range=[integer_range])),
            ('to_value_no_step', 10, ParameterDescriptor(integer_range=[integer_range])),
            ('in_range_no_step', 5, ParameterDescriptor(integer_range=[integer_range])),
        ]

        result = self.node.declare_parameters('', parameters)

        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], Parameter)
        self.assertIsInstance(result[1], Parameter)
        self.assertIsInstance(result[2], Parameter)
        self.assertEqual(result[0].value, -10)
        self.assertEqual(result[1].value, 10)
        self.assertEqual(result[2].value, 5)
        self.assertEqual(self.node.get_parameter('from_value_no_step').value, -10)
        self.assertEqual(self.node.get_parameter('to_value_no_step').value, 10)
        self.assertEqual(self.node.get_parameter('in_range_no_step').value, 5)


class TestCreateNode(unittest.TestCase):

    def test_use_global_arguments(self):
        context = rclpy.context.Context()
        rclpy.init(args=['process_name', '__node:=global_node_name'], context=context)
        try:
            node1 = rclpy.create_node(
                'my_node', namespace='/my_ns', use_global_arguments=True, context=context)
            node2 = rclpy.create_node(
                'my_node', namespace='/my_ns', use_global_arguments=False, context=context)
            self.assertEqual('global_node_name', node1.get_name())
            self.assertEqual('my_node', node2.get_name())
            node1.destroy_node()
            node2.destroy_node()
        finally:
            rclpy.shutdown(context=context)

    def test_node_arguments(self):
        context = rclpy.context.Context()
        rclpy.init(context=context)
        try:
            node = rclpy.create_node(
                'my_node', namespace='/my_ns', cli_args=['__ns:=/foo/bar'], context=context)
            self.assertEqual('/foo/bar', node.get_namespace())
            node.destroy_node()
        finally:
            rclpy.shutdown(context=context)


if __name__ == '__main__':
    unittest.main()
