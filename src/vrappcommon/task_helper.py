import asyncio
import traceback


def handle_errors(task):
    try:
        exc = task.exception()
        if exc:
            traceback.print_exception(type(exc), exc, exc.__traceback__)
    except asyncio.exceptions.CancelledError:
        pass


all_tasks = []

# https://textual.textualize.io/blog/2023/02/11/the-heisenbug-lurking-in-your-async-code/
# TODO: there's an issue/discussion about this


def task_done(task):
    all_tasks.remove(task)
    handle_errors(task)


def spawn_task(
    awaitable,
    loop: asyncio.TaskGroup | asyncio.AbstractEventLoop | None = None,
    name=None,
):
    loop = loop or asyncio.get_running_loop()
    task = loop.create_task(awaitable)
    if name:
        task.set_name(name)
    all_tasks.append(task)
    task.add_done_callback(task_done)
    return task
