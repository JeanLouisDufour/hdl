"""
 *  A simple lexer for Verilog code. Non-preprocessor compiler directives are
 *  handled here. The preprocessor stuff is handled in preproc.cc. Everything
 *  else is left to the bison parser (see verilog_parser.y).
"""

"""
%{

#ifdef __clang__
// bison generates code using the 'register' storage class specifier
#pragma clang diagnostic ignored "-Wdeprecated-register"
#endif

#include "kernel/log.h"
#include "frontends/verilog/verilog_frontend.h"
#include "frontends/ast/ast.h"
#include "verilog_parser.tab.hh"

USING_YOSYS_NAMESPACE
using namespace AST;
using namespace VERILOG_FRONTEND;

YOSYS_NAMESPACE_BEGIN
namespace VERILOG_FRONTEND {
	std::vector<std::string> fn_stack;
	std::vector<int> ln_stack;
}
YOSYS_NAMESPACE_END

#define YYSTYPE FRONTEND_VERILOG_YYSTYPE
#define YYLTYPE FRONTEND_VERILOG_YYLTYPE

#define SV_KEYWORD(_tok) \
	if (sv_mode) return _tok; \
	log("Lexer warning: The SystemVerilog keyword `%s' (at %s:%d) is not "\
			"recognized unless read_verilog is called with -sv!\n", yytext, \
			AST::current_filename.c_str(), frontend_verilog_yyget_lineno()); \
	yylval->string = new std::string(std::string("\\") + yytext); \
	return TOK_ID;

#define NON_KEYWORD() \
	yylval->string = new std::string(std::string("\\") + yytext); \
	return TOK_ID;

#define YY_INPUT(buf,result,max_size) \
	result = readsome(*VERILOG_FRONTEND::lexin, buf, max_size)

YYLTYPE real_location;
YYLTYPE old_location;

#define YY_USER_ACTION \
       old_location = real_location; \
       real_location.first_line = real_location.last_line; \
       real_location.first_column = real_location.last_column; \
       for(int i = 0; yytext[i] != '\0'; ++i){ \
               if(yytext[i] == '\n') { \
                       real_location.last_line++; \
                       real_location.last_column = 1; \
               } \
               else { \
                       real_location.last_column++; \
               } \
       } \
    (*yylloc) = real_location;

#define YY_BREAK \
    (*yylloc) = old_location; \
    break;

#undef YY_BUF_SIZE
#define YY_BUF_SIZE 65536

extern int frontend_verilog_yylex(YYSTYPE *yylval_param, YYLTYPE *yyloc_param);

static bool isUserType(std::string &s)
{
	// check current scope then outer scopes for a name
	for (auto it = user_type_stack.rbegin(); it != user_type_stack.rend(); ++it) {
		if ((*it)->count(s) > 0) {
			return true;
		}
	}
	return false;
}
"""

def isUserType(s):
	""
	return False

"""

%}

%option yylineno
%option noyywrap
%option nounput
%option bison-locations
%option bison-bridge
%option prefix="frontend_verilog_yy"

%x COMMENT
%x STRING
%x SYNOPSYS_TRANSLATE_OFF
%x SYNOPSYS_FLAGS
%x IMPORT_DPI
%x BASED_CONST
"""
"""
%%
	int comment_caller;

<INITIAL,SYNOPSYS_TRANSLATE_OFF>"`file_push "[^\n]* {
	fn_stack.push_back(current_filename);
	ln_stack.push_back(frontend_verilog_yyget_lineno());
	current_filename = yytext+11;
	if (!current_filename.empty() && current_filename.front() == '"')
		current_filename = current_filename.substr(1);
	if (!current_filename.empty() && current_filename.back() == '"')
		current_filename = current_filename.substr(0, current_filename.size()-1);
	frontend_verilog_yyset_lineno(0);
	yylloc->first_line = yylloc->last_line = 0;
	real_location.first_line = real_location.last_line = 0;
}

<INITIAL,SYNOPSYS_TRANSLATE_OFF>"`file_pop"[^\n]*\n {
	current_filename = fn_stack.back();
	fn_stack.pop_back();
	frontend_verilog_yyset_lineno(ln_stack.back());
	yylloc->first_line = yylloc->last_line = ln_stack.back();
	real_location.first_line = real_location.last_line = ln_stack.back();
	ln_stack.pop_back();
}

<INITIAL,SYNOPSYS_TRANSLATE_OFF>"`line"[ \t]+[^ \t\r\n]+[ \t]+\"[^ \r\n]+\"[^\r\n]*\n {
	char *p = yytext + 5;
	while (*p == ' ' || *p == '\t') p++;
	frontend_verilog_yyset_lineno(atoi(p));
	yylloc->first_line = yylloc->last_line = atoi(p);
	real_location.first_line = real_location.last_line = atoi(p);
	while (*p && *p != ' ' && *p != '\t') p++;
	while (*p == ' ' || *p == '\t') p++;
	char *q = *p ? p + 1 : p;
	while (*q && *q != '"') q++;
	current_filename = std::string(p).substr(1, q-p-1);
}

"`file_notfound "[^\n]* {
	log_error("Can't open include file `%s'!\n", yytext + 15);
}

"`timescale"[ \t]+[^ \t\r\n/]+[ \t]*"/"[ \t]*[^ \t\r\n]* /* ignore timescale directive */

"`celldefine"[^\n]* /* ignore `celldefine */
"`endcelldefine"[^\n]* /* ignore `endcelldefine */

"`default_nettype"[ \t]+[^ \t\r\n/]+ {
	char *p = yytext;
	while (*p != 0 && *p != ' ' && *p != '\t') p++;
	while (*p == ' ' || *p == '\t') p++;
	if (!strcmp(p, "none"))
		VERILOG_FRONTEND::default_nettype_wire = false;
	else if (!strcmp(p, "wire"))
		VERILOG_FRONTEND::default_nettype_wire = true;
	else
		frontend_verilog_yyerror("Unsupported default nettype: %s", p);
}

"`protect"[^\n]* /* ignore `protect*/
"`endprotect"[^\n]* /* ignore `endprotect*/

"`"[a-zA-Z_$][a-zA-Z0-9_$]* {
	frontend_verilog_yyerror("Unimplemented compiler directive or undefined macro %s.", yytext);
}

"""

specify_mode = True

reserved_common = [
"module",
"endmodule",
"function",
"endfunction",
"task",
"endtask",
"endspecify",
"specparam",
"parameter",
"localparam",
"defparam",
"assign",
"always",
"initial",
"begin",
"end",
"if",
"else",
"for",
"posedge",
"negedge",
"or", # because events --> special
"case",
"casex",
"casez",
"endcase",
"default",
"generate",
"endgenerate",
"while",
"repeat",
"automatic",
"input",
"output",
"inout",
"wire",
"wor",
"wand",
"reg",
"integer",
"signed",
"genvar",
"real",
"supply0",
"supply1"]

reserved_common = {k: 'TOK_' + k.upper() for k in reserved_common}
reserved_common.update({'$signed':'TOK_TO_SIGNED', '$unsigned':'TOK_TO_UNSIGNED'})

"""
"specify"      { return specify_mode ? TOK_SPECIFY : TOK_IGNORED_SPECIFY; }
"""

reserved_sv = [ ## SV_KEYWORD(TOK_PACKAGE);
"package",
"endpackage",
"interface",
"endinterface",
"modport",
"unique",
"unique0",
"priority",
"always_comb",
"always_ff",
"always_latch",
"final",
"logic",
"var",
"bit",
"enum",
"typedef"]

reserved_sv = {k: 'TOK_' + k.upper() for k in reserved_sv}

"""
 /* use special token for labels on assert, assume, cover, and restrict because it's insanley complex
    to fix parsing of cells otherwise. (the current cell parser forces a reduce very early to update some
    global state.. its a mess) */
[a-zA-Z_$][a-zA-Z0-9_$]*/[ \t\r\n]*:[ \t\r\n]*(assert|assume|cover|restrict)[^a-zA-Z0-9_$\.] {
	if (!strcmp(yytext, "default"))
		return TOK_DEFAULT;
	yylval->string = new std::string(std::string("\\") + yytext);
	return TOK_SVA_LABEL;
}
"""

reserved_formal_set = { # { if (formal_mode) return TOK_ASSERT; SV_KEYWORD(TOK_ASSERT); }
"assert",
"assume",
"cover",
"restrict",
"property",
"rand",
"const",
"checker",
"endchecker",
"eventually"}

reserved_formal = {k: 'TOK_' + k.upper() for k in reserved_formal_set}

## WARNING : "or" -> TOK_OR
reserved_primitive_set = {
	"and","nand","nor","xor","xnor","not","buf","bufif0","bufif1","notif0","notif1"
	}

reserved_primitive = {k: 'TOK_PRIMITIVE' for k in reserved_primitive_set}

reserved = reserved_common.copy()
reserved.update(reserved_sv)
reserved.update(reserved_formal)
reserved.update(reserved_primitive)

tokens = (
	'ATTR_BEGIN',
	'ATTR_END',
	'DEFATTR_BEGIN',
	'DEFATTR_END',
	'DOT',
	'OP_POW',
	'OP_LOR',
	'OP_LAND',
	'OP_EQ',
	'OP_NE',
	'OP_LE',
	'OP_GE',
	'OP_EQX',
	'OP_NEX',
	'OP_NAND',
	'OP_NOR',
	'OP_XNOR',
	'OP_SHL',
	'OP_SHR',
	'OP_SSHL',
	'OP_SSHR',
	'TOK_BASED_CONSTVAL',
	'TOK_CONSTVAL',
	'TOK_DECREMENT',
	'TOK_ID',
	'TOK_IGNORED_SPECIFY',
	'TOK_INCREMENT',
	'TOK_NEG_INDEXED',
	'TOK_PACKAGESEP',
	'TOK_POS_INDEXED',
	'TOK_PRIMITIVE',
	'TOK_REALVAL',
	'TOK_SPECIFY',
	'TOK_STRING',
	'TOK_SVA_LABEL',
	'TOK_UNBASED_UNSIZED_CONSTVAL',
	'TOK_USER_TYPE',
	) \
	+ tuple(reserved_common.values()) \
	+ tuple(reserved_sv.values()) \
	+ tuple(reserved_formal.values())

"""


    



"s_eventually" { if (formal_mode) return TOK_EVENTUALLY; SV_KEYWORD(TOK_EVENTUALLY); }


"""

literals = "#=><+-*/^@:,;[](){}|?&!~%"  # . ne passe pas au parsing # on vire '

t_DOT = r'\.'

t_TOK_CONSTVAL = "[0-9][0-9_]*"

t_TOK_UNBASED_UNSIZED_CONSTVAL = "'[01zxZX]"

"""
\'[sS]?[bodhBODH] {
	BEGIN(BASED_CONST);
	yylval->string = new std::string(yytext);
	return TOK_BASE;
}

<BASED_CONST>[0-9a-fA-FzxZX?][0-9a-fA-FzxZX?_]* {
	BEGIN(0);
	yylval->string = new std::string(yytext);
	return TOK_BASED_CONSTVAL;
}
"""
t_TOK_BASED_CONSTVAL = "'[sS]?[bodhBODH]\s*[0-9a-fA-FzxZX?][0-9a-fA-FzxZX?_]*"

def t_TOK_REALVAL_1(t):
	r"[0-9][0-9_]*\.[0-9][0-9_]*([eE][-+]?[0-9_]+)?"
	return t

def t_TOK_REALVAL_2(t):
	r"[0-9][0-9_]*[eE][-+]?[0-9_]+"
	return t

"""
\"		{ BEGIN(STRING); }
<STRING>\\.	{ yymore(); real_location = old_location; }
<STRING>\"	{
	BEGIN(0);
	char *yystr = strdup(yytext);
	yystr[strlen(yytext) - 1] = 0;
	int i = 0, j = 0;
	while (yystr[i]) {
		if (yystr[i] == '\\' && yystr[i + 1]) {
			i++;
			if (yystr[i] == 'a')
				yystr[i] = '\a';
			else if (yystr[i] == 'f')
				yystr[i] = '\f';
			else if (yystr[i] == 'n')
				yystr[i] = '\n';
			else if (yystr[i] == 'r')
				yystr[i] = '\r';
			else if (yystr[i] == 't')
				yystr[i] = '\t';
			else if (yystr[i] == 'v')
				yystr[i] = '\v';
			else if ('0' <= yystr[i] && yystr[i] <= '7') {
				yystr[i] = yystr[i] - '0';
				if ('0' <= yystr[i + 1] && yystr[i + 1] <= '7') {
					yystr[i + 1] = yystr[i] * 8 + yystr[i + 1] - '0';
					i++;
				}
				if ('0' <= yystr[i + 1] && yystr[i + 1] <= '7') {
					yystr[i + 1] = yystr[i] * 8 + yystr[i + 1] - '0';
					i++;
				}
			}
		}
		yystr[j++] = yystr[i++];
	}
	yystr[j] = 0;
	yylval->string = new std::string(yystr, j);
	free(yystr);
	return TOK_STRING;
}
<STRING>.	{ yymore(); real_location = old_location; }

"""
# t_TOK_STRING = '"[^"]*"'
t_TOK_STRING = r'\"(\\\"|[^\n\"])*\"'
"""

"$"(display|write|strobe|monitor|time|stop|finish|dumpfile|dumpvars|dumpon|dumpoff|dumpall) {
	yylval->string = new std::string(yytext);
	return TOK_ID;
}

"$"(setup|hold|setuphold|removal|recovery|recrem|skew|timeskew|fullskew|nochange) {
	if (!specify_mode) REJECT;
	yylval->string = new std::string(yytext);
	return TOK_ID;
}

"$"(info|warning|error|fatal) {
	yylval->string = new std::string(yytext);
	return TOK_MSG_TASKS;
}
"""

"""
[a-zA-Z_][a-zA-Z0-9_]*::[a-zA-Z_$][a-zA-Z0-9_$]* {
	// package qualifier
	auto s = std::string("\\") + yytext;
	if (pkg_user_types.count(s) > 0) {
		// package qualified typedefed name
		yylval->string = new std::string(s);
		return TOK_PKG_USER_TYPE;
	}
	else {
		// backup before :: just return first part
		size_t len = strchr(yytext, ':') - yytext;
		yyless(len);
		yylval->string = new std::string(std::string("\\") + yytext);
		return TOK_ID;
	}
}

[a-zA-Z_$][a-zA-Z0-9_$]* {
	auto s = std::string("\\") + yytext;
	if (isUserType(s)) {
		// previously typedefed name
		yylval->string = new std::string(s);
		return TOK_USER_TYPE;
	}
	else {
		yylval->string = new std::string(std::string("\\") + yytext);
		return TOK_ID;
	}
}

[a-zA-Z_$][a-zA-Z0-9_$\.]* {
	yylval->string = new std::string(std::string("\\") + yytext);
	return TOK_ID;
}
"""
def t_TOK_ID(t):
	r"[a-zA-Z_$][a-zA-Z0-9_$]*"
	s = t.value
	k = reserved.get(s)
	if k:
		t.type = k
	elif isUserType(s):
		t.type = 'TOK_USER_TYPE'
	return t

"""
"/*"[ \t]*(synopsys|synthesis)[ \t]*translate_off[ \t]*"*/" {
	static bool printed_warning = false;
	if (!printed_warning) {
		log_warning("Found one of those horrible `(synopsys|synthesis) translate_off' comments.\n"
				"Yosys does support them but it is recommended to use `ifdef constructs instead!\n");
		printed_warning = true;
	}
	BEGIN(SYNOPSYS_TRANSLATE_OFF);
}
<SYNOPSYS_TRANSLATE_OFF>.    /* ignore synopsys translate_off body */
<SYNOPSYS_TRANSLATE_OFF>\n   /* ignore synopsys translate_off body */
<SYNOPSYS_TRANSLATE_OFF>"/*"[ \t]*(synopsys|synthesis)[ \t]*"translate_on"[ \t]*"*/" { BEGIN(0); }

"/*"[ \t]*(synopsys|synthesis)[ \t]+ {
	BEGIN(SYNOPSYS_FLAGS);
}
<SYNOPSYS_FLAGS>full_case {
	static bool printed_warning = false;
	if (!printed_warning) {
		log_warning("Found one of those horrible `(synopsys|synthesis) full_case' comments.\n"
				"Yosys does support them but it is recommended to use Verilog `full_case' attributes instead!\n");
		printed_warning = true;
	}
	return TOK_SYNOPSYS_FULL_CASE;
}
<SYNOPSYS_FLAGS>parallel_case {
	static bool printed_warning = false;
	if (!printed_warning) {
		log_warning("Found one of those horrible `(synopsys|synthesis) parallel_case' comments.\n"
				"Yosys does support them but it is recommended to use Verilog `parallel_case' attributes instead!\n");
		printed_warning = true;
	}
	return TOK_SYNOPSYS_PARALLEL_CASE;
}
<SYNOPSYS_FLAGS>. /* ignore everything else */
<SYNOPSYS_FLAGS>"*/" { BEGIN(0); }

import[ \t\r\n]+\"(DPI|DPI-C)\"[ \t\r\n]+function[ \t\r\n]+ {
	BEGIN(IMPORT_DPI);
	return TOK_DPI_FUNCTION;
}

<IMPORT_DPI>[a-zA-Z_$][a-zA-Z0-9_$]* {
	yylval->string = new std::string(std::string("\\") + yytext);
	return TOK_ID;
}

<IMPORT_DPI>[ \t\r\n] /* ignore whitespaces */

<IMPORT_DPI>";" {
	BEGIN(0);
	return *yytext;
}

<IMPORT_DPI>. {
	return *yytext;
}

"\\"[^ \t\r\n]+ {
	yylval->string = new std::string(yytext);
	return TOK_ID;
}
"""

t_ATTR_BEGIN = r"\(\*"
t_ATTR_END = r"\*\)"

t_DEFATTR_BEGIN = r"{\*"
t_DEFATTR_END = r"\*}"

t_OP_POW = r"\*\*"
t_OP_LOR = r"\|\|"
t_OP_LAND = "&&"
t_OP_EQ = "=="
t_OP_NE = "!="
t_OP_LE = "<="
t_OP_GE = ">="

t_OP_EQX = "==="
t_OP_NEX = "!=="

t_OP_NAND = "~&"
t_OP_NOR = r"~\|"
t_OP_XNOR = "~^|^~"

t_OP_SHL = "<<"
t_OP_SHR = ">>"
t_OP_SSHL = "<<<"
t_OP_SSHR = ">>>"

t_TOK_PACKAGESEP = "::"
t_TOK_INCREMENT = r"\+\+"
t_TOK_DECREMENT = "--"

t_TOK_POS_INDEXED = r"\+:"
t_TOK_NEG_INDEXED = "-:"

"""
".*" { return TOK_WILDCARD_CONNECT; }

[-+]?[=*]> {
	if (!specify_mode) REJECT;
	yylval->string = new std::string(yytext);
	return TOK_SPECIFY_OPER;
}

"&&&" {
	if (!specify_mode) return TOK_IGNORED_SPECIFY_AND;
	return TOK_SPECIFY_AND;
}

<INITIAL,BASED_CONST>"/*" { comment_caller=YY_START; BEGIN(COMMENT); }
<COMMENT>.    /* ignore comment body */
<COMMENT>\n   /* ignore comment body */
<COMMENT>"*/" { BEGIN(comment_caller); }

<INITIAL,BASED_CONST>[ \t\r\n]		/* ignore whitespaces */
<INITIAL,BASED_CONST>\\[\r\n]		/* ignore continuation sequence */
<INITIAL,BASED_CONST>"//"[^\r\n]*	/* ignore one-line comments */

<INITIAL>. { return *yytext; }
<*>. { BEGIN(0); return *yytext; }

%%

// this is a hack to avoid the 'yyinput defined but not used' error msgs
void *frontend_verilog_avoid_input_warnings() {
	return (void*)&yyinput;
}

"""
import ply.lex as lex



###################### A SUPPRIMER

#def t_preproc_1(t):
#	r"`(ifdef|ifndef|elsif|define)\s+([A-Z][A-Z_]*|assume|debug|assert).*"
#	pass
#
#def t_preproc_2(t):
#	r"`(else|endif).*"
#	pass
#
#def t_preproc_3(t):
#	r"`([A-Z][A-Z_]*|include|assert|debug)"
#	pass

def t_preproc_4(t):
	r"`timescale"
	pass

def t_preproc_5(t): ### simple/techmap/top.v
	r"\\\\[a-z][a-z_]+"
	pass

######################

def t_comment(t):
	r'/\*(.|\n)*?\*/'
	tv = t.value
	t.lexer.lineno += tv.count('\n') + tv.count('\r') - tv.count('\r\n')

def t_comment_2(t):
	r'//.*'
	pass

def t_space(t):
	r'\s+'
	tv = t.value
	t.lexer.lineno += tv.count('\n') + tv.count('\r') - tv.count('\r\n')
	
def t_error(t):
	ch = t.value[0]
	if True:
		assert False, (ch, ord(ch), t.lexer.current_file)

lexer = lex.lex(optimize=0)

if __name__ == '__main__':
	import codecs, os
	import verilog_preproc
	encoding = 'latin-1' # 'utf-8'
	fn = r'C:\Temp\github\yosys-tests-master\simple\aigmap'
	fn = r'C:\Temp\github\yosys-tests-master\simple'
	fn = r'C:\Temp\github\yosys-tests-master\bigsim'
	for root, dirs, files in os.walk(fn):
		for file in files:
			if file.endswith('.v'):
				macros_preproc = {}
				fn = os.path.join(root,file)
				print('*** '+fn)
				fd = codecs.open(fn, 'r',encoding=encoding)
				#s = fd.read()
				sl = verilog_preproc.pp(fd, **macros_preproc)
				s = ''.join(sl)
				fd.close()
				lexer.current_file = fn
				lexer.lineno = 1
				lexer.input(s)
				t = True
				while t:
					t = lexer.token()
					print(t)
