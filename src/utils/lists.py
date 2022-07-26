import functools
import operator


def flatten(obj_list):
    """ Flatten a list of list of object into a list of object """
    return functools.reduce(operator.iconcat, obj_list, [])
