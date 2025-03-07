#!/usr/bin/env python
import sys
import rospy

from autobahn.twisted.websocket import WebSocketClientFactory, connectWS
from twisted.internet import reactor, ssl
from twisted.internet.error import ReactorNotRunning
from autobahn.websocket.compress import (PerMessageDeflateOffer, PerMessageDeflateOfferAccept)

from rosbridge_client.autobahn_websocket import RosbridgeWebSocket

from rosbridge_library.capabilities.advertise import Advertise
from rosbridge_library.capabilities.publish import Publish
from rosbridge_library.capabilities.subscribe import Subscribe
from rosbridge_library.capabilities.advertise_service import AdvertiseService
from rosbridge_library.capabilities.unadvertise_service import UnadvertiseService
from rosbridge_library.capabilities.call_service import CallService


def shutdown_hook():
    try:
        reactor.stop()
    except ReactorNotRunning:
        rospy.logwarn("Can't stop the reactor, it wasn't running")


if __name__ == "__main__":
    rospy.init_node("rosbridge_websocket_client")

    ##################################################
    # Parameter handling                             #
    ##################################################
    retry_startup_delay = rospy.get_param('~retry_startup_delay', 2.0)  # seconds

    use_compression = rospy.get_param('~use_compression', False)

    # RosbridgeProtocol parameters
    RosbridgeWebSocket.fragment_timeout = rospy.get_param(
        '~fragment_timeout', RosbridgeWebSocket.fragment_timeout
    )
    RosbridgeWebSocket.delay_between_messages = rospy.get_param(
        '~delay_between_messages', RosbridgeWebSocket.delay_between_messages
    )
    RosbridgeWebSocket.max_message_size = rospy.get_param(
        '~max_message_size', RosbridgeWebSocket.max_message_size
    )
    RosbridgeWebSocket.unregister_timeout = rospy.get_param(
        '~unregister_timeout', RosbridgeWebSocket.unregister_timeout
    )
    bson_only_mode = rospy.get_param('~bson_only_mode', False)

    if RosbridgeWebSocket.max_message_size == "None":
        RosbridgeWebSocket.max_message_size = None

    ping_interval = float(rospy.get_param('~websocket_ping_interval', 0))
    ping_timeout = float(rospy.get_param('~websocket_ping_timeout', 30))

    # SSL options
    certfile = rospy.get_param('~certfile', None)
    keyfile = rospy.get_param('~keyfile', None)
    # if authentication should be used
    RosbridgeWebSocket.authenticate = rospy.get_param('~authenticate', False)

    # target port and address should be defined in the launch file!
    port = rospy.get_param('~port')
    address = rospy.get_param('~address')
    endpoint = rospy.get_param('~endpoint', "/")

    # Get the glob strings and parse them as arrays.
    RosbridgeWebSocket.topics_glob = [
        element.strip().strip("'")
        for element in rospy.get_param('~topics_glob', '')[1:-1].split(',')
        if len(element.strip().strip("'")) > 0]
    RosbridgeWebSocket.services_glob = [
        element.strip().strip("'")
        for element in rospy.get_param('~services_glob', '')[1:-1].split(',')
        if len(element.strip().strip("'")) > 0]
    RosbridgeWebSocket.params_glob = [
        element.strip().strip("'")
        for element in rospy.get_param('~params_glob', '')[1:-1].split(',')
        if len(element.strip().strip("'")) > 0]

    if "--port" in sys.argv:
        idx = sys.argv.index("--port") + 1
        if idx < len(sys.argv):
            port = int(sys.argv[idx])
        else:
            print("--port argument provided without a value.")
            sys.exit(-1)

    if "--address" in sys.argv:
        idx = sys.argv.index("--address") + 1
        if idx < len(sys.argv):
            address = str(sys.argv[idx])
        else:
            print("--address argument provided without a value.")
            sys.exit(-1)

    if "--retry_startup_delay" in sys.argv:
        idx = sys.argv.index("--retry_startup_delay") + 1
        if idx < len(sys.argv):
            retry_startup_delay = int(sys.argv[idx])
        else:
            print("--retry_startup_delay argument provided without a value.")
            sys.exit(-1)

    if "--fragment_timeout" in sys.argv:
        idx = sys.argv.index("--fragment_timeout") + 1
        if idx < len(sys.argv):
            RosbridgeWebSocket.fragment_timeout = int(sys.argv[idx])
        else:
            print("--fragment_timeout argument provided without a value.")
            sys.exit(-1)

    if "--delay_between_messages" in sys.argv:
        idx = sys.argv.index("--delay_between_messages") + 1
        if idx < len(sys.argv):
            RosbridgeWebSocket.delay_between_messages = float(sys.argv[idx])
        else:
            print("--delay_between_messages argument provided without a value.")
            sys.exit(-1)

    if "--max_message_size" in sys.argv:
        idx = sys.argv.index("--max_message_size") + 1
        if idx < len(sys.argv):
            value = sys.argv[idx]
            if value == "None":
                RosbridgeWebSocket.max_message_size = None
            else:
                RosbridgeWebSocket.max_message_size = int(value)
        else:
            print("--max_message_size argument provided without a value. (can be None or <Integer>)")
            sys.exit(-1)

    if "--unregister_timeout" in sys.argv:
        idx = sys.argv.index("--unregister_timeout") + 1
        if idx < len(sys.argv):
            unregister_timeout = float(sys.argv[idx])
        else:
            print("--unregister_timeout argument provided without a value.")
            sys.exit(-1)

    if "--topics_glob" in sys.argv:
        idx = sys.argv.index("--topics_glob") + 1
        if idx < len(sys.argv):
            value = sys.argv[idx]
            if value == "None":
                RosbridgeWebSocket.topics_glob = []
            else:
                RosbridgeWebSocket.topics_glob = [element.strip().strip("'") for element in value[1:-1].split(',')]
        else:
            print("--topics_glob argument provided without a value. (can be None or a list)")
            sys.exit(-1)

    if "--services_glob" in sys.argv:
        idx = sys.argv.index("--services_glob") + 1
        if idx < len(sys.argv):
            value = sys.argv[idx]
            if value == "None":
                RosbridgeWebSocket.services_glob = []
            else:
                RosbridgeWebSocket.services_glob = [element.strip().strip("'") for element in value[1:-1].split(',')]
        else:
            print("--services_glob argument provided without a value. (can be None or a list)")
            sys.exit(-1)

    if "--params_glob" in sys.argv:
        idx = sys.argv.index("--params_glob") + 1
        if idx < len(sys.argv):
            value = sys.argv[idx]
            if value == "None":
                RosbridgeWebSocket.params_glob = []
            else:
                RosbridgeWebSocket.params_glob = [element.strip().strip("'") for element in value[1:-1].split(',')]
        else:
            print("--params_glob argument provided without a value. (can be None or a list)")
            sys.exit(-1)

    if ("--bson_only_mode" in sys.argv) or bson_only_mode:
        RosbridgeWebSocket.bson_only_mode = bson_only_mode

    if "--websocket_ping_interval" in sys.argv:
        idx = sys.argv.index("--websocket_ping_interval") + 1
        if idx < len(sys.argv):
            ping_interval = float(sys.argv[idx])
        else:
            print("--websocket_ping_interval argument provided without a value.")
            sys.exit(-1)

    if "--websocket_ping_timeout" in sys.argv:
        idx = sys.argv.index("--websocket_ping_timeout") + 1
        if idx < len(sys.argv):
            ping_timeout = float(sys.argv[idx])
        else:
            print("--websocket_ping_timeout argument provided without a value.")
            sys.exit(-1)

    # To be able to access the list of topics and services, you must be able to access the rosapi services.
    if RosbridgeWebSocket.services_glob:
        RosbridgeWebSocket.services_glob.append("/rosapi/*")

    Subscribe.topics_glob = RosbridgeWebSocket.topics_glob
    Advertise.topics_glob = RosbridgeWebSocket.topics_glob
    Publish.topics_glob = RosbridgeWebSocket.topics_glob
    AdvertiseService.services_glob = RosbridgeWebSocket.services_glob
    UnadvertiseService.services_glob = RosbridgeWebSocket.services_glob
    CallService.services_glob = RosbridgeWebSocket.services_glob

    # Support the legacy "" address value.
    # The socket library would interpret this as INADDR_ANY.
    if not address:
        address = '0.0.0.0'

    ##################################################
    # Done with parameter handling                   #
    ##################################################

    def handle_compression_offers(offers):
        if not use_compression:
            return
        for offer in offers:
            if isinstance(offer, PerMessageDeflateOffer):
                return PerMessageDeflateOfferAccept(offer)

    if certfile is not None and keyfile is not None:
        protocol = 'wss'
        context_factory = ssl.DefaultOpenSSLContextFactory(keyfile, certfile)
    else:
        protocol = 'ws'
        context_factory = None

    # TODO testing port
    uri = "{}://{}:{}{}".format(protocol, address, port, endpoint)
    factory = WebSocketClientFactory(uri)
    factory.protocol = RosbridgeWebSocket
    factory.setProtocolOptions(
        perMessageCompressionAccept=handle_compression_offers,
        autoPingInterval=ping_interval,
        autoPingTimeout=ping_timeout,
    )

    connected = False
    while not connected and not rospy.is_shutdown():
        try:
            # TODO add timeout
            connectWS(factory)
            rospy.loginfo('Rosbridge WebSocket client daemon started for {}'.format(uri))
            connected = True
        except Exception as e:  # TODO refine exception
            rospy.logwarn(
                "Unable to start server: " + str(e) +
                " Retrying in " + str(retry_startup_delay) + "s."
            )
            rospy.sleep(retry_startup_delay)

    rospy.on_shutdown(shutdown_hook)
    reactor.run()
