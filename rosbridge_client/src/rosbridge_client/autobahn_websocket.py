from autobahn.twisted.websocket import WebSocketClientProtocol


class RosbridgeWebSocket(WebSocketClientProtocol):
    def onOpen(self):
        pass

    def onMessage(self, payload, isBinary):
        pass

    def onClose(self, wasClean, code, reason):
        pass