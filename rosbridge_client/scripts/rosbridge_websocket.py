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

    if "--retry_startup_delay" in sys.argv:
        idx = sys.argv.index("--retry_startup_delay") + 1
        if idx < len(sys.argv):
            retry_startup_delay = int(sys.argv[idx])
        else:
            print("--retry_startup_delay argument provided without a value.")
            sys.exit(-1)

    # TODO get parameters from launch file
    address = "ws://localhost"
    port = 9090
    uri = "{}:{}".format(address, port)
    factory = WebSocketClientFactory(uri)
    factory.protocol = RosbridgeWebSocket

    connected = False
    while not connected and not rospy.is_shutdown():
        try:
            connectWS(factory)
            rospy.loginfo('Rosbridge WebSocket client connected to {}'.format(uri))
            connected = True
        except Exception as e:  # TODO refine exception
            rospy.logwarn(
                "Unable to start server: " + str(e) +
                " Retrying in " + str(retry_startup_delay) + "s."
            )
            rospy.sleep(retry_startup_delay)

    rospy.on_shutdown(shutdown_hook)
    reactor.run()
