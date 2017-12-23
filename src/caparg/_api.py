import argparse

import attr
import pyrsistent

@attr.s(frozen=True)
class _Command(object):

    _name = attr.ib(convert=lambda x: pyrsistent.pvector(x.split()))
    _args = attr.ib()
    _options = attr.ib(convert=lambda x:
                               pyrsistent.pvector(value.with_name(key)
                                                  for key, value in x.items()))

    def _make_parser(self):
        options = self._options
        subcommands = pyrsistent.m()
        for thing in self._args:
            options += thing.get_options()
        for thing in self._args:
            for name, subcommand in thing.add_to(self._name, options):
                subcommands = subcommands.set(name, subcommand)
        return _Parser(subcommands)

    def get_options(self):
        return []

    def add_to(self, parent_name, options):
        ret = pyrsistent.m()
        full_name = parent_name + self._name
        for thing in self._args:
            options += thing.get_options()
        for thing in self._args:
            for name, suboptions in thing.add_to(full_name, options):
                yield name, suboptions
        if self._name:
            yield full_name, options + self._options

    def parse(self, args):
        parser = self._make_parser()
        parsed = parser.parse_args(args)
        return parser.get_value(parsed)

@attr.s(frozen=True)
class ParseError(ValueError):

     message = attr.ib()

class _RaisingArgumentParser(argparse.ArgumentParser):

    def error(self, message):
        raise ParseError(message)

@attr.s(frozen=True)
class _Parser(object):

    _subcommands = attr.ib()

    def parse_args(self, args):
        args = pyrsistent.pvector(args)
        candidates = [i
                      for i in range(1, len(args)+1)
                      if args[:i] in self._subcommands]
        if not candidates:
            raise ParseError(self._make_help())
        parts = max(candidates)
        subcommand, rest = self._subcommands[args[:parts]], args[parts:]
        parser = _RaisingArgumentParser(' '.join(args[:parts]))
        for thing in subcommand:
            thing.add_argument(parser)
        ret = parser.parse_args(rest)
        ret.__caparg_subcommand__ = args[:parts]
        return ret

    def get_value(self, namespace):
        subcommand = namespace.__caparg_subcommand__
        ret = pyrsistent.m(__caparg_subcommand__=subcommand)
        for thing in self._subcommands[subcommand]:
            ret = ret.update(thing.get_value(namespace))
        return ret

    def _make_help(self):
        parts = ["Usage:\n"]
        for key in sorted(self._subcommands):
            parts.append("    " + " ".join(key) + "\n")
        return ''.join(parts)

@attr.s(frozen=True)
class _PreOption(object):

    _type = attr.ib()
    _required = attr.ib(default=False)
    _have_default = attr.ib(default=False)

    @attr.s(frozen=True)
    class Option(object):

        _type = attr.ib()
        _required = attr.ib()
        _have_default = attr.ib()
        _name = attr.ib()
        _MISSING = object()

        def add_argument(self, parser):
            if self._type == str:
                parser.add_argument('--' + self._name,
                                    type=str,
                                    required=self._required,
                                    default=self._MISSING)
                return
            if self._type == bool:
                parser.add_argument('--' + self._name, action='store_true',
                                    default=False)
                return
            raise NotImplementedError("cannot add to parser",
                                      self, parser)

        def get_value(self, namespace):
            value = getattr(namespace, self._name, self._MISSING)
            ret = pyrsistent.m()
            if value is not self._MISSING:
                ret = ret.set(self._name, value)
            elif self._have_default is True:
                if self._type == str:
                    ret = ret.set(self._name, '')
                else:
                    raise NotImplementedError("cannot default value",
                                              self._name, self._type)
            return ret

    def with_name(self, name):
        return self.Option(name=name, type=self._type, required=self._required,
                                      have_default=self._have_default)


def command(_name, *args, **kwargs):
    return _Command(_name, args, kwargs)

def option(type, required=False, have_default=False):
    return _PreOption(type, required=required, have_default=have_default)

@attr.s(frozen=True)
class _OptionList(object):

    _options = attr.ib(convert=lambda x:
                               pyrsistent.pvector(value.with_name(key)
                                                  for key, value in x.items()))

    def get_options(self):
        return self._options

    def add_to(self, parent_name, options):
        return pyrsistent.v()


def options(**kwargs):
    return _OptionList(pyrsistent.pmap(kwargs))

@attr.s(frozen=True)
class _Positional(object):

    _name = attr.ib()
    _type = attr.ib()
    _required = attr.ib()
    _have_default = attr.ib()
    _MISSING = object()

    def get_options(self):
        return pyrsistent.v(self)

    def add_to(self, parent_name, options):
        return pyrsistent.v()

    def add_argument(self, parser):
        if self._type == str:
            parser.add_argument(self._name, type=str, default=self._MISSING)
            return
        raise NotImplementedError("cannot add to parser",
                                  self, parser)

    def get_value(self, namespace):
        value = getattr(namespace, self._name, self._MISSING)
        ret = pyrsistent.m()
        if value is not self._MISSING:
            ret = ret.set(self._name, value)
        elif self._have_default is True:
            if self._type == str:
                ret = ret.set(self._name, '')
            else:
                raise NotImplementedError("cannot default value",
                                          self._name, self._type)
        return ret

def positional(name, type, required=False, have_default=False):
    return _Positional(name, type, required, have_default)