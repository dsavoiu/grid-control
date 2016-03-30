#-#  Copyright 2012-2016 Karlsruhe Institute of Technology
#-#
#-#  Licensed under the Apache License, Version 2.0 (the "License");
#-#  you may not use this file except in compliance with the License.
#-#  You may obtain a copy of the License at
#-#
#-#      http://www.apache.org/licenses/LICENSE-2.0
#-#
#-#  Unless required by applicable law or agreed to in writing, software
#-#  distributed under the License is distributed on an "AS IS" BASIS,
#-#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#-#  See the License for the specific language governing permissions and
#-#  limitations under the License.

import shlex
from grid_control import utils
from grid_control.config import ConfigError, changeImpossible, noDefault
from grid_control.utils.parsing import parseDict
from python_compat import imap, irange, lmap, lzip

def parseTuple(t, delimeter):
	t = t.strip()
	if t.startswith('('):
		return tuple(imap(str.strip, utils.split_advanced(t[1:-1], lambda tok: tok == delimeter, lambda tok: False)))
	return (t,)


def frange(start, end = None, num = None, steps = None, format = '%g'):
	if (end is None) and (num is None):
		raise ConfigError('frange: No exit condition!')
	if (end is not None) and (num is not None) and (steps is not None):
		raise ConfigError('frange: Overdetermined parameters!')
	if (end is not None) and (num is not None) and (steps is None):
		steps = (end - start) / (num - 1)
		num -= 1
	if (end is not None) and (num is None):
		steps = steps or 1
		num = int(1 + (end - start) / steps)
	result = imap(lambda i: start + (steps or 1) * i, irange(num)) + utils.QM(end, [end], [])
	return lmap(lambda x: format % x, result)


def parseParameterOption(option):
	result = lmap(str.strip, utils.split_advanced(option.lower(), lambda t: t in ')]}', lambda t: True))
	if len(result) and '(' in result[0]:
		validChar = lambda c: c.isalnum() or (c in ['_'])
		result[0] = tuple(utils.accumulate(result[0], '', lambda i, b: not validChar(i), lambda i, b: validChar(i)))
	elif len(result) == 1:
		result = lmap(str.strip, result[0].split(' ', 1))
	if len(result) == 1:
		result.append(None)
	return tuple(result)


def parseParameterOptions(options):
	(varDict, optDict) = ({}, {})
	for rawOpt in options:
		var, opt = parseParameterOption(rawOpt)
		optDict[(var, opt)] = rawOpt
		if opt is None:
			if isinstance(var, tuple):
				for sk in var:
					varDict[sk] = var
			else:
				varDict[var] = var
	return (varDict, optDict)


class ParameterConfig:
	def __init__(self, config, static):
		(self.config, self.static) = (config, static)
		(self.varDict, self.optDict) = parseParameterOptions(config.getOptions())


	def parseParameter(self, varName, value, ptype):
		if ptype == 'verbatim':
			return [value]
		elif ptype == 'split':
			delimeter = self.get(self.getParameterOption(varName), 'delimeter', ',')
			return lmap(str.strip, value.split(delimeter))
		elif ptype == 'lines':
			return value.splitlines()
		elif ptype == 'expr' or ptype == 'eval':
			result = eval(value) # pylint:disable=eval-used
			if isinstance(result, (list, type(range(1)))):
				return list(result)
			return [result]
		elif ptype == 'default':
			return shlex.split(value)
		elif ptype == 'format':
			fsource = self.get(self.getParameterOption(varName), 'source')
			fdefault = self.get(self.getParameterOption(varName), 'default', '')
			return (ptype, varName, value, fsource, fdefault)
		raise ConfigError('[Variable: %s] Invalid parameter type: %s' % (varName, ptype))


	def parseParameterTuple(self, varName, tupleValue, tupleType, varType, varIndex):
		if tupleType == 'tuple':
			tupleDelimeter = self.get(self.getParameterOption(varName), 'delimeter', ',')
			tupleStrings = lmap(str.strip, utils.split_advanced(tupleValue, lambda tok: tok in ')]}', lambda tok: True))
			tupleList = lmap(lambda t: parseTuple(t, tupleDelimeter), tupleStrings)
		elif tupleType == 'binning':
			tupleList = lzip(tupleValue.split(), tupleValue.split()[1:])

		def yieldEntries():
			for tupleEntry in tupleList:
				try:
					tmp = self.parseParameter(varName, tupleEntry[varIndex], varType)
				except Exception:
					raise ConfigError('Unable to parse %r' % tupleEntry)
				if isinstance(tmp, list):
					if len(tmp) != 1:
						raise ConfigError('[Variable: %s] Tuple entry (%s) expands to multiple variable entries (%s)!' % (varName, tupleEntry[varIndex], tmp))
					yield tmp[0]
				else:
					yield tmp
		return list(yieldEntries())


	def onChange(self, config, old_obj, cur_obj, cur_entry, obj2str):
		if self.static:
			return changeImpossible(config, old_obj, cur_obj, cur_entry, obj2str)
		return cur_obj


	def getOpt(self, var, opt = None):
		return self.optDict.get((var, opt), ('%s %s' % (var, opt or '')).replace('\'', ''))


	def get(self, var, opt = None, default = noDefault):
		result = self.config.get(self.getOpt(var, opt), default, onChange = self.onChange)
		return result


	def getBool(self, var, opt = None, default = noDefault):
		result = self.config.getBool(self.getOpt(var, opt), default, onChange = self.onChange)
		return result


	def getParameterOption(self, varName):
		try:
			return self.varDict[varName.lower()]
		except Exception:
			raise ConfigError('Variable %s is undefined' % varName)


	def parseDict(self, varName, value, valueParser):
		keyTupleDelimeter = self.get(self.getParameterOption(varName), 'key delimeter', ',')
		return parseDict(value, valueParser, lambda k: parseTuple(k, keyTupleDelimeter))


	def getParameter(self, varName):
		optKey = self.getParameterOption(varName)

		if isinstance(optKey, tuple):
			varIndex = list(optKey).index(varName.lower())
			tupleValue = self.get(optKey, None, '')
			tupleType = self.get(optKey, 'type', 'tuple')
			varType = self.get(varName, 'type', 'verbatim')

			if '=>' in tupleValue:
				return self.parseDict(varName, tupleValue,
					lambda v: self.parseParameterTuple(varName, v, tupleType, varType, varIndex))
			return self.parseParameterTuple(varName, tupleValue, tupleType, varType, varIndex)

		else:
			varValue = self.get(optKey, None, '')
			varType = self.get(varName, 'type', 'default')

			if '=>' in varValue:
				enableDict = self.getBool(optKey, 'parse dict', True)
				if enableDict:
					return self.parseDict(varName, varValue,
						lambda v: self.parseParameter(varName, v, varType))
			return self.parseParameter(varName, varValue, varType)
