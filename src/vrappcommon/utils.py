from .AsyncOSCDispatcher import AsyncOSCDispatcher  # noqa: F401
from .task_helper import all_tasks, spawn_task, task_done  # noqa: F401


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


def clamp(num, min_value, max_value):
    return max(min(num, max_value), min_value)


def remap(OldValue, OldMin, OldMax, NewMin, NewMax):
    OldRange = OldMax - OldMin
    NewRange = NewMax - NewMin
    return (((OldValue - OldMin) * NewRange) / OldRange) + NewMin
