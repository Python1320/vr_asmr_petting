import asyncio
import inspect
import traceback
from collections.abc import Callable
from typing import Any, List, Union, overload, override  # noqa: UP035

from pythonosc.dispatcher import Dispatcher, Handler
from pythonosc.udp_client import SimpleUDPClient


def oscfloat(args):
    """Catch all function to convert OSC arguments to float (do not use)"""
    a = args[0]
    if isinstance(a, (int, float)):
        return float(a)
    # boolean
    elif isinstance(a, bool):
        return 1.0 if a else 0.0
    elif isinstance(a, (list, tuple)):
        # how?
        return oscfloat(a)
    elif isinstance(a, str):
        try:
            return float(a)
        except ValueError as e:
            raise ValueError(
                f"oscfloat() cannot convert string '{a}' to a float"
            ) from e
    else:
        raise ValueError(
            f"oscfloat() cannot convert {args} (type {type(args)}) to float"
        )


class AsyncOSCDispatcher(Dispatcher):
    """OSC dispatcher that supports async handlers by dispatching
      them to an asyncio task group worker.

    NOTE: There is only a single worker per mapped address, so if multiple messages are
        received for the same address while the handler is still processing, they will
        be queued and processed sequentially. This means that if a handler is blocked
        for some reason (e.g. waiting for I/O),  the queue can fill up and eventually
        overflow, causing messages to be dropped and a QueueFull exception to be raised.
    """

    _taskgroup: asyncio.TaskGroup | None
    _registered_tasks: list[tuple[str | None, Callable]]

    # NOTE: There can be a queue overflow if the asyncio handler is blocked (it is for example sleeping)
    _queue_maxsize: int = 2

    @override
    def __init__(
        self, task_group: asyncio.TaskGroup | None = None, queue_maxsize: int = 1024
    ):
        super().__init__()
        self._registered_tasks = []
        if task_group is not None and not isinstance(task_group, asyncio.TaskGroup):
            raise ValueError(
                "task_group must be an instance of asyncio.TaskGroup or None"
            )
        self._taskgroup = task_group
        self._queue_maxsize = queue_maxsize

    async def set_task_group(self, tg: asyncio.TaskGroup):
        if self._taskgroup:
            raise RuntimeError("Task group is already set")
        self._taskgroup = tg
        if self._registered_tasks:
            for name, task in self._registered_tasks:
                self._taskgroup.create_task(task(), name=name)
            self._registered_tasks = []

    async def on_first_message(self, address: str, handler, handler_args, args, queue):
        """Escape hatch: Override this method to do something on the first message received."""
        pass

    @override
    def map(
        self,
        address: str,
        handler: Callable,
        *args: Any | list[Any],
        needs_reply_address: bool = False,
    ) -> Handler:
        queue = asyncio.Queue(maxsize=self._queue_maxsize)
        awaitable = inspect.iscoroutinefunction(handler)

        async def dispatcher_async_worker():
            first = True
            try:
                while True:
                    handler_args = await queue.get()
                    if first:
                        ret = await self.on_first_message(
                            address, handler, handler_args, args, queue
                        )
                        first = False

                    ret = None
                    if awaitable:
                        # print("calling", handler, handler_args)
                        ret = await handler(*handler_args)
                    else:
                        # print("calling sync handler", handler, handler_args)
                        ret = handler(*handler_args)
                    if ret is not None:
                        raise ValueError(
                            f"Handler for address {address} returned a value {ret!r}, but this is not supported for async handlers"
                        )
            except asyncio.CancelledError:
                pass
            except asyncio.QueueShutDown as e:
                # NOTE: this code attempts avoiding swallowing excs. from the handler
                # without a performance hit on the normal code path
                tb = e.__traceback__
                ok = True
                for frame, _ in traceback.walk_tb(tb):
                    if frame.f_code.co_name == handler.__name__:
                        ok = False
                        break
                if not ok:
                    raise

        name = f"AsyncOSCDispatcher:{address}"
        self._add_task(dispatcher_async_worker, name=name)

        printed_queue_full = False

        def cb_handler(*handler_args):
            nonlocal printed_queue_full
            # print(f"cb_handler called for address {address} with args {handler_args}")
            try:
                queue.put_nowait(handler_args)
            except asyncio.QueueFull:
                if not printed_queue_full:
                    print(f"Queue is full! address: {address}")
                    printed_queue_full = True
                raise  # where does this raise?

        return super().map(
            address, cb_handler, *args, needs_reply_address=needs_reply_address
        )

    @overload
    def unmap(self, address: str, handler: Handler) -> None:
        raise NotImplementedError(
            "Unmapping handlers is not implemented in AsyncDispatcher"
        )

    @overload
    def unmap(
        self,
        address: str,
        handler: Callable,
        *args: Union[Any, List[Any]],  # noqa: UP006, UP007
        needs_reply_address: bool = False,
    ) -> None:
        raise NotImplementedError(
            "Unmapping handlers is not implemented in AsyncDispatcher"
        )

    @override
    def unmap(self, address, handler, *args, needs_reply_address=False):
        raise NotImplementedError(
            "Unmapping handlers is not implemented in AsyncDispatcher"
        )

    @override
    def set_default_handler(
        self, handler: Callable, needs_reply_address: bool = False
    ) -> None:
        """Sets the default handler

        The default handler is invoked every time no other handler is mapped to an address.

        Args:
            handler: Callback function to handle unmapped requests
            needs_reply_address: Whether the callback shall be passed the client address
        """
        awaitable = inspect.iscoroutinefunction(handler)
        if handler is None or not awaitable:
            super().set_default_handler(handler, needs_reply_address)
            return

        queue = asyncio.Queue(maxsize=self._queue_maxsize)

        async def dispatcher_async_worker():
            try:
                while True:
                    handler_args = await queue.get()

                    ret = await handler(*handler_args)
                    if ret is not None:
                        raise ValueError(
                            f"Default handler returned a value {ret!r}, but this is not supported for async handlers"
                        )

            except asyncio.CancelledError:
                pass  # TODO: raise?
            except asyncio.QueueShutDown as e:
                # NOTE: this code attempts avoiding swallowing excs. from the handler
                tb = e.__traceback__
                ok = True
                for frame, _ in traceback.walk_tb(tb):
                    if frame.f_code.co_name == handler.__name__:
                        ok = False
                        break
                if not ok:
                    raise

        self._add_task(
            dispatcher_async_worker, name="AsyncOSCDispatcher default handler"
        )

        printed_queue_full = False

        def cb_handler(*handler_args):
            try:
                queue.put_nowait(handler_args)
            except asyncio.QueueFull:
                nonlocal printed_queue_full
                if not printed_queue_full:
                    print("Queue is full! default_handler")
                    printed_queue_full = True
                raise  # where does this raise?

        super().set_default_handler(cb_handler, needs_reply_address)

    def _add_task(self, coroutine_fn: Callable, name: str | None = None):
        """Add a task to the dispatcher,
        either immediately if the task group is set, or register it for later creation.
        """
        if self._taskgroup:
            self._taskgroup.create_task(coroutine_fn(), name=name)
        else:
            self._registered_tasks.append((name, coroutine_fn))


if __name__ == "__main__":
    from pythonosc.udp_client import SimpleUDPClient

    class HandleTestException(Exception):
        pass

    async def _test_dispatch(
        dispatch_locally: bool,
        dispatcher: AsyncOSCDispatcher,
        client: SimpleUDPClient,
        exceptiontest: bool = False,
    ):

        dgram_sync = b"/sync\x00\x00\x00,\x00\x00\x00"
        dgram_async = b"/async\x00\x00,\x00\x00\x00"
        dgram_default = b"/default\x00\x00\x00\x00,f\x00\x00\x42\xf6\x00\x00"
        print(
            "=======",
            "Dispatching locally" if dispatch_locally else "Dispatching via socket",
            "=======",
        )
        sync_called = False

        def sync_handler(address, *args):
            print(
                " ! sync_handler called with address:",
                address,
                "and args:",
                args,
            )
            nonlocal sync_called
            sync_called = True

        async_called = False

        async def async_handler(address, *args):
            print(
                " ! async_handler called with address:",
                address,
                "and args:",
                args,
            )
            if exceptiontest:
                raise HandleTestException("Test exception from async handler")
            nonlocal async_called
            async_called = True

        dispatcher.map("/sync", sync_handler)
        dispatcher.map("/async", async_handler)

        default_handler_called = False

        async def default_handler(address, *args):
            print(
                " ! default_handler called with address:",
                address,
                "and args:",
                args,
            )
            nonlocal default_handler_called
            default_handler_called = True

        dispatcher.set_default_handler(default_handler)

        print("dispatching sync packet...")
        if dispatch_locally:
            await dispatcher.async_call_handlers_for_packet(
                dgram_sync, ("127.0.0.1", 1234)
            )
        else:
            client.send_message("/sync", [])

        print("dispatching async packet...")
        if dispatch_locally:
            await dispatcher.async_call_handlers_for_packet(
                dgram_async, ("127.0.0.1", 1234)
            )
        else:
            client.send_message("/async", [])

        print("dispatching default handler packet...")
        # Dispatch default handler
        if dispatch_locally:
            await dispatcher.async_call_handlers_for_packet(
                dgram_default, ("127.0.0.1", 1234)
            )
        else:
            client.send_message("/default", [123.0])

        print("await asyncio.sleep(0.2)...")
        await asyncio.sleep(0.2)
        print("\nFinished waiting\n")

        assert sync_called, "Sync handler was not called"
        assert async_called, "Async handler was not called"
        assert default_handler_called, "Default handler was not called"

    async def test_async_call_handlers_for_packet(exceptiontest=False):
        (ip, port) = ("127.0.0.1", exceptiontest and 12345 or 12344)

        dispatcher = AsyncOSCDispatcher()

        from pythonosc.osc_server import AsyncIOOSCUDPServer
        from pythonosc.udp_client import SimpleUDPClient

        transport = None
        try:
            async with asyncio.TaskGroup() as tg:
                await dispatcher.set_task_group(tg)

                client = SimpleUDPClient(ip, port)
                server = AsyncIOOSCUDPServer(
                    (ip, port),
                    dispatcher,
                    asyncio.get_running_loop(),  # type: ignore
                )

                (
                    transport,
                    protocol,
                ) = await server.create_serve_endpoint()
                # Create datagram endpoint and start serving

                for dispatch_locally in (True, False):
                    await _test_dispatch(
                        dispatch_locally, dispatcher, client, exceptiontest
                    )
                print(
                    "AsyncOSCDispatcher: complete! Feel free to test ctrl+c handling now (sleeping 2 seconds)..."
                )
                await asyncio.sleep(2)
                raise asyncio.CancelledError("Test complete!")
        finally:
            if transport:
                print("Closing transport...", ip, port)
                transport.close()

    async def test():
        # Test exception handling
        try:
            await test_async_call_handlers_for_packet(exceptiontest=True)

        except* HandleTestException as eg:
            for error in eg.exceptions:
                print(f"Success! Handled a HandleTestException: {error}")
        except* asyncio.CancelledError as ce:
            raise RuntimeError(
                "Test failed: this should not happen or you ctrl+c'd very quickly"
            ) from ce

        # Test normal execution
        try:
            await test_async_call_handlers_for_packet()
        except asyncio.CancelledError as e:
            print("Successfully caught CancelledError from TaskGroup (2)!...", e)

    asyncio.run(test())
