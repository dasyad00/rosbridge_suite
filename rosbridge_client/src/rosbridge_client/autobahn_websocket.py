import rospy

from rosauth.srv import Authentication

import sys
import threading
import traceback
from functools import wraps
from collections import deque

from autobahn.twisted.websocket import WebSocketClientProtocol
from twisted.internet import interfaces, reactor
from zope.interface import implementer

from rosbridge_library.rosbridge_protocol import RosbridgeProtocol
from rosbridge_library.util import json, bson


# directly copied from rosbridge_server/autobahn_websocket.py
def _log_exception():
    """Log the most recent exception to ROS."""
    exc = traceback.format_exception(*sys.exc_info())
    rospy.logerr(''.join(exc))


def log_exceptions(f):
    """Decorator for logging exceptions to ROS."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except:
            _log_exception()
            raise

    return wrapper


class IncomingQueue(threading.Thread):
    """Decouples incoming messages from the Autobahn thread.

    This mitigates cases where outgoing messages are blocked by incoming,
    and vice versa.
    """

    def __init__(self, protocol):
        threading.Thread.__init__(self)
        self.daemon = True
        self.queue = deque()
        self.protocol = protocol

        self.cond = threading.Condition()
        self._finished = False

    def finish(self):
        """Clear the queue and do not accept further messages."""
        with self.cond:
            self._finished = True
            while len(self.queue) > 0:
                self.queue.popleft()
            self.cond.notify()

    def push(self, msg):
        with self.cond:
            self.queue.append(msg)
            self.cond.notify()

    def run(self):
        while True:
            with self.cond:
                if len(self.queue) == 0 and not self._finished:
                    self.cond.wait()

                if self._finished:
                    break

                msg = self.queue.popleft()

            self.protocol.incoming(msg)

        self.protocol.finish()


@implementer(interfaces.IPushProducer)
class OutgoingValve:
    """Allows the Autobahn transport to pause outgoing messages from rosbridge.

    The purpose of this valve is to connect backpressure from the WebSocket client
    back to the rosbridge protocol, which depends on backpressure for queueing.
    Without this flow control, rosbridge will happily keep writing messages to
    the WebSocket until the system runs out of memory.

    This valve is closed and opened automatically by the Twisted TCP server.
    In practice, Twisted should only close the valve when its userspace write buffer
    is full and it should only open the valve when that buffer is empty.

    When the valve is closed, the rosbridge protocol instance's outgoing writes
    must block until the valve is opened.
    """

    def __init__(self, proto):
        self._proto = proto
        self._valve = threading.Event()
        self._finished = False

    @log_exceptions
    def relay(self, message):
        self._valve.wait()
        if self._finished:
            return
        reactor.callFromThread(self._proto.outgoing, message)

    def pauseProducing(self):
        if not self._finished:
            self._valve.clear()

    def resumeProducing(self):
        self._valve.set()

    def stopProducing(self):
        self._finished = True
        self._valve.set()


# end of direct copy from rosbridge_server/autobahn_websocket.py


class RosbridgeWebSocket(WebSocketClientProtocol):
    authenticate = False

    # The following are passed on to RosbridgeProtocol
    # defragmentation.py:
    fragment_timeout = 600  # seconds
    # protocol.py:
    delay_between_messages = 0  # seconds
    max_message_size = None  # bytes
    unregister_timeout = 10.0  # seconds
    bson_only_mode = False

    def onOpen(self):
        cls = self.__class__
        try:
            self.protocol = RosbridgeProtocol(
                client_id=0,
                parameters=self.get_parameters()
            )
            self.incoming_queue = IncomingQueue(self.protocol)
            self.incoming_queue.start()
            producer = OutgoingValve(self)
            self.transport.outgoing = producer.relay
            self.authenticated = False
            self.target = self.transport.getPeer().host
            rospy.loginfo("Client connected to {}".format(self.target))
        except Exception as exc:
            rospy.logerr("Unable to accept incoming connection.  Reason: %s", str(exc))
        if cls.authenticate:
            rospy.loginfo("Awaiting proper authentication...")

    def onMessage(self, message, binary):
        cls = self.__class__
        if not binary:
            message = message.decode('utf-8')
        # check if we need to authenticate
        if cls.authenticate and not self.authenticated:
            try:
                if cls.bson_only_mode:
                    msg = bson.BSON(message).decode()
                else:
                    msg = json.loads(message)

                if msg['op'] == 'auth':
                    # check the authorization information
                    auth_srv = rospy.ServiceProxy('authenticate', Authentication)
                    resp = auth_srv(
                        msg['mac'], msg['client'], msg['dest'],
                        msg['rand'], rospy.Time(msg['t']),
                        msg['level'], rospy.Time(msg['end'])
                    )
                    self.authenticated = resp.authenticated
                    if self.authenticated:
                        rospy.loginfo("Client has authenticated.")
                        return

                # if we are here, no valid authentication was given
                rospy.logwarn("Client %d did not authenticate. Closing connection.",
                              self.protocol.client_id)
                self.sendClose()
            except:
                # proper error will be handled in the protocol class
                self.incoming_queue.push(message)
        else:
            # no authentication required
            self.incoming_queue.push(message)

    def outgoing(self, message):
        if type(message) == bson.BSON:
            binary = True
            message = bytes(message)
        elif type(message) == bytearray:
            binary = True
            message = bytes(message)
        else:
            binary = False
            message = message.encode('utf-8')

        self.sendMessage(message, binary)

    def onClose(self, was_clean, code, reason):
        rospy.loginfo("Client disconnected. {}. code={}".format(reason, code))
        if not hasattr(self, 'protocol'):
            return  # Closed before connection was opened.

        self.incoming_queue.finish()
        # TODO
        # rospy.signal_shutdown(reason)

    @classmethod
    def get_parameters(cls):
        return {
            "fragment_timeout": cls.fragment_timeout,
            "delay_between_messages": cls.delay_between_messages,
            "max_message_size": cls.max_message_size,
            "unregister_timeout": cls.unregister_timeout,
            "bson_only_mode": cls.bson_only_mode
        }
