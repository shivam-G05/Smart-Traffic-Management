import asyncio

from app.ws.connection_manager import ConnectionManager


class FakeWebSocket:
    def __init__(self, manager=None, on_send=None):
        self.manager = manager
        self.on_send = on_send
        self.sent = []

    async def accept(self):
        pass

    async def send_json(self, payload):
        # Simulate a client connecting mid-broadcast: mutate the manager's
        # connection set while broadcast_json is iterating it. Before the fix
        # (iterating the live set) this raised "Set changed size during
        # iteration" and killed the simulation loop.
        if self.on_send is not None:
            self.on_send()
        self.sent.append(payload)


def test_broadcast_survives_connection_added_mid_iteration():
    manager = ConnectionManager()

    def add_new_connection():
        manager._connections.add(FakeWebSocket())

    existing = FakeWebSocket(on_send=add_new_connection)
    manager._connections.add(existing)

    # Must not raise RuntimeError: Set changed size during iteration.
    asyncio.run(manager.broadcast_json({"tick": 1}))
    assert existing.sent == [{"tick": 1}]


def test_broadcast_drops_failing_connection():
    manager = ConnectionManager()

    class ExplodingWebSocket(FakeWebSocket):
        async def send_json(self, payload):
            raise ConnectionResetError("boom")

    good = FakeWebSocket()
    bad = ExplodingWebSocket()
    manager._connections.update({good, bad})

    asyncio.run(manager.broadcast_json({"tick": 1}))

    assert bad not in manager._connections
    assert good in manager._connections
