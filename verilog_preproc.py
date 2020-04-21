import codecs, os, re

encoding = 'latin-1' # 'utf-8'

re_pp = re.compile(r'\s*`\s*(define|else|elsif|endif|ifdef|ifndef|include|undef)')
re_ifdef = re.compile(r'\s*`\s*ifn?def\s+(\w+)\s*')
re_elsif = re.compile(r'\s*`\s*elsif\s+(\w+)\s*')
re_define = re.compile(r'\s*`\s*define\s+(\w+)(\([^\)]*\))?\s+(.*?)\s*')
re_include = re.compile(r'\s*`\s*include\s+(".*")\s*')
re_undef = re.compile(r'\s*`\s*undef\s+(\w+)\s*')

re_ident = re.compile(r'\w*')

class Error(Exception):
	def __init__(self, li, line, msg=''):
		self.li = li;
		self.line = line;
		self.msg = msg;

pp_state = None
pp_condition = None

def pp_eval(e1,pred,e2, vd):
	""
	v1 = vd[e1] if isinstance(e1,str) and e1.isidentifier() else int(e1)
	v2 = vd[e2] if isinstance(e2,str) and e2.isidentifier() else int(e2)
	assert isinstance(v1,int) and isinstance(v2,int)
	if pred in ('=','=='):
		cond = v1 == v2
	elif pred == '!=':
		cond = v1 != v2
	elif pred == '>=':
		cond = v1 >= v2
	else:
		assert False, pred
	return cond	

def pp_args(s):
	""" returns une paire (arg_list/None , length)
	on peut avoir 0 argument -> []
	"""
	if s=='' or s[0] != '(': return None,-1
	ii = last_ii = 1; nb_par = 0; eff_params = []
	while ii < len(s) and not(nb_par == 0 and s[ii] == ')'):
		if s[ii] == '(': nb_par += 1
		elif s[ii] == ')': nb_par -= 1
		elif nb_par == 0 and s[ii] == ',':
			eff_params.append(s[last_ii:ii].strip())
			last_ii = ii+1
		ii +=1
	if ii < len(s):
		eff_params.append(s[last_ii:ii].strip())
		if eff_params == ['']: eff_params = []
		if any(p=='' for p in eff_params):
			return None, -1
		else:
			return eff_params, ii+1
	else:
		return None, -1

assert pp_args(' ()') == (None,-1)
assert pp_args('()') == ([],2)
assert pp_args('( )') == ([],3)
assert pp_args('( a )') == (['a'],5)
assert pp_args('( a,b )') == (['a','b'],7)
assert pp_args('( a, )') == (None,-1)

def pp_subst(s, vd):
	""
	r = ''
	i = 0
	bqi = s.find('`', i)
	while bqi >= 0:
		m_ident = re_ident.match(s[bqi+1:])
		if m_ident:
			var = m_ident.group(0)
			val = vd.get(var)
			if val is None:
				r += s[i:bqi+1]
				i = bqi+1
			else:
				params, val = (None, val) if isinstance(val, str) else val
				if params is None:
					r += s[i:bqi] + val
					i = bqi + 1 + len(var)
				else:
					eff_params, len_p = pp_args(s[bqi+1+len(var):])
					if eff_params is None or len(eff_params) != len(params):
						r += s[i:bqi+1]
						i = bqi+1
					else:
						subst_params = [pp_subst(p,vd) for p in eff_params]
						val = val.format_map(dict(zip(params,subst_params)))
						r += s[i:bqi] + val
						i = bqi + 1 + len(var) + len_p
		else:
			r += '`'
			i += 1
		bqi = s.find('`', i)
	r += s[i:]
	return r

assert pp_subst('`',{'foo':'bar'}) == '`'
assert pp_subst('``',{'foo':'bar'}) == '``'
assert pp_subst('``foox',{'foo':'bar'}) == '``foox'
assert pp_subst('``foo x',{'foo':'bar'}) == '`bar x'
assert pp_subst(' ``foo(x`foo) ',{'foo':'bar'}) == ' `bar(xbar) '
assert pp_subst('`foo`foo',{'foo':'bar'}) == 'barbar'
#
assert pp_subst('`foo',{'foo':([],'bar')}) == '`foo'
assert pp_subst('`foo(x)',{'foo':([],'bar')}) == '`foo(x)'
assert pp_subst('`foo()',{'foo':([],'bar')}) == 'bar'
#
assert pp_subst('`foo(a)',{'foo':(['x'],'{x}+1')}) == 'a+1'
assert pp_subst('`foo(`bar(a))',{'foo':(['x'],'{x}+1'), 'bar':(['y'],'{y}-1')}) == 'a-1+1'
#
assert pp_subst('`foo(`bar(a),b)',{'foo':(['x','y'],'{x}+{y}'), 'bar':(['y'],'{y}-1')}) == 'a-1+b'

def pp(fd, **vd):
	"""
	#if c1
				auth = True
				cond = c1
	#elif c2
				auth = -c1
				cond = c2
	#else
				auth = -c1 & -c2
				cond = True
	#endif
	"""
	global pp_state, pp_condition
	for k,v in vd.items():
		if not isinstance(v,int):
			assert isinstance(v, str)
			vd[k] = vd[v]
	pp_auth = []; pp_condition = []
	define_state = 'DEFINE_START' # ou DEFINE_CONT
	line_list = []
	for li,line in enumerate(fd, start=1):
		# line[-1] == '\n', sauf peut-etre sur la derniere ligne
		assert len(pp_auth) == len(pp_condition)
		if define_state == 'DEFINE_CONT':
			assert line and line[-1] == '\n'
			if len(line) >= 2 and line[-2] == '\\':
				val += line[:-2] + '\n'
			else:
				define_state = 'DEFINE_START'
				val += line[:-1]
				if params is not None:
					val = val.replace('{','{{').replace('}','}}')
					for p in params:
						val = val.replace(p,'{'+p+'}')
					vd[var] = (params,val)
				else:
					vd[var] = val
			continue
		m_pp = re_pp.match(line)
		if m_pp != None:
			kind = m_pp.group(1)
			if kind.startswith('if'):
				assert kind in ('ifdef','ifndef')
				m_ifdef = re_ifdef.fullmatch(line)
				if m_ifdef is None:
					print("PP : IF*DEF : bad condition -> condition == ''")
					var = ''
				else:
					var = m_ifdef.group(1)
				cond = var in vd or var in ()
				if kind=='ifndef': cond = not cond
				pp_auth.append(True)
				pp_condition.append(cond)
			elif kind == 'elsif':
				m_elsif = re_elsif.fullmatch(line)
				if m_elsif is None:
					print("PP : ELSIF : bad condition -> condition == ''")
					var = ''
				else:
					var = m_elsif.group(1)
				pp_auth[-1] = pp_auth[-1] and not pp_condition[-1]
				pp_condition[-1] = var in vd
			elif kind == 'else':
				if pp_auth == []:
					raise Error(li,line, 'else sans if')
				pp_auth[-1] = pp_auth[-1] and not pp_condition[-1]
				pp_condition[-1] = True
			elif kind == 'endif':
				if pp_auth == []:
					raise Error(li,line, 'endif sans if')
				pp_auth.pop()
				pp_condition.pop()
			elif kind == 'define':
				if all((auth and cond) for (auth, cond) in zip(pp_auth,pp_condition)):
					m_define = re_define.fullmatch(line)
					if m_define is None:
						raise Error(li,line)
					assert line[-1] == '\n'
					var, params, val = m_define.groups()
					if var in vd:
						print("PP : DEFINE : var {} already exist".format(var))
					if var in ('celldefine','default_nettype','endcelldefine','resetall','timescale'):
						print("PP : DEFINE : var {} is a compiler directive".format(var))
						assert False
					if params:
						params = params[1:-1].split(',')
						params = [p.strip() for p in params]
						if params == ['']: params = []  ### because ''.split(',') -> ['']
						for pi,p in enumerate(params):
							if not p.isidentifier(): ## a1=HERE in ivltests/br_gh105b.v
								print("PP : DEFINE : bad param " + p)
					if len(line) >= 2 and line[-2] == '\\':
						assert val[-1] == '\\', (val, line)
						define_state = 'DEFINE_CONT'
						val = val[:-1] + '\n'
					elif params is not None:
						val = val.replace('{','{{').replace('}','}}')
						for p in params:
							val = val.replace(p,'{'+p+'}')
						vd[var] = (params,val)
					else:
						vd[var] = val
			elif kind == 'undef':
				if all((auth and cond) for (auth, cond) in zip(pp_auth,pp_condition)):
					m_undef = re_undef.fullmatch(line)
					if m_undef is None:
						raise Error(li,line)
					var = m_undef.group(1)
					if var not in vd:
						print("PP : UNDEF : var {} doesn't exist".format(var))
					else:
						del vd[var]
			elif kind == 'include':
				if all((auth and cond) for (auth, cond) in zip(pp_auth,pp_condition)):
					m_include = re_include.fullmatch(line)
					if m_include is None:
						raise Error(li,line)
					fn1 = m_include.group(1)
					fn1 = fn1[1:-1]
					if not fn1.endswith(('.v','.vh')):
						print('*** STRANGE include '+fn1)
					fn_head, fn_tail = os.path.split(os.path.realpath(fd.name))
					fn1_full = os.path.join(fn_head, fn1)
					if os.path.exists(fn1_full):
						print('*** GOOD include '+fn1)
						fd1 = codecs.open(fn1_full, 'r',encoding=encoding)
						fs1 = fd1.read()
						fd1.close()
						if '`if' in fs1:
							print('*** PP : INCLUDE : WARNING macros in '+fn1)
						line = '/* BEGIN include {} */ '.format(fn1) + fs1 + ' /* END include {} */\n'.format(fn1)
						m_pp = None # pour ne pas la commenter
					else:
						print('*** BAD include '+fn1)
					# assert False, 'include'
			else:
				assert False, (li,line)
		elif all((auth and cond) for (auth, cond) in zip(pp_auth,pp_condition)): # ligne normale non inhibée
			# 
			line = pp_subst(line, vd)
		##
		if m_pp != None or any(not(auth and cond) for (auth, cond) in zip(pp_auth,pp_condition)):
			line = '//'+line
			# print('{}:\t{}'.format(li,line))
		line_list.append(line)
	if not( pp_auth == pp_condition == [] ):
		raise Error(0,'','if/endif nonbalanced')
	return line_list

if __name__ == '__main__':
	vlib = r'C:\Temp\github\verilog'
	fn = vlib + r'\yosys-tests-master\simple'
	# fn = vlib + r'\yosys-tests-master\simple\proc_arst'
	#fn = vlib + r'\yosys-tests-master\bigsim'
	fn = vlib + r'\yosys-tests-master\frontends\read_verilog'
	fn = vlib + r'\yosys-tests-master'
	# fn = vlib + r'\yosys-master'
	#fn = vlib + r'\yosys-master\techlibs\common\mul2dsp.v'
	#fn = vlib + r'\ivtest-master'
	fn = vlib + r'\verilator_ext_tests-master'
	fn = vlib + r'\verilator-master'
	fn = vlib
	for root, dirs, files in os.walk(fn):
		for file in files:
			if file.endswith('.v'):
				# if file != 'mul2dsp.v': continue
				macros_preproc = {}
				fn = os.path.join(root,file)
				print('*** '+fn)
				fd = codecs.open(fn, 'r',encoding=encoding)
				try:
					sl = pp(fd, **macros_preproc)
				except Error as err:
					print('!!!! PP : Error : {} : {}'.format(err.li,err.line))
				fd.close()
