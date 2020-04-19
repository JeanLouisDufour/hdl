import codecs, os, re

re_pp = re.compile(r'\s*`\s*(define|else|elsif|endif|ifdef|ifndef|include|undef)')
re_ifdef = re.compile(r'\s*`\s*ifn?def\s+(\w+)\s*')
re_elsif = re.compile(r'\s*`\s*elsif\s+(\w+)\s*')
re_define = re.compile(r'\s*`\s*define\s+(\w+)(\([^\)]+\))?\s+(.*?)\s*')
re_include = re.compile(r'\s*`\s*include\s+(".*")\s*')
re_undef = re.compile(r'\s*`\s*undef\s+(\w+)\s*')

re_ident = re.compile(r'\w+')

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
	line_list = []
	for li,line in enumerate(fd, start=1):
		# line[-1] == '\n', sauf peut-etre sur la derniere ligne
		assert len(pp_auth) == len(pp_condition)
		m_pp = re_pp.match(line)
		if m_pp != None:
			kind = m_pp.group(1)
			if kind.startswith('if'):
				if False:
					2+2
				else:
					assert kind in ('ifdef','ifndef')
					m_ifdef = re_ifdef.fullmatch(line)
					assert m_ifdef != None, (li,line)
					var = m_ifdef.group(1)
					cond = var in vd or var in ()
					if kind=='ifndef': cond = not cond				
				pp_auth.append(True)
				pp_condition.append(cond)
			elif kind == 'elsif':
				m_elsif = re_elsif.fullmatch(line)
				assert m_elsif != None, (li,line)
				var = m_elsif.group(1)
				pp_auth[-1] = pp_auth[-1] and not pp_condition[-1]
				pp_condition[-1] = var in vd
#				assert var in vd, (li,line)
#				if pred == '!=':
#					pp_condition[-1] = vd[var] != val
#				else:
#					pp_condition[-1] = vd[var] == val
			elif kind == 'else':
				pp_auth[-1] = pp_auth[-1] and not pp_condition[-1]
				pp_condition[-1] = True
			elif kind == 'endif':
				pp_auth.pop()
				pp_condition.pop()
			elif kind == 'define':
				if all((auth and cond) for (auth, cond) in zip(pp_auth,pp_condition)):
					m_define = re_define.fullmatch(line)
					var, params, val = m_define.groups()
					if var in vd:
						assert False, (var,vd)
					if params:
						params = params[1:-1].split(',')
						val = val.replace('{','{{').replace('}','}}')
						for p in params:
							assert p.isidentifier()
							val = val.replace(p,'{'+p+'}')
					# assert '`' not in val
					vd[var] = (params,val) if params else val
			elif kind == 'undef':
				if all((auth and cond) for (auth, cond) in zip(pp_auth,pp_condition)):
					m_undef = re_undef.fullmatch(line)
					var = m_undef.group(1)
					assert var in vd
					del vd[var]
			elif kind == 'include':
				if all((auth and cond) for (auth, cond) in zip(pp_auth,pp_condition)):
					m_include = re_include.fullmatch(line)
					fn1 = m_include.group(1)
					fn1 = fn1[1:-1]
					assert fn1.endswith('.v')
					fn_head, fn_tail = os.path.split(os.path.realpath(fd.name))
					fn1_full = os.path.join(fn_head, fn1)
					if os.path.exists(fn1_full):
						print('*** GOOD include '+fn1)
					else:
						print('*** BAD include '+fn1)
					# assert False, 'include'
			else:
				assert False, (li,line)
		elif all((auth and cond) for (auth, cond) in zip(pp_auth,pp_condition)): # ligne normale non inhibée
			idx = line.find('//')
			if '`' in line[:idx] and all(pp not in line[:idx] for pp in ('`celldefine','`endcelldefine','`resetall','`timescale')):
				sl = line[:idx].split('`')
				for i,s in enumerate(sl[1:], start=1):
					m_ident = re_ident.match(s)
					var = m_ident.group(0) if m_ident else None
					if var in vd:
						val = vd[var]
						if isinstance(val,str):
							sl[i] = val + s[len(var):]
						else:
							params, val = val
							assert s[len(var)] == '('
#							ii = s[len(var):].find(')')
#							assert ii > 0
#							assert '(' not in s[len(var)+1:len(var)+ii]
							ii = last_ii = 1; nb_par = 0; eff_params = []
							while not(nb_par == 0 and s[len(var)+ii] == ')'):
								if s[len(var)+ii] == '(': nb_par += 1
								elif s[len(var)+ii] == ')': nb_par -= 1
								elif nb_par == 0 and s[len(var)+ii] == ',':
									eff_params.append(s[len(var)+last_ii:len(var)+ii])
									last_ii = ii+1
								ii +=1
							eff_params.append(s[len(var)+last_ii:len(var)+ii])
							assert len(eff_params) == len(params)
							val = val.format_map(dict(zip(params,eff_params)))
							sl[i] = val + s[len(var)+ii+1:]
				line = ''.join(sl) + line[idx:]
		##
		if m_pp != None or any(not(auth and cond) for (auth, cond) in zip(pp_auth,pp_condition)):
			line = '//'+line
			# print('{}:\t{}'.format(li,line))
		line_list.append(line)
	assert pp_auth == pp_condition == []
	return line_list

if __name__ == '__main__':
	encoding = 'latin-1' # 'utf-8'
	fn = r'C:\Temp\github\yosys-tests-master\simple'
	# fn = r'C:\Temp\github\yosys-tests-master\simple\proc_arst'
	#fn = r'C:\Temp\github\yosys-tests-master\bigsim'
	fn = r'C:\Temp\github\yosys-tests-master\frontends\read_verilog'
	fn = r'C:\Temp\github\yosys-tests-master'
	for root, dirs, files in os.walk(fn):
		for file in files:
			if file.endswith('.v'):
				macros_preproc = {}
				fn = os.path.join(root,file)
				print('*** '+fn)
				fd = codecs.open(fn, 'r',encoding=encoding)
				sl = pp(fd, **macros_preproc)
				# print(''.join(sl))
				fd.close()
