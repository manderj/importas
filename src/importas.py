import argparse
import importlib
import itertools
import pathlib
import webbrowser

try:
    # checking django imports without setting it up raises an ImproperlyConfigured exception
    import django
    from django.conf import settings

    settings.configure()
    django.setup()
except ImportError:
    pass


import parso
import parso.python.tree as parso_tree

from src.utils.display import print_changes
from src.utils.lists import flatten
from src.utils.paths import is_relative_to


def _git_repo_relation(git_repos, py_path):
    for repo in git_repos:
        if is_relative_to(repo, py_path):
            return repo
    return None


def _get_python_files(paths):
    """ Get all git repos and all python files from paths """

    for path in paths:
        data = ([childpath.parent for childpath in path.rglob('.git')], path)
        if path.is_dir():
            yield (
                (_git_repo_relation(data[0], py_path), py_path)
                for py_path in data[1].rglob('*.py')
            )
        elif path.is_file() and path.match('*.py'):
            yield iter([
                (_git_repo_relation(data[0] or [], path), path)
            ])


def _rewrite_node(absolute_path, node):
    """ Rewrite from w.x import y as z:

    [
        <Keyword: from>,
        PythonNode(dotted_name, [<Name: x@1,5>, <Operator: .>, <Name: y@1,7>]),
        <Keyword: import>,
        PythonNode(import_as_name, [<Name: z@1,16>, <Keyword: as>, <Name: zbis@1,21>]),
    ]

    to import w.x.y as z:

    [
       <Keyword: import>,
       PythonNode(dotted_as_name, [
          PythonNode(dotted_name, [
             <Name: x@1,7>,
             <Operator: .>,
             <Name: y@1,9>,
             <Operator: .>,
             <Name: z@1,11>
          ]),
       <Keyword: as>,
       <Name: zbis@1,16>
       ])
    ]
    """

    # replace from .. import x as y to import <current_file_absolute_path_parent - <number of dot> level>.x as y
    absolute_import_path = (str(
        absolute_path.parents[node.level - 1]
    ) + '/').replace('/', '.') if node.level else ''

    # node can contain the previous returnline, comment, etc?!
    before_import = node.get_code().split('from')
    import_str = f"{before_import[0] if len(before_import) > 1 else ''}"
    for path, defined_name in zip(node.get_paths(), node.get_defined_names()):
        import_str += f"import {absolute_import_path}{'.'.join(name.value for name in path)} as {defined_name.value}\n"
    return import_str


def _can_be_rewritten(node, *, check_dotted_path=False):
    """ Check import can be rewritten  """

    paths = []

    # rewrite dotted path only if parameter is passed to the script
    if node.level and not check_dotted_path:
        return False

    for import_node in node.get_paths():
        # Rewritting: from x.y import z as zz to import x.y.z as zz
        # require z to be a python module

        try:
            paths.append(importlib.util.find_spec(
                '.'.join(name.value for name in import_node)
            ) is not None)
        except ModuleNotFoundError:
            paths.append(False)
    return all(paths)


def _get_imports(obj):
    """ Get all imports from a given parso parsed file """

    if isinstance(obj, (parso_tree.Module, parso_tree.Class, parso_tree.Function)):
        import_list = [list(obj.iter_imports())]
        import_list.extend(
            flatten(imp)
            for scope in itertools.chain(obj.iter_classdefs(), obj.iter_funcdefs())
            if (imp := _get_imports(scope))
        )
        return import_list
    return []


def _visit_file_imports(parser, paths, check_dotted_path):
    filepaths = itertools.chain.from_iterable(paths)

    for repo, filepath in filepaths:
        module = parser.parse(filepath.read_text())
        import_nodes = []

        for node in flatten(_get_imports(module)):
            if (
                isinstance(node, parso_tree.ImportFrom)
                and len(node._aliases())
                and _can_be_rewritten(node, check_dotted_path=check_dotted_path)
            ):
                import_nodes.append(node.parent)
        if import_nodes:
            yield repo, filepath, module, import_nodes
    yield None, None, None, ()


def _fix_imports(args):
    parser = parso.load_grammar()

    for repo, path, module, import_nodes in _visit_file_imports(
        parser, _get_python_files(args.paths), args.dotted_path
    ):
        if import_nodes:
            rewritten_nodes = {}
            for import_node in import_nodes:

                rewritten_nodes[import_node] = _rewrite_node(
                    pathlib.Path(str(path).replace(str(repo) + '/', '')),
                    import_node.children[0],
                )

            if args.save:
                path.write_text(parser.refactor(module, rewritten_nodes))
            else:
                print_changes(path, [{
                    'before': import_node.get_code(),
                    'after': rewritten_nodes[import_node],
                    'line': import_node.start_pos[0],
                } for import_node in import_nodes])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'paths',
        nargs='*', type=pathlib.Path, default=[pathlib.Path.cwd()],
        help="file or repo paths",
    )
    parser.add_argument('--save', '-s', action='store_true')
    parser.add_argument(
        '--dotted-path',
        '-d',
        action='store_true',
        help="Refactor dotted-path imports as well",
    )

    args = parser.parse_args()
    _fix_imports(args)


if __name__ == "__main__":
    main()
