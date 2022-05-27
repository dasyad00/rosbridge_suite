#!/usr/bin/env python
import sys
import rospy

from autobahn.twisted.websocket import WebSocketClientFactory, connectWS
from twisted.internet import reactor
from twisted.internet.error import ReactorNotRunning

from rosbridge_client.autobahn_websocket import RosbridgeWebSocket


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

    # target port and address should be defined in the launch file!
    port = rospy.get_param('~port')
    address = rospy.get_param('~address')
    endpoint = rospy.get_param('~endpoint', "/")

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

    # TODO support wss
    protocol = "ws"
    uri = "{}://{}:{}{}".format(protocol, address, port, endpoint)
    factory = WebSocketClientFactory(uri)
    factory.protocol = RosbridgeWebSocket

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
