import asyncio

from pulsar import create_future
from pulsar.apps.data.channels import Channels, StatusType, Json


class Tester:

    def __init__(self):
        self.end = create_future()

    def __call__(self, *args, **kwargs):
        if not self.end.done():
            self.end.set_result((args, kwargs))


class ChannelsTests:

    def channels(self):
        return Channels(self.store.pubsub(protocol=Json()),
                        namespace='testpulsar')

    async def test_channels(self):
        channels = self.channels()
        self.assertTrue(channels.pubsub)
        self.assertTrue(channels.status_channel)
        self.assertEqual(channels.status, StatusType.initialised)
        self.assertFalse(channels)
        self.assertEqual(list(channels), [])
        await channels.register('foo', '*', lambda c, e, d: d)
        self.assertTrue(channels)
        self.assertEqual(len(channels), 1)
        self.assertTrue('foo' in channels)
        self.assertEqual(channels.status, StatusType.initialised)

    async def test_wildcard(self):
        channels = self.channels()

        future = asyncio.Future()

        def fire(channel, event, data):
            future.set_result(event)

        await channels.register('test1', '*', fire)
        self.assertEqual(channels.status, StatusType.initialised)
        await channels.connect()
        self.assertEqual(channels.status, StatusType.connected)
        await channels.publish('test1', 'boom', 'ciao!')
        result = await future
        self.assertEqual(result, 'boom')
        self.assertEqual(len(channels), 1)
        self.assertTrue(repr(channels))
        await channels.close()
        self.assertEqual(channels.status, StatusType.closed)

    async def test_fail_publish(self):
        channels = self.channels()
        original, warning, critical = self._patch(
            channels, channels.pubsub, 'publish'
        )
        await channels.publish('channel3', 'event2', 'failure')
        args, kw = await critical.end
        self.assertEqual(len(args), 3)
        self.assertEqual(args[1], channels)

    def _log_error(self, coro, *args, **kwargs):
        coro.switch((args, kwargs))

    def _connection_error(self, *args, **kwargs):
        raise ConnectionRefusedError

    def _patch(self, channels, obj, method):
        original = getattr(obj, method)
        setattr(obj, method, self._connection_error)
        critical = Tester()
        warning = Tester()
        channels.logger.critical = critical
        channels.logger.warning = warning
        return original, warning, critical
